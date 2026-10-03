"""Explorador guiado por operadora (fluxo em 4 passos).

Passos:
    1. Selecionar operadora
    2. Selecionar UF (ou Brasil inteiro)
    3. Selecionar filtro de tecnologia
    4. Navegar por municípios (com painel interativo)

Recursos:
    - Filtro por quantidade de ERBs por cidade
    - Exportação CSV da lista de cidades
    - Integração com painel_interativo_municipio
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ..painel import painel_interativo_municipio, salvar_csv_tui
from ..texto import formatar_lista_tec
from ..tui.cores import CAIXA_TEXTO, CAIXA_TITULO
from ..tui.janelas import (
    criar_item_tui,
    alerta_tui,
    abrir_droplist_popup,
    menu_popup_centralizado,
)
from ..tui.navegador import navegador_tui

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Opções de filtro de tecnologia
_OPCAO_TODAS = ("", "TODAS AS TECNOLOGIAS")
_OPCAO_5G = ("5", "5G ATIVO")
_OPCAO_4G = ("L", "4G ATIVO")
_OPCAO_3G = ("H", "3G ATIVO")
_OPCAO_2G = ("E", "2G ATIVO")

# Opções de filtro de quantidade
_OPCAO_EXATAMENTE_1 = "1"
_OPCAO_ATE_2 = "<=2"
_OPCAO_ATE_5 = "<=5"
_OPCAO_5_OU_MAIS = ">=5"
_OPCAO_10_OU_MAIS = ">=10"

# Título do módulo
_MODULO = "EXPLORADOR GUIADO"

# Opção especial para Brasil inteiro
_OPCAO_TODOS = "TODOS"
_ROTULO_BRASIL = "[BRASIL INTEIRO]"


# ---------------------------------------------------------------------------
# Passo 1: Selecionar operadora
# ---------------------------------------------------------------------------

def _passo1_selecionar_operadora(
    df_erbs: pd.DataFrame,
) -> tuple[str, pd.DataFrame] | None:
    """Passo 1: seleciona operadora.

    Args:
        df_erbs: DataFrame completo de ERBs.

    Returns:
        Tupla (operadora_selecionada, df_filtrado), ou None se cancelado.
    """
    # Calcula ranking de operadoras
    ranking_op = (
        df_erbs.groupby("OPERADORA")
        .agg(
            ERBS=("ID_ERB", "nunique"),
            UFS=("UF", "nunique"),
            CIDADES=("MUNICIPIO_NORM", "nunique"),
        )
        .sort_values(by="ERBS", ascending=False)
        .reset_index()
    )

    # Monta itens do menu
    itens_op: list[dict[str, Any]] = []

    # Iteração vetorizada
    operadoras = ranking_op["OPERADORA"].tolist()
    erbs_count = ranking_op["ERBS"].tolist()
    ufs_count = ranking_op["UFS"].tolist()
    cidades_count = ranking_op["CIDADES"].tolist()

    for idx in range(len(ranking_op)):
        atalho = str(idx + 1) if idx < 9 else None
        txt = (
            f"{idx + 1:2d}. {operadoras[idx]:<14} "
            f"({erbs_count[idx]:6,d} ERBs | {ufs_count[idx]:2d} UFs | "
            f"{cidades_count[idx]:4d} Cid.)"
        ).replace(",", ".")

        itens_op.append(criar_item_tui(
            txt, CAIXA_TEXTO, "esq",
            selecionavel=True,
            dados=operadoras[idx],
            atalho=atalho,
        ))

    acao, op_sel, _ = menu_popup_centralizado(
        modulo=f"{_MODULO} (1/4)",
        titulo_caixa="SELECIONE A OPERADORA",
        itens_menu=itens_op,
        largura_caixa=58,
    )

    if acao != "SELECT" or not op_sel:
        return None

    df_op = df_erbs[df_erbs["OPERADORA"] == op_sel].copy()
    logger.info("Operadora selecionada: %s (%d ERBs)", op_sel, len(df_op))

    return op_sel, df_op


# ---------------------------------------------------------------------------
# Passo 2: Selecionar UF
# ---------------------------------------------------------------------------

def _passo2_selecionar_uf(
    df_op: pd.DataFrame,
    operadora: str,
) -> tuple[str, pd.DataFrame] | None:
    """Passo 2: seleciona UF ou Brasil inteiro.

    Args:
        df_op: DataFrame filtrado pela operadora.
        operadora: Nome da operadora selecionada.

    Returns:
        Tupla (uf_selecionada, df_filtrado), ou None se cancelado.
    """
    # Calcula estatísticas por UF
    ufs_op = (
        df_op.groupby("UF")
        .agg(
            ERBS=("NUM_ESTACAO", "nunique"),
            CIDADES=("MUNICIPIO_NORM", "nunique"),
            ERBS_5G=("TECS_RAW", lambda s: s.str.contains("5", na=False).sum()),
            ERBS_4G=("TECS_RAW", lambda s: s.str.contains("L", na=False).sum()),
        )
        .sort_values(by="ERBS", ascending=False)
        .reset_index()
    )

    # Monta itens do navegador
    itens_uf: list[dict[str, Any]] = [
        criar_item_tui(
            f"{_ROTULO_BRASIL} Todos os {len(ufs_op)} estados "
            f"({df_op['NUM_ESTACAO'].nunique()} ERBs)",
            CAIXA_TITULO,
            selecionavel=True,
            dados=_OPCAO_TODOS,
        )
    ]

    # Iteração vetorizada
    ufs = ufs_op["UF"].tolist()
    erbs_uf = ufs_op["ERBS"].tolist()
    cidades_uf = ufs_op["CIDADES"].tolist()
    erbs_5g_uf = ufs_op["ERBS_5G"].tolist()
    erbs_4g_uf = ufs_op["ERBS_4G"].tolist()

    for idx in range(len(ufs_op)):
        ln = (
            f"UF: {ufs[idx]:<4} │ ERBs: {erbs_uf[idx]:6d} │ "
            f"Cidades: {cidades_uf[idx]:4d} │ 5G: {erbs_5g_uf[idx]:5d} │ "
            f"4G: {erbs_4g_uf[idx]:5d}"
        )
        itens_uf.append(criar_item_tui(
            ln, CAIXA_TEXTO,
            selecionavel=True,
            dados=ufs[idx],
        ))

    acao_uf, uf_esc, _, _ = navegador_tui(
        modulo=f"{_MODULO}: {operadora} (2/4)",
        titulo_janela=(
            f"SELECIONE O ESTADO (UF) DE ATUAÇÃO DA {operadora} E TECLE [ENTER]"
        ),
        itens_conteudo=itens_uf,
        dica_teclas=(
            "↑/↓=Mover | PgUp/PgDn=Página | ENTER=Selecionar | ESC/0=Voltar"
        ),
    )

    if acao_uf != "SELECT" or not uf_esc:
        return None

    if uf_esc != _OPCAO_TODOS:
        df_op = df_op[df_op["UF"] == uf_esc]
        logger.info("UF selecionada: %s (%d ERBs)", uf_esc, len(df_op))

    escopo = uf_esc if uf_esc != _OPCAO_TODOS else "BRASIL"
    return escopo, df_op


# ---------------------------------------------------------------------------
# Passo 3: Selecionar tecnologia
# ---------------------------------------------------------------------------

def _passo3_selecionar_tecnologia(
    df_op: pd.DataFrame,
    operadora: str,
    escopo: str,
) -> tuple[str, str, pd.DataFrame] | None:
    """Passo 3: seleciona filtro de tecnologia.

    Args:
        df_op: DataFrame filtrado por operadora e UF.
        operadora: Nome da operadora.
        escopo: Escopo atual (UF ou "BRASIL").

    Returns:
        Tupla (sigla_tecnologia, nome_filtro, df_filtrado), ou None se cancelado.
    """
    # Calcula quantidades por tecnologia
    qtd_total = df_op["NUM_ESTACAO"].nunique()
    qtd_5g = df_op[df_op["TECS_RAW"].str.contains("5", na=False)]["NUM_ESTACAO"].nunique()
    qtd_4g = df_op[df_op["TECS_RAW"].str.contains("L", na=False)]["NUM_ESTACAO"].nunique()
    qtd_3g = df_op[df_op["TECS_RAW"].str.contains("H", na=False)]["NUM_ESTACAO"].nunique()
    qtd_2g = df_op[df_op["TECS_RAW"].str.contains("E", na=False)]["NUM_ESTACAO"].nunique()

    itens_tec: list[dict[str, Any]] = [
        criar_item_tui(
            f"1. Todas as Tecnologias ({qtd_total} ERBs)",
            CAIXA_TEXTO,
            selecionavel=True,
            dados=_OPCAO_TODAS,
            atalho="1",
        ),
        criar_item_tui(
            f"2. Apenas ERBs com 5G Ativo ({qtd_5g} ERBs)",
            CAIXA_TEXTO,
            selecionavel=True,
            dados=_OPCAO_5G,
            atalho="2",
        ),
        criar_item_tui(
            f"3. Apenas ERBs com 4G Ativo ({qtd_4g} ERBs)",
            CAIXA_TEXTO,
            selecionavel=True,
            dados=_OPCAO_4G,
            atalho="3",
        ),
        criar_item_tui(
            f"4. Apenas ERBs com 3G Ativo ({qtd_3g} ERBs)",
            CAIXA_TEXTO,
            selecionavel=True,
            dados=_OPCAO_3G,
            atalho="4",
        ),
        criar_item_tui(
            f"5. Apenas ERBs com 2G Ativo ({qtd_2g} ERBs)",
            CAIXA_TEXTO,
            selecionavel=True,
            dados=_OPCAO_2G,
            atalho="5",
        ),
    ]

    acao_t, dados_t, _ = menu_popup_centralizado(
        modulo=f"{_MODULO}: {operadora} (3/4)",
        titulo_caixa=f"FILTRO DE TECNOLOGIA ({escopo})",
        itens_menu=itens_tec,
        largura_caixa=54,
    )

    if acao_t != "SELECT" or not dados_t:
        return None

    sig_t, filtro_tec_nome = dados_t

    if sig_t:
        df_op = df_op[df_op["TECS_RAW"].str.contains(sig_t, na=False)]
        if df_op.empty:
            alerta_tui(
                "FILTRO VAZIO",
                "NENHUMA ERB ENCONTRADA",
                [f"A {operadora} não possui ERBs com {filtro_tec_nome} neste recorte."],
            )
            return None
        logger.info("Filtro de tecnologia aplicado: %s (%d ERBs)", sig_t, len(df_op))

    return sig_t, filtro_tec_nome, df_op


# ---------------------------------------------------------------------------
# Passo 4: Navegar por municípios
# ---------------------------------------------------------------------------

def _passo4_navegar_municipios(
    df_op: pd.DataFrame,
    operadora: str,
    escopo: str,
    sig_t: str,
    filtro_tec_nome: str,
) -> None:
    """Passo 4: navega por municípios com painel interativo.

    Args:
        df_op: DataFrame filtrado por operadora, UF e tecnologia.
        operadora: Nome da operadora.
        escopo: Escopo atual (UF ou "BRASIL").
        sig_t: Sigla da tecnologia filtrada (vazio = todas).
        filtro_tec_nome: Nome do filtro de tecnologia.
    """
    while True:
        # Calcula resumo por município
        resumo = (
            df_op.groupby(["UF", "MUNICIPIO", "MUNICIPIO_LIMPO"], as_index=False)
            .agg(
                TOTAL_ERBS=("NUM_ESTACAO", "nunique"),
                BAIRROS=("BAIRRO", "nunique"),
                TECS_ATIVAS=(
                    "TECS_RAW",
                    lambda s: formatar_lista_tec(",".join(s).split(",")),
                ),
            )
            .sort_values(
                by=["TOTAL_ERBS", "MUNICIPIO_LIMPO"],
                ascending=[False, True],
            )
            .reset_index(drop=True)
        )

        # Monta itens do navegador
        itens: list[dict[str, Any]] = []

        # Iteração vetorizada
        ufs_mun = resumo["UF"].tolist()
        municipios = resumo["MUNICIPIO"].tolist()
        municipios_limpos = resumo["MUNICIPIO_LIMPO"].tolist()
        total_erbs_mun = resumo["TOTAL_ERBS"].tolist()
        bairros_mun = resumo["BAIRROS"].tolist()
        tecs_mun = resumo["TECS_ATIVAS"].tolist()

        for idx in range(len(resumo)):
            ln = (
                f"{ufs_mun[idx]:<4} {municipios_limpos[idx][:31]:<32} "
                f"{total_erbs_mun[idx]:^10} {bairros_mun[idx]:^10} "
                f"{tecs_mun[idx]}"
            )
            itens.append(criar_item_tui(
                ln, CAIXA_TEXTO,
                selecionavel=True,
                dados=(ufs_mun[idx], municipios[idx], municipios_limpos[idx]),
            ))

        cab = (
            f"   {'UF':<4} {'MUNICÍPIO':<32} {'ERBs':^10} {'BAIRROS':^10} "
            f"{'TECNOLOGIAS ([ENTER] ABRE CIDADE)'}"
        )

        acao_c, dados_c, _, _ = navegador_tui(
            modulo=f"{_MODULO}: {operadora} ({escopo})",
            titulo_janela=(
                f"PASSO 4: SELECIONE UM MUNICÍPIO E TECLE [ENTER] "
                f"({len(resumo)} CIDADES / {df_op['NUM_ESTACAO'].nunique()} ERBs)"
            ),
            itens_conteudo=itens,
            colunas_fixas_tabela=cab,
            comandos_rodape=[
                "[ENTER] Abrir Painel do Município   |   [Q] Filtrar Qtd ERBs   |   "
                "[6] Salvar CSV   |   [ESC/0] Voltar",
            ],
            teclas_rapidas={"Q", "6"},
            dica_teclas=(
                "↑/↓=Mover | PgUp/PgDn=Página | ENTER=Abrir Cidade | "
                "Q=Filtrar Qtd | 6=CSV | ESC/0=Voltar"
            ),
        )

        if acao_c == "SELECT" and dados_c:
            uf_c, mun_c, nome_l = dados_c
            grp = df_op[(df_op["UF"] == uf_c) & (df_op["MUNICIPIO"] == mun_c)]
            painel_interativo_municipio(
                grp, nome_l, uf_c,
                filtro_extra_info=f"{operadora} ({filtro_tec_nome})",
            )

        elif acao_c == "KEY" and dados_c == "Q":
            df_op = _aplicar_filtro_quantidade(df_op, resumo)
            if df_op.empty:
                alerta_tui(
                    "FILTRO VAZIO",
                    "NENHUMA CIDADE ENCONTRADA",
                    ["O filtro removeu todas as cidades. Tente outro critério."],
                )
                return

        elif acao_c == "KEY" and dados_c == "6":
            padrao = f"explorador_{operadora.lower()}_{escopo.lower()}.csv"
            salvar_csv_tui(resumo, padrao, "EXPORTAR LISTA DO EXPLORADOR")

        else:
            break


def _aplicar_filtro_quantidade(
    df_op: pd.DataFrame,
    resumo: pd.DataFrame,
) -> pd.DataFrame:
    """Aplica filtro por quantidade de ERBs por cidade.

    Args:
        df_op: DataFrame atual.
        resumo: DataFrame com resumo por município.

    Returns:
        DataFrame filtrado.
    """
    opcoes_qtd = [
        (_OPCAO_EXATAMENTE_1, "Exatamente 1 ERB na cidade (= 1)"),
        (_OPCAO_ATE_2, "Até 2 ERBs na cidade (<= 2)"),
        (_OPCAO_ATE_5, "Até 5 ERBs na cidade (<= 5)"),
        (_OPCAO_5_OU_MAIS, "5 ou mais ERBs na cidade (>= 5)"),
        (_OPCAO_10_OU_MAIS, "10 ou mais ERBs na cidade (>= 10)"),
    ]

    qtd_in = abrir_droplist_popup("FILTRAR POR QUANTIDADE DE ERBs", opcoes_qtd)

    if not qtd_in:
        return df_op

    try:
        if qtd_in.startswith("<="):
            limite = int(qtd_in[2:])
            cids = resumo[resumo["TOTAL_ERBS"] <= limite]["MUNICIPIO"].tolist()
        elif qtd_in.startswith(">="):
            limite = int(qtd_in[2:])
            cids = resumo[resumo["TOTAL_ERBS"] >= limite]["MUNICIPIO"].tolist()
        else:
            limite = int(qtd_in)
            cids = resumo[resumo["TOTAL_ERBS"] == limite]["MUNICIPIO"].tolist()

        df_filtrado = df_op[df_op["MUNICIPIO"].isin(cids)]
        logger.info("Filtro de quantidade aplicado: %s (%d cidades)", qtd_in, len(cids))
        return df_filtrado

    except ValueError:
        logger.warning("Valor inválido para filtro de quantidade: %s", qtd_in)
        return df_op


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def pesquisa_guiada_operadora(df_erbs: pd.DataFrame) -> None:
    """Ponto de entrada do explorador guiado.

    Fluxo em 4 passos:
        1. Selecionar operadora
        2. Selecionar UF (ou Brasil inteiro)
        3. Selecionar filtro de tecnologia
        4. Navegar por municípios

    Args:
        df_erbs: DataFrame completo de ERBs.
    """
    # Passo 1: operadora
    resultado1 = _passo1_selecionar_operadora(df_erbs)
    if not resultado1:
        return
    op_sel, df_op = resultado1

    # Passo 2: UF
    resultado2 = _passo2_selecionar_uf(df_op, op_sel)
    if not resultado2:
        return
    escopo, df_op = resultado2

    # Passo 3: tecnologia
    resultado3 = _passo3_selecionar_tecnologia(df_op, op_sel, escopo)
    if not resultado3:
        return
    sig_t, filtro_tec_nome, df_op = resultado3

    # Passo 4: municípios
    _passo4_navegar_municipios(df_op, op_sel, escopo, sig_t, filtro_tec_nome)