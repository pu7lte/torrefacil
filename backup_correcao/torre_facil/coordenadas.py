"""Conversão de coordenadas e padronização de operadora/tecnologia.

Este módulo fornece funções puras para:
    - Converter coordenadas da Anatel (formato GMS) para graus decimais.
    - Padronizar nomes de operadoras para siglas canônicas.
    - Mapear descrições de tecnologia para siglas (E/H/L/5).

Formatos aceitos pela Anatel:
    - Sufixo:  ``"235907S"``  → 23°59'07" Sul
    - Prefixo: ``"S235907"``  → Sul 23°59'07"
    - Decimal: ``"-23.985278"`` ou ``"23.985278"`` (heurística: > 15 → negativo)

Example:
    >>> from torre_facil.coordenadas import converter_coord_anatel
    >>> converter_coord_anatel("235907S")
    -23.985278
    >>> converter_coord_anatel("S235907")
    -23.985278
    >>> converter_coord_anatel("-23.985278")
    -23.985278
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Final

import pandas as pd

from . import dicionarios as dicionarios_module

logger = logging.getLogger(__name__)

__all__ = [
    "converter_coord_anatel",
    "padronizar_operadora",
    "mapear_sigla_tecnologia",
]


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Valores que indicam "sem coordenada" em dados brutos
_VALORES_VAZIOS: Final[frozenset[str]] = frozenset({
    "NAN", "NONE", "0", "0.0", "",
})

# Hemisférios que indicam coordenadas negativas
_HEMISFERIOS_NEGATIVOS: Final[frozenset[str]] = frozenset({"S", "W", "O"})

# Heurística: coordenadas decimais > 15 são assumidas como sul
# (Brasil está entre latitudes -33 e +5, então valores positivos > 15
# provavelmente são do hemisfério sul sem sinal)
_LIMIAR_HEURISTICA_SUL: Final[float] = 15.0

# Mapeamento de tecnologia para sigla (ordem importa: primeiro match vence)
_MAPA_TECNOLOGIAS: Final[tuple[tuple[str, ...], str], ...] = (
    (("5G", "NR"), "5"),
    (("4G", "LTE"), "L"),
    (("3G", "WCDMA", "UMTS", "HSPA", "HSDPA", "HSUPA"), "H"),
    (("2G", "GSM", "EDGE", "GPRS", "TDMA", "CDMA"), "E"),
)


# ---------------------------------------------------------------------------
# Regex pré-compiladas para formato GMS da Anatel
# ---------------------------------------------------------------------------

# Sufixo: "235907S" → (23)(59)(07)(S)
# Latitude: 2-3 dígitos de graus + 2 minutos + 2 segundos + fração opcional
RE_GMS_SUFIXO: Final[re.Pattern[str]] = re.compile(
    r"^0*(\d{2,3})(\d{2})(\d{2})(\d*)([NSWEOL])$"
)
"""Regex para GMS com hemisfério no final (ex: '235907S')."""

# Prefixo: "S235907" → (S)(23)(59)(07)
RE_GMS_PREFIXO: Final[re.Pattern[str]] = re.compile(
    r"^([NSWEOL])0*(\d{2,3})(\d{2})(\d{2})(\d*)$"
)
"""Regex para GMS com hemisfério no início (ex: 'S235907')."""


# ---------------------------------------------------------------------------
# Conversão de coordenadas
# ---------------------------------------------------------------------------

def _decimal_de_gms(
    graus: int,
    minutos: int,
    segundos: float,
    hemisferio: str,
) -> float:
    """Converte componentes GMS em grau decimal assinado.

    Args:
        graus: Componente de graus (0-180).
        minutos: Componente de minutos (0-59).
        segundos: Componente de segundos (0-59.999...).
        hemisferio: Hemisfério ('N', 'S', 'W', 'E', 'O', 'L').

    Returns:
        Grau decimal com sinal (negativo para S/W/O).

    Example:
        >>> _decimal_de_gms(23, 59, 7.0, "S")
        -23.985278
    """
    decimal = graus + (minutos / 60.0) + (segundos / 3600.0)
    if hemisferio in _HEMISFERIOS_NEGATIVOS:
        decimal = -decimal
    return round(decimal, 6)


def _processar_match_gms(
    grupos: tuple[str, ...],
    hemisferio_pos: int,
) -> float | None:
    """Processa match de regex GMS e retorna coordenada decimal.

    Args:
        grupos: Tupla de grupos capturados pela regex.
        hemisferio_pos: Índice do hemisfério na tupla (0 para prefixo, -1 para sufixo).

    Returns:
        Coordenada decimal, ou None se os dados forem inválidos.
    """
    hemisferio = grupos[hemisferio_pos]

    # Extrai componentes (ordem depende se hemisfério é prefixo ou sufixo)
    if hemisferio_pos == 0:
        # Prefixo: (hemisferio, graus, minutos, segundos, fracao)
        graus, minutos, segundos, fracao = grupos[1], grupos[2], grupos[3], grupos[4]
    else:
        # Sufixo: (graus, minutos, segundos, fracao, hemisferio)
        graus, minutos, segundos, fracao = grupos[0], grupos[1], grupos[2], grupos[3]

    try:
        graus_int = int(graus)
        minutos_int = int(minutos)
        segundos_float = int(segundos)
        if fracao:
            segundos_float += float(f"0.{fracao}")
        return _decimal_de_gms(graus_int, minutos_int, segundos_float, hemisferio)
    except (ValueError, IndexError):
        return None


def converter_coord_anatel(valor: object) -> float | None:
    """Converte coordenada da Anatel em grau decimal assinado.

    Aceita três formatos:
        1. Decimal puro: ``"-23.985278"`` ou ``"23.985278"``
        2. GMS com hemisfério no final: ``"235907S"``
        3. GMS com hemisfério no início: ``"S235907"``

    Nota:
        A heurística ``if num > 15: num = -num`` assume que coordenadas
        decimais positivas > 15 são do hemisfério sul (Brasil está entre
        latitudes -33 e +5). Isso corrige dados que vieram sem sinal.

    Args:
        valor: Coordenada bruta (pode ser str, float, int, None, NaN).

    Returns:
        Coordenada em graus decimais com sinal, ou None se inválida.

    Example:
        >>> converter_coord_anatel("235907S")
        -23.985278
        >>> converter_coord_anatel("-23.985278")
        -23.985278
        >>> converter_coord_anatel(None)
        None
        >>> converter_coord_anatel("invalido")
        None
    """
    if valor is None:
        return None

    # Trata float/NaN do pandas
    if isinstance(valor, float):
        try:
            if pd.isna(valor):
                return None
        except (TypeError, ValueError):
            pass

    v = str(valor).strip().upper().replace(",", ".")
    if not v or v in _VALORES_VAZIOS:
        return None

    # 1) Tenta decimal puro
    try:
        num = float(v)
        if -180.0 <= num <= 180.0 and num != 0:
            # Heurística: Brasil é hemisfério sul, então valores > 15
            # provavelmente são negativos (dados vieram sem sinal)
            if num > _LIMIAR_HEURISTICA_SUL:
                num = -num
            return round(num, 6)
    except ValueError:
        pass

    # 2) Tenta GMS com hemisfério no final
    if m := RE_GMS_SUFIXO.match(v):
        return _processar_match_gms(m.groups(), hemisferio_pos=-1)

    # 3) Tenta GMS com hemisfério no início
    if m := RE_GMS_PREFIXO.match(v):
        return _processar_match_gms(m.groups(), hemisferio_pos=0)

    return None


# ---------------------------------------------------------------------------
# Padronização de operadora
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1024)
def padronizar_operadora(nome: str) -> str:
    """Mapeia o nome bruto da operadora para a sigla canônica.

    Lê ``dicionarios_module.DICIONARIOS`` de forma dinâmica, para funcionar
    mesmo se o dicionário for carregado depois deste módulo.

    Args:
        nome: Nome bruto da operadora (ex: "VIVO S.A.").

    Returns:
        Sigla canônica (ex: "VIVO"), ou o nome em uppercase se não encontrado.

    Example:
        >>> padronizar_operadora("VIVO S.A.")
        'VIVO'
        >>> padronizar_operadora("Claro")
        'CLARO'
    """
    nome_up = str(nome).upper()
    operadoras = dicionarios_module.DICIONARIOS.get("operadoras_padrao", {})

    for op_padrao, termos in operadoras.items():
        if any(t in nome_up for t in termos):
            return op_padrao

    return nome_up


# ---------------------------------------------------------------------------
# Mapeamento de tecnologia
# ---------------------------------------------------------------------------

def mapear_sigla_tecnologia(texto: str) -> str:
    """Converte descrição de tecnologia em sigla (E/H/L/5).

    Args:
        texto: Descrição da tecnologia (ex: "4G LTE", "5G NR").

    Returns:
        Sigla da tecnologia ('E', 'H', 'L', '5'), ou '' se não reconhecida.

    Example:
        >>> mapear_sigla_tecnologia("4G LTE")
        'L'
        >>> mapear_sigla_tecnologia("5G NR")
        '5'
        >>> mapear_sigla_tecnologia("desconhecido")
        ''
    """
    t = str(texto).upper()

    for palavras, sigla in _MAPA_TECNOLOGIAS:
        if any(palavra in t for palavra in palavras):
            return sigla

    return ""