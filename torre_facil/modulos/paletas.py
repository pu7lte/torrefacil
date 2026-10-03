"""Seletor de paleta de cores retrô.

Módulo que permite ao usuário escolher entre diferentes temas de cores
para a interface TUI. As mudanças são aplicadas no próximo início do app.

Recursos:
    - Preview ao vivo de cada paleta
    - Navegação por teclado (↑/↓/HOME/END/ENTER/ESC)
    - Persistência em ``config_usuario``
"""
from __future__ import annotations

import logging
from typing import Any

from ..config_usuario import obter_paleta, definir_paleta
from ..estado import INFO
from ..tui import cores as _cores
from ..tui.cores import PALETAS, ORDEM_PALETAS, RESET
from ..tui.janelas import alerta_tui
from ..tui.motor import (
    obter_dimensoes_terminal,
    ajustar_texto_puro,
    desenhar_desktop_base,
    sobrepor_janela_no_canvas,
    renderizar_quadro_completo,
)
from ..tui.teclado import ler_tecla

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Título do módulo
_MODULO = "SELETOR DE PALETA"

# Largura padrão da caixa
_LARGURA_MAX_CAIXA = 90
_MARGEM_HORIZONTAL = 6

# Tamanho do pedaço de amostra
_TAMANHO_PEDACO = 4

# Teclas de controle
_TECLA_SAIR = "X"
_TECLA_CANCELAR = "ESC"
_TECLA_CIMA = "UP"
_TECLA_BAIXO = "DOWN"
_TECLA_HOME = "HOME"
_TECLA_END = "END"
_TECLA_ENTER = "ENTER"


# ---------------------------------------------------------------------------
# Preview de paleta
# ---------------------------------------------------------------------------

def _preview_paleta(nome: str, largura: int) -> str:
    """Gera uma linha de amostra da paleta.

    Args:
        nome: Nome da paleta (chave em ``PALETAS``).
        largura: Largura total da linha em caracteres.

    Returns:
        String formatada com as cores da paleta.
    """
    p = PALETAS[nome]
    fundo = p["FUNDO_DESKTOP"]
    texto = p["CAIXA_TEXTO"]
    destaque = p["CAIXA_CIANO"]
    selecao = p["CAIXA_SELECAO"]

    pedaco = " " * _TAMANHO_PEDACO
    amostra = (
        f"{fundo}{texto}{pedaco}"
        f"{fundo}{destaque}{pedaco}"
        f"{selecao}{pedaco}"
        f"{RESET}"
    )

    usado = _TAMANHO_PEDACO * 3
    sobra = max(0, largura - usado)
    return amostra + (" " * sobra)


# ---------------------------------------------------------------------------
# Renderização da tela
# ---------------------------------------------------------------------------

def _renderizar_tela(
    idx: int,
    atual: str,
) -> tuple[list[str], int]:
    """Renderiza a tela do seletor de paletas.

    Args:
        idx: Índice da paleta atualmente selecionada.
        atual: Nome da paleta atualmente em uso.

    Returns:
        Tupla (linhas_renderizadas, largura_da_caixa).
    """
    larg_t, alt_t = obter_dimensoes_terminal()
    larg_box = min(larg_t - _MARGEM_HORIZONTAL, _LARGURA_MAX_CAIXA)
    miolo = larg_box - 4
    larg_preview = miolo - 34

    linhas: list[str] = [
        f"{_cores.CAIXA_BORDA}╭{'─' * (larg_box - 2)}╮{RESET}",
        f"{_cores.CAIXA_BORDA}│{_cores.BARRA_STATUS_TOPO}"
        f"{ajustar_texto_puro(' ESCOLHA A PALETA DE CORES ', larg_box - 2, 'centro')}"
        f"{_cores.CAIXA_BORDA}│{RESET}",
        f"{_cores.CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{RESET}",
    ]

    for i, nome in enumerate(ORDEM_PALETAS):
        label = PALETAS[nome]["label"]
        marca = "●" if nome == atual else " "
        sel = (i == idx)
        prefixo = "►" if sel else " "
        cor_linha = _cores.CAIXA_SELECAO if sel else _cores.CAIXA_TEXTO
        texto_nome = f"{prefixo} {marca} {nome:<10} {label[:30]:<30}"
        preview = _preview_paleta(nome, larg_preview)

        linhas.append(
            f"{_cores.CAIXA_BORDA}│ {cor_linha}"
            f"{ajustar_texto_puro(texto_nome, miolo - larg_preview - 2)} "
            f"{preview}"
            f"{_cores.CAIXA_BORDA}│{RESET}"
        )

    linhas.append(f"{_cores.CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{RESET}")

    dica = (
        "↑/↓ navega | ENTER escolhe | ESC cancela "
        "(mudança aplicada no próximo início)"
    )
    linhas.append(
        f"{_cores.CAIXA_BORDA}│ {_cores.CAIXA_CIANO}"
        f"{ajustar_texto_puro(dica, miolo, 'centro')}"
        f"{_cores.CAIXA_BORDA} │{RESET}"
    )
    linhas.append(f"{_cores.CAIXA_BORDA}╰{'─' * (larg_box - 2)}╯{RESET}")

    return linhas, larg_box


# ---------------------------------------------------------------------------
# Loop do seletor
# ---------------------------------------------------------------------------

def _tela_seletor_paletas() -> str | None:
    """Loop da tela de escolha de paleta.

    Returns:
        Nome da paleta escolhida, ou None se cancelado.

    Raises:
        KeyboardInterrupt: Se usuário pressionar X.
    """
    atual = obter_paleta()
    idx = ORDEM_PALETAS.index(atual) if atual in ORDEM_PALETAS else 0

    INFO.modulo_atual = _MODULO
    logger.info("Abrindo seletor de paletas (atual: %s)", atual)

    while True:
        # Renderiza tela
        linhas, larg_box = _renderizar_tela(idx, atual)

        # Desenha no canvas
        larg_t, alt_t = obter_dimensoes_terminal()
        canvas = desenhar_desktop_base(
            larg_t, alt_t,
            msg_rodape="Seletor de paleta — as cores trocam no próximo início do app",
        )
        sobrepor_janela_no_canvas(canvas, larg_t, alt_t, linhas, larg_box, sombra=True)
        renderizar_quadro_completo(canvas)

        # Lê tecla
        tecla = ler_tecla()
        if tecla is None or tecla == "IGNORE":
            continue

        t_up = tecla.upper() if len(tecla) == 1 else tecla

        # Trata teclas
        if t_up == _TECLA_SAIR:
            logger.info("Usuário pressionou X, encerrando app")
            raise KeyboardInterrupt

        if tecla == _TECLA_CANCELAR:
            logger.info("Usuário cancelou seleção de paleta")
            return None

        if tecla == _TECLA_CIMA:
            idx = (idx - 1) % len(ORDEM_PALETAS)
        elif tecla == _TECLA_BAIXO:
            idx = (idx + 1) % len(ORDEM_PALETAS)
        elif tecla == _TECLA_HOME:
            idx = 0
        elif tecla == _TECLA_END:
            idx = len(ORDEM_PALETAS) - 1
        elif tecla == _TECLA_ENTER:
            escolhida = ORDEM_PALETAS[idx]
            logger.info("Paleta escolhida: %s", escolhida)
            return escolhida


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def escolher_paleta(df_erbs: Any = None) -> None:
    """Ponto de entrada do seletor de paletas.

    Chamado pelo menu de Manutenção.

    Args:
        df_erbs: DataFrame de ERBs (não usado, mantido para compatibilidade).
    """
    try:
        escolhida = _tela_seletor_paletas()
    except KeyboardInterrupt:
        raise

    if not escolhida:
        return

    atual = obter_paleta()

    if escolhida == atual:
        logger.info("Paleta atual mantida: %s", atual)
        alerta_tui(
            "PALETA",
            "PALETA ATUAL MANTIDA",
            [f"A paleta '{PALETAS[escolhida]['label']}' já estava em uso."],
        )
        return

    if definir_paleta(escolhida):
        logger.info("Paleta salva com sucesso: %s", escolhida)
        alerta_tui(
            "PALETA",
            "PALETA SALVA COM SUCESSO",
            [
                f"Nova paleta: {PALETAS[escolhida]['label']}",
                "",
                "Feche e reabra o Torre Fácil para ver as novas cores.",
            ],
        )
    else:
        logger.error("Falha ao salvar paleta: %s", escolhida)
        alerta_tui(
            "PALETA",
            "FALHA AO SALVAR",
            ["Não foi possível gravar o arquivo de configuração."],
        )