"""Análise de distribuição por faixa de frequência e tipo de infraestrutura.

Requer as colunas: FAIXA_NOMINAL, FREQ_MHZ, INFRA, TEC5G_TIPO, CARATER.

Fluxo de 3 níveis:
    1. Resumo geral (contagem + barra ASCII) por faixa
    2. Lista de municípios que possuem a faixa
    3. Painel interativo do município filtrado pela faixa
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ..dicionarios import DICIONARIOS, carregar_globais, obter_opcoes_uf
from ..painel import painel_interativo_municipio, salvar_csv_tui
from ..texto import normalizar_texto
from ..tui.cores import CAIXA_TEXTO, CAIXA_TITULO
from ..tui.janelas import criar_item_tui, formulario_tui, alerta_tui
from ..tui.navegador import navegador_tui

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Ordem de exibição das faixas
_ORDEM_FAIXAS: tuple[str, ...] = (
    "450", "700", "850", "900", "1700", "1800", "1900",
    "2100", "2300", "2600", "3500", "3700", "26000", "outra",
)

# Rótulos especiais para faixas
_ROTULOS_ESPECIAIS: dict[str, str] = {
    "3500": "3500 MHz (5G principal)",
    "26000": "26000 MHz (5G mmWave)",
    "outra": "Outras / não classificada",
}

# Título do módulo
_MODULO = "ANÁLISE POR FAIXA"

# Largura padrão da barra ASCII
_LARGURA_BARRA = 20


# ---------------------------------------------------------------------------
# Helpers de formatação
# ---------------------------------------------------------------------------

def _barras_ascii(valor: int, maximo: int, largura: int = _LARGURA_BARRA) -> str:
    """Gera barra ASCII proporcional ao valor.

    Args:
        valor: Valor atual.
        maximo: Valor máximo para escala.
        largura: Largura da barra em caracteres.

    Returns:
        String com barra ASCII (ex: "████████░░░░").

    Examples:
        >>> _barras_ascii(50, 100, largura=10)
        '█████░░░░░'
    """
    if maximo <= 0:
        return "░" * largura
    cheio = int(round((valor / maximo) * largura))
    cheio = max(0, min(largura, cheio))
    return "█" * cheio + "░" * (largura - cheio)


def _ordenar_faixas(presentes: list[str]) -> list[str]:
    """Ordena faixas conforme _ORDEM_FAIXAS.

    Args:
        presentes: Lista de faixas presentes.

    Returns:
        Lista ordenada.
    """
    ordem = {f: i for i, f in enumerate(_ORDEM_FAIXAS)}
    return sorted(presentes, key=lambda f: (ordem.get(f, 999), f))


def _rotulo_faixa(faixa: str) -> str:
    """Retorna rótulo legível para a faixa.

    Args:
        faixa: Código da faixa (ex: "3500", "outra").

    Returns:
        Rótulo formatado.

    Examples:
        >>> _rotulo_faixa("3500")
        '3500 MHz (5G principal)'
        >>> _rotulo_faixa("700")
        '700 MHz'
    """
    return _ROTULOS_ESPECIAIS.get(faixa, f"{faixa} MHz")


# ---------------------------------------------------------------------------
# Nível 1: Seleção de UF
# ---------------------------------------------------------------------------

def _selecionar_uf(df: pd.DataFrame) -> str | None:
    """Formulário para escolher a UF.

    Args:
        df: DataFrame completo de ERBs.

    Returns:
        UF selecionada (vazio = Brasil inteiro), ou None se cancelado.
    """
    # Opções fixas: Brasil inteiro (consolidado) + os 27 estados.
    # ✅ CORREÇÃO: garante que os dicionários estão carregados ANTES de montar
    # a lista — antes, se DICIONARIOS estivesse vazio no momento da chamada,
    # a lista ficava apenas com "BRASIL INTEIRO" e nenhum estado aparecia.
    if not DICIONARIOS.get("ufs_brasil"):
        carregar_globais()

    def opcoes_uf(_valores=None):
        return obter_opcoes_uf(True, "BRASIL INTEIRO (CONSOLIDADO)")

    res = formulario_tui(
        modulo=_MODULO,
        titulo_janela="ANÁLISE POR FAIXA DE FREQUÊNCIA",
        campos=[{
            "nome": "uf",
            "rotulo": "Estado / UF",
            "tipo": "droplist",
            "largura": 30,
            "padrao": "",
            "opcoes": opcoes_uf,
            "dica": (
                "Digite a sigla (ex.: SP), deixe em branco para Brasil ou "
                "pressione F2 e escolha na lista (Brasil + 27 UFs)."
            ),
        }],
        instrucoes_topo=[
            "Selecione a UF para o resumo por faixa (ou Brasil inteiro):",
        ],
    )

    if res is None:
        return None

    uf = res.get("uf", "").strip().upper()

    # Proteção contra rótulos selecionados por digitação direta (ex.: o
    # usuário teclou "SP" com a droplist fechada). Normaliza para a sigla.
    if uf and uf not in {u for u, _ in opcoes_uf()}:
        for val, rot in opcoes_uf():
            if rot.upper() == uf or normalizar_texto(rot) == normalizar_texto(uf):
                uf = val
                break

    return uf


# ---------------------------------------------------------------------------
# Nível 2: Resumo por faixa
# ---------------------------------------------------------------------------

def _resumo_por_faixa(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula resumo agregado por faixa.

    Args:
        df: DataFrame com coluna FAIXA_NOMINAL.

    Returns:
        DataFrame com colunas: FAIXA_NOMINAL, ERBS, MUNICIPIOS, UFS, OPERADORAS.
    """
    if "FAIXA_NOMINAL" not in df.columns or df.empty:
        return pd.DataFrame()

    agrupado = (
        df.groupby("FAIXA_NOMINAL")
        .agg(
            ERBS=("ID_ERB", "nunique"),
            MUNICIPIOS=("MUNICIPIO_NORM", "nunique"),
            UFS=("UF", "nunique"),
            OPERADORAS=("OPERADORA", "nunique"),
        )
        .reset_index()
    )

    ordem = {f: i for i, f in enumerate(_ORDEM_FAIXAS)}
    agrupado["ORDEM"] = agrupado["FAIXA_NOMINAL"].map(lambda x: ordem.get(x, 999))
    agrupado = agrupado.sort_values("ORDEM").drop(columns=["ORDEM"]).reset_index(drop=True)

    return agrupado


def _montar_itens_resumo(resumo: pd.DataFrame) -> list[dict[str, Any]]:
    """Monta lista de itens para o navegador de resumo.

    Args:
        resumo: DataFrame com resumo por faixa.

    Returns:
        Lista de itens para ``navegador_tui``.
    """
    itens: list[dict[str, Any]] = []
    total = int(resumo["ERBS"].sum())
    max_val = int(resumo["ERBS"].max())

    # Iteração vetorizada (mais rápida que iterrows)
    faixas = resumo["FAIXA_NOMINAL"].tolist()
    erbs_list = resumo["ERBS"].tolist()
    muns_list = resumo["MUNICIPIOS"].tolist()
    ufs_list = resumo["UFS"].tolist()
    ops_list = resumo["OPERADORAS"].tolist()

    for idx in range(len(resumo)):
        faixa = faixas[idx]
        erbs = int(erbs_list[idx])
        muns = int(muns_list[idx])
        ufs = int(ufs_list[idx])
        ops = int(ops_list[idx])
        pct = (erbs / total * 100) if total > 0 else 0

        barra = _barras_ascii(erbs, max_val)
        rot = _rotulo_faixa(faixa)

        linha = (
            f"{rot:<28} {barra}  {erbs:>7,} ERBs ({pct:5.1f}%)  │  "
            f"{muns:>5} mun  │  {ufs:>2} UFs  │  {ops} op"
        ).replace(",", ".")

        itens.append(criar_item_tui(
            linha, CAIXA_TEXTO, "esq",
            selecionavel=(faixa != "outra" and erbs > 0),
            dados=faixa,
        ))

    return itens


def _mostrar_resumo_faixas(df: pd.DataFrame, escopo_label: str) -> str | None:
    """Nível 2: mostra resumo por faixa e permite selecionar uma.

    Args:
        df: DataFrame filtrado pelo escopo (UF ou Brasil).
        escopo_label: Rótulo do escopo (ex: "UF SP", "BRASIL").

    Returns:
        Faixa selecionada, ou None se cancelado.
    """
    resumo = _resumo_por_faixa(df)

    if resumo.empty:
        alerta_tui(
            _MODULO,
            "SEM DADOS DE FAIXA",
            [
                "A coluna FAIXA_NOMINAL está vazia ou não existe.",
                "Verifique se a base foi recompilada com VERSAO_CACHE=5.",
            ],
        )
        return None

    total = int(resumo["ERBS"].sum())
    itens = _montar_itens_resumo(resumo)

    cab = (
        f"   {'FAIXA':<28} {'DISTRIBUIÇÃO':<{_LARGURA_BARRA}}  "
        f"{'ERBs':>7}         {'MUNICÍPIOS':>5}    {'UFs':>2}    OPERADORAS"
    )

    while True:
        acao, dados, _, _ = navegador_tui(
            modulo=_MODULO,
            titulo_janela=(
                f"DISTRIBUIÇÃO POR FAIXA — {escopo_label}   "
                f"(Total: {total:,} ERBs)".replace(",", ".")
            ),
            itens_conteudo=itens,
            subcabecalho_fixo=[
                f"Escopo: {escopo_label}   │   Total: {total:,} ERBs   │   "
                f"Faixas distintas: {len(resumo)}".replace(",", "."),
            ],
            colunas_fixas_tabela=cab,
            comandos_rodape=[
                "[ENTER] Abrir faixa (lista municípios)   |   "
                "[6] Exportar resumo p/ CSV   |   [ESC/0] Voltar",
            ],
            teclas_rapidas={"6"},
            dica_teclas=(
                "↑/↓=Mover | PgUp/PgDn=Página | ENTER=Abrir faixa | "
                "6=CSV | ESC/0=Voltar"
            ),
        )

        if acao == "SELECT" and dados:
            return dados

        if acao == "KEY" and dados == "6":
            nome_arq = (
                f"faixas_{normalizar_texto(escopo_label).lower().replace(' ', '_')}.csv"
            )
            salvar_csv_tui(resumo, nome_arq, "EXPORTAR RESUMO POR FAIXA")
        else:
            return None


# ---------------------------------------------------------------------------
# Nível 3: Lista de municípios de uma faixa
# ---------------------------------------------------------------------------

def _montar_itens_municipios(
    resumo: pd.DataFrame,
) -> list[dict[str, Any]]:
    """Monta lista de itens para o navegador de municípios.

    Args:
        resumo: DataFrame com resumo por município.

    Returns:
        Lista de itens para ``navegador_tui``.
    """
    itens: list[dict[str, Any]] = []

    # Iteração vetorizada (mais rápida que iterrows)
    ufs = resumo["UF"].tolist()
    municipios_limpos = resumo["MUNICIPIO_LIMPO"].tolist()
    erbs_list = resumo["ERBS"].tolist()
    bairros_list = resumo["BAIRROS"].tolist()
    ops_list = resumo["OPERADORAS"].tolist()
    ops_lista = resumo["OPS_LISTA"].tolist()
    municipios = resumo["MUNICIPIO"].tolist()

    for idx in range(len(resumo)):
        linha = (
            f"{ufs[idx]:<4} {municipios_limpos[idx][:27]:<28} "
            f"{int(erbs_list[idx]):>6} {int(bairros_list[idx]):>8} "
            f"{int(ops_list[idx]):>4}  {ops_lista[idx]}"
        )
        itens.append(criar_item_tui(
            linha, CAIXA_TEXTO, "esq",
            selecionavel=True,
            dados={
                "UF": ufs[idx],
                "MUNICIPIO": municipios[idx],
                "MUNICIPIO_LIMPO": municipios_limpos[idx],
            },
        ))

    return itens


def _municipios_da_faixa(
    df_escopo: pd.DataFrame,
    faixa: str,
    escopo_label: str,
) -> None:
    """Nível 3: lista municípios que têm a faixa.

    Ao dar Enter, abre o painel do município já recortado para a faixa.

    Args:
        df_escopo: DataFrame filtrado pelo escopo.
        faixa: Código da faixa (ex: "3500").
        escopo_label: Rótulo do escopo.
    """
    df_faixa = df_escopo[df_escopo["FAIXA_NOMINAL"] == faixa].copy()

    if df_faixa.empty:
        alerta_tui(
            _MODULO,
            "FAIXA VAZIA",
            [f"Nenhuma ERB na faixa {faixa} MHz neste escopo."],
        )
        return

    resumo = (
        df_faixa
        .groupby(["UF", "MUNICIPIO", "MUNICIPIO_LIMPO"], as_index=False)
        .agg(
            ERBS=("ID_ERB", "nunique"),
            BAIRROS=("BAIRRO", "nunique"),
            OPERADORAS=("OPERADORA", "nunique"),
            OPS_LISTA=(
                "OPERADORA",
                lambda s: ", ".join(sorted(set(s))[:5])
                + ("..." if len(set(s)) > 5 else ""),
            ),
        )
        .sort_values(by=["ERBS", "MUNICIPIO_LIMPO"], ascending=[False, True])
        .reset_index(drop=True)
    )

    cab = (
        f"   {'UF':<4} {'MUNICÍPIO':<28} {'ERBs':>6} {'BAIRROS':>8} "
        f"{'OPS':>4}  OPERADORAS"
    )

    itens = _montar_itens_municipios(resumo)

    total_erbs = int(resumo["ERBS"].sum())
    total_muns = len(resumo)

    while True:
        acao, dados, _, _ = navegador_tui(
            modulo=_MODULO,
            titulo_janela=(
                f"FAIXA {faixa} MHz — {escopo_label}   "
                f"({total_erbs:,} ERBs em {total_muns:,} municípios)".replace(",", ".")
            ),
            itens_conteudo=itens,
            colunas_fixas_tabela=cab,
            comandos_rodape=[
                "[ENTER] Abrir painel do município (filtrado pela faixa)   |   "
                "[6] Exportar CSV   |   [ESC/0] Voltar",
            ],
            teclas_rapidas={"6"},
            dica_teclas=(
                "↑/↓=Mover | PgUp/PgDn=Página | ENTER=Abrir município | "
                "6=CSV | ESC/0=Voltar"
            ),
        )

        if acao == "SELECT" and isinstance(dados, dict):
            uf_c = dados.get("UF")
            mun_c = dados.get("MUNICIPIO")
            nome_l = dados.get("MUNICIPIO_LIMPO", "")

            # Filtra o recorte do município E da faixa
            grp = df_faixa[
                (df_faixa["UF"] == uf_c) & (df_faixa["MUNICIPIO"] == mun_c)
            ]

            if grp.empty:
                alerta_tui(
                    "PAINEL DO MUNICÍPIO",
                    "SEM DADOS NA FAIXA",
                    [
                        f"O município {nome_l}/{uf_c} não possui ERBs na faixa "
                        f"{faixa} MHz neste escopo."
                    ],
                )
                continue

            painel_interativo_municipio(
                grp, nome_l, uf_c,
                filtro_extra_info=f"Faixa {faixa} MHz",
            )

        elif acao == "KEY" and dados == "6":
            nome_arq = (
                f"faixa_{faixa}_"
                f"{normalizar_texto(escopo_label).lower().replace(' ', '_')}.csv"
            )
            salvar_csv_tui(resumo, nome_arq, f"EXPORTAR FAIXA {faixa}")

        else:
            return


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def analise_por_faixa(df_erbs: pd.DataFrame) -> None:
    """Ponto de entrada do módulo.

    Args:
        df_erbs: DataFrame completo de ERBs.
    """
    if "FAIXA_NOMINAL" not in df_erbs.columns:
        alerta_tui(
            _MODULO,
            "COLUNA AUSENTE",
            [
                "A base atual não possui a coluna FAIXA_NOMINAL.",
                "Isso acontece quando o cache foi compilado com uma versão antiga.",
                "Solução: apague torre_facil_cache.pkl e reabra o app.",
                "Ou vá em 0 (Manutenção) → 1 (Baixar nova versão da Anatel).",
            ],
        )
        return

    uf = _selecionar_uf(df_erbs)

    if uf is None:
        return

    if uf:
        df_escopo = df_erbs[df_erbs["UF"] == uf].copy()
        escopo_label = f"UF {uf}"
    else:
        df_escopo = df_erbs
        escopo_label = "BRASIL"

    if df_escopo.empty:
        alerta_tui(
            _MODULO,
            "SEM DADOS",
            [f"Nenhuma ERB no escopo {escopo_label}."],
        )
        return

    while True:
        faixa = _mostrar_resumo_faixas(df_escopo, escopo_label)
        if not faixa:
            return
        _municipios_da_faixa(df_escopo, faixa, escopo_label)