"""Menus pull-down ancorados na barra superior + ações universais.

Este módulo implementa:
    - ``menu_dropdown_ancorado_tui``: menu dropdown ancorado na barra superior
    - ``executar_acao_menu_comum``: executor de ações universais (QUIT, LOGO, HELP, etc.)
    - ``_mostrar_atalhos_tui``: caixa de ajuda com atalhos do sistema

Arquitetura:
    - Navegação por teclado completa (setas, HOME, END, PGUP, PGDN)
    - Suporte a atalhos (ALT+letra, letra da tecla quente)
    - Cache do último quadro para evitar redesenho
    - Suporte a itens desabilitados com navegação inteligente
"""
from __future__ import annotations

import datetime
import logging
from typing import Any

from ..estado import INFO, AbrirMenuOutroModo, obter_base_global
from ..texto import normalizar_texto
from .cores import (
    RESET,
    BARRA_STATUS_TOPO,
    MENU_BARRA,
    MENU_BARRA_HOT,
    MENU_BARRA_ATIVO,
    MENU_BARRA_ATIVO_HOT,
    MENU_ITEM,
    MENU_ITEM_HOT,
    MENU_ITEM_SEL,
    MENU_ITEM_SEL_HOT,
    MENU_ITEM_OFF,
    MENU_BORDA,
)
from .menu_barra import (
    montar_menus,
    posicoes_barra,
    renderizar_menu_superior_fixo,
    indice_menu_por_tecla,
    ACOES_MENU_PARA_TECLA,
)
from .motor import (
    obter_dimensoes_terminal,
    ajustar_texto_puro,
    desenhar_desktop_base,
    sobrepor_janela_no_canvas,
    renderizar_quadro_completo,
    obter_ultimo_quadro,
)
from .teclado import ler_tecla

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Ações de retorno do menu
_ACAO_CLOSE = "CLOSE"
_ACAO_QUIT = "QUIT"
_ACAO_LOGO = "LOGO"

# Ações universais
_ACAO_GLOBAL_SEARCH = "GLOBAL_SEARCH"
_ACAO_HELP = "HELP"
_ACAO_ABOUT = "ABOUT"

# Título do módulo de ajuda
_MODULO_AJUDA = "AJUDA"
_TITULO_ATALHOS = "ATALHOS DA TELA"


# ---------------------------------------------------------------------------
# Helpers de renderização
# ---------------------------------------------------------------------------

def _linha_item_menu(
    item: dict[str, Any],
    iw: int,
    selecionado: bool,
    habilitado: bool,
) -> str:
    """Renderiza uma linha de item de menu.

    Args:
        item: Dicionário com dados do item.
        iw: Largura interna do menu.
        selecionado: Se o item está selecionado.
        habilitado: Se o item está habilitado.

    Returns:
        Linha formatada com códigos ANSI.
    """
    if selecionado:
        cor, hot = MENU_ITEM_SEL, MENU_ITEM_SEL_HOT
    elif habilitado:
        cor, hot = MENU_ITEM, MENU_ITEM_HOT
    else:
        cor, hot = MENU_ITEM_OFF, MENU_ITEM_OFF

    rot = item["rotulo"]
    atalho = item.get("atalho") or ""
    espaco = max(1, iw - 2 - len(rot) - len(atalho))

    # Destaca a tecla quente
    pos = normalizar_texto(rot).find(item["tecla"]) if item.get("tecla") else -1
    if pos < 0 or pos >= len(rot):
        rot_pintado = f"{cor}{rot}"
    else:
        rot_pintado = f"{cor}{rot[:pos]}{hot}{rot[pos]}{cor}{rot[pos + 1:]}"

    corpo = f"{cor} {rot_pintado}{cor}{' ' * espaco}{atalho} "
    return f"{MENU_BORDA}│{corpo}{MENU_BORDA}│{RESET}"


def _linha_rodape_menu(larg: int, alt: int, mensagem: str) -> str:
    """Renderiza a linha do rodapé com hora.

    Args:
        larg: Largura do terminal.
        alt: Altura do terminal.
        mensagem: Mensagem a exibir.

    Returns:
        Linha formatada com códigos ANSI.
    """
    hora_str = f" {datetime.datetime.now().strftime('%H:%M')} "
    larg_msg = max(10, larg - len(hora_str) - 1)
    return (
        f"\033[{alt};1H{BARRA_STATUS_TOPO}"
        f"{ajustar_texto_puro(' ' + mensagem, larg_msg, 'esq')}"
        f"│{hora_str}{RESET}"
    )


# ---------------------------------------------------------------------------
# Helpers de navegação
# ---------------------------------------------------------------------------

def _item_habilitado(
    item: dict[str, Any],
    habilitadas: set[str] | None,
) -> bool:
    """Verifica se um item está habilitado.

    Args:
        item: Dicionário com dados do item.
        habilitadas: Conjunto de ações habilitadas (None = todas).

    Returns:
        True se o item está habilitado.
    """
    if item.get("sep"):
        return False
    if habilitadas is None:
        return True
    return item["acao"] in habilitadas


def _primeiro_habilitado(
    itens: list[dict[str, Any]],
    habilitadas: set[str] | None,
) -> int:
    """Encontra o índice do primeiro item habilitado.

    Args:
        itens: Lista de itens do menu.
        habilitadas: Conjunto de ações habilitadas.

    Returns:
        Índice do primeiro item habilitado, ou -1 se nenhum.
    """
    for i, it in enumerate(itens):
        if _item_habilitado(it, habilitadas):
            return i
    return -1


def _ultimo_habilitado(
    itens: list[dict[str, Any]],
    habilitadas: set[str] | None,
) -> int:
    """Encontra o índice do último item habilitado.

    Args:
        itens: Lista de itens do menu.
        habilitadas: Conjunto de ações habilitadas.

    Returns:
        Índice do último item habilitado, ou -1 se nenhum.
    """
    for i in range(len(itens) - 1, -1, -1):
        if _item_habilitado(itens[i], habilitadas):
            return i
    return -1


def _vizinho(
    itens: list[dict[str, Any]],
    habilitadas: set[str] | None,
    atual: int,
    passo: int,
) -> int:
    """Encontra o vizinho habilitado na direção do passo.

    Args:
        itens: Lista de itens do menu.
        habilitadas: Conjunto de ações habilitadas.
        atual: Índice atual.
        passo: +1 para próximo, -1 para anterior.

    Returns:
        Índice do vizinho habilitado.
    """
    i = atual
    for _ in range(len(itens)):
        i = (i + passo) % len(itens)
        if _item_habilitado(itens[i], habilitadas):
            return i
    return atual


# ---------------------------------------------------------------------------
# Menu dropdown ancorado
# ---------------------------------------------------------------------------

def menu_dropdown_ancorado_tui(
    modulo: str,
    categoria_inicial: int = 0,
    habilitadas: set[str] | None = None,
) -> str:
    """Menu dropdown ancorado na barra superior.

    Args:
        modulo: Nome do módulo (para montar os menus).
        categoria_inicial: Índice da categoria inicial (0-based).
        habilitadas: Conjunto de ações habilitadas (None = todas).

    Returns:
        Ação selecionada (ex: "QUIT", "LOGO", "GLOBAL_SEARCH") ou "CLOSE".

    Raises:
        AbrirMenuOutroModo: Se usuário pressionar F12.
    """
    menus = montar_menus(modulo)
    total_menus = len(menus)
    cat = max(0, min(int(categoria_inicial or 0), total_menus - 1))

    idx = _primeiro_habilitado(menus[cat]["itens"], habilitadas)

    # Cache do último quadro para evitar redesenho
    larg0, alt0 = obter_dimensoes_terminal()
    ultimo = obter_ultimo_quadro()
    base_salva = None
    if ultimo["dim"] == (larg0, alt0) and ultimo["cmds"]:
        base_salva = list(ultimo["cmds"])

    logger.debug("Abrindo menu dropdown: %s (cat=%d)", modulo, cat)

    while True:
        larg_t, alt_t = obter_dimensoes_terminal()

        # Usa base salva se dimensões não mudaram
        if base_salva is not None and (larg_t, alt_t) == (larg0, alt0):
            canvas = list(base_salva)
        else:
            canvas = desenhar_desktop_base(larg_t, alt_t)

        itens = menus[cat]["itens"]

        # Barra de menu superior destacada
        canvas.append(
            f"\033[3;1H{renderizar_menu_superior_fixo(larg_t, modulo, cat)}"
        )

        # Calcula largura do dropdown
        iw = max(22, max(
            (len(it["rotulo"]) + (len(it["atalho"]) + 3 if it.get("atalho") else 0)
             for it in itens if not it.get("sep")),
            default=0,
        ) + 2)

        # Monta linhas do dropdown
        linhas_drop = _montar_linhas_dropdown(itens, iw, idx, habilitadas)
        larg_box = iw + 2

        # Posição X do dropdown
        x_col = posicoes_barra(menus)[cat][0]
        pos_x = max(1, min(x_col, larg_t - larg_box - 2))

        # Sobrepõe no canvas
        sobrepor_janela_no_canvas(
            canvas, larg_t, alt_t, linhas_drop, larg_box,
            sombra=True, pos_y=4, pos_x=pos_x,
        )

        # Rodapé com dica
        dica = itens[idx]["dica"] if idx >= 0 else ""
        canvas.append(_linha_rodape_menu(
            larg_t, alt_t,
            dica or "←/→ Menu   ↑/↓ Item   ENTER Executa   ESC Fecha",
        ))

        renderizar_quadro_completo(canvas, lembrar=False)

        # Lê tecla
        tecla = ler_tecla()
        if tecla is None or tecla == "IGNORE":
            continue

        # Trata tecla
        resultado = _tratar_tecla_menu(
            tecla, cat, idx, itens, habilitadas, modulo, menus, total_menus
        )

        if resultado is not None:
            if isinstance(resultado, tuple):
                cat, idx = resultado
            else:
                return resultado


def _montar_linhas_dropdown(
    itens: list[dict[str, Any]],
    iw: int,
    idx: int,
    habilitadas: set[str] | None,
) -> list[str]:
    """Monta linhas do dropdown.

    Args:
        itens: Lista de itens do menu.
        iw: Largura interna.
        idx: Índice do item selecionado.
        habilitadas: Conjunto de ações habilitadas.

    Returns:
        Lista de linhas formatadas.
    """
    linhas: list[str] = [f"{MENU_BORDA}╭{'─' * iw}╮{RESET}"]

    for i, it in enumerate(itens):
        if it.get("sep"):
            linhas.append(f"{MENU_BORDA}├{'─' * iw}┤{RESET}")
        else:
            linhas.append(
                _linha_item_menu(it, iw, i == idx, _item_habilitado(it, habilitadas))
            )

    linhas.append(f"{MENU_BORDA}╰{'─' * iw}╯{RESET}")
    return linhas


def _tratar_tecla_menu(
    tecla: str,
    cat: int,
    idx: int,
    itens: list[dict[str, Any]],
    habilitadas: set[str] | None,
    modulo: str,
    menus: list[dict[str, Any]],
    total_menus: int,
) -> str | tuple[int, int] | None:
    """Trata tecla pressionada no menu.

    Args:
        tecla: Tecla pressionada.
        cat: Categoria atual.
        idx: Índice atual.
        itens: Itens do menu atual.
        habilitadas: Conjunto de ações habilitadas.
        modulo: Nome do módulo.
        menus: Lista de todos os menus.
        total_menus: Total de menus.

    Returns:
        Ação selecionada, ou ``(nova_cat, novo_idx)`` para navegar, ou None.
    """
    if tecla in ("F12", "CTRL_F12"):
        raise AbrirMenuOutroModo()

    if tecla in ("ESC", "F10"):
        return _ACAO_CLOSE

    # Navegação entre menus
    if tecla == "LEFT":
        nova_cat = (cat - 1) % total_menus
        novo_idx = _primeiro_habilitado(menus[nova_cat]["itens"], habilitadas)
        return (nova_cat, novo_idx)

    if tecla == "RIGHT":
        nova_cat = (cat + 1) % total_menus
        novo_idx = _primeiro_habilitado(menus[nova_cat]["itens"], habilitadas)
        return (nova_cat, novo_idx)

    # Navegação dentro do menu
    if tecla == "UP":
        return (cat, _vizinho(itens, habilitadas, idx, -1))

    if tecla == "DOWN":
        return (cat, _vizinho(itens, habilitadas, idx, +1))

    if tecla in ("HOME", "PGUP"):
        return (cat, _primeiro_habilitado(itens, habilitadas))

    if tecla in ("END", "PGDN"):
        return (cat, _ultimo_habilitado(itens, habilitadas))

    # Seleção
    if tecla == "ENTER":
        if idx >= 0 and _item_habilitado(itens[idx], habilitadas):
            logger.info("Ação selecionada: %s", itens[idx]["acao"])
            return itens[idx]["acao"]

    # ALT+tecla → troca de menu
    if tecla.startswith("ALT_"):
        novo = indice_menu_por_tecla(tecla, modulo)
        if novo is not None:
            if novo == cat:
                return _ACAO_CLOSE
            novo_idx = _primeiro_habilitado(menus[novo]["itens"], habilitadas)
            return (novo, novo_idx)

    # Tecla quente do item
    if len(tecla) == 1:
        letra = normalizar_texto(tecla)
        for it in itens:
            if _item_habilitado(it, habilitadas) and it.get("tecla") == letra:
                logger.info("Tecla quente: %s → %s", letra, it["acao"])
                return it["acao"]

    return None


# ---------------------------------------------------------------------------
# Caixa de ajuda
# ---------------------------------------------------------------------------

def _mostrar_atalhos_tui(modulo: str = "") -> None:
    """Exibe caixa com atalhos do sistema.

    Args:
        modulo: Nome do módulo (para o cabeçalho).
    """
    from .janelas import caixa_notificacao_tui

    caixa_notificacao_tui(
        modulo=modulo or _MODULO_AJUDA,
        titulo=_TITULO_ATALHOS,
        linhas_mensagem=[
            "ALT+letra / F10 = abre o menu",
            "←/→ troca de menu | ↑/↓ item | ENTER executa | ESC fecha",
            "/ = pesquisa GLOBAL na base inteira",
            "↑/↓ move | PgUp/PgDn página | Home/End início/fim",
            "ENTER abre o registro selecionado",
            "ESC limpa o filtro; novamente, volta",
            "X = encerra o programa",
        ],
        botoes=[("ENTER", "Fechar", "OK")],
    )


# ---------------------------------------------------------------------------
# Executor de ações universais
# ---------------------------------------------------------------------------

def executar_acao_menu_comum(acao: str, modulo: str = "") -> str | None:
    """Executa uma ação universal do menu.

    Args:
        acao: Nome da ação (ex: "QUIT", "LOGO", "HELP").
        modulo: Nome do módulo (para mensagens).

    Returns:
        String especial ("QUIT", "LOGO") ou tecla pendente, ou None.
    """
    if acao == _ACAO_GLOBAL_SEARCH:
        from ..pesquisa_global import pesquisa_global_tui
        pesquisa_global_tui()
        return None

    if acao == _ACAO_HELP:
        _mostrar_atalhos_tui(modulo)
        return None

    if acao == _ACAO_ABOUT:
        from ..modulos.sobre import sobre_sistema_tui
        df_base = obter_base_global()
        if df_base is not None:
            sobre_sistema_tui(df_base)
        else:
            _mostrar_atalhos_tui(modulo)
        return None

    if acao == _ACAO_QUIT:
        logger.info("Ação QUIT executada")
        return _ACAO_QUIT

    if acao == _ACAO_LOGO:
        logger.info("Ação LOGO executada")
        return _ACAO_LOGO

    return ACOES_MENU_PARA_TECLA.get(acao)