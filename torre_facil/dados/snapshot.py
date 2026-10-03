"""Snapshot e comparação da base ANATEL.

Este módulo mantém um arquivo ``torre_facil_snapshot.json`` com o último estado
conhecido da base. Na próxima compilação, comparamos o snapshot antigo
com o novo e devolvemos uma estrutura de diferenças.

Estrutura do snapshot:
    {
        "versao_snapshot": 1,
        "gerado_em": "2025-10-02T14:30:00",
        "data_base": "02/10/2025",
        "total_erbs": 228106,
        "total_setores": 512345,
        "por_uf": {"SP": 45231, ...},
        "por_operadora": {"VIVO": 83662, ...},
        "por_operadora_uf": {"VIVO|SP": 12345, ...},
        "por_tecnologia": {"5": 12345, "L": 98765, ...},
        "por_operadora_5g": {"VIVO": 8765, ...},
        "por_operadora_5g_sa": {"VIVO": 3210, ...},
        "por_municipio_5g": {"SAO PAULO|SP": 523, ...},
        "por_municipio_op": {"NATAL|RN": ["VIVO", "CLARO", "TIM"], ...},
        "erbs_ids": {
            "VIVO|1015798524": {
                "uf": "RN",
                "mun": "NATAL",
                "bairro": "PONTA NEGRA",
                "tecs": "5,L",
                "5g_sa": true
            },
            ...
        }
    }
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

ARQUIVO_SNAPSHOT = "torre_facil_snapshot.json"
VERSAO_SNAPSHOT = 1

# Tecnologias monitoradas
_TECNOLOGIAS_MONITORADAS = frozenset({"5", "L", "H", "E"})


# ---------------------------------------------------------------------------
# Geração
# ---------------------------------------------------------------------------

def gerar_snapshot(
    df_erbs: pd.DataFrame | None,
    total_setores: int = 0,
    data_base: str = "",
) -> dict[str, Any]:
    """Constrói o dict do snapshot a partir do DataFrame.

    O DataFrame esperado tem as colunas padrão do app:
        UF, MUNICIPIO_LIMPO, OPERADORA, NUM_ESTACAO, TECNOLOGIA,
        TECS_RAW, BAIRRO, TEC5G_TIPO.

    Args:
        df_erbs: DataFrame de ERBs (pode ser None ou vazio).
        total_setores: Número total de setores antes da agregação.
        data_base: Data base do snapshot (formato DD/MM/AAAA).

    Returns:
        Dicionário com o snapshot completo.
    """
    if df_erbs is None or df_erbs.empty:
        return _snapshot_vazio(total_setores, data_base)

    df = df_erbs
    hoje = datetime.datetime.now().isoformat(timespec="seconds")
    data_fmt = data_base or datetime.date.today().strftime("%d/%m/%Y")

    # Contagens agregadas
    por_uf = _contar_por_uf(df)
    por_op = _contar_por_operadora(df)
    por_op_uf = _contar_por_operadora_uf(df)
    por_tec = _contar_por_tecnologia(df)
    por_op_5g = _contar_5g_por_operadora(df)
    por_op_5g_sa = _contar_5g_sa_por_operadora(df)
    por_mun_5g = _contar_5g_por_municipio(df)
    por_mun_op = _contar_operadoras_por_municipio(df)

    # Metadados por ERB
    erbs_ids = _extrair_metadados_erbs(df)

    # Total de ERBs únicas
    total_erbs = (
        int(df["ID_ERB"].nunique())
        if "ID_ERB" in df.columns
        else len(df)
    )

    return {
        "versao_snapshot": VERSAO_SNAPSHOT,
        "gerado_em": hoje,
        "data_base": data_fmt,
        "total_erbs": total_erbs,
        "total_setores": int(total_setores),
        "por_uf": por_uf,
        "por_operadora": por_op,
        "por_operadora_uf": por_op_uf,
        "por_tecnologia": por_tec,
        "por_operadora_5g": por_op_5g,
        "por_operadora_5g_sa": por_op_5g_sa,
        "por_municipio_5g": por_mun_5g,
        "por_municipio_op": por_mun_op,
        "erbs_ids": erbs_ids,
    }


def _snapshot_vazio(total_setores: int, data_base: str) -> dict[str, Any]:
    """Retorna snapshot vazio quando não há dados.

    Args:
        total_setores: Número total de setores.
        data_base: Data base do snapshot.

    Returns:
        Dicionário com estrutura vazia.
    """
    return {
        "versao_snapshot": VERSAO_SNAPSHOT,
        "gerado_em": datetime.datetime.now().isoformat(timespec="seconds"),
        "data_base": data_base or datetime.date.today().strftime("%d/%m/%Y"),
        "total_erbs": 0,
        "total_setores": total_setores,
        "por_uf": {},
        "por_operadora": {},
        "por_operadora_uf": {},
        "por_tecnologia": {},
        "por_operadora_5g": {},
        "por_operadora_5g_sa": {},
        "por_municipio_5g": {},
        "por_municipio_op": {},
        "erbs_ids": {},
    }


def _contar_por_uf(df: pd.DataFrame) -> dict[str, int]:
    """Conta ERBs únicas por UF.

    Args:
        df: DataFrame de ERBs.

    Returns:
        Dicionário {UF: contagem}.
    """
    return df.groupby("UF")["ID_ERB"].nunique().to_dict()


def _contar_por_operadora(df: pd.DataFrame) -> dict[str, int]:
    """Conta ERBs únicas por operadora.

    Args:
        df: DataFrame de ERBs.

    Returns:
        Dicionário {operadora: contagem}.
    """
    return df.groupby("OPERADORA")["ID_ERB"].nunique().to_dict()


def _contar_por_operadora_uf(df: pd.DataFrame) -> dict[str, int]:
    """Conta ERBs únicas por operadora+UF.

    Args:
        df: DataFrame de ERBs.

    Returns:
        Dicionário {"OPERADORA|UF": contagem}.
    """
    por_op_uf = (
        df.groupby(["OPERADORA", "UF"])["ID_ERB"]
        .nunique()
        .to_dict()
    )
    return {f"{op}|{uf}": v for (op, uf), v in por_op_uf.items()}


def _contar_por_tecnologia(df: pd.DataFrame) -> dict[str, int]:
    """Conta ERBs por tecnologia (2G/3G/4G/5G).

    Args:
        df: DataFrame de ERBs.

    Returns:
        Dicionário {tecnologia: contagem}.
    """
    tec_counts = {tec: 0 for tec in _TECNOLOGIAS_MONITORADAS}

    if "TECS_RAW" not in df.columns:
        return {k: v for k, v in tec_counts.items() if v > 0}

    # Uma linha por ERB com a string "L,5" ou "E,H,L,5"
    erbs = df.drop_duplicates(subset=["ID_ERB"])
    for tec_raw in erbs["TECS_RAW"]:
        for t in str(tec_raw).split(","):
            t = t.strip()
            if t in tec_counts:
                tec_counts[t] += 1

    return {k: v for k, v in tec_counts.items() if v > 0}


def _contar_5g_por_operadora(df: pd.DataFrame) -> dict[str, int]:
    """Conta ERBs com 5G por operadora.

    Args:
        df: DataFrame de ERBs.

    Returns:
        Dicionário {operadora: contagem}.
    """
    if "TECS_RAW" not in df.columns:
        return {}

    df_5g = df[df["TECS_RAW"].str.contains("5", na=False)]
    if df_5g.empty:
        return {}

    return df_5g.groupby("OPERADORA")["ID_ERB"].nunique().to_dict()


def _contar_5g_sa_por_operadora(df: pd.DataFrame) -> dict[str, int]:
    """Conta ERBs com 5G SA (SA-NSA) por operadora.

    Args:
        df: DataFrame de ERBs.

    Returns:
        Dicionário {operadora: contagem}.
    """
    if "TEC5G_TIPO" not in df.columns:
        return {}

    df_5g_sa = df[df["TEC5G_TIPO"].str.contains("SA", na=False)]
    if df_5g_sa.empty:
        return {}

    return df_5g_sa.groupby("OPERADORA")["ID_ERB"].nunique().to_dict()


def _contar_5g_por_municipio(df: pd.DataFrame) -> dict[str, int]:
    """Conta ERBs com 5G por município.

    Args:
        df: DataFrame de ERBs.

    Returns:
        Dicionário {"MUNICIPIO|UF": contagem}.
    """
    if "TECS_RAW" not in df.columns:
        return {}

    df_5g = df[df["TECS_RAW"].str.contains("5", na=False)]
    if df_5g.empty:
        return {}

    mun_5g = df_5g.groupby(["MUNICIPIO_LIMPO", "UF"])["ID_ERB"].nunique()
    return {f"{mun}|{uf}": v for (mun, uf), v in mun_5g.items()}


def _contar_operadoras_por_municipio(df: pd.DataFrame) -> dict[str, list[str]]:
    """Lista operadoras presentes em cada município.

    Args:
        df: DataFrame de ERBs.

    Returns:
        Dicionário {"MUNICIPIO|UF": [lista de operadoras]}.
    """
    tmp = (
        df.groupby(["MUNICIPIO_LIMPO", "UF"])["OPERADORA"]
        .apply(lambda s: sorted(set(s)))
        .to_dict()
    )
    return {f"{mun}|{uf}": ops for (mun, uf), ops in tmp.items()}


def _extrair_metadados_erbs(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    """Extrai metadados de cada ERB para detalhamento fino.

    A chave é ID_ERB (formato "OPERADORA|NUM_ESTACAO").

    Args:
        df: DataFrame de ERBs.

    Returns:
        Dicionário {ID_ERB: {uf, mun, bairro, tecs, 5g_sa}}.

    Note:
        Usa iteração vetorizada em vez de iterrows() para melhor performance.
    """
    if "ID_ERB" not in df.columns:
        return {}

    tem_bairro = "BAIRRO" in df.columns
    tem_5g_tipo = "TEC5G_TIPO" in df.columns

    # Extração vetorizada (muito mais rápida que iterrows)
    ids = df["ID_ERB"].astype(str).tolist()
    ufs = df["UF"].fillna("").astype(str).tolist()
    muns = df["MUNICIPIO_LIMPO"].fillna("").astype(str).tolist()
    bairros = df["BAIRRO"].fillna("").astype(str).tolist() if tem_bairro else [""] * len(df)
    tecs = df["TECS_RAW"].fillna("").astype(str).tolist() if "TECS_RAW" in df.columns else [""] * len(df)

    if tem_5g_tipo:
        t5g = df["TEC5G_TIPO"].fillna("").astype(str).str.upper().tolist()
        sa_flags = ["SA" in t for t in t5g]
    else:
        sa_flags = [False] * len(df)

    erbs_ids = {}
    for i, chave in enumerate(ids):
        if not chave:
            continue
        erbs_ids[chave] = {
            "uf": ufs[i],
            "mun": muns[i],
            "bairro": bairros[i] if tem_bairro else "",
            "tecs": tecs[i],
            "5g_sa": sa_flags[i],
        }

    return erbs_ids


# ---------------------------------------------------------------------------
# Persistência
# ---------------------------------------------------------------------------

def salvar_snapshot(snap: dict[str, Any], caminho: str | None = None) -> bool:
    """Salva snapshot em arquivo JSON.

    Args:
        snap: Dicionário do snapshot.
        caminho: Caminho do arquivo (padrão: ``ARQUIVO_SNAPSHOT``).

    Returns:
        True se salvou com sucesso, False caso contrário.
    """
    caminho = caminho or ARQUIVO_SNAPSHOT
    try:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, separators=(",", ":"))
        logger.info("Snapshot salvo em %s", caminho)
        return True
    except Exception:
        logger.exception("Falha ao salvar snapshot")
        return False


def carregar_snapshot(caminho: str | None = None) -> dict[str, Any] | None:
    """Carrega snapshot do arquivo JSON.

    Args:
        caminho: Caminho do arquivo (padrão: ``ARQUIVO_SNAPSHOT``).

    Returns:
        Dicionário do snapshot, ou None se não existir ou for inválido.
    """
    caminho = caminho or ARQUIVO_SNAPSHOT
    if not os.path.exists(caminho):
        logger.debug("Snapshot não encontrado: %s", caminho)
        return None

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            snap = json.load(f)

        if snap.get("versao_snapshot") != VERSAO_SNAPSHOT:
            logger.warning(
                "Versão de snapshot incompatível: %s != %s",
                snap.get("versao_snapshot"),
                VERSAO_SNAPSHOT,
            )
            return None

        logger.debug("Snapshot carregado: %s", caminho)
        return snap

    except Exception:
        logger.exception("Falha ao carregar snapshot")
        return None


def carregar_snapshot_anterior() -> dict[str, Any] | None:
    """Carrega snapshot anterior (backup).

    Returns:
        Dicionário do snapshot anterior, ou None se não existir.
    """
    # Tenta carregar de um arquivo de backup
    caminho_backup = ARQUIVO_SNAPSHOT.replace(".json", "_anterior.json")
    return carregar_snapshot(caminho_backup)


# ---------------------------------------------------------------------------
# Comparação
# ---------------------------------------------------------------------------

def _diff_dicts(
    a: dict[str, Any],
    b: dict[str, Any],
    chaves_int: bool = True,
) -> list[tuple[str, int, int, int | None]]:
    """Compara dois dicts {chave: valor} e devolve diferenças.

    Args:
        a: Dicionário antigo.
        b: Dicionário novo.
        chaves_int: Se True, trata valores como inteiros.

    Returns:
        Lista de tuplas ``(chave, valor_a, valor_b, delta)``.
        Inclui chaves que apareceram (a=0) ou desapareceram (b=0).
    """
    chaves = set(a.keys()) | set(b.keys())
    saida = []

    for k in sorted(chaves):
        va = int(a.get(k, 0)) if chaves_int else a.get(k)
        vb = int(b.get(k, 0)) if chaves_int else b.get(k)

        if chaves_int:
            if va != vb:
                saida.append((k, va, vb, vb - va))
        else:
            if va != vb:
                saida.append((k, va, vb, None))

    return saida


def comparar(antigo: dict[str, Any], novo: dict[str, Any]) -> dict[str, Any]:
    """Compara dois snapshots e devolve dict de diferenças.

    Args:
        antigo: Snapshot anterior.
        novo: Snapshot atual.

    Returns:
        Dicionário com diferenças:
            - ``data_antiga``, ``data_nova``
            - ``total``: {antes, agora, delta}
            - ``por_operadora``: [(op, antes, agora, delta), ...]
            - ``por_uf``: [(uf, antes, agora, delta), ...]
            - ``por_tecnologia``: [(tec, antes, agora, delta), ...]
            - ``5g_ativado_op``: {op: n_cidades}
            - ``5g_desativado_op``: {op: n_cidades}
            - ``5g_sa_ativado_op``: {op: n_cidades}
            - ``novas_cidades_2op``: [cidades]
            - ``novas_cidades_3op``: [cidades]
            - ``erbs_novas``: [{id, uf, mun, bairro, tecs, 5g_sa}, ...]
            - ``erbs_removidas``: [{id, uf, mun, bairro, tecs, 5g_sa}, ...]
    """
    if not antigo or not novo:
        return {}

    diff: dict[str, Any] = {
        "data_antiga": antigo.get("data_base", "?"),
        "data_nova": novo.get("data_base", "?"),
    }

    # Total
    n_antigo = int(antigo.get("total_erbs", 0))
    n_novo = int(novo.get("total_erbs", 0))
    diff["total"] = {
        "antes": n_antigo,
        "agora": n_novo,
        "delta": n_novo - n_antigo,
    }

    # Por operadora
    diff["por_operadora"] = _diff_dicts(
        antigo.get("por_operadora", {}),
        novo.get("por_operadora", {}),
    )
    diff["por_operadora"].sort(key=lambda x: -abs(x[3]))

    # Por UF
    diff["por_uf"] = _diff_dicts(
        antigo.get("por_uf", {}),
        novo.get("por_uf", {}),
    )
    diff["por_uf"].sort(key=lambda x: -abs(x[3]))

    # Por tecnologia
    diff["por_tecnologia"] = _diff_dicts(
        antigo.get("por_tecnologia", {}),
        novo.get("por_tecnologia", {}),
    )
    diff["por_tecnologia"].sort(key=lambda x: -abs(x[3]))

    # 5G por município
    mun_5g_antigo = set(antigo.get("por_municipio_5g", {}).keys())
    mun_5g_novo = set(novo.get("por_municipio_5g", {}).keys())
    novas_5g = mun_5g_novo - mun_5g_antigo
    saiu_5g = mun_5g_antigo - mun_5g_novo

    # ERBs novas e removidas
    antigo_ids = antigo.get("erbs_ids", {})
    novo_ids = novo.get("erbs_ids", {})
    chaves_antigas = set(antigo_ids.keys())
    chaves_novas = set(novo_ids.keys())
    ids_novas = chaves_novas - chaves_antigas
    ids_removidas = chaves_antigas - chaves_novas

    diff["erbs_novas"] = [
        {"id": k, **(novo_ids[k] or {})} for k in sorted(ids_novas)
    ]
    diff["erbs_removidas"] = [
        {"id": k, **(antigo_ids[k] or {})} for k in sorted(ids_removidas)
    ]

    # 5G ativado por operadora
    cidades_com_5g_antes = mun_5g_antigo
    ativ_5g_op: dict[str, set[str]] = {}
    for e in diff["erbs_novas"]:
        tecs = str(e.get("tecs", ""))
        if "5" not in tecs:
            continue
        chave_cid = f"{e.get('mun', '')}|{e.get('uf', '')}"
        if chave_cid in cidades_com_5g_antes:
            continue
        op = e["id"].split("|", 1)[0]
        ativ_5g_op.setdefault(op, set()).add(chave_cid)
    diff["5g_ativado_op"] = {k: len(v) for k, v in ativ_5g_op.items()}

    # 5G SA ativado por operadora
    cidades_5g_sa_antes = _cidades_com_5g_sa(antigo_ids)
    cidades_5g_sa_agora = _cidades_com_5g_sa(novo_ids)
    novas_sa = cidades_5g_sa_agora - cidades_5g_sa_antes
    saiu_sa = cidades_5g_sa_antes - cidades_5g_sa_agora

    ativ_5g_sa_op: dict[str, set[str]] = {}
    for e in diff["erbs_novas"]:
        if not e.get("5g_sa"):
            continue
        chave_cid = f"{e.get('mun', '')}|{e.get('uf', '')}"
        if chave_cid not in novas_sa:
            continue
        op = e["id"].split("|", 1)[0]
        ativ_5g_sa_op.setdefault(op, set()).add(chave_cid)

    diff["5g_sa_ativado_op"] = {k: len(v) for k, v in ativ_5g_sa_op.items()}
    diff["5g_sa_novas_cidades"] = sorted(novas_sa)
    diff["5g_sa_cidades_perdidas"] = sorted(saiu_sa)

    # 5G desativado por operadora
    desativ_5g_op: dict[str, set[str]] = {}
    for e in diff["erbs_removidas"]:
        tecs = str(e.get("tecs", ""))
        if "5" not in tecs:
            continue
        chave_cid = f"{e.get('mun', '')}|{e.get('uf', '')}"
        if chave_cid not in mun_5g_novo:
            op = e["id"].split("|", 1)[0]
            desativ_5g_op.setdefault(op, set()).add(chave_cid)
    diff["5g_desativado_op"] = {k: len(v) for k, v in desativ_5g_op.items()}

    # Cidades que ganharam/perderam operadoras
    mun_op_antigo = antigo.get("por_municipio_op", {})
    mun_op_novo = novo.get("por_municipio_op", {})
    ganharam_2op, ganharam_3op, perderam_op = _comparar_operadoras_por_municipio(
        mun_op_antigo, mun_op_novo
    )

    diff["novas_cidades_2op"] = sorted(ganharam_2op)
    diff["novas_cidades_3op"] = sorted(ganharam_3op)
    diff["cidades_perderam_op"] = sorted(perderam_op)

    return diff


def _cidades_com_5g_sa(erbs_ids: dict[str, dict[str, Any]]) -> set[str]:
    """Retorna conjunto de cidades com pelo menos uma ERB 5G SA.

    Args:
        erbs_ids: Dicionário de ERBs do snapshot.

    Returns:
        Conjunto de chaves "MUNICIPIO|UF".
    """
    cidades = set()
    for v in erbs_ids.values():
        if v and v.get("5g_sa"):
            cidades.add(f"{v.get('mun', '')}|{v.get('uf', '')}")
    return cidades


def _comparar_operadoras_por_municipio(
    mun_op_antigo: dict[str, list[str]],
    mun_op_novo: dict[str, list[str]],
) -> tuple[list[str], list[str], list[str]]:
    """Compara operadoras por município entre dois snapshots.

    Args:
        mun_op_antigo: Operadoras por município no snapshot antigo.
        mun_op_novo: Operadoras por município no snapshot novo.

    Returns:
        Tupla ``(ganharam_2op, ganharam_3op, perderam_op)``.
    """
    ganharam_2op: list[str] = []
    ganharam_3op: list[str] = []
    perderam_op: list[str] = []

    for chave_cid in set(mun_op_antigo.keys()) | set(mun_op_novo.keys()):
        ops_antes = set(mun_op_antigo.get(chave_cid, []))
        ops_agora = set(mun_op_novo.get(chave_cid, []))

        if len(ops_agora) > len(ops_antes):
            if len(ops_agora) == 2:
                ganharam_2op.append(chave_cid)
            elif len(ops_agora) >= 3:
                ganharam_3op.append(chave_cid)
        elif len(ops_agora) < len(ops_antes):
            perderam_op.append(chave_cid)

    return ganharam_2op, ganharam_3op, perderam_op


# ---------------------------------------------------------------------------
# Helpers para formatação
# ---------------------------------------------------------------------------

def formatar_delta(delta: int) -> str:
    """Formata delta com sinal e separador de milhar.

    Args:
        delta: Valor numérico (positivo, negativo ou zero).

    Returns:
        String formatada (ex: "+1.234", "-567", "0").

    Examples:
        >>> formatar_delta(1234)
        '+1.234'
        >>> formatar_delta(-567)
        '-567'
        >>> formatar_delta(0)
        '0'
    """
    if delta > 0:
        return f"+{delta:,}".replace(",", ".")
    if delta < 0:
        return f"{delta:,}".replace(",", ".")
    return "0"


def tem_novidade_relevante(diff: dict[str, Any]) -> bool:
    """Verifica se há algo digno de abrir a tela de novidades.

    Args:
        diff: Dicionário de diferenças retornado por ``comparar()``.

    Returns:
        True se houver novidade relevante, False caso contrário.
    """
    if not diff:
        return False

    if diff.get("total", {}).get("delta", 0) != 0:
        return True

    if diff.get("erbs_novas") or diff.get("erbs_removidas"):
        return True

    if diff.get("5g_ativado_op") or diff.get("5g_sa_ativado_op"):
        return True

    if diff.get("novas_cidades_2op") or diff.get("novas_cidades_3op"):
        return True

    return False