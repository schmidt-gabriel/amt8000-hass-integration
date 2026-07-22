"""Modulo de comunicacao com a central Intelbras AMT-8000 (protocolo ISECNet2).

Reescrito para robustez de sessao:
  * leitura de frame pelo tamanho declarado no header (trata leitura parcial e desync);
  * drain de qualquer frame pendente ao conectar (a central deixa lixo de sessao anterior);
  * encerramento correto com o comando "bye" (0xf0f1) + close() idempotente;
  * autenticacao como software de monitoramento (sw_type=0x02);
  * senha codificada em Contact-ID (digito 0 -> 0x0a).

A interface publica (Client.connect/auth/status/arm_system/disarm_system/panic/close)
e o formato do dict de status foram mantidos compativeis com o coordinator e o
alarm_control_panel existentes.
"""

import logging
import socket

LOGGER = logging.getLogger(__name__)

# tempos (segundos)
CONNECT_TIMEOUT = 5
IO_TIMEOUT = 5
DRAIN_TIMEOUT = 0.4  # tempo curto para descartar frames pendentes ao conectar

DST_ID = [0x00, 0x00]
OUR_ID = [0x8F, 0xFF]

# comandos ISECNet2
CMD_AUTH = 0xF0F0
CMD_BYE = 0xF0F1
CMD_STATUS = 0x0B4A
CMD_ARM_DISARM = 0x401E
CMD_PANIC = 0x401A
CMD_ZONE_SIGNAL = 0x0B73   # nivel de sinal por zona (0xff = zona inexistente)
CMD_ZONE_STATUS = 0x0B74   # byte de status por zona
CMD_EXT_STATUS = 0x0B7A    # status estendido (contem bitmap de tamper por zona)
CMD_READ_CONFIG = 0x33E0   # leitura de config por indice (nomes de zona)

MAX_ZONES = 64
ZONE_ABSENT = 0xFF         # valor de sinal para zona nao configurada

# comandos de resposta especiais da central
CMD_BUSY = 0xF0F7  # "central ocupada" (ja ha outra sessao)
CMD_NAK = 0xF0FD   # erro de protocolo
CMD_ACK = 0xF0FE   # ack generico

# tipo de software na autenticacao: 0x02 monitoramento, 0x03 app mobile
SW_TYPE_MONITOR = 0x02
SW_VERSION = 0x10  # nibble.nibble -> 1.0


class CommunicationError(Exception):
    """Erro de comunicacao com a central."""


class AuthError(Exception):
    """Erro de autenticacao."""


class PanelBusyError(CommunicationError):
    """A central esta ocupada com outra sessao (app mobile ou monitoramento)."""


def calculate_checksum(buffer):
    """Checksum ISECNet2: XOR de todos os bytes, depois XOR 0xFF."""
    checksum = 0
    for value in buffer:
        checksum ^= value
    checksum ^= 0xFF
    return checksum & 0xFF


def build_frame(cmd, data=()):
    """Monta um frame ISECNet2 completo (com checksum)."""
    data = list(data)
    length = 2 + len(data)
    body = (
        DST_ID
        + OUR_ID
        + [(length >> 8) & 0xFF, length & 0xFF, (cmd >> 8) & 0xFF, cmd & 0xFF]
        + data
    )
    return bytes(body + [calculate_checksum(body)])


def encode_password(password):
    """Codifica a senha em Contact-ID (cada digito; 0 vira 0x0a)."""
    if len(password) not in (4, 6) or not password.isdigit():
        raise CommunicationError(
            "Senha invalida: use 4 ou 6 digitos numericos"
        )
    return [(0x0A if int(c) == 0 else int(c)) for c in password]


def merge_octets(buf):
    """Junta dois octetos big-endian."""
    return buf[0] * 256 + buf[1]


def get_status(payload):
    """Estado geral a partir do byte 20 do payload."""
    status = (payload[20] >> 5) & 0x03
    if status == 0x00:
        return "disarmed"
    if status == 0x01:
        return "partial_armed"
    if status == 0x03:
        return "armed_away"
    return "unknown"


def battery_status_for(payload):
    """Status da bateria (byte 134 do payload)."""
    if len(payload) <= 134:
        return "unknown"
    batt = payload[134]
    return {0x01: "dead", 0x02: "low", 0x03: "middle", 0x04: "full"}.get(
        batt, "unknown"
    )


def zone_numbers(payload, start, end):
    """Lista os numeros de zona (1-based) cujos bits estao setados em payload[start:end].

    Cada octeto carrega 8 zonas; o bit j do octeto i corresponde a zona
    (1 + j + i*8). Retorna [] se o payload nao alcancar essa faixa.
    """
    zones = []
    if len(payload) < end:
        return zones
    for i, octet in enumerate(payload[start:end]):
        for j in range(8):
            if octet & (1 << j):
                zones.append(1 + j + i * 8)
    return zones


def build_status(payload):
    """Monta o dict de status a partir do payload (sem header/checksum).

    Mantem as chaves esperadas pelo coordinator/alarm_control_panel e
    adiciona as listas de zonas (abertas, em alarme, em bypass).
    """
    if len(payload) < 21:
        raise CommunicationError(
            f"Payload de status curto demais ({len(payload)} bytes)"
        )

    # Obs: em alguns firmwares o byte 0 nao vem 0x01; a central e sabidamente
    # AMT-8000, entao reportamos o modelo de forma tolerante.
    model = "AMT-8000" if payload[0] in (0x01, 0x8A) else f"unknown(0x{payload[0]:02x})"

    status = {
        "model": model,
        "version": f"{payload[1]}.{payload[2]}.{payload[3]}",
        "status": get_status(payload),
        "zonesFiring": (payload[20] & 0x08) > 0,
        "zonesClosed": (payload[20] & 0x04) > 0,
        "siren": (payload[20] & 0x02) > 0,
        "batteryStatus": battery_status_for(payload),
        "tamper": (payload[71] & (1 << 0x01)) > 0 if len(payload) > 71 else False,
        # zonas: bitmaps de 8 octetos (ate 64 zonas) cada
        "openZones": zone_numbers(payload, 38, 46),
        "firingZones": zone_numbers(payload, 46, 54),
        "bypassZones": zone_numbers(payload, 54, 62),
    }
    return status


class Client:
    """Cliente de comunicacao com a AMT-8000."""

    def __init__(self, host, port, device_type=SW_TYPE_MONITOR,
                 software_version=SW_VERSION):
        """Inicializa o cliente (nao conecta ainda)."""
        self.host = host
        self.port = port
        self.device_type = device_type
        self.software_version = software_version
        self.client = None
        self._buf = bytearray()

    # ------------------------------------------------------------------ #
    # conexao / encerramento
    # ------------------------------------------------------------------ #
    def connect(self):
        """Abre a conexao e limpa qualquer frame pendente (desync)."""
        self.close()  # garante estado limpo antes de reconectar
        self._buf = bytearray()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(CONNECT_TIMEOUT)
        sock.connect((self.host, self.port))
        sock.settimeout(IO_TIMEOUT)
        self.client = sock
        self._drain()

    def close(self):
        """Encerra a sessao de forma limpa. Idempotente (nunca levanta)."""
        if self.client is None:
            return
        try:
            self.client.sendall(build_frame(CMD_BYE))
        except OSError:
            pass
        try:
            self.client.close()
        except OSError:
            pass
        finally:
            self.client = None
            self._buf = bytearray()

    # ------------------------------------------------------------------ #
    # baixo nivel: envio e leitura de frames
    # ------------------------------------------------------------------ #
    def _require_connection(self):
        if self.client is None:
            raise CommunicationError("Nao conectado. Chame Client.connect() antes.")

    def _drain(self):
        """Descarta qualquer byte pendente vindo de uma sessao anterior."""
        self._require_connection()
        self.client.settimeout(DRAIN_TIMEOUT)
        try:
            while True:
                chunk = self.client.recv(2048)
                if not chunk:
                    break
                LOGGER.debug("drain: descartados %d bytes", len(chunk))
        except socket.timeout:
            pass
        except OSError:
            pass
        finally:
            if self.client is not None:
                self.client.settimeout(IO_TIMEOUT)
        self._buf = bytearray()

    def _fill(self, need):
        while len(self._buf) < need:
            chunk = self.client.recv(2048)
            if not chunk:
                raise CommunicationError("Conexao fechada pela central")
            self._buf.extend(chunk)

    def _recv_frame(self):
        """Le um frame completo respeitando o tamanho declarado no header.

        Retorna (cmd, payload_bytes).
        """
        self._require_connection()
        self._fill(6)  # dst(2) + src(2) + length(2)
        length = merge_octets(self._buf[4:6])
        total = 6 + length + 1  # + checksum
        self._fill(total)
        frame = bytes(self._buf[:total])
        del self._buf[:total]

        if calculate_checksum(frame[:-1]) != frame[-1]:
            raise CommunicationError(f"Checksum invalido: {frame.hex()}")

        cmd = (frame[6] << 8) | frame[7]
        payload = frame[8:8 + (length - 2)]
        return cmd, payload

    def _send(self, cmd, data=()):
        self._require_connection()
        self.client.sendall(build_frame(cmd, data))

    def _command(self, cmd, data=()):
        """Envia um comando e devolve (resp_cmd, payload), tratando busy/nak."""
        self._send(cmd, data)
        resp_cmd, payload = self._recv_frame()
        if resp_cmd == CMD_BUSY:
            raise PanelBusyError(
                "Central ocupada: feche o app AMT Remoto Mobile ou verifique "
                "se ha empresa de monitoramento/outra sessao conectada."
            )
        if resp_cmd == CMD_NAK:
            reason = payload[0] if payload else -1
            raise CommunicationError(f"Central respondeu NAK (motivo 0x{reason:02x})")
        return resp_cmd, payload

    # ------------------------------------------------------------------ #
    # comandos de alto nivel
    # ------------------------------------------------------------------ #
    def auth(self, password):
        """Autentica na central. Retorna True ou levanta AuthError."""
        self._require_connection()
        data = [self.device_type] + encode_password(password) + [self.software_version]
        resp_cmd, payload = self._command(CMD_AUTH, data)

        if resp_cmd != CMD_AUTH:
            raise CommunicationError(
                f"Resposta inesperada na autenticacao: 0x{resp_cmd:04x}"
            )
        if not payload:
            raise CommunicationError("Resposta de autenticacao sem payload")

        result = payload[0]
        if result == 0:
            return True
        raise AuthError(
            {
                1: "Senha incorreta",
                2: "Versao de software incorreta",
                3: "A central fara callback",
                4: "Aguardando permissao do usuario na central",
            }.get(result, f"Falha de autenticacao (codigo {result})")
        )

    def status(self):
        """Consulta e devolve o status atual da central."""
        _cmd, payload = self._command(CMD_STATUS)
        return build_status(payload)

    def zone_signals(self):
        """0x0b73: nivel de sinal por zona (lista de 64; 0xff = zona inexistente)."""
        _cmd, payload = self._command(CMD_ZONE_SIGNAL, [0x01])
        # payload[0] e o echo do parametro; zonas 1..64 vem a seguir
        return list(payload[1:1 + MAX_ZONES])

    def zone_status_bytes(self):
        """0x0b74: byte de status por zona (lista de 64; zona 1 em [0])."""
        _cmd, payload = self._command(CMD_ZONE_STATUS, [0x01])
        return list(payload[0:MAX_ZONES])

    def zone_names(self):
        """0x33e0: nomes de zona. Retorna dict {zona(1..64): nome}.

        A resposta traz registros de 15 bytes: [indice(1)][nome(14)].
        """
        names = {}
        for base in (0x00, 0x10, 0x20, 0x30):
            _cmd, payload = self._command(
                CMD_READ_CONFIG, list(range(base, base + 0x10))
            )
            off = 0
            while off + 15 <= len(payload):
                rec = payload[off:off + 15]
                idx = rec[0]
                name = bytes(rec[1:]).decode("latin1").rstrip("\x00 ").strip()
                names[idx + 1] = name
                off += 15
        return names

    def status_with_zones(self):
        """Status completo: 0x0b4a + sinal (0x0b73) + status por zona (0x0b74).

        Tudo na mesma sessao autenticada. Acrescenta ao dict de status:
          enabledZones: lista de zonas configuradas (sinal != 0xff)
          zoneSignals:  {zona: nivel de sinal}
          zoneStatusBytes: {zona: byte de status}
        """
        st = self.status()
        try:
            signals = self.zone_signals()
        except CommunicationError:
            signals = []
        try:
            status_bytes = self.zone_status_bytes()
        except CommunicationError:
            status_bytes = []

        enabled = [i + 1 for i, v in enumerate(signals) if v != ZONE_ABSENT]
        st["enabledZones"] = enabled
        st["zoneSignals"] = {z: signals[z - 1] for z in enabled}
        st["zoneStatusBytes"] = {
            z: status_bytes[z - 1] for z in enabled if z - 1 < len(status_bytes)
        }

        # Per-zone tamper comes from the extended status (0x0b7a): an 8-octet
        # bitmap at offset 89 (zone 1 = byte 89 bit 0). Verified live.
        try:
            _c, ext = self._command(CMD_EXT_STATUS, [0x01])
            st["tamperZones"] = zone_numbers(ext, 89, 97)
        except CommunicationError:
            st["tamperZones"] = []
        if st["tamperZones"]:
            st["tamper"] = True
        return st

    def arm_system(self, partition):
        """Arma a central. partition=0 arma tudo (0xFF)."""
        part = 0xFF if partition == 0 else partition
        resp_cmd, _payload = self._command(CMD_ARM_DISARM, [part, 0x01])
        if resp_cmd in (CMD_ARM_DISARM, CMD_ACK):
            return "armed"
        return "not_armed"

    def disarm_system(self, partition):
        """Desarma a central. partition=0 desarma tudo (0xFF)."""
        part = 0xFF if partition == 0 else partition
        resp_cmd, _payload = self._command(CMD_ARM_DISARM, [part, 0x00])
        if resp_cmd in (CMD_ARM_DISARM, CMD_ACK):
            return "disarmed"
        return "not_disarmed"

    def panic(self, panic_type):
        """Dispara panico. NAO testado ao vivo (aciona a sirene)."""
        resp_cmd, _payload = self._command(CMD_PANIC, [panic_type])
        if resp_cmd in (CMD_PANIC, CMD_ACK):
            return "triggered"
        return "not_triggered"


# --------------------------------------------------------------------- #
# uso direto para teste manual (nao roda quando importado pelo HA):
#   AMT_PASSWORD=xxxxxx python3 client.py 192.168.1.10 9009
# --------------------------------------------------------------------- #
if __name__ == "__main__":
    import os
    import sys

    host = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.10"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 9009
    pw = os.environ.get("AMT_PASSWORD", "")

    logging.basicConfig(level=logging.DEBUG)
    c = Client(host, port)
    try:
        c.connect()
        c.auth(pw)
        print("auth OK")
        print("status:", c.status())
    finally:
        c.close()
