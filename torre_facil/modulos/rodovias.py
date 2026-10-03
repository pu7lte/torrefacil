"""Consulta de ERBs em BRs e rodovias estaduais.

Módulo que localiza ERBs cujo endereço de licenciamento cita uma rodovia
(BR-xxx, RS-xxx, RN-xxx, etc.) e permite navegar por município.

Recursos:
    - Combobox com BRs mapeadas
    - Seleção de UF quando rodovia passa por múltiplos estados
    - Diagnóstico de melhor cobertura
    - Exportação CSV da lista de ERBs
"""
from __future__ import annotations

import datetime
import logging
import re
from typing import Any

import pandas as pd

from ..dicionarios import DICIONARIOS
from ..painel import (
    filtrar_erbs_rodovia,
    salvar_csv_tui,
    diagnosticar_melhor_cobertura,
    painel_interativo_municipio,
)
from ..texto import normalizar_texto
from ..tui.cores import CAIXA_TEXTO, CAIXA_TITULO
from ..tui.janelas import (
    criar_item_tui,
    formulario_tui,
    alerta_tui,
    menu_popup_centralizado,
)
from ..tui.motor import obter_dimensoes_terminal
from ..tui.navegador import navegador_tui

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Título do módulo
_MODULO = "CONSULTA DE RODOVIAS"

# Opção especial para todas as UFs
_OPCAO_TODOS = "TODOS"

# Colunas para exportação CSV
_COLUNAS_CSV: tuple[str, ...] = (
    "UF", "MUNICIPIO", "OPERADORA", "NUM_ESTACAO",
    "TECNOLOGIA", "ENDERECO", "BAIRRO", "GPS",
)


# ---------------------------------------------------------------------------
# Helpers para formulário
# ---------------------------------------------------------------------------

def _obter_opcoes_brs() -> list[tuple[str, str]]:
    """Gera lista de opções de BRs mapeadas.

    Returns:
        Lista de tuplas (valor, rótulo) para o combobox.
    """
    mapa_ufs_br = DICIONARIOS.get("mapa_ufs_br", {})
    return [
        (f"BR-{num}", f"BR-{num} (Estados: {', '.join(ufs)})")
        for num, ufs in sorted(mapa_ufs_br.items())
    ]


# ---------------------------------------------------------------------------
# Helpers para seleção de UF
# ---------------------------------------------------------------------------

def _selecionar_uf_rodovia(
    df_rod: pd.DataFrame, rodovia: str
) -> pd.DataFrame | None:
    """Permite ao usuário escolher UF quando rodovia passa por múltiplos estados.

    Args:
        df_rod: DataFrame com ERBs da rodovia.
        rodovia: Nome da rodovia.

    Returns:
        DataFrame filtrado pela UF escolhida, ou None se cancelado.
    """
    contagem_ufs = df_rod.groupby("UF")["ID_ERB"].nunique().to_dict()
    ufs_disp = sorted(contagem_ufs.keys())

    if len(ufs_disp) <= 1:
        return df_rod

    itens_uf: list[dict[str, Any]] = [
        criar_item_tui(
            f"[TODOS OS ESTADOS] Toda a extensão da {rodovia} "
            f"({df_rod['ID_ERB'].nunique()} ERBs)",
            CAIXA_TITULO,
            selecionavel=True,
            dados=_OPCAO_TODOS,
        )
    ]

    for u in ufs_disp:
        itens_uf.append(criar_item_tui(
            f"Estado {u} ({contagem_ufs[u]} ERBs registradas na rodovia)",
            CAIXA_TEXTO,
            selecionavel=True,
            dados=u,
        ))

    acao, uf_escolha, _ = menu_popup_centralizado(
        modulo=f"RODOVIA {rodovia}",
        titulo_caixa=f"{rodovia} PASSA POR {len(ufs_disp)} ESTADOS",
        itens_menu=itens_uf,
        largura_caixa=58,
    )

    if acao != "SELECT" or not uf_escolha:
        return None

    if uf_escolha != _OPCAO_TODOS:
        return df_rod[df_rod["UF"] == uf_escolha]

    return df_rod


# ---------------------------------------------------------------------------
# Helpers para montagem de itens
# ---------------------------------------------------------------------------

def _montar_itens_rodovia(
    df_rod: pd.DataFrame, larg_end: int
) -> list[dict[str, Any]]:
    """Monta lista de itens para o navegador de rodovia.

    Args:
        df_rod: DataFrame com ERBs da rodovia.
        larg_end: Largura da coluna de endereço.

    Returns:
        Lista de itens para ``navegador_tui``.
    """
    itens: list[dict[str, Any]] = []

    # Agrupa por município
    grupos = list(df_rod.groupby(["UF", "MUNICIPIO_LIMPO"]))

    for idx_m, ((uf, mun_limpo), grp) in enumerate(grupos):
        if idx_m > 0:
            itens.append(criar_item_tui("", divisor=True))

        qtd = grp["ID_ERB"].nunique()
        itens.append(criar_item_tui(
            f"====== [ MUNICÍPIO: {mun_limpo} ({uf}) — {qtd} ERB(s) na via ] ======",
            CAIXA_TITULO,
            "centro",
            selecionavel=True,
            dados=(uf, grp["MUNICIPIO"].iloc[0], mun_limpo),
        ))

        # Iteração vetorizada (mais rápida que iterrows)
        operadoras = grp["OPERADORA"].tolist()
        tecnologias = grp["TECNOLOGIA"].tolist()
        enderecos = grp["ENDERECO"].tolist()
        gps_list = grp["GPS"].tolist()
        municipios = grp["MUNICIPIO"].tolist()

        for i in range(len(grp)):
            trecho = enderecos[i][:larg_end - 1]
            ln = (
                f"{operadoras[i]:<10} {tecnologias[i]:<10} "
                f"{trecho:<{larg_end}} {gps_list[i]}"
            )
            itens.append(criar_item_tui(
                ln, CAIXA_TEXTO, "esq",
                selecionavel=True,
                dados=(uf, municipios[i], mun_limpo),
            ))

    return itens


def _gerar_nome_arquivo_csv(rodovia: str) -> str:
    """Gera nome de arquivo CSV para exportação.

    Args:
        rodovia: Nome da rodovia.

    Returns:
        Nome do arquivo (ex: "erbs_rodovia_br101_20251004_143000.csv").
    """
    nome_limpo = re.sub(
        r"[^A-Z0-9]", "", normalizar_texto(rodovia)
    ).lower()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"erbs_rodovia_{nome_limpo}_{timestamp}.csv"


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def consultar_estradas(df_erbs: pd.DataFrame) -> None:
    """Ponto de entrada do módulo de consulta de rodovias.

    Args:
        df_erbs: DataFrame completo de ERBs.
    """
    # 1) Formulário
    brs_mapeadas = _obter_opcoes_brs()

    res = formulario_tui(
        modulo=_MODULO,
        titulo_janela="6. MAPEAMENTO DE ERbs EM BRs E RODOVIAS ESTADUAIS",
        campos=[
            {
                "nome": "rodovia",
                "rotulo": "BR ou Rodovia Estadual",
                "tipo": "combobox",
                "largura": 28,
                "opcoes": brs_mapeadas,
                "dica": (
                    "Digite (ex: BR-101, RS-122, RN-093) OU tecle [F2] "
                    "p/ abrir a Droplist de BRs"
                ),
            }
        ],
        instrucoes_topo=[
            "• Localiza ERBs cujo endereço de licenciamento cita a rodovia.",
            "• Pressione [F2] no campo para abrir a Droplist de BRs.",
        ],
    )

    if not res or not res["rodovia"]:
        return

    rodovia = res["rodovia"]

    # 2) Filtra ERBs da rodovia
    df_rod = filtrar_erbs_rodovia(df_erbs, rodovia)

    if df_rod.empty:
        alerta_tui(
            "RESULTADO RODOVIA",
            f"NENHUMA ERB CADASTRADA NA '{rodovia}'",
            [
                f"Não foram encontradas estações licenciadas na '{rodovia}'.",
                "A via pode ter áreas de sombra ou ser atendida só por "
                "torres urbanas próximas.",
            ],
        )
        return

    # 3) Seleciona UF se rodovia passa por múltiplos estados
    try:
        df_rod = _selecionar_uf_rodovia(df_rod, rodovia)
    except Exception:
        logger.exception("Erro ao selecionar UF da rodovia")
        return

    if df_rod is None or df_rod.empty:
        return

    # 4) Estatísticas
    total_erbs = df_rod["ID_ERB"].nunique()
    total_cidades = df_rod[["UF", "MUNICIPIO_NORM"]].drop_duplicates().shape[0]

    df_rod.sort_values(
        by=["UF", "MUNICIPIO_LIMPO", "OPERADORA"],
        inplace=True,
    )

    # 5) Diagnóstico de melhor cobertura
    _, linhas_diag = diagnosticar_melhor_cobertura(df_rod)

    # 6) Monta itens
    larg, _ = obter_dimensoes_terminal()
    larg_end = max(20, larg - 54)

    cab = (
        f"   {'OPERADORA':<10} {'TECNOLOGIA':<10} "
        f"{'TRECHO / ENDEREÇO CADASTRADO (KM)':<{larg_end}} "
        f"{'COORDENADAS GPS'}"
    )

    itens = _montar_itens_rodovia(df_rod, larg_end)

    # 7) Loop do navegador
    while True:
        acao, dados, _, _ = navegador_tui(
            modulo=f"RODOVIA {rodovia}",
            titulo_janela=(
                f"RODOVIA {rodovia}: {total_erbs} ERBs EM "
                f"{total_cidades} MUNICÍPIOS ([ENTER] ABRE O MUNICÍPIO)"
            ),
            itens_conteudo=itens,
            subcabecalho_fixo=linhas_diag,
            colunas_fixas_tabela=cab,
            comandos_rodape=[
                "[ENTER] Abrir Painel do Município   |   [6] Exportar CSV   |   "
                "[ESC/0] Voltar"
            ],
            teclas_rapidas={"6"},
        )

        if acao == "SELECT" and dados:
            uf_c, mun_c, nome_l = dados
            grp = df_erbs[
                (df_erbs["UF"] == uf_c) & (df_erbs["MUNICIPIO"] == mun_c)
            ]
            painel_interativo_municipio(grp, nome_l, uf_c)

        elif acao == "KEY" and dados == "6":
            nome_arq = _gerar_nome_arquivo_csv(rodovia)
            salvar_csv_tui(
                df_rod[list(_COLUNAS_CSV)],
                nome_arq,
                f"EXPORTAR RODOVIA {rodovia}",
            )

        else:
            break