"""Barra de menu superior fixa (F10 / ALT+letra).

Este módulo implementa:
    - ``montar_menus``: monta a lista de menus conforme o módulo atual
    - ``indice_menu_por_tecla``: mapeia ALT+letra → índice do menu
    - ``renderizar_menu_superior_fixo``: renderiza a barra superior
    - ``posicoes_barra``: calcula posições X de cada menu
    - ``ACOES_MENU_*``: conjuntos de ações habilitadas por contexto

Arquitetura:
    - Menus são definidos por módulo (COMPARADOR, RAIO-X, etc.)
    - Hotkeys são destacadas com cor diferente
    - Ações universais (BACK, FIRST, LAST, etc.) são mapeadas para teclas
"""
from __future__ import annotations

import logging
from typing import Any

from ..texto import normalizar_texto
from . import cores as C

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Separador visual entre itens de menu
_SEPARADOR: dict[str, bool] = {"sep": True}

# Ações mapeadas para teclas (menu → tecla)
ACOES_MENU_PARA_TECLA: dict[str, str] = {
    "BACK": "ESC",
    "FIRST": "HOME",
    "LAST": "END",
    "PAGE_UP": "PGUP",
    "PAGE_DOWN": "PGDN",
    "ADD": "F2",
    "TOP5": "T",
    "GENERATE": "G",
    "REMOVE": "R",
}

# Estado global: barra de menu visível (alternado com F10)
_BARRA_VISIVEL: bool = True


def barra_visivel() -> bool:
    """Retorna True se a barra de menu superior está visível."""
    return _BARRA_VISIVEL


def alternar_barra_menu(mostrar: bool | None = None) -> bool:
    """Alterna (ou define) a visibilidade da barra de menu superior.

    Args:
        mostrar: True/False para definir explicitamente; None alterna.

    Returns:
        Estado resultante da visibilidade.
    """
    global _BARRA_VISIVEL
    _BARRA_VISIVEL = (not _BARRA_VISIVEL) if mostrar is None else bool(mostrar)
    return _BARRA_VISIVEL


# Conjuntos de ações habilitadas por contexto
ACOES_MENU_BASICAS: frozenset[str] = frozenset({
    "GLOBAL_SEARCH", "HELP", "ABOUT", "CLOSE", "REDRAW", "FIRST", "LAST",
})

ACOES_MENU_NAVEGADOR: frozenset[str] = ACOES_MENU_BASICAS | {
    "BACK", "PAGE_UP", "PAGE_DOWN", "CLEAR", "FILTER", "PODIO",
}

ACOES_MENU_CESTA: frozenset[str] = ACOES_MENU_BASICAS | {
    "BACK", "PAGE_UP", "PAGE_DOWN", "ADD", "TOP5", "GENERATE", "REMOVE",
}


# ---------------------------------------------------------------------------
# Construtor de item de menu
# ---------------------------------------------------------------------------

def _mi(
    rotulo: str,
    tecla: str,
    acao: str,
    atalho: str = "",
    dica: str = "",
) -> dict[str, str]:
    """Constrói um item de menu.

    Args:
        rotulo: Texto do item.
        tecla: Letra da tecla quente.
        acao: Nome da ação.
        atalho: Atalho de teclado (ex: "F2", "Esc").
        dica: Texto de dica para o rodapé.

    Returns:
        Dicionário com dados do item.
    """
    return {
        "rotulo": rotulo,
        "tecla": tecla,
        "acao": acao,
        "atalho": atalho,
        "dica": dica,
    }


# ---------------------------------------------------------------------------
# Montagem de menus por módulo
# ---------------------------------------------------------------------------

def montar_menus(modulo: str = "") -> list[dict[str, Any]]:
    """Monta a lista de menus conforme o módulo atual.

    Args:
        modulo: Nome do módulo (ex: "COMPARADOR", "RAIO-X").

    Returns:
        Lista de dicionários com ``{nome, tecla, itens}``.
    """
    mod = normalizar_texto(modulo or "")

    # Menus comuns
    m_arquivo = {
        "nome": "Arquivo", "tecla": "A",
        "itens": [
            _mi("Voltar / Fechar", "V", "BACK", "Esc", "Volta à tela anterior."),
            _mi("Recarregar tela", "R", "REDRAW", "", "Redesenha a tela atual."),
        ],
    }
    m_editar = {
        "nome": "Editar", "tecla": "E",
        "itens": [
            _mi("Limpar filtro", "L", "CLEAR", "", "Remove o filtro ao vivo."),
            _mi("Limpar seleção", "S", "CLEAR_SELECTION", "", "Limpa seleções."),
        ],
    }
    m_cesta = {
        "nome": "Cesta", "tecla": "C",
        "itens": [
            _mi("Adicionar município", "A", "ADD", "F2", "Abre a lista."),
            _mi("Top 5 da UF", "T", "TOP5", "T", "Cinco municípios com mais ERBs."),
            _mi("Gerar comparação", "G", "GENERATE", "G", "Gera o comparativo."),
            _SEPARADOR,
            _mi("Remover município", "R", "REMOVE", "R", "Remove o destacado."),
        ],
    }
    m_filtro = {
        "nome": "Filtro", "tecla": "F",
        "itens": [
            _mi("Filtro ao vivo", "F", "FILTER", "", "Filtra conforme digita."),
            _mi("Limpar filtro", "L", "CLEAR", "", "Remove o filtro atual."),
        ],
    }
    m_exibir = {
        "nome": "Exibir", "tecla": "X",
        "itens": [
            _mi("Primeiro registro", "P", "FIRST", "Home", "Vai ao primeiro."),
            _mi("Último registro", "U", "LAST", "End", "Vai ao último."),
            _SEPARADOR,
            _mi("Pódio completo", "D", "PODIO", "P", "Classificação completa."),
        ],
    }
    m_pesquisa = {
        "nome": "Pesquisa", "tecla": "P",
        "itens": [
            _mi("Pesquisa global", "P", "GLOBAL_SEARCH", "/", "Busca na base."),
        ],
    }
    m_nav = {
        "nome": "Navegação", "tecla": "N",
        "itens": [
            _mi("Primeiro registro", "P", "FIRST", "Home", "Vai ao primeiro."),
            _mi("Último registro", "U", "LAST", "End", "Vai ao último."),
            _SEPARADOR,
            _mi("Página anterior", "A", "PAGE_UP", "PgUp", "Rola acima."),
            _mi("Próxima página", "X", "PAGE_DOWN", "PgDn", "Rola abaixo."),
        ],
    }
    m_ajuda = {
        "nome": "Ajuda", "tecla": "J",
        "itens": [
            _mi("Atalhos da tela", "A", "HELP", "", "Atalhos de teclado."),
            _mi("Sobre o Sistema", "S", "ABOUT", "", "Info e estatísticas."),
        ],
    }

    # Seleciona menus conforme o módulo
    if "COMPARADOR" in mod:
        return [m_arquivo, m_cesta, m_exibir, m_pesquisa, m_nav, m_ajuda]
    if "RAIO-X" in mod or "OPERADORA" in mod:
        return [m_arquivo, m_filtro, m_exibir, m_pesquisa, m_nav, m_ajuda]
    return [m_arquivo, m_editar, m_exibir, m_pesquisa, m_nav, m_ajuda]


# ---------------------------------------------------------------------------
# Mapeamento de tecla → índice do menu
# ---------------------------------------------------------------------------

def indice_menu_por_tecla(
    tecla: str,
    modulo: str = "",
    permitir_f10: bool = False,
) -> int | None:
    """Mapeia ALT+letra → índice do menu.

    Args:
        tecla: Tecla pressionada (ex: "ALT_A", "F10").
        modulo: Nome do módulo.
        permitir_f10: Se True, "F10" abre o primeiro menu (retorna 0).
            Por padrão F10 NÃO é tratado aqui — quem trata é o loop da
            tela (alternância de visibilidade da barra), evitando que a
            barra seja desenhada em duplicidade.

    Returns:
        Índice do menu (0-based), ou None se não encontrado.
    """
    if tecla == "F10":
        return 0 if permitir_f10 else None

    if isinstance(tecla, str) and tecla.startswith("ALT_") and len(tecla) > 4:
        letra = normalizar_texto(tecla[4:])
        for i, m in enumerate(montar_menus(modulo)):
            if m["tecla"] == letra:
                return i

    return None


# ---------------------------------------------------------------------------
# Renderização da hotkey
# ---------------------------------------------------------------------------

def _rotulo_hotkey(
    texto: str,
    letra: str,
    cor: str,
    cor_hot: str,
) -> str:
    """Destaca a letra quente no rótulo do menu.

    Args:
        texto: Texto do rótulo.
        letra: Letra a destacar.
        cor: Cor normal.
        cor_hot: Cor da letra quente.

    Returns:
        Texto formatado com a letra destacada.
    """
    pos = normalizar_texto(texto).find(letra) if letra else -1
    if pos < 0 or pos >= len(texto):
        return f"{cor}{texto}"
    return f"{cor}{texto[:pos]}{cor_hot}{texto[pos]}{cor}{texto[pos + 1:]}"


# ---------------------------------------------------------------------------
# Posições da barra
# ---------------------------------------------------------------------------

def posicoes_barra(
    menus: list[dict[str, Any]]
) -> list[tuple[int, int]]:
    """Calcula posições X de cada menu na barra.

    Args:
        menus: Lista de menus.

    Returns:
        Lista de tuplas ``(x, largura)`` para cada menu.
    """
    pos: list[tuple[int, int]] = []
    x = 2
    for m in menus:
        larg = len(m["nome"]) + 2
        pos.append((x, larg))
        x += larg + 1
    return pos


# ---------------------------------------------------------------------------
# Renderização da barra superior
# ---------------------------------------------------------------------------

def renderizar_menu_superior_fixo(
    larg: int,
    modulo: str = "",
    categoria_ativa: int | str | None = None,
) -> str:
    """Renderiza a barra de menu superior.

    Args:
        larg: Largura do terminal.
        modulo: Nome do módulo.
        categoria_ativa: Índice ou nome do menu ativo (None = nenhum).

    Returns:
        String com a barra renderizada (com códigos ANSI).
    """
    menus = montar_menus(modulo)
    partes: list[str] = [f"{C.MENU_BARRA}"]
    usado = 1

    for i, m in enumerate(menus):
        if isinstance(categoria_ativa, str):
            ativo = (categoria_ativa == m["nome"])
        else:
            ativo = (categoria_ativa is not None and categoria_ativa == i)

        cor, hot = (
            (C.MENU_BARRA_ATIVO, C.MENU_BARRA_ATIVO_HOT)
            if ativo
            else (C.MENU_BARRA, C.MENU_BARRA_HOT)
        )

        partes.append(
            f"{cor} {_rotulo_hotkey(m['nome'], m['tecla'], cor, hot)} "
            f"{cor}{C.MENU_BARRA}"
        )
        usado += len(m["nome"]) + 3

    dica = "X=Sair  F10=Menu  "
    sobra = max(0, larg - usado)

    if sobra > len(dica) + 1:
        partes.append(" " * (sobra - len(dica)) + dica)
    else:
        partes.append(" " * sobra)

    return "".join(partes) + C.RESET