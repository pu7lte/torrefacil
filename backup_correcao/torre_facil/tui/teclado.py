"""Leitor de teclado atômico.

Suporta TODOS os formatos de sequência ANSI em uso hoje:
    - CSI clássico:         ESC [ A          (seta para cima)
                            ESC [ 5 ~        (PgUp)
    - SS3:                  ESC O A          (seta para cima)
    - CSI com modificador:  ESC [ 1;2A       (Shift+↑)
    - CSI u / kitty:        ESC [ 57352;1u   (↑)
                            ESC [ 57440;5u   (F12 no kitty)
                            ESC [ 57375;1u   (F12 oficial)
    - modifyOtherKeys:      ESC [ 27;2;65~   (Shift+A)

Trata o caso do kitty (e alguns outros terminais) que entregam
sequências ESC em MÚLTIPLAS leituras separadas:
    1º read: b'\\x1b['
    2º read: b'B'

O buffer parcial é retido entre chamadas e concatenado.

Garantia: ``ler_tecla()`` nunca devolve None. Sempre devolve uma string;
quando não consegue decodificar, devolve o sentinela ``"IGNORE"``.
"""
from __future__ import annotations

import logging
import os
import re
import sys
import time
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Buffer global — retido entre chamadas (nunca descartado sem consumir)
# ---------------------------------------------------------------------------

_BUFFER_TECLADO: bytes = b""


def resetar_buffer() -> None:
    """Limpa o buffer entre telas (evita lixo acumulado entre frames)."""
    global _BUFFER_TECLADO
    _BUFFER_TECLADO = b""
    logger.debug("Buffer de teclado resetado")


# ---------------------------------------------------------------------------
# Windows: mapeamento de scan codes
# ---------------------------------------------------------------------------

_TECLAS_ESTENDIDAS_WIN: dict[str, str] = {
    "H": "UP", "P": "DOWN", "K": "LEFT", "M": "RIGHT",
    "I": "PGUP", "Q": "PGDN", "G": "HOME", "O": "END",
    "S": "DEL", "R": "INSERT",
    ";": "F1", "<": "F2", "=": "F3", ">": "F4", "?": "F5",
    "@": "F6", "A": "F7", "B": "F8", "C": "F9", "D": "F10",
    "\x84": "PGUP", "v": "PGDN",
    "\x85": "F11", "\x86": "F12",
}

_ALT_SCANCODES_WIN: dict[int, str] = {
    16: "Q", 17: "W", 18: "E", 19: "R", 20: "T", 21: "Y", 22: "U",
    23: "I", 24: "O", 25: "P",
    30: "A", 31: "S", 32: "D", 33: "F", 34: "G", 35: "H", 36: "J",
    37: "K", 38: "L",
    44: "Z", 45: "X", 46: "C", 47: "V", 48: "B", 49: "N", 50: "M",
}


# ---------------------------------------------------------------------------
# Tabelas comuns a todos os terminais Unix
# ---------------------------------------------------------------------------

# CSI/SS3 + letra final → tecla
_TECLAS_FINAL_CSI: dict[str, str] = {
    "A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT",
    "E": "CENTER", "F": "END", "H": "HOME",
    "P": "F1", "Q": "F2", "R": "F3", "S": "F4",
    "Z": "SHIFT_TAB",
}

# CSI + número + ~ → tecla (formato clássico xterm)
_TECLAS_TIL_CSI: dict[int, str] = {
    1: "HOME", 2: "INSERT", 3: "DEL", 4: "END",
    5: "PGUP", 6: "PGDN", 7: "HOME", 8: "END",
    11: "F1", 12: "F2", 13: "F3", 14: "F4", 15: "F5",
    17: "F6", 18: "F7", 19: "F8", 20: "F9", 21: "F10",
    23: "F11", 24: "F12",
    25: "F13", 26: "F14", 28: "F15", 29: "F16",
    31: "F17", 32: "F18", 33: "F19", 34: "F20",
}


# ---------------------------------------------------------------------------
# Mapa CSI u — faixa Unicode funcional (kitty keyboard protocol)
# ---------------------------------------------------------------------------

_TECLAS_CSI_U_FUNCIONAIS: dict[int, str] = {
    # Bloco 57344..57363
    57344: "ESC", 57345: "ENTER", 57346: "TAB", 57347: "BACKSPACE",
    57348: "INSERT", 57349: "DEL", 57350: "LEFT", 57351: "RIGHT",
    57352: "UP", 57353: "DOWN", 57354: "PGUP", 57355: "PGDN",
    57356: "HOME", 57357: "END", 57358: "CAPSLOCK", 57359: "SCROLLLOCK",
    57360: "NUMLOCK", 57361: "PRINTSCREEN", 57362: "PAUSE", 57363: "MENU",
    # F1..F35 (faixa oficial kitty: 57364..57398)
    57364: "F1", 57365: "F2", 57366: "F3", 57367: "F4",
    57368: "F5", 57369: "F6", 57370: "F7", 57371: "F8",
    57372: "F9", 57373: "F10", 57374: "F11", 57375: "F12",
    57376: "F13", 57377: "F14", 57378: "F15", 57379: "F16",
    57380: "F17", 57381: "F18", 57382: "F19", 57383: "F20",
    57384: "F21", 57385: "F22", 57386: "F23", 57387: "F24",
    57388: "F25", 57389: "F26", 57390: "F27", 57391: "F28",
    57392: "F29", 57393: "F30", 57394: "F31", 57395: "F32",
    57396: "F33", 57397: "F34", 57398: "F35",
    # Faixa estendida de alguns terminais
    57425: "F36", 57426: "F37", 57427: "F38", 57428: "F39",
    57429: "F40", 57430: "F41", 57431: "F42", 57432: "F43",
    57433: "F44", 57434: "F45", 57435: "F46", 57436: "F47",
    57437: "F48",
    # Aliases alternativos usados por alguns builds do kitty
    57438: "F11", 57439: "F12", 57440: "F12",
}


# ---------------------------------------------------------------------------
# Modificadores (bitmask kitty / xterm)
# ---------------------------------------------------------------------------

_MOD_SHIFT: int = 1
_MOD_ALT: int = 2
_MOD_CTRL: int = 4


def _tem_mod(mod: int | None, bit: int) -> bool:
    """Verifica se um bit de modificador está ativo.

    Args:
        mod: Valor do modificador (1-based no protocolo kitty).
        bit: Bit a verificar (1=Shift, 2=Alt, 4=Ctrl).

    Returns:
        True se o bit está ativo.
    """
    if mod is None:
        return False
    try:
        return bool((int(mod) - 1) & bit)
    except (TypeError, ValueError):
        return False


def _prefixo_mod(mod: int | None) -> str:
    """Gera prefixo de modificador (ex: "CTRL+ALT+").

    Args:
        mod: Valor do modificador.

    Returns:
        Prefixo formatado (vazio se nenhum modificador ativo).
    """
    if mod is None:
        return ""

    partes: list[str] = []
    if _tem_mod(mod, _MOD_CTRL):
        partes.append("CTRL")
    if _tem_mod(mod, _MOD_ALT):
        partes.append("ALT")
    if _tem_mod(mod, _MOD_SHIFT):
        partes.append("SHIFT")

    if not partes:
        return ""

    return "+".join(partes) + "+"


# ---------------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------------

_RE_CSI = re.compile(r"^\x1b\[([0-9;:?]*)([@-~])$")
_RE_SS3 = re.compile(r"^\x1bO([@-~])$")


# ---------------------------------------------------------------------------
# Decodificador — reconhece todos os formatos
# ---------------------------------------------------------------------------

def decodificar_sequencia_escape(seq: str) -> str:
    """Converte uma sequência ESC completa no nome canônico da tecla.

    Args:
        seq: Sequência de escape completa (ex: "\\x1b[A", "\\x1bOP").

    Returns:
        Nome canônico da tecla (ex: "UP", "F1", "CTRL+X") ou "IGNORE".
    """
    if seq == "\x1b":
        return "ESC"

    # ALT + caractere imprimível
    if len(seq) == 2 and seq[0] == "\x1b" and seq[1] not in "[O":
        if seq[1].isprintable():
            return "ALT_" + seq[1].upper()
        return "IGNORE"

    # SS3: ESC O x
    m_ss3 = _RE_SS3.match(seq)
    if m_ss3:
        final = m_ss3.group(1)
        return _TECLAS_FINAL_CSI.get(final, "IGNORE")

    # CSI: ESC [ params final
    m_csi = _RE_CSI.match(seq)
    if not m_csi:
        return "IGNORE"

    params, final = m_csi.groups()
    partes = params.split(";") if params else []
    primeiro = partes[0] if partes else ""
    segundo = partes[1] if len(partes) > 1 else None
    terceiro = partes[2] if len(partes) > 2 else None

    # ---- CSI u (kitty) ----
    if final == "u":
        return _decodificar_csi_u(primeiro, segundo)

    # ---- final em letra (CSI clássico ou com modificador) ----
    if final in _TECLAS_FINAL_CSI:
        tecla = _TECLAS_FINAL_CSI[final]
        if segundo is not None and segundo.isdigit():
            mod = int(segundo)
            return _prefixo_mod(mod) + tecla
        return tecla

    # ---- final ~ (números) ----
    if final == "~":
        return _decodificar_csi_tilde(primeiro, segundo, terceiro)

    return "IGNORE"


def _decodificar_csi_u(cod_str: str, mod_str: str | None) -> str:
    """Decodifica sequência CSI u (kitty keyboard protocol).

    Args:
        cod_str: String do código (pode ter formato "code:event").
        mod_str: String do modificador (pode ter formato "mod:event").

    Returns:
        Nome da tecla ou "IGNORE".
    """
    # Formato pode ser "code:event" ou "code" ou "code;mod:event"
    if ":" in cod_str:
        cod_str = cod_str.split(":", 1)[0]
    if mod_str and ":" in mod_str:
        mod_str = mod_str.split(":", 1)[0]

    if not cod_str.isdigit():
        return "IGNORE"

    cod = int(cod_str)
    mod = int(mod_str) if mod_str and mod_str.isdigit() else None

    # Teclas funcionais (faixa Unicode)
    if cod in _TECLAS_CSI_U_FUNCIONAIS:
        tecla = _TECLAS_CSI_U_FUNCIONAIS[cod]
        return _prefixo_mod(mod) + tecla

    # Caracteres ASCII imprimíveis
    if 32 <= cod <= 126:
        return _prefixo_mod(mod) + chr(cod).upper()

    # Controle
    if cod == 27:
        return "ESC"
    if cod == 13:
        return "ENTER"
    if cod == 9:
        return "TAB"
    if cod == 127:
        return "BACKSPACE"

    return "IGNORE"


def _decodificar_csi_tilde(
    primeiro: str,
    segundo: str | None,
    terceiro: str | None,
) -> str:
    """Decodifica sequência CSI com final ~ (xterm clássico).

    Args:
        primeiro: Primeiro parâmetro (número da tecla).
        segundo: Segundo parâmetro (modificador, opcional).
        terceiro: Terceiro parâmetro (código ASCII, opcional).

    Returns:
        Nome da tecla ou "IGNORE".
    """
    if primeiro == "27":
        if terceiro and terceiro.isdigit():
            cod = int(terceiro)
            mod = int(segundo) if segundo and segundo.isdigit() else None
            if 32 <= cod <= 126:
                return _prefixo_mod(mod) + chr(cod).upper()
        return "IGNORE"

    if not primeiro.isdigit():
        return "IGNORE"

    num = int(primeiro)
    if num in _TECLAS_TIL_CSI:
        tecla = _TECLAS_TIL_CSI[num]
        if segundo is not None and segundo.isdigit():
            mod = int(segundo)
            return _prefixo_mod(mod) + tecla
        return tecla

    return "IGNORE"


# ---------------------------------------------------------------------------
# Completo / incompleto
# ---------------------------------------------------------------------------

def _sequencia_escape_completa(seq: str) -> bool:
    """Verifica se uma sequência de escape está completa.

    Args:
        seq: Sequência começando com ESC.

    Returns:
        True se a sequência está completa e pode ser decodificada.
    """
    if len(seq) < 2:
        return False
    if seq[1] == "O":
        return len(seq) >= 3
    if seq[1] == "[":
        return any("@" <= c <= "~" for c in seq[2:])
    return True


def _tamanho_utf8(byte_inicial: int) -> int:
    """Retorna o tamanho esperado de um caractere UTF-8 pelo byte inicial.

    Args:
        byte_inicial: Primeiro byte do caractere.

    Returns:
        Número de bytes (1-4).
    """
    if byte_inicial < 0xC0:
        return 1
    if byte_inicial < 0xE0:
        return 2
    if byte_inicial < 0xF0:
        return 3
    return 4


# ---------------------------------------------------------------------------
# Extração — devolve (tecla, bytes_usados) OU None se incompleto
# ---------------------------------------------------------------------------

def _extrair_tecla_unix(buf: bytes) -> tuple[str, int] | None:
    """Lê UMA tecla do início do buffer.

    Args:
        buf: Buffer de bytes acumulado.

    Returns:
        Tupla ``(tecla, bytes_consumidos)`` ou ``None`` se incompleto.
    """
    if not buf:
        return None

    b0 = buf[0]

    # Ctrl+C
    if b0 == 0x03:
        raise KeyboardInterrupt

    # ESC
    if b0 == 0x1B:
        # ESC sozinho no buffer: incompleto
        if len(buf) == 1:
            return None

        b1 = buf[1]

        # SS3: ESC O x
        if b1 == 0x4F:
            if len(buf) < 3:
                return None
            return decodificar_sequencia_escape(buf[:3].decode("latin-1")), 3

        # CSI: ESC [ ... final
        if b1 == 0x5B:
            i = 2
            while i < len(buf):
                c = buf[i]
                if 0x40 <= c <= 0x7E:
                    seq_bytes = buf[:i + 1]
                    try:
                        seq = seq_bytes.decode("latin-1")
                    except Exception:
                        return "IGNORE", i + 1
                    return decodificar_sequencia_escape(seq), i + 1
                i += 1
            return None

        # ESC ESC → ESC
        if b1 == 0x1B:
            return "ESC", 1

        # ALT + caractere UTF-8
        n = _tamanho_utf8(b1)
        if len(buf) < 1 + n:
            return None
        ch = buf[1:1 + n].decode("utf-8", errors="ignore")
        if ch and ch.isprintable():
            return ("ALT_" + ch.upper()), 1 + n
        return "IGNORE", 1 + n

    # CR/LF
    if b0 in (0x0D, 0x0A):
        return "ENTER", 1

    # Backspace / DEL
    if b0 in (0x7F, 0x08):
        return "BACKSPACE", 1

    # Tab
    if b0 == 0x09:
        return "TAB", 1

    # UTF-8 padrão
    n = _tamanho_utf8(b0)
    if len(buf) < n:
        return None
    ch = buf[:n].decode("utf-8", errors="ignore")
    return (ch or "IGNORE"), n


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------

def _ler_tecla_windows() -> str:
    """Lê uma tecla no Windows usando msvcrt.

    Returns:
        Nome da tecla.

    Raises:
        KeyboardInterrupt: Se Ctrl+C for pressionado.
    """
    import msvcrt

    ch = msvcrt.getwch()

    if ch == "\x03":
        raise KeyboardInterrupt

    if ch in ("\r", "\n"):
        return "ENTER"
    if ch == "\x08":
        return "BACKSPACE"
    if ch == "\t":
        return "TAB"

    # Teclas estendidas (setas, F1-F12, etc.)
    if ch in ("\x00", "\xe0"):
        ch2 = msvcrt.getwch()
        if ch2 in _TECLAS_ESTENDIDAS_WIN:
            return _TECLAS_ESTENDIDAS_WIN[ch2]
        letra_alt = _ALT_SCANCODES_WIN.get(ord(ch2))
        if letra_alt:
            return "ALT_" + letra_alt
        return "IGNORE"

    # ESC — espera para ver se é sequência ANSI
    if ch == "\x1b":
        t_ini = time.time()
        while not msvcrt.kbhit() and (time.time() - t_ini) < 0.05:
            time.sleep(0.004)

        if not msvcrt.kbhit():
            return "ESC"

        seq = ch + msvcrt.getwch()
        if seq[1] in ("[", "O"):
            t_ini = time.time()
            while not _sequencia_escape_completa(seq) and (time.time() - t_ini) < 0.15:
                if msvcrt.kbhit():
                    seq += msvcrt.getwch()
                    t_ini = time.time()
                else:
                    time.sleep(0.004)

        return decodificar_sequencia_escape(seq)

    return ch


# ---------------------------------------------------------------------------
# Unix / macOS — leitura persistente e tolerante a fragmentação
# ---------------------------------------------------------------------------

def _ler_tecla_unix() -> str:
    """Lê uma tecla no Unix/macOS usando termios.

    Returns:
        Nome da tecla.

    Raises:
        KeyboardInterrupt: Se Ctrl+C for pressionado.
    """
    import termios
    import tty
    import select

    global _BUFFER_TECLADO

    fd = sys.stdin.fileno()

    if not os.isatty(fd):
        try:
            linha = sys.stdin.readline()
        except Exception:
            return "ESC"
        if not linha:
            return "ESC"
        texto = linha.strip()
        return texto if texto else "ESC"

    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)

        while True:
            # 1) Garante pelo menos 1 byte no buffer
            if not _BUFFER_TECLADO:
                dados = os.read(fd, 64)
                if not dados:
                    return "ESC"
                _BUFFER_TECLADO += dados

            # 2) Tenta decodificar
            resultado = _extrair_tecla_unix(_BUFFER_TECLADO)
            if resultado is not None:
                tecla, usados = resultado
                _BUFFER_TECLADO = _BUFFER_TECLADO[usados:]
                return tecla if tecla is not None else "IGNORE"

            # 3) Incompleto. Espera mais bytes com timeout.
            t_ini = time.time()
            while time.time() - t_ini < 0.40:
                if select.select([fd], [], [], 0.05)[0]:
                    mais = os.read(fd, 64)
                    if not mais:
                        break
                    _BUFFER_TECLADO += mais
                    t_ini = time.time()
                    resultado = _extrair_tecla_unix(_BUFFER_TECLADO)
                    if resultado is not None:
                        tecla, usados = resultado
                        _BUFFER_TECLADO = _BUFFER_TECLADO[usados:]
                        return tecla if tecla is not None else "IGNORE"

            # 4) Timeout. Decide o que fazer:
            if _BUFFER_TECLADO == b"\x1b":
                _BUFFER_TECLADO = b""
                return "ESC"

            # Sequência parcial começando com ESC: preserva
            if _BUFFER_TECLADO.startswith(b"\x1b"):
                if len(_BUFFER_TECLADO) > 8:
                    _BUFFER_TECLADO = b""
                return "IGNORE"

            # UTF-8 multi-byte parcial: preserva
            if _BUFFER_TECLADO and 0xC0 <= _BUFFER_TECLADO[0] < 0xF0:
                if len(_BUFFER_TECLADO) > 4:
                    _BUFFER_TECLADO = b""
                return "IGNORE"

            # Caso contrário, descarta 1 byte
            _BUFFER_TECLADO = _BUFFER_TECLADO[1:]
            return "IGNORE"

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


# ---------------------------------------------------------------------------
# Entrada pública
# ---------------------------------------------------------------------------

def _ler_tecla_impl() -> str:
    """Implementação interna que escolhe Windows ou Unix.

    Returns:
        Nome da tecla.
    """
    if os.name == "nt":
        return _ler_tecla_windows()
    return _ler_tecla_unix()


def ler_tecla() -> str:
    """Lê uma tecla do terminal. Nunca retorna None.

    Returns:
        Nome da tecla (ex: "UP", "ENTER", "a", "CTRL+C").
        Retorna "IGNORE" se não conseguir decodificar.

    Raises:
        KeyboardInterrupt: Se Ctrl+C for pressionado.
    """
    tecla = _ler_tecla_impl()
    if tecla is None:
        return "IGNORE"
    return tecla