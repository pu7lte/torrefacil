"""Funções geográficas compartilhadas pelos módulos do Modo Loja.

Centraliza:
    - Cálculo de distância (haversine) entre coordenadas
    - Encontrar ERBs próximas a um ponto (raio configurável)
    - Resumir cobertura por operadora num ponto
    - Nota de cobertura para exibição na TUI

Este módulo é privado (prefixo `_`) e não faz parte da API pública.
"""
from __future__ import annotations

import logging
import math
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Raio médio da Terra em quilômetros (usado no cálculo haversine)
_RAIO_TERRA_KM = 6371.0

# Tecnologias válidas
_TECNOLOGIAS_VALIDAS: frozenset[str] = frozenset({"E", "H", "L", "5"})

# Tipos de 5G reconhecidos
_TIPOS_5G_VALIDOS: frozenset[str] = frozenset({"SA-NSA", "NSA"})


# ---------------------------------------------------------------------------
# Haversine
# ---------------------------------------------------------------------------

def distancia_km(lat1: Any, lon1: Any, lat2: Any, lon2: Any) -> float:
    """Calcula distância em km entre dois pontos usando fórmula haversine.

    Args:
        lat1: Latitude do ponto 1.
        lon1: Longitude do ponto 1.
        lat2: Latitude do ponto 2.
        lon2: Longitude do ponto 2.

    Returns:
        Distância em quilômetros, ou ``float('inf')`` se algum valor for inválido.

    Examples:
        >>> distancia_km(-5.79, -35.21, -5.80, -35.22)  # ~1.5 km
        1.5...
        >>> distancia_km(None, None, -5.80, -35.22)
        inf
    """
    # Validação de entrada
    if any(v is None or (isinstance(v, float) and pd.isna(v))
           for v in (lat1, lon1, lat2, lon2)):
        return float("inf")

    try:
        rlat1, rlon1 = math.radians(float(lat1)), math.radians(float(lon1))
        rlat2, rlon2 = math.radians(float(lat2)), math.radians(float(lon2))

        dlat = rlat2 - rlat1
        dlon = rlon2 - rlon1

        a = (math.sin(dlat / 2) ** 2
             + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2)

        return 2 * _RAIO_TERRA_KM * math.asin(math.sqrt(a))

    except (TypeError, ValueError):
        logger.debug("Valores inválidos para haversine: %s, %s, %s, %s",
                     lat1, lon1, lat2, lon2)
        return float("inf")


# ---------------------------------------------------------------------------
# Buscar ERBs próximas
# ---------------------------------------------------------------------------

def erbs_proximas(
    df: pd.DataFrame,
    lat: Any,
    lon: Any,
    raio_km: float = 3.0,
    limite: int | None = None,
) -> pd.DataFrame:
    """Retorna ERBs dentro do raio, com coluna ``DIST_KM`` adicionada.

    Estratégia de otimização:
        1. Filtro grosso por bounding box (muito mais rápido)
        2. Haversine exato apenas nos candidatos

    Args:
        df: DataFrame completo de ERBs.
        lat: Latitude do ponto de referência.
        lon: Longitude do ponto de referência.
        raio_km: Raio de busca em quilômetros (padrão: 3.0).
        limite: Número máximo de resultados (opcional).

    Returns:
        DataFrame filtrado e ordenado por distância, ou vazio se sem resultados.

    Examples:
        >>> df = pd.DataFrame({'LAT_NUM': [-5.79], 'LON_NUM': [-35.21]})
        >>> resultado = erbs_proximas(df, -5.80, -35.22, raio_km=5.0)
    """
    if df.empty or lat is None or lon is None:
        return df.head(0).copy()

    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        logger.debug("Coordenadas inválidas: lat=%s, lon=%s", lat, lon)
        return df.head(0).copy()

    # 1) Filtro grosso por bounding box
    delta_lat = raio_km / 111.0
    cos_lat = max(0.001, math.cos(math.radians(lat_f)))
    delta_lon = raio_km / (111.0 * cos_lat)

    lat_min, lat_max = lat_f - delta_lat, lat_f + delta_lat
    lon_min, lon_max = lon_f - delta_lon, lon_f + delta_lon

    mask = (
        df["LAT_NUM"].notna()
        & df["LON_NUM"].notna()
        & (df["LAT_NUM"] >= lat_min)
        & (df["LAT_NUM"] <= lat_max)
        & (df["LON_NUM"] >= lon_min)
        & (df["LON_NUM"] <= lon_max)
    )
    sub = df.loc[mask].copy()

    if sub.empty:
        return sub

    # 2) Haversine exato só nos candidatos
    sub["DIST_KM"] = [
        distancia_km(lat_f, lon_f, la, lo)
        for la, lo in zip(sub["LAT_NUM"], sub["LON_NUM"])
    ]
    sub = sub[sub["DIST_KM"] <= raio_km]
    sub = sub.sort_values("DIST_KM")

    if limite:
        sub = sub.head(limite)

    return sub.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Resumo por operadora num ponto
# ---------------------------------------------------------------------------

def _extrair_tecnologias(grupo: pd.DataFrame) -> set[str]:
    """Extrai conjunto de tecnologias de um grupo de ERBs.

    Args:
        grupo: DataFrame com coluna ``TECS_RAW``.

    Returns:
        Conjunto de siglas de tecnologia (ex: {"E", "H", "L", "5"}).
    """
    todas: set[str] = set()
    if "TECS_RAW" not in grupo.columns:
        return todas

    for t in grupo["TECS_RAW"]:
        for s in str(t).split(","):
            s = s.strip()
            if s in _TECNOLOGIAS_VALIDAS:
                todas.add(s)

    return todas


def _extrair_tipos_5g(grupo: pd.DataFrame) -> set[str]:
    """Extrai conjunto de tipos de 5G (SA-NSA, NSA) de um grupo.

    Args:
        grupo: DataFrame com coluna ``TEC5G_TIPO``.

    Returns:
        Conjunto de tipos de 5G (ex: {"SA-NSA"}).
    """
    tipos: set[str] = set()
    if "TEC5G_TIPO" not in grupo.columns:
        return tipos

    for t in grupo["TEC5G_TIPO"].dropna().unique():
        if t in _TIPOS_5G_VALIDOS:
            tipos.add(t)

    return tipos


def _extrair_faixas(grupo: pd.DataFrame) -> set[str]:
    """Extrai conjunto de faixas nominais de um grupo.

    Args:
        grupo: DataFrame com coluna ``FAIXA_NOMINAL``.

    Returns:
        Conjunto de faixas (ex: {"700", "1800", "3500"}).
    """
    faixas: set[str] = set()
    if "FAIXA_NOMINAL" not in grupo.columns:
        return faixas

    for f in grupo["FAIXA_NOMINAL"].dropna().unique():
        if f:
            faixas.add(str(f))

    return faixas


def resumo_por_operadora(df_prox: pd.DataFrame) -> pd.DataFrame:
    """Agrega cobertura por operadora num ponto geográfico.

    Args:
        df_prox: DataFrame já filtrado por proximidade (com coluna ``DIST_KM``).

    Returns:
        DataFrame com uma linha por operadora e colunas:
            - ``OPERADORA``: Nome da operadora
            - ``ERBS``: Número de ERBs próximas
            - ``DIST_MIN``: Distância mínima em km
            - ``DIST_MEDIA``: Distância média em km
            - ``TECNOLOGIAS``: String com tecnologias (ex: "E,H,L,5")
            - ``TEM_5G``, ``TEM_4G``, ``TEM_3G``, ``TEM_2G``: Booleanos
            - ``TEC5G_TIPO``: Tipo de 5G (ex: "SA-NSA/NSA")
            - ``FAIXAS``: String com faixas (ex: "700,1800,3500")

    Examples:
        >>> df = pd.DataFrame({
        ...     'OPERADORA': ['VIVO', 'VIVO'],
        ...     'DIST_KM': [0.5, 1.2],
        ...     'TECS_RAW': ['L,5', 'L,5'],
        ... })
        >>> resumo = resumo_por_operadora(df)
    """
    if df_prox.empty:
        return pd.DataFrame()

    linhas: list[dict[str, Any]] = []

    for op, grp in df_prox.groupby("OPERADORA"):
        tecs = _extrair_tecnologias(grp)
        tipos5g = _extrair_tipos_5g(grp)
        faixas = _extrair_faixas(grp)

        linhas.append({
            "OPERADORA": op,
            "ERBS": int(len(grp)),
            "DIST_MIN": float(grp["DIST_KM"].min()),
            "DIST_MEDIA": float(grp["DIST_KM"].mean()),
            "TECNOLOGIAS": ", ".join(sorted(tecs)),
            "TEM_5G": "5" in tecs,
            "TEM_4G": "L" in tecs,
            "TEM_3G": "H" in tecs,
            "TEM_2G": "E" in tecs,
            "TEC5G_TIPO": "/".join(sorted(tipos5g)) if tipos5g else "",
            "FAIXAS": ", ".join(
                sorted(faixas, key=lambda x: int(x) if x.isdigit() else 999)
            ),
        })

    df_s = pd.DataFrame(linhas)
    df_s = df_s.sort_values(
        by=["TEM_5G", "ERBS", "DIST_MIN"],
        ascending=[False, False, True],
    ).reset_index(drop=True)

    return df_s


# ---------------------------------------------------------------------------
# Nota de cobertura para exibição
# ---------------------------------------------------------------------------

def nota_cobertura(row: dict[str, Any]) -> tuple[str, str]:
    """Calcula nota de cobertura para exibição na TUI.

    Args:
        row: Dicionário com dados da operadora (de ``resumo_por_operadora``).

    Returns:
        Tupla ``(texto_nota, chave_cor)`` onde:
            - ``texto_nota``: "EXCELENTE", "BOA", "REGULAR", "FRACA" ou "SEM COBERTURA"
            - ``chave_cor``: "otimo", "bom", "fraco" ou "sem"

    Examples:
        >>> nota_cobertura({"ERBS": 3, "TEM_5G": True, "DIST_MIN": 0.3})
        ('EXCELENTE', 'otimo')
        >>> nota_cobertura({"ERBS": 0})
        ('SEM COBERTURA', 'sem')
    """
    if not row.get("ERBS"):
        return "SEM COBERTURA", "sem"

    # 5G muito próximo = excelente
    if row.get("TEM_5G") and row.get("DIST_MIN", 99) < 0.5:
        return "EXCELENTE", "otimo"

    # 5G ou 4G próximo = boa
    if row.get("TEM_5G") or (row.get("TEM_4G") and row.get("DIST_MIN", 99) < 1.0):
        return "BOA", "bom"

    # 4G ou 3G = regular
    if row.get("TEM_4G") or row.get("TEM_3G"):
        return "REGULAR", "bom"

    # Só 2G ou nada = fraca
    return "FRACA", "fraco"