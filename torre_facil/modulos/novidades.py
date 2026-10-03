"""Tela de novidades entre duas atualizações da base ANATEL.

Fluxo de 3 níveis:
    1. **Caixa de resumo** — abre automaticamente quando há novidade
    2. **Tela navegável** — variações por operadora, UF, 5G, etc.
    3. **Detalhamento ERB por ERB** — tecla [A] dentro do nível 2

Nenhuma alteração de configuração é feita aqui — só leitura.
"""
from __future__ import annotations

import logging
from typing import Any

from ..dados import snapshot as snap_mod
from ..estado import AbrirMenuOutroModo
from ..tui import cores as C
from ..tui.janelas import (
    criar_item_tui,
    caixa_notificacao_tui,
    alerta_tui,
)
from ..tui.navegador import navegador_tui

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Ações da caixa de resumo (nível 1)
_ACAO_VER = "ver"
_ACAO_FECHAR = "fechar"

# Limite de cidades exibidas antes do "e mais N..."
_LIMITE_CIDADES_EXIBIDAS = 20


# ---------------------------------------------------------------------------
# Helpers de formatação
# ---------------------------------------------------------------------------

def _fmt_int(n: Any) -> str:
    """Formata número inteiro com separador de milhar.

    Args:
        n: Valor a formatar (int, float, str, etc.).

    Returns:
        String formatada (ex: "1.234") ou "?" se inválido.

    Examples:
        >>> _fmt_int(1234)
        '1.234'
        >>> _fmt_int("abc")
        '?'
    """
    try:
        return f"{int(n):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "?"


def _delta_str(delta: int) -> str:
    """Formata delta com sinal.

    Args:
        delta: Valor numérico.

    Returns:
        String com sinal (ex: "+1.234", "-567", "0").

    Examples:
        >>> _delta_str(1234)
        '+1.234'
        >>> _delta_str(-567)
        '-567'
    """
    if delta > 0:
        return f"+{_fmt_int(delta)}"
    if delta < 0:
        return f"-{_fmt_int(abs(delta))}"
    return "0"


def _formatar_linha_tabela(
    rotulo: str,
    antes: int,
    agora: int,
    delta: int,
    largura_rotulo: int = 14,
) -> str:
    """Formata linha de tabela com antes/agora/delta.

    Args:
        rotulo: Rótulo da linha (operadora, UF, etc.).
        antes: Valor anterior.
        agora: Valor atual.
        delta: Diferença.
        largura_rotulo: Largura da coluna de rótulo.

    Returns:
        Linha formatada alinhada.
    """
    return (
        f"   {rotulo:<{largura_rotulo}} "
        f"{_fmt_int(antes):>10} {_fmt_int(agora):>10} "
        f"{_delta_str(delta):>10}"
    )


def _cor_delta(delta: int) -> str:
    """Retorna cor baseada no sinal do delta.

    Args:
        delta: Valor numérico.

    Returns:
        Código de cor (verde se positivo, amarelo se negativo).
    """
    return C.CAIXA_VERDE if delta > 0 else C.CAIXA_AMARELO


# ---------------------------------------------------------------------------
# Nível 1 — Caixa de resumo
# ---------------------------------------------------------------------------

def _caixa_resumo(diff: dict[str, Any]) -> str:
    """Exibe caixa de resumo e retorna ação escolhida.

    Args:
        diff: Dicionário de diferenças retornado por ``snap_mod.comparar()``.

    Returns:
        Ação escolhida: ``"ver"`` ou ``"fechar"``.
    """
    total = diff.get("total", {})
    delta_total = total.get("delta", 0)
    novas = len(diff.get("erbs_novas", []))
    removidas = len(diff.get("erbs_removidas", []))

    linhas_msg: list[str] = [
        f"Base atualizada: {diff.get('data_nova', '?')}  "
        f"(antes {diff.get('data_antiga', '?')})",
        "",
    ]

    # ERBs novas/removidas
    if novas > 0 or removidas > 0:
        linhas_msg.append(
            f"ERBs novas: {_fmt_int(novas)}   |   "
            f"ERBs removidas: {_fmt_int(removidas)}"
        )
        linhas_msg.append(f"Saldo líquido: {_delta_str(delta_total)} ERBs")
        linhas_msg.append("")

    # 5G ativado
    _adicionar_secao_5g_ativado(linhas_msg, diff)

    # Cidades com nova operadora
    _adicionar_secao_nova_operadora(linhas_msg, diff)

    # 5G desativado
    _adicionar_secao_5g_desativado(linhas_msg, diff)

    if len(linhas_msg) <= 2:
        linhas_msg.append("Nenhuma novidade relevante detectada.")

    resposta = caixa_notificacao_tui(
        modulo="NOVIDADES NA BASE",
        titulo="NOVIDADES NA BASE",
        linhas_mensagem=linhas_msg,
        botoes=[
            ("ENTER", "Ver detalhes", _ACAO_VER),
            ("ESC", "Fechar", _ACAO_FECHAR),
        ],
    )

    return resposta or _ACAO_FECHAR


def _adicionar_secao_5g_ativado(linhas: list[str], diff: dict[str, Any]) -> None:
    """Adiciona seção de 5G ativado na caixa de resumo.

    Args:
        linhas: Lista de linhas da mensagem (modificada in-place).
        diff: Dicionário de diferenças.
    """
    ativ_5g = diff.get("5g_ativado_op", {})
    ativ_sa = diff.get("5g_sa_ativado_op", {})

    if ativ_5g:
        linhas.append("5G ativado em novas cidades:")
        for op, n in sorted(ativ_5g.items(), key=lambda x: -x[1]):
            linhas.append(f"   {op:<10} — {n} cidade(s)")
        linhas.append("")

    if ativ_sa:
        linhas.append("5G SA (pleno) ativado:")
        for op, n in sorted(ativ_sa.items(), key=lambda x: -x[1]):
            linhas.append(f"   {op:<10} — {n} cidade(s)")
        linhas.append("")


def _adicionar_secao_nova_operadora(linhas: list[str], diff: dict[str, Any]) -> None:
    """Adiciona seção de cidades com nova operadora.

    Args:
        linhas: Lista de linhas da mensagem (modificada in-place).
        diff: Dicionário de diferenças.
    """
    cid_2op = diff.get("novas_cidades_2op", [])
    cid_3op = diff.get("novas_cidades_3op", [])

    if cid_2op or cid_3op:
        if cid_2op:
            linhas.append(f"{len(cid_2op)} cidade(s) ganharam uma 2ª operadora")
        if cid_3op:
            linhas.append(f"{len(cid_3op)} cidade(s) ganharam uma 3ª operadora")
        linhas.append("")


def _adicionar_secao_5g_desativado(linhas: list[str], diff: dict[str, Any]) -> None:
    """Adiciona seção de 5G desativado.

    Args:
        linhas: Lista de linhas da mensagem (modificada in-place).
        diff: Dicionário de diferenças.
    """
    desativ = diff.get("5g_desativado_op", {})
    if desativ:
        linhas.append("5G desativado:")
        for op, n in sorted(desativ.items(), key=lambda x: -x[1]):
            linhas.append(f"   {op:<10} — {n} cidade(s)")
        linhas.append("")


# ---------------------------------------------------------------------------
# Nível 2 — Tela navegável com o resumo detalhado
# ---------------------------------------------------------------------------

def _montar_itens_detalhe(diff: dict[str, Any]) -> list[dict[str, Any]]:
    """Monta lista de itens para a tela de detalhes (nível 2).

    Args:
        diff: Dicionário de diferenças.

    Returns:
        Lista de itens para ``navegador_tui``.
    """
    itens: list[dict[str, Any]] = []

    # Resumo geral
    _adicionar_secao_resumo_geral(itens, diff)

    # Por operadora
    _adicionar_secao_por_operadora(itens, diff)

    # Por UF
    _adicionar_secao_por_uf(itens, diff)

    # Por tecnologia
    _adicionar_secao_por_tecnologia(itens, diff)

    # 5G ativado
    _adicionar_secao_5g_ativado_detalhe(itens, diff)

    # 5G SA ativado
    _adicionar_secao_5g_sa_ativado_detalhe(itens, diff)

    # 5G desativado
    _adicionar_secao_5g_desativado_detalhe(itens, diff)

    # Cidades com nova operadora
    _adicionar_secao_cidades_nova_operadora(itens, diff)

    # Cidades que perderam operadora
    _adicionar_secao_cidades_perderam_operadora(itens, diff)

    return itens


def _adicionar_secao_resumo_geral(
    itens: list[dict[str, Any]], diff: dict[str, Any]
) -> None:
    """Adiciona seção de resumo geral.

    Args:
        itens: Lista de itens (modificada in-place).
        diff: Dicionário de diferenças.
    """
    total = diff.get("total", {})
    itens.append(criar_item_tui("━━ RESUMO GERAL ━━", C.CAIXA_TITULO, "centro"))
    itens.append(criar_item_tui(
        f"Total de ERBs: {_fmt_int(total.get('antes', 0))} → "
        f"{_fmt_int(total.get('agora', 0))}  "
        f"({_delta_str(total.get('delta', 0))})",
        C.CAIXA_TEXTO, "esq",
    ))
    itens.append(criar_item_tui(
        f"Novas: {_fmt_int(len(diff.get('erbs_novas', [])))}   |   "
        f"Removidas: {_fmt_int(len(diff.get('erbs_removidas', [])))}",
        C.CAIXA_TEXTO, "esq",
    ))
    itens.append(criar_item_tui("", divisor=True))


def _adicionar_secao_por_operadora(
    itens: list[dict[str, Any]], diff: dict[str, Any]
) -> None:
    """Adiciona seção de variação por operadora.

    Args:
        itens: Lista de itens (modificada in-place).
        diff: Dicionário de diferenças.
    """
    ops = diff.get("por_operadora", [])
    if not ops:
        return

    itens.append(criar_item_tui(
        "━━ VARIAÇÃO POR OPERADORA ━━", C.CAIXA_TITULO, "centro"
    ))
    itens.append(criar_item_tui(
        f"   {'OPERADORA':<14} {'ANTES':>10} {'AGORA':>10} {'DELTA':>10}",
        C.CAIXA_CIANO, "esq",
    ))

    for op, antes, agora, delta in ops:
        if delta == 0:
            continue
        linha = _formatar_linha_tabela(op, antes, agora, delta)
        itens.append(criar_item_tui(linha, _cor_delta(delta), "esq"))

    itens.append(criar_item_tui("", divisor=True))


def _adicionar_secao_por_uf(
    itens: list[dict[str, Any]], diff: dict[str, Any]
) -> None:
    """Adiciona seção de variação por UF.

    Args:
        itens: Lista de itens (modificada in-place).
        diff: Dicionário de diferenças.
    """
    ufs = diff.get("por_uf", [])
    if not ufs:
        return

    itens.append(criar_item_tui(
        "━━ VARIAÇÃO POR UF ━━", C.CAIXA_TITULO, "centro"
    ))
    itens.append(criar_item_tui(
        f"   {'UF':<6} {'ANTES':>10} {'AGORA':>10} {'DELTA':>10}",
        C.CAIXA_CIANO, "esq",
    ))

    for uf, antes, agora, delta in ufs:
        if delta == 0:
            continue
        linha = _formatar_linha_tabela(uf, antes, agora, delta, largura_rotulo=6)
        itens.append(criar_item_tui(linha, _cor_delta(delta), "esq"))

    itens.append(criar_item_tui("", divisor=True))


def _adicionar_secao_por_tecnologia(
    itens: list[dict[str, Any]], diff: dict[str, Any]
) -> None:
    """Adiciona seção de variação por tecnologia.

    Args:
        itens: Lista de itens (modificada in-place).
        diff: Dicionário de diferenças.
    """
    tecs = diff.get("por_tecnologia", [])
    if not tecs:
        return

    nomes_tec = {"5": "5G", "L": "4G", "H": "3G", "E": "2G"}

    itens.append(criar_item_tui(
        "━━ VARIAÇÃO POR TECNOLOGIA ━━", C.CAIXA_TITULO, "centro"
    ))

    for tec, antes, agora, delta in tecs:
        if delta == 0:
            continue
        nome = nomes_tec.get(tec, tec)
        linha = _formatar_linha_tabela(nome, antes, agora, delta, largura_rotulo=6)
        itens.append(criar_item_tui(linha, _cor_delta(delta), "esq"))

    itens.append(criar_item_tui("", divisor=True))


def _adicionar_secao_5g_ativado_detalhe(
    itens: list[dict[str, Any]], diff: dict[str, Any]
) -> None:
    """Adiciona seção de 5G ativado (detalhe).

    Args:
        itens: Lista de itens (modificada in-place).
        diff: Dicionário de diferenças.
    """
    ativ_5g = diff.get("5g_ativado_op", {})
    if not ativ_5g:
        return

    itens.append(criar_item_tui(
        "━━ 5G ATIVADO (por operadora) ━━", C.CAIXA_TITULO, "centro"
    ))
    for op, n in sorted(ativ_5g.items(), key=lambda x: -x[1]):
        itens.append(criar_item_tui(
            f"   {op:<14} — {n} cidade(s)", C.CAIXA_VERDE, "esq"
        ))
    itens.append(criar_item_tui("", divisor=True))


def _adicionar_secao_5g_sa_ativado_detalhe(
    itens: list[dict[str, Any]], diff: dict[str, Any]
) -> None:
    """Adiciona seção de 5G SA ativado.

    Args:
        itens: Lista de itens (modificada in-place).
        diff: Dicionário de diferenças.
    """
    ativ_sa = diff.get("5g_sa_ativado_op", {})
    if not ativ_sa:
        return

    itens.append(criar_item_tui(
        "━━ 5G SA (pleno) ATIVADO ━━", C.CAIXA_TITULO, "centro"
    ))
    for op, n in sorted(ativ_sa.items(), key=lambda x: -x[1]):
        itens.append(criar_item_tui(
            f"   {op:<14} — {n} cidade(s)", C.CAIXA_VERDE, "esq"
        ))
    itens.append(criar_item_tui("", divisor=True))


def _adicionar_secao_5g_desativado_detalhe(
    itens: list[dict[str, Any]], diff: dict[str, Any]
) -> None:
    """Adiciona seção de 5G desativado.

    Args:
        itens: Lista de itens (modificada in-place).
        diff: Dicionário de diferenças.
    """
    desativ = diff.get("5g_desativado_op", {})
    if not desativ:
        return

    itens.append(criar_item_tui(
        "━━ 5G DESATIVADO ━━", C.CAIXA_TITULO, "centro"
    ))
    for op, n in sorted(desativ.items(), key=lambda x: -x[1]):
        itens.append(criar_item_tui(
            f"   {op:<14} — {n} cidade(s)", C.CAIXA_AMARELO, "esq"
        ))
    itens.append(criar_item_tui("", divisor=True))


def _adicionar_secao_cidades_nova_operadora(
    itens: list[dict[str, Any]], diff: dict[str, Any]
) -> None:
    """Adiciona seção de cidades com nova operadora.

    Args:
        itens: Lista de itens (modificada in-place).
        diff: Dicionário de diferenças.
    """
    cid_2op = diff.get("novas_cidades_2op", [])
    cid_3op = diff.get("novas_cidades_3op", [])

    if not cid_2op and not cid_3op:
        return

    itens.append(criar_item_tui(
        "━━ CIDADES COM NOVA OPERADORA ━━", C.CAIXA_TITULO, "centro"
    ))

    if cid_3op:
        _adicionar_lista_cidades(itens, cid_3op, "3ª operadora", C.CAIXA_CIANO)

    if cid_2op:
        itens.append(criar_item_tui("", divisor=True))
        _adicionar_lista_cidades(itens, cid_2op, "2ª operadora", C.CAIXA_TEXTO)

    itens.append(criar_item_tui("", divisor=True))


def _adicionar_lista_cidades(
    itens: list[dict[str, Any]],
    cidades: list[str],
    descricao: str,
    cor: str,
) -> None:
    """Adiciona lista de cidades com limite de exibição.

    Args:
        itens: Lista de itens (modificada in-place).
        cidades: Lista de chaves "MUNICIPIO|UF".
        descricao: Descrição (ex: "3ª operadora").
        cor: Cor do texto.
    """
    itens.append(criar_item_tui(
        f"   {len(cidades)} cidade(s) ganharam uma {descricao}:",
        C.CAIXA_TEXTO, "esq",
    ))

    for cid in cidades[:_LIMITE_CIDADES_EXIBIDAS]:
        mun, uf = cid.rsplit("|", 1)
        itens.append(criar_item_tui(
            f"     {mun:<30} ({uf})", cor, "esq"
        ))

    if len(cidades) > _LIMITE_CIDADES_EXIBIDAS:
        itens.append(criar_item_tui(
            f"     ... e mais {len(cidades) - _LIMITE_CIDADES_EXIBIDAS} cidade(s)",
            C.CAIXA_TEXTO, "esq",
        ))


def _adicionar_secao_cidades_perderam_operadora(
    itens: list[dict[str, Any]], diff: dict[str, Any]
) -> None:
    """Adiciona seção de cidades que perderam operadora.

    Args:
        itens: Lista de itens (modificada in-place).
        diff: Dicionário de diferenças.
    """
    cid_perd = diff.get("cidades_perderam_op", [])
    if not cid_perd:
        return

    itens.append(criar_item_tui(
        "━━ CIDADES QUE PERDERAM OPERADORA ━━", C.CAIXA_TITULO, "centro"
    ))

    for cid in cid_perd[:_LIMITE_CIDADES_EXIBIDAS]:
        mun, uf = cid.rsplit("|", 1)
        itens.append(criar_item_tui(
            f"   {mun:<30} ({uf})", C.CAIXA_AMARELO, "esq"
        ))

    if len(cid_perd) > _LIMITE_CIDADES_EXIBIDAS:
        itens.append(criar_item_tui(
            f"   ... e mais {len(cid_perd) - _LIMITE_CIDADES_EXIBIDAS} cidade(s)",
            C.CAIXA_TEXTO, "esq",
        ))

    itens.append(criar_item_tui("", divisor=True))


def _tela_detalhe(diff: dict[str, Any]) -> None:
    """Nível 2: tela navegável com resumo detalhado.

    Args:
        diff: Dicionário de diferenças.

    Raises:
        AbrirMenuOutroModo: Se usuário pressionar F12.
    """
    itens = _montar_itens_detalhe(diff)
    if not itens:
        alerta_tui("NOVIDADES", "SEM DETALHES", ["Nada para exibir."])
        return

    while True:
        try:
            acao, dados, _, _ = navegador_tui(
                modulo="NOVIDADES",
                titulo_janela=(
                    f"NOVIDADES NA BASE — {diff.get('data_antiga', '?')} → "
                    f"{diff.get('data_nova', '?')}"
                ),
                itens_conteudo=itens,
                comandos_rodape=[
                    "[A] Detalhamento ERB por ERB   |   [ESC] Voltar",
                ],
                teclas_rapidas={"A"},
                dica_teclas=(
                    "↑/↓=Rolar | PgUp/PgDn=Página | "
                    "A=Detalhe fino | ESC=Voltar"
                ),
            )
        except AbrirMenuOutroModo:
            raise

        if acao == "KEY" and dados == "A":
            _tela_detalhe_fino(diff)
            continue

        return


# ---------------------------------------------------------------------------
# Nível 3 — Detalhe fino (ERB por ERB)
# ---------------------------------------------------------------------------

def _formatar_linha_erb(e: dict[str, Any], removida: bool = False) -> str:
    """Formata linha de ERB para exibição.

    Args:
        e: Dicionário com dados da ERB.
        removida: Se True, omite marca de 5G.

    Returns:
        Linha formatada.
    """
    op = e["id"].split("|", 1)[0]
    est = e["id"].split("|", 1)[1] if "|" in e["id"] else ""
    uf = e.get("uf", "")
    mun = e.get("mun", "")
    bairro = e.get("bairro", "")
    tecs = e.get("tecs", "")

    if removida:
        marca_5g = ""
    else:
        marca_5g = " [5G SA]" if e.get("5g_sa") else (" [5G]" if "5" in tecs else "")

    return (
        f"{op:<10} {est:<12} {uf:<3} {mun[:22]:<22} "
        f"{bairro[:18]:<18} {tecs:<10}{marca_5g}"
    )


def _tela_detalhe_fino(diff: dict[str, Any]) -> None:
    """Nível 3: listas completas de ERBs novas e removidas.

    Args:
        diff: Dicionário de diferenças.

    Raises:
        AbrirMenuOutroModo: Se usuário pressionar F12.
    """
    erbs_novas = diff.get("erbs_novas", [])
    erbs_removidas = diff.get("erbs_removidas", [])

    if not erbs_novas and not erbs_removidas:
        alerta_tui(
            "NOVIDADES", "SEM ERBs NOVAS/REMOVIDAS",
            ["Não houve entrada ou saída de ERBs nesta atualização."],
        )
        return

    itens: list[dict[str, Any]] = []

    # ERBs novas
    if erbs_novas:
        itens.append(criar_item_tui(
            f"━━ ERBs NOVAS ({_fmt_int(len(erbs_novas))}) ━━",
            C.CAIXA_TITULO, "centro",
        ))
        for e in erbs_novas:
            linha = _formatar_linha_erb(e, removida=False)
            itens.append(criar_item_tui(linha, C.CAIXA_VERDE, "esq"))

    # ERBs removidas
    if erbs_removidas:
        if erbs_novas:
            itens.append(criar_item_tui("", divisor=True))
        itens.append(criar_item_tui(
            f"━━ ERBs REMOVIDAS ({_fmt_int(len(erbs_removidas))}) ━━",
            C.CAIXA_TITULO, "centro",
        ))
        for e in erbs_removidas:
            linha = _formatar_linha_erb(e, removida=True)
            itens.append(criar_item_tui(linha, C.CAIXA_AMARELO, "esq"))

    cab = (
        f"   {'OPERADORA':<10} {'ESTAÇÃO':<12} {'UF':<3} "
        f"{'MUNICÍPIO':<22} {'BAIRRO':<18} TECNOLOGIAS"
    )

    while True:
        try:
            navegador_tui(
                modulo="NOVIDADES - DETALHE",
                titulo_janela=(
                    f"DETALHE ERB POR ERB — "
                    f"{_fmt_int(len(erbs_novas))} nova(s) / "
                    f"{_fmt_int(len(erbs_removidas))} removida(s)"
                ),
                itens_conteudo=itens,
                colunas_fixas_tabela=cab,
                comandos_rodape=["[ESC] Voltar"],
                dica_teclas="↑/↓=Rolar | PgUp/PgDn=Página | ESC=Voltar",
            )
        except AbrirMenuOutroModo:
            raise
        return


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def mostrar_novidades(diff: dict[str, Any]) -> None:
    """Mostra sequência de telas de novidades.

    Chamada pelo ``__main__`` na abertura, se houver diferenças entre snapshots.

    Fluxo:
        Caixa de resumo → (se [ENTER]) → Tela de detalhe → (se [A]) → Detalhe fino

    Args:
        diff: Dicionário de diferenças retornado por ``snap_mod.comparar()``.
    """
    if not diff:
        logger.debug("Diff vazio, pulando novidades.")
        return

    if not snap_mod.tem_novidade_relevante(diff):
        logger.debug("Nenhuma novidade relevante detectada.")
        return

    logger.info("Exibindo novidades ao usuário.")

    # Nível 1: caixa
    acao = _caixa_resumo(diff)
    if acao != _ACAO_VER:
        return

    # Nível 2: tela navegável
    _tela_detalhe(diff)