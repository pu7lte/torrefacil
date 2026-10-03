"""Consultor / Indicador de chip (SIM card).

Módulo que recomenda a melhor operadora com base no perfil de uso:
    - Perfil 1: Máxima velocidade / 5G / Streaming
    - Perfil 2: Uso geral / Equilíbrio no dia a dia
    - Perfil 3: Interior / Alcance / Zona Rural / Voz

Easter egg F12: aceita abrir o menu do outro modo por cima desta tela,
mantendo o estado atual da análise.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ..dicionarios import obter_opcoes_uf
from ..estado import AbrirMenuOutroModo
from ..painel import (
    filtrar_municipios_exatos,
    selecionar_bairro_interativo,
    calcular_metricas_operadoras,
    diagnosticar_melhor_cobertura,
    abrir_inspecao_detalhada_erbs,
)
from ..tui.cores import CAIXA_TEXTO
from ..tui.janelas import (
    criar_item_tui,
    formulario_tui,
    caixa_notificacao_tui,
)
from ..tui.navegador import (
    navegador_tui,
    mostrar_podio_completo_tui,
    obter_estilo_posicao,
    gerar_barra_sinal,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Perfis de uso
_PERFIL_VELOCIDADE = "1"
_PERFIL_GERAL = "2"
_PERFIL_MOBILIDADE = "3"

_NOMES_PERFIL: dict[str, str] = {
    _PERFIL_VELOCIDADE: "MÁXIMA VELOCIDADE / 5G",
    _PERFIL_GERAL: "USO GERAL / EQUILÍBRIO NO DIA A DIA",
    _PERFIL_MOBILIDADE: "MOBILIDADE / ALCANCE / ZONA RURAL E VOZ",
}

# Opções de perfil para o formulário
_OPCOES_PERFIL: list[tuple[str, str]] = [
    (_PERFIL_VELOCIDADE, "1. Máxima Velocidade / 5G / Streaming"),
    (_PERFIL_GERAL, "2. Uso Geral / Equilíbrio no Dia a Dia"),
    (_PERFIL_MOBILIDADE, "3. Interior / Alcance / Zona Rural / Voz"),
]

# Título do módulo
_MODULO = "CONSULTOR DE CHIP"


# ---------------------------------------------------------------------------
# Tratamento de F12
# ---------------------------------------------------------------------------

def _tratar_f12(df_erbs: pd.DataFrame) -> None:
    """Trata o Easter egg F12 (abrir menu do outro modo).

    Args:
        df_erbs: DataFrame completo de ERBs.
    """
    from ..main import _abrir_menu_do_outro_modo
    _abrir_menu_do_outro_modo(df_erbs, "cache", modo_atual="analista")


# ---------------------------------------------------------------------------
# Helpers para formulário
# ---------------------------------------------------------------------------

def _sugerir_cidades(df_erbs: pd.DataFrame, uf: str) -> list[tuple[str, str]]:
    """Gera lista de cidades sugeridas para o combobox.

    Args:
        df_erbs: DataFrame completo de ERBs.
        uf: UF selecionada (vazio = todas).

    Returns:
        Lista de tuplas (cidade, cidade) para o combobox.
    """
    sub = df_erbs[df_erbs["UF"] == uf] if uf else df_erbs
    return [(c, c) for c in sorted(sub["MUNICIPIO_LIMPO"].unique())]


# ---------------------------------------------------------------------------
# Helpers para montagem de itens
# ---------------------------------------------------------------------------

def _calcular_pontos_operadora(row: dict[str, Any], max_5g: int, max_4g: int) -> list[str]:
    """Calcula lista de pontos destacados da operadora.

    Args:
        row: Dicionário com dados da operadora.
        max_5g: Máximo de ERBs 5G entre todas as operadoras.
        max_4g: Máximo de ERBs 4G entre todas as operadoras.

    Returns:
        Lista de strings com pontos destacados.
    """
    pontos: list[str] = []

    # 5G
    if row["5G"] > 0 and row["5G"] == max_5g:
        pontos.append(f"Líder 5G ({row['5G']} ERBs)")
    elif row["5G"] > 0:
        pontos.append(f"{row['5G']} ERB(s) 5G")
    else:
        pontos.append("Sem 5G")

    # 4G
    if row["4G"] > 0 and row["4G"] == max_4g:
        pontos.append(f"Líder 4G ({row['4G']} ERBs)")
    elif row["4G"] > 0:
        pontos.append(f"{row['4G']} ERB(s) 4G")

    # 3G
    if row["3G"] > 0:
        pontos.append(f"{row['3G']} c/ 3G")

    # Bairros
    pontos.append(f"{row['BAIRROS']} local(is)")

    return pontos


def _montar_itens_podio(df_s: pd.DataFrame) -> list[dict[str, Any]]:
    """Monta lista de itens para o navegador de pódio.

    Args:
        df_s: DataFrame com métricas por operadora (ordenado por SCORE).

    Returns:
        Lista de itens para ``navegador_tui``.
    """
    itens: list[dict[str, Any]] = []

    # Calcula máximos para destacar líderes
    max_5g = df_s["5G"].max() if not df_s.empty else 0
    max_4g = df_s["4G"].max() if not df_s.empty else 0

    # Iteração vetorizada (mais rápida que iterrows)
    operadoras = df_s["OPERADORA"].tolist()
    scores = df_s["SCORE"].tolist()
    notas = df_s["NOTA"].tolist()
    totals = df_s["TOTAL"].tolist()
    erbs_5g = df_s["5G"].tolist()
    erbs_4g = df_s["4G"].tolist()
    erbs_3g = df_s["3G"].tolist()
    bairros = df_s["BAIRROS"].tolist()
    shares = df_s["SHARE"].tolist()

    pos_atual = 1
    score_ant = None

    for idx in range(len(df_s)):
        if idx > 0:
            itens.append(criar_item_tui("", divisor=True))

        # Atualiza posição se score mudou
        if score_ant is not None and scores[idx] < score_ant:
            pos_atual = idx + 1
        score_ant = scores[idx]

        cor, _, rot_pos = obter_estilo_posicao(pos_atual)
        barra_sinal = gerar_barra_sinal(notas[idx])

        row = {
            "5G": erbs_5g[idx],
            "4G": erbs_4g[idx],
            "3G": erbs_3g[idx],
            "BAIRROS": bairros[idx],
        }

        pontos = _calcular_pontos_operadora(row, max_5g, max_4g)
        resumo_op = " | ".join(pontos)

        # Linha principal
        itens.append(criar_item_tui(
            f"{rot_pos} -> {operadoras[idx]:<10} {barra_sinal} "
            f"[Share: {shares[idx]:5.1f}%]",
            cor, "esq",
            selecionavel=True,
            dados=operadoras[idx],
        ))

        # Linha de detalhe
        itens.append(criar_item_tui(
            f"   └─ Detalhe: {totals[idx]} ERB(s) no total  [{resumo_op}]",
            cor, "esq",
        ))

    return itens


# ---------------------------------------------------------------------------
# Helpers para escopo de análise
# ---------------------------------------------------------------------------

def _definir_escopo_bairro(
    df_f: pd.DataFrame, nome_cid: str, uf_cid: str
) -> tuple[pd.DataFrame, str]:
    """Permite ao usuário escolher entre município inteiro ou bairro específico.

    Args:
        df_f: DataFrame filtrado pelo município.
        nome_cid: Nome do município.
        uf_cid: UF do município.

    Returns:
        Tupla (DataFrame final, título do recorte).

    Raises:
        AbrirMenuOutroModo: Se usuário pressionar F12.
    """
    try:
        esc = caixa_notificacao_tui(
            modulo="ESCOPO DE ANÁLISE",
            titulo=f"DEFINIÇÃO DE ÁREA EM {nome_cid} ({uf_cid})",
            linhas_mensagem=[
                f"Foram localizadas {df_f['ID_ERB'].nunique()} ERBs "
                f"distribuídas em {df_f['BAIRRO'].nunique()} bairros/locais.",
                "Deseja avaliar o melhor chip para o município inteiro "
                "ou para um bairro específico?",
            ],
            botoes=[
                ("1", f"Município Inteiro ({nome_cid})", "1"),
                ("2", "Escolher um Bairro na Droplist", "2"),
            ],
        )
    except AbrirMenuOutroModo:
        _tratar_f12(df_f)
        raise

    if esc == "2":
        df_b = selecionar_bairro_interativo(df_f, nome_cid)
        if df_b is not None and not df_b.empty:
            b_esc = ", ".join(sorted(df_b["BAIRRO"].unique()))
            titulo = f"BAIRRO {b_esc} — {nome_cid} ({uf_cid})"
            return df_b, titulo

    # Retorna município inteiro
    titulo = f"{nome_cid} ({uf_cid})"
    return df_f, titulo


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def indicador_de_chips(df_erbs: pd.DataFrame) -> None:
    """Ponto de entrada do módulo.

    F12 → abre o menu do outro modo por cima, sem perder o estado.

    Args:
        df_erbs: DataFrame completo de ERBs.

    Raises:
        AbrirMenuOutroModo: Se usuário pressionar F12.
    """
    # 1) Formulário
    try:
        res = formulario_tui(
            modulo=_MODULO,
            titulo_janela="5. CONSULTOR / INDICADOR DE CHIP (SIM CARD)",
            campos=[
                {
                    "nome": "uf",
                    "rotulo": "Estado / UF",
                    "tipo": "droplist",
                    "largura": 28,
                    "padrao": "",
                    "opcoes": obter_opcoes_uf(True, "QUALQUER UF"),
                    "dica": "Use ←/→ ou ESPAÇO/F2 para selecionar a UF",
                },
                {
                    "nome": "municipio",
                    "rotulo": "Município de Uso",
                    "tipo": "combobox",
                    "largura": 34,
                    "opcoes": lambda vals: _sugerir_cidades(
                        df_erbs, vals.get("uf", "")
                    ),
                    "dica": "Digite o nome OU tecle [F2] p/ escolher na Droplist",
                },
                {
                    "nome": "perfil",
                    "rotulo": "Perfil de Uso Principal",
                    "tipo": "droplist",
                    "largura": 34,
                    "padrao": _PERFIL_GERAL,
                    "opcoes": _OPCOES_PERFIL,
                    "dica": "Use ←/→ ou ESPAÇO/F2 para escolher o perfil",
                },
            ],
            instrucoes_topo=[
                "Selecione o local e o seu Perfil de Uso nas Droplists abaixo:"
            ],
        )
    except AbrirMenuOutroModo:
        _tratar_f12(df_erbs)
        return

    if not res or (not res["uf"] and not res["municipio"]):
        return

    # 2) Filtra base
    df_f = df_erbs.copy()
    if res["uf"]:
        ufs = [u.strip() for u in res["uf"].split(",") if u.strip()]
        df_f = df_f[df_f["UF"].isin(ufs)]

    if res["municipio"]:
        df_f = filtrar_municipios_exatos(df_f, res["municipio"])
        if df_f.empty:
            return

    # 3) Define título do recorte
    titulo_recorte = (
        f"ESTADO {res['uf']}"
        if not res["municipio"]
        else res["municipio"].upper()
    )

    # 4) Se município único, permite escolher bairro
    if (
        res["municipio"]
        and df_f[["UF", "MUNICIPIO"]].drop_duplicates().shape[0] == 1
    ):
        uf_cid = df_f["UF"].iloc[0]
        nome_cid = df_f["MUNICIPIO_LIMPO"].iloc[0]

        try:
            df_f, titulo_recorte = _definir_escopo_bairro(df_f, nome_cid, uf_cid)
        except AbrirMenuOutroModo:
            _tratar_f12(df_erbs)
            return

    # 5) Calcula métricas
    perfil = res.get("perfil", _PERFIL_GERAL)
    nome_perfil = _NOMES_PERFIL.get(perfil, _NOMES_PERFIL[_PERFIL_GERAL])

    df_s = calcular_metricas_operadoras(df_f, perfil_uso=perfil)
    df_s.sort_values(
        by=["SCORE", "TOTAL", "5G", "4G"],
        ascending=False,
        inplace=True,
    )
    df_s.reset_index(drop=True, inplace=True)

    # 6) Monta itens do pódio
    itens = _montar_itens_podio(df_s)

    # 7) Diagnóstico de melhor cobertura
    _, linhas_podio = diagnosticar_melhor_cobertura(df_f)

    # 8) Loop do navegador
    while True:
        try:
            acao, op_escolhida, _, _ = navegador_tui(
                modulo="LAUDO DE INDICAÇÃO DE CHIP",
                titulo_janela=(
                    f"GUIA DE COMPRA DE CHIP — {titulo_recorte} | "
                    f"PERFIL: {nome_perfil}"
                ),
                itens_conteudo=itens,
                subcabecalho_fixo=linhas_podio,
                comandos_rodape=[
                    "[P] Pódio completo   |   [ENTER] Ver ERBs da Operadora   "
                    "|   [ESC/0] Voltar ao Menu"
                ],
                teclas_rapidas={"P"},
                dica_teclas=(
                    "↑/↓=Mover no Pódio | ENTER=Inspecionar ERBs | "
                    "P=Pódio | ESC/0=Voltar"
                ),
            )
        except AbrirMenuOutroModo:
            _tratar_f12(df_erbs)
            continue

        if acao == "KEY" and op_escolhida == "P":
            mostrar_podio_completo_tui()
            continue

        if acao == "SELECT" and op_escolhida:
            sub = df_f[df_f["OPERADORA"] == op_escolhida]
            try:
                abrir_inspecao_detalhada_erbs(
                    sub,
                    f"CHIP {op_escolhida} EM {titulo_recorte}",
                    titulo_recorte,
                    "",
                )
            except AbrirMenuOutroModo:
                _tratar_f12(df_erbs)
                continue
        else:
            break