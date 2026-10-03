"""Favoritos do modo loja.

Lista de endereços salvos pelo usuário. ENTER abre Consulta Rápida
já preenchida com o endereço selecionado.

Ações disponíveis:
    - ENTER: abrir Consulta Rápida com endereço pré-preenchido
    - A: adicionar favorito manualmente
    - R: remover favorito (com confirmação)
    - ESC: voltar ao menu principal
"""
from __future__ import annotations

import logging
from typing import Any

from ..config_usuario import (
    listar_favoritos,
    adicionar_favorito,
    remover_favorito,
)
from ..tui.cores import (
    CAIXA_TEXTO,
    CAIXA_TITULO,
    BARRA_VERDE,
    BARRA_ALERTA,
)
from ..tui.janelas import (
    criar_item_tui,
    alerta_tui,
    caixa_notificacao_tui,
    formulario_tui,
    menu_popup_centralizado,
)
from ..tui.navegador import navegador_tui
from . import consulta_rapida

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Largura das colunas na tabela de favoritos
_LARGURA_APELIDO = 40
_LARGURA_NUMERO = 4

# Título do módulo
_MODULO = "FAVORITOS"


# ---------------------------------------------------------------------------
# Helpers de formatação
# ---------------------------------------------------------------------------

def _formatar_linha_favorito(indice: int, favorito: dict[str, Any]) -> str:
    """Formata linha de favorito para exibição.

    Args:
        indice: Número do favorito (1-based).
        favorito: Dicionário com dados do favorito.

    Returns:
        Linha formatada alinhada.

    Examples:
        >>> _formatar_linha_favorito(1, {"apelido": "Casa", "endereco": "Rua X"})
        '[ 1] Casa                                     │  Rua X'
    """
    apelido = favorito.get("apelido") or favorito.get("endereco", "")
    endereco = favorito.get("endereco", "")
    return f"[{indice:2d}] {apelido:<{_LARGURA_APELIDO}}  │  {endereco}"


def _montar_itens_favoritos(favs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Monta lista de itens para exibição na TUI.

    Args:
        favs: Lista de favoritos.

    Returns:
        Lista de itens para ``navegador_tui``.
    """
    itens: list[dict[str, Any]] = []

    if not favs:
        itens.append(criar_item_tui(
            "Nenhum favorito salvo ainda.",
            CAIXA_TITULO,
            "centro",
        ))
        itens.append(criar_item_tui(
            "Use [F] na Consulta Rápida para salvar endereços.",
            CAIXA_TEXTO,
            "centro",
        ))
        return itens

    for i, favorito in enumerate(favs, start=1):
        linha = _formatar_linha_favorito(i, favorito)
        itens.append(criar_item_tui(
            linha,
            CAIXA_TEXTO,
            "esq",
            selecionavel=True,
            dados=favorito,
        ))

    return itens


def _montar_itens_remocao(favs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Monta lista de itens para tela de remoção.

    Args:
        favs: Lista de favoritos.

    Returns:
        Lista de itens para ``menu_popup_centralizado``.
    """
    itens: list[dict[str, Any]] = []

    for i, favorito in enumerate(favs, start=1):
        apelido = favorito.get("apelido") or favorito.get("endereco", "")
        itens.append(criar_item_tui(
            f"[{i:2d}] {apelido}",
            CAIXA_TEXTO,
            "esq",
            selecionavel=True,
            dados=favorito,
        ))

    return itens


# ---------------------------------------------------------------------------
# Ações
# ---------------------------------------------------------------------------

def _adicionar_manual() -> None:
    """Adiciona favorito manualmente via formulário.

    Solicita endereço e apelido opcional ao usuário.
    """
    res = formulario_tui(
        modulo=_MODULO,
        titulo_janela="ADICIONAR FAVORITO",
        campos=[
            {
                "nome": "endereco",
                "rotulo": "Endereço / CEP",
                "tipo": "texto",
                "largura": 40,
                "maiusculo": False,
            },
            {
                "nome": "apelido",
                "rotulo": "Apelido (opcional)",
                "tipo": "texto",
                "largura": 40,
                "maiusculo": False,
            },
        ],
        instrucoes_topo=[
            "O endereço será consultado quando você abrir este favorito.",
        ],
    )

    if not res or not res.get("endereco"):
        return

    endereco = res["endereco"]
    apelido = res.get("apelido") or ""

    ok = adicionar_favorito(endereco, apelido=apelido)

    if ok:
        logger.info("Favorito adicionado: %s", endereco)
        alerta_tui(
            _MODULO,
            "SALVO COM SUCESSO",
            [f"Endereço: {endereco}"],
            cor_titulo=BARRA_VERDE,
        )
    else:
        logger.warning("Falha ao salvar favorito: %s", endereco)
        alerta_tui(
            _MODULO,
            "FALHA AO SALVAR",
            ["Verifique a permissão de escrita."],
        )


def _remover_interativo() -> None:
    """Remove favorito de forma interativa com confirmação.

    Lista favoritos e solicita confirmação antes de remover.
    """
    favs = listar_favoritos()

    if not favs:
        alerta_tui(_MODULO, "SEM FAVORITOS", ["Nada para remover."])
        return

    itens = _montar_itens_remocao(favs)

    acao, dados, _ = menu_popup_centralizado(
        modulo=_MODULO,
        titulo_caixa="REMOVER FAVORITO",
        itens_menu=itens,
        largura_caixa=60,
    )

    if acao != "SELECT" or not dados:
        return

    endereco = dados.get("endereco", "")
    apelido = dados.get("apelido", endereco)

    conf = caixa_notificacao_tui(
        modulo=_MODULO,
        titulo="CONFIRMAR REMOÇÃO",
        linhas_mensagem=[
            "Remover o favorito?",
            f"  {apelido}",
        ],
        botoes=[
            ("S", "Sim, remover", "SIM"),
            ("N", "Não, cancelar", "NAO"),
        ],
        cor_cabecalho=BARRA_ALERTA,
    )

    if conf == "SIM":
        remover_favorito(endereco)
        logger.info("Favorito removido: %s", endereco)


# ---------------------------------------------------------------------------
# Tela principal
# ---------------------------------------------------------------------------

def favoritos(df_erbs: Any) -> None:
    """Ponto de entrada do módulo de favoritos.

    Lista endereços salvos e permite consultar, adicionar ou remover.

    Args:
        df_erbs: DataFrame completo de ERBs (passado para ``consulta_rapida``).
    """
    while True:
        favs = listar_favoritos()
        itens = _montar_itens_favoritos(favs)

        acao, dados, _, _ = navegador_tui(
            modulo=_MODULO,
            titulo_janela=f"FAVORITOS — {len(favs)} endereço(s) salvo(s)",
            itens_conteudo=itens,
            colunas_fixas_tabela=(
                f"   {'#':<{_LARGURA_NUMERO}} "
                f"{'APELIDO':<{_LARGURA_APELIDO}}  ENDEREÇO"
            ),
            comandos_rodape=[
                "[ENTER] Abrir Consulta Rápida   |   "
                "[A] Adicionar favorito manual   |   "
                "[R] Remover favorito   |   [ESC] Voltar",
            ],
            teclas_rapidas={"A", "R"},
            dica_teclas=(
                "↑/↓=Mover | ENTER=Consultar | A=Adicionar | R=Remover | ESC=Voltar"
            ),
        )

        if acao == "SELECT" and isinstance(dados, dict):
            endereco = dados.get("endereco", "")
            consulta_rapida.consulta_rapida(df_erbs, endereco_inicial=endereco)

        elif acao == "KEY" and dados == "A":
            _adicionar_manual()

        elif acao == "KEY" and dados == "R":
            _remover_interativo()

        else:
            return