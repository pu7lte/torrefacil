"""Pesquisa avançada parametrizada (6 filtros).

Filtros disponíveis:
    1. Estado/UF
    2. Município(s)
    3. Filtro de Operadora
    4. Tecnologia Exigida
    5. Nº ERBs na Cidade
    6. Operadora Única

Recursos:
    - Combobox com cidades sugeridas
    - Relatório em tabela ou painel direto
    - Exportação CSV do relatório
"""
from __future__ import annotations

import datetime
import logging
import re
from typing import Any

import pandas as pd

from ..dicionarios import obter_opcoes_uf
from ..painel import (
    filtrar_municipios_exatos,
    painel_interativo_municipio,
    salvar_csv_tui,
    dataframe_para_itens_tui,
)
from ..texto import formatar_lista_tec
from ..tui.janelas import formulario_tui
from ..tui.navegador import navegador_tui

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Título do módulo
_MODULO = "PESQUISA AVANÇADA"

# Opções de operadoras
_OPCAO_TODAS_OPERADORAS = ""
_OPCAO_GRANDES = "1"
_OPCAO_VIVO = "VIVO"
_OPCAO_CLARO = "CLARO"
_OPCAO_TIM = "TIM"
_OPCAO_BRISANET = "BRISANET"
_OPCAO_ALGAR = "ALGAR"
_OPCAO_UNIFIQUE = "UNIFIQUE"

_OPCOES_OPERADORAS: list[tuple[str, str]] = [
    (_OPCAO_TODAS_OPERADORAS, "TODAS AS OPERADORAS"),
    (_OPCAO_GRANDES, "APENAS GRANDES (CLARO / VIVO / TIM)"),
    (_OPCAO_VIVO, "VIVO"),
    (_OPCAO_CLARO, "CLARO"),
    (_OPCAO_TIM, "TIM"),
    (_OPCAO_BRISANET, "BRISANET"),
    (_OPCAO_ALGAR, "ALGAR"),
    (_OPCAO_UNIFIQUE, "UNIFIQUE"),
]

# Operadoras grandes
_OPERADORAS_GRANDES: frozenset[str] = frozenset({"CLARO", "VIVO", "TIM"})

# Opções de tecnologia
_OPCAO_QUALQUER_TEC = ""
_OPCAO_5G = "5"
_OPCAO_4G = "L"
_OPCAO_3G = "H"
_OPCAO_2G = "E"

_OPCOES_TEC: list[tuple[str, str]] = [
    (_OPCAO_QUALQUER_TEC, "QUALQUER TECNOLOGIA"),
    (_OPCAO_5G, "5G ATIVO (NR)"),
    (_OPCAO_4G, "4G ATIVO (LTE)"),
    (_OPCAO_3G, "3G ATIVO (HSPA/WCDMA)"),
    (_OPCAO_2G, "2G ATIVO (GSM/EDGE)"),
]

# Mapeamento de tecnologia
_MAPA_TEC: dict[str, str] = {
    "2G": "E", "E": "E",
    "3G": "H", "H": "H",
    "4G": "L", "LTE": "L", "L": "L",
    "5G": "5", "NR": "5", "5": "5",
}

# Opções de quantidade
_OPCAO_QUALQUER_QTD = ""
_OPCAO_EXATAMENTE_1 = "1"
_OPCAO_ATE_2 = "<=2"
_OPCAO_ATE_3 = "<=3"
_OPCAO_ATE_5 = "<=5"
_OPCAO_5_OU_MAIS = ">=5"
_OPCAO_10_OU_MAIS = ">=10"
_OPCAO_50_OU_MAIS = ">=50"

_OPCOES_QTD: list[tuple[str, str]] = [
    (_OPCAO_QUALQUER_QTD, "QUALQUER QUANTIDADE"),
    (_OPCAO_EXATAMENTE_1, "EXATAMENTE 1 ERB NA CIDADE (= 1)"),
    (_OPCAO_ATE_2, "ATÉ 2 ERBs NA CIDADE (<= 2)"),
    (_OPCAO_ATE_3, "ATÉ 3 ERBs NA CIDADE (<= 3)"),
    (_OPCAO_ATE_5, "ATÉ 5 ERBs NA CIDADE (<= 5)"),
    (_OPCAO_5_OU_MAIS, "5 OU MAIS ERBs (>= 5)"),
    (_OPCAO_10_OU_MAIS, "10 OU MAIS ERBs (>= 10)"),
    (_OPCAO_50_OU_MAIS, "50 OU MAIS ERBs (>= 50)"),
]

# Opções de operadora única
_OPCAO_NAO = "N"
_OPCAO_SIM = "S"

_OPCOES_UNICA_OP: list[tuple[str, str]] = [
    (_OPCAO_NAO, "NÃO (QUALQUER CIDADE)"),
    (_OPCAO_SIM, "SIM (APENAS 1 OPERADORA NA CIDADE)"),
]


# ---------------------------------------------------------------------------
# Helpers para formulário
# ---------------------------------------------------------------------------

def _sugerir_cidades(df_erbs: pd.DataFrame, vals: dict[str, str]) -> list[tuple[str, str]]:
    """Gera lista de cidades sugeridas para o combobox.

    Args:
        df_erbs: DataFrame completo de ERBs.
        vals: Valores atuais do formulário.

    Returns:
        Lista de tuplas (cidade, cidade) para o combobox.
    """
    uf = vals.get("uf", "")
    sub = df_erbs[df_erbs["UF"] == uf] if uf else df_erbs
    return [(c, c) for c in sorted(sub["MUNICIPIO_LIMPO"].unique())]


# ---------------------------------------------------------------------------
# Aplicação de filtros
# ---------------------------------------------------------------------------

def _aplicar_filtros(
    df_erbs: pd.DataFrame,
    res: dict[str, str],
) -> tuple[pd.DataFrame, bool]:
    """Aplica os 6 filtros ao DataFrame.

    Args:
        df_erbs: DataFrame completo de ERBs.
        res: Dicionário com valores do formulário.

    Returns:
        Tupla (DataFrame filtrado, pesquisa_por_municipio).
    """
    df_f = df_erbs.copy()
    pesquisa_por_municipio = False

    # 1. UF
    if res.get("uf"):
        ufs = [u.strip() for u in res["uf"].split(",") if u.strip()]
        df_f = df_f[df_f["UF"].isin(ufs)]

    # 2. Município
    if res.get("municipio"):
        df_f = filtrar_municipios_exatos(df_f, res["municipio"])
        pesquisa_por_municipio = True
        if df_f.empty:
            return df_f, pesquisa_por_municipio

    # 3. Operadora
    op_in = res.get("operadora", "")
    if op_in == _OPCAO_GRANDES:
        df_f = df_f[df_f["OPERADORA"].isin(_OPERADORAS_GRANDES)]
    elif op_in:
        df_f = df_f[df_f["OPERADORA"].str.contains(op_in, na=False)]

    # 4. Tecnologia
    tec_in = res.get("tecnologia", "")
    if tec_in in _MAPA_TEC:
        sig = _MAPA_TEC[tec_in]
        df_f = df_f[df_f["TECS_RAW"].str.contains(sig, na=False)]

    logger.info(
        "Filtros aplicados: %d registros restantes",
        len(df_f),
    )

    return df_f, pesquisa_por_municipio


# ---------------------------------------------------------------------------
# Montagem do relatório
# ---------------------------------------------------------------------------

def _montar_relatorio(
    df_f: pd.DataFrame,
    res: dict[str, str],
) -> pd.DataFrame:
    """Monta relatório resumido por município.

    Args:
        df_f: DataFrame filtrado.
        res: Dicionário com valores do formulário.

    Returns:
        DataFrame com relatório resumido.
    """
    # Agrupa por município
    resumo = (
        df_f.groupby(["UF", "MUNICIPIO"], as_index=False)
        .agg(
            TOTAL_ERBS=("ID_ERB", "nunique"),
            TECNOLOGIAS=(
                "TECS_RAW",
                lambda s: formatar_lista_tec(",".join(s).split(",")),
            ),
            QTD_OPERADORAS=("OPERADORA", "nunique"),
            OPERADORAS=("OPERADORA", lambda x: ", ".join(sorted(set(x)))),
        )
    )

    # 5. Quantidade de ERBs
    qtd_in = res.get("qtd_erbs", "")
    if qtd_in:
        resumo = _aplicar_filtro_quantidade(resumo, qtd_in)

    # 6. Operadora única
    if res.get("unica_op") in (_OPCAO_SIM, "Y"):
        resumo = resumo[resumo["QTD_OPERADORAS"] == 1]

    # Ordena
    resumo.sort_values(
        by=["UF", "TOTAL_ERBS", "MUNICIPIO"],
        inplace=True,
    )
    resumo.reset_index(drop=True, inplace=True)

    return resumo


def _aplicar_filtro_quantidade(
    resumo: pd.DataFrame,
    qtd_in: str,
) -> pd.DataFrame:
    """Aplica filtro de quantidade de ERBs ao relatório.

    Args:
        resumo: DataFrame com relatório.
        qtd_in: Valor do filtro (ex: "<=2", ">=5", "1").

    Returns:
        DataFrame filtrado.
    """
    try:
        if qtd_in.startswith("<="):
            limite = int(qtd_in[2:])
            return resumo[resumo["TOTAL_ERBS"] <= limite]
        elif qtd_in.startswith(">="):
            limite = int(qtd_in[2:])
            return resumo[resumo["TOTAL_ERBS"] >= limite]
        elif qtd_in.startswith("<"):
            limite = int(qtd_in[1:])
            return resumo[resumo["TOTAL_ERBS"] < limite]
        elif qtd_in.startswith(">"):
            limite = int(qtd_in[1:])
            return resumo[resumo["TOTAL_ERBS"] > limite]
        else:
            limite = int(qtd_in)
            return resumo[resumo["TOTAL_ERBS"] == limite]
    except ValueError:
        logger.warning("Valor inválido para filtro de quantidade: %s", qtd_in)
        return resumo


# ---------------------------------------------------------------------------
# Geração de nome de arquivo CSV
# ---------------------------------------------------------------------------

def _gerar_nome_arquivo_csv() -> str:
    """Gera nome de arquivo CSV para exportação.

    Returns:
        Nome do arquivo (ex: "pesquisa_avancada_20251004_143000.csv").
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"pesquisa_avancada_{timestamp}.csv"


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def pesquisa_avancada(df_erbs: pd.DataFrame) -> None:
    """Ponto de entrada do módulo de pesquisa avançada.

    Args:
        df_erbs: DataFrame completo de ERBs.
    """
    # 1) Formulário
    res = formulario_tui(
        modulo=_MODULO,
        titulo_janela="7. PESQUISA AVANÇADA PARAMETRIZADA (COM DROPLISTS)",
        campos=[
            {
                "nome": "uf",
                "rotulo": "1. Estado/UF",
                "tipo": "droplist",
                "largura": 34,
                "padrao": "",
                "opcoes": obter_opcoes_uf(True, "TODOS OS ESTADOS (BRASIL)"),
            },
            {
                "nome": "municipio",
                "rotulo": "2. Município(s)",
                "tipo": "combobox",
                "largura": 34,
                "opcoes": lambda vals: _sugerir_cidades(df_erbs, vals),
                "dica": "Vazio = Todo o Estado | [F2] Abre lista de cidades",
            },
            {
                "nome": "operadora",
                "rotulo": "3. Filtro de Operadora",
                "tipo": "droplist",
                "largura": 34,
                "padrao": "",
                "opcoes": _OPCOES_OPERADORAS,
            },
            {
                "nome": "tecnologia",
                "rotulo": "4. Tecnologia Exigida",
                "tipo": "droplist",
                "largura": 34,
                "padrao": "",
                "opcoes": _OPCOES_TEC,
            },
            {
                "nome": "qtd_erbs",
                "rotulo": "5. Nº ERBs na Cidade",
                "tipo": "droplist",
                "largura": 34,
                "padrao": "",
                "opcoes": _OPCOES_QTD,
            },
            {
                "nome": "unica_op",
                "rotulo": "6. Operadora Única",
                "tipo": "droplist",
                "largura": 34,
                "padrao": _OPCAO_NAO,
                "opcoes": _OPCOES_UNICA_OP,
            },
        ],
        instrucoes_topo=[
            "Use ←/→ ou ESPAÇO/F2 para selecionar nas Droplists e "
            "↑/↓ para mudar de campo:"
        ],
    )

    if res is None:
        return

    # 2) Aplica filtros
    df_f, pesquisa_por_municipio = _aplicar_filtros(df_erbs, res)

    if df_f.empty:
        return

    # 3) Se pesquisa por município, abre painel direto
    if pesquisa_por_municipio:
        for (uf, mun), grp in df_f.groupby(["UF", "MUNICIPIO"]):
            nome_l = re.sub(r"\s*-\s*[A-Za-z]{2}$", "", mun).upper()
            painel_interativo_municipio(
                grp, nome_l, uf, filtro_extra_info="Pesquisa Avançada"
            )
        return

    # 4) Monta relatório
    resumo = _montar_relatorio(df_f, res)

    if resumo.empty:
        return

    # 5) Monta itens para o navegador
    cab, itens = dataframe_para_itens_tui(resumo, selecionavel=True)

    for i, it in enumerate(itens):
        if i < len(resumo):
            it["dados"] = (resumo.iloc[i]["UF"], resumo.iloc[i]["MUNICIPIO"])

    # 6) Loop do navegador
    while True:
        acao, dados, _, _ = navegador_tui(
            modulo="RELATÓRIO AVANÇADO",
            titulo_janela=(
                f"RESULTADO: {len(resumo)} MUNICÍPIO(S) "
                f"([ENTER] ABRE O MUNICÍPIO SELECIONADO)"
            ),
            itens_conteudo=itens,
            colunas_fixas_tabela=("   " + cab) if cab else None,
            comandos_rodape=[
                "[ENTER] Abrir Painel do Município   |   [6] Exportar CSV   |   "
                "[ESC/0] Voltar"
            ],
            teclas_rapidas={"6"},
        )

        if acao == "SELECT" and dados:
            uf_c, mun_c = dados
            grp = df_erbs[
                (df_erbs["UF"] == uf_c) & (df_erbs["MUNICIPIO"] == mun_c)
            ]
            nome_l = re.sub(r"\s*-\s*[A-Za-z]{2}$", "", mun_c).upper()
            painel_interativo_municipio(grp, nome_l, uf_c)

        elif acao == "KEY" and dados == "6":
            nome_arq = _gerar_nome_arquivo_csv()
            salvar_csv_tui(resumo, nome_arq, "EXPORTAR PESQUISA AVANÇADA")

        else:
            break