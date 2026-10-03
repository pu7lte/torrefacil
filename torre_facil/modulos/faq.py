"""Perguntas frequentes (modo loja).

Cada pergunta leva a uma ação pré-configurada:
    - Consulta rápida (5G, melhor operadora)
    - Comparador A vs B (streaming/jogos, ligações)
    - Informações sobre cobertura rural e cidade

Estrutura:
    _PERGUNTAS: lista de (texto, atalho, ação)
    faq(): ponto de entrada, monta menu e despacha
    _despachar(): executa ação pré-configurada
"""
from __future__ import annotations

import logging
from typing import Any

from ..tui.cores import CAIXA_TEXTO, CAIXA_TITULO, CAIXA_CIANO
from ..tui.janelas import (
    criar_item_tui,
    menu_popup_centralizado,
    alerta_tui,
)
from . import consulta_rapida, comparador_loja

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Cada pergunta é: (texto da pergunta, atalho, ação)
# Ação é uma string que o despachante interpreta.
_PERGUNTAS: list[tuple[str, str, str]] = [
    ("Aqui pega 5G?", "1", "consulta_5g"),
    ("Qual a melhor operadora neste endereço?", "2", "consulta_melhor"),
    ("Tem cobertura em zona rural?", "3", "consulta_rural"),
    ("Qual o melhor para streaming/jogos?", "4", "comparador_5g"),
    ("Qual o melhor para ligações?", "5", "comparador_voz"),
    ("Cobre em toda a cidade?", "6", "consulta_cidade"),
]

# Título do módulo
_MODULO = "FAQ"


# ---------------------------------------------------------------------------
# Montagem do menu
# ---------------------------------------------------------------------------

def _montar_itens_menu() -> list[dict[str, Any]]:
    """Monta lista de itens para o menu de perguntas frequentes.

    Returns:
        Lista de itens para ``menu_popup_centralizado``.
    """
    itens: list[dict[str, Any]] = [
        criar_item_tui(
            "Perguntas frequentes do cliente",
            CAIXA_TITULO,
            "centro",
        ),
        criar_item_tui("", divisor=True),
    ]

    for pergunta, atalho, _ in _PERGUNTAS:
        itens.append(criar_item_tui(
            f"  {pergunta}",
            CAIXA_TEXTO,
            "esq",
            selecionavel=True,
            dados=atalho,
            atalho=atalho,
        ))

    itens.append(criar_item_tui("", divisor=True))
    itens.append(criar_item_tui(
        "  [ESC] Voltar",
        CAIXA_CIANO,
        "esq",
    ))

    return itens


def _encontrar_acao(atalho: str) -> str | None:
    """Encontra a ação correspondente ao atalho selecionado.

    Args:
        atalho: Atalho selecionado pelo usuário.

    Returns:
        Nome da ação, ou None se não encontrada.
    """
    for _, at, acao in _PERGUNTAS:
        if at == atalho:
            return acao
    return None


# ---------------------------------------------------------------------------
# Despacho de ações
# ---------------------------------------------------------------------------

def _acao_consulta(df_erbs: Any, endereco_inicial: str) -> None:
    """Ação: abrir consulta rápida.

    Usada por: consulta_5g, consulta_melhor.

    Args:
        df_erbs: DataFrame completo de ERBs.
        endereco_inicial: Endereço pré-preenchido.
    """
    consulta_rapida.consulta_rapida(df_erbs, endereco_inicial)


def _acao_comparador(df_erbs: Any, endereco_inicial: str) -> None:
    """Ação: abrir comparador A vs B.

    Usada por: comparador_5g, comparador_voz.

    Args:
        df_erbs: DataFrame completo de ERBs.
        endereco_inicial: Endereço pré-preenchido.
    """
    comparador_loja.comparador_loja(df_erbs, endereco_inicial)


def _acao_cobertura_rural() -> None:
    """Ação: mostrar informações sobre cobertura rural."""
    alerta_tui(
        _MODULO,
        "COBERTURA RURAL",
        [
            "Para zonas rurais, recomendamos:",
            "",
            "  1. Use o menu 6 (Consulta de rodovias) do modo analista",
            "     para ver ERBs em estradas e áreas remotas.",
            "",
            "  2. Use o menu 1 (Raio-X) e filtre por bairro 'ZONA RURAL'.",
            "",
            "  3. Se o endereço exato for conhecido, use a Consulta Rápida",
            "     com raio de 10 km.",
        ],
    )


def _acao_cobertura_cidade() -> None:
    """Ação: mostrar informações sobre cobertura de cidade inteira."""
    alerta_tui(
        _MODULO,
        "COBERTURA NA CIDADE",
        [
            "Para ver a cobertura de uma cidade inteira:",
            "",
            "  1. Use o menu 1 (Raio-X de cidade) do modo analista.",
            "  2. Escolha a UF e a cidade.",
            "  3. A visão 1 mostra todas as operadoras, com total de ERBs.",
            "",
            "Para saber se uma operadora cobre TODA a cidade,",
            "é preciso verificar bairro a bairro — o modo loja não",
            "responde isso diretamente hoje.",
        ],
    )


# Mapeamento de ações para funções
_ACOES: dict[str, Any] = {
    "consulta_5g": _acao_consulta,
    "consulta_melhor": _acao_consulta,
    "comparador_5g": _acao_comparador,
    "comparador_voz": _acao_comparador,
    "consulta_rural": _acao_cobertura_rural,
    "consulta_cidade": _acao_cobertura_cidade,
}


def _despachar(df_erbs: Any, acao: str, endereco_inicial: str) -> None:
    """Executa a ação pré-configurada.

    Args:
        df_erbs: DataFrame completo de ERBs.
        acao: Nome da ação a executar.
        endereco_inicial: Endereço pré-preenchido.
    """
    funcao = _ACOES.get(acao)

    if funcao is None:
        logger.warning("Ação desconhecida: %s", acao)
        return

    # Ações que precisam de df_erbs e endereco_inicial
    if funcao in (_acao_consulta, _acao_comparador):
        funcao(df_erbs, endereco_inicial)
    else:
        # Ações que não precisam de parâmetros
        funcao()


# ---------------------------------------------------------------------------
# Tela principal
# ---------------------------------------------------------------------------

def faq(df_erbs: Any, endereco_inicial: str = "") -> None:
    """Menu de perguntas frequentes.

    Args:
        df_erbs: DataFrame completo de ERBs.
        endereco_inicial: Endereço pré-preenchido (opcional).
    """
    while True:
        itens = _montar_itens_menu()

        acao, dados, _ = menu_popup_centralizado(
            modulo=_MODULO,
            titulo_caixa="PERGUNTAS FREQUENTES",
            itens_menu=itens,
            largura_caixa=56,
        )

        if acao != "SELECT" or not dados:
            return

        acao_nome = _encontrar_acao(dados)

        if not acao_nome:
            logger.warning("Atalho não encontrado: %s", dados)
            continue

        logger.info("Executando ação FAQ: %s", acao_nome)
        _despachar(df_erbs, acao_nome, endereco_inicial)