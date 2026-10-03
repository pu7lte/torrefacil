"""Navegador paginado de listas longas + pódio de operadoras.

Este módulo implementa:
    - ``navegador_tui``: navegador genérico de listas com filtro ao vivo
    - ``mostrar_podio_completo_tui``: popup com ranking completo
    - ``obter_estilo_posicao``: estilo visual para pódio (ouro/prata/bronze)
    - ``gerar_barra_sinal``: barra visual de intensidade de sinal

Arquitetura:
    - Suporte a filtro ao vivo (tecla /)
    - Integração com menus pull-down
    - Easter egg F12 (``AbrirMenuOutroModo``)
    - Barra de scroll visual (▲▼█░)
"""
from __future__ import annotations

import logging
from typing import Any

from ..estado import INFO, AbrirMenuOutroModo
from ..texto import normalizar_texto
from .cores import (
    RESET,
    BARRA_STATUS_TOPO,
    CAIXA_BORDA,
    CAIXA_TITULO,
    CAIXA_TEXTO,
    CAIXA_CIANO,
    CAIXA_SELECAO,
    COR_OURO,
    COR_PRATA,
    COR_BRONZE,
    COR_DEMAIS,
)
from .menu_barra import (
    indice_menu_por_tecla,
    ACOES_MENU_PARA_TECLA,
    ACOES_MENU_NAVEGADOR,
)
from .janelas import caixa_notificacao_tui
from .motor import (
    obter_dimensoes_terminal,
    ajustar_texto_puro,
    desenhar_desktop_base,
    sobrepor_janela_no_canvas,
    renderizar_quadro_completo,
)
from .teclado import ler_tecla

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Ações de retorno do navegador
_ACAO_SELECT = "SELECT"
_ACAO_VOLTAR = "VOLTAR"
_ACAO_KEY = "KEY"
_ACAO_LOGO = "LOGO"

# Alinhamentos
_ALINHAMENTO_ESQ = "esq"
_ALINHAMENTO_CENTRO = "centro"

# Limite de itens exibidos em listas de cidades
_LIMITE_CIDADES_EXIBIDAS = 20


# ---------------------------------------------------------------------------
# Estilo de posição (pódio)
# ---------------------------------------------------------------------------

def _obter_estilo_posicao(pos: int) -> tuple[str, str, str]:
    """Retorna (cor, ícone, rótulo) para a posição no pódio.

    Args:
        pos: Posição (1-based).

    Returns:
        Tupla com código ANSI, ícone e rótulo.
    """
    if pos == 1:
        return COR_OURO, "[#1 OURO]", "1º LUGAR [OURO]"
    if pos == 2:
        return COR_PRATA, "[#2 PRATA]", "2º LUGAR [PRATA]"
    if pos == 3:
        return COR_BRONZE, "[#3 BRONZE]", "3º LUGAR [BRONZE]"
    return COR_DEMAIS, f"[#{pos} COLOC.]", f"{pos}º LUGAR"


def obter_estilo_posicao(pos: int) -> tuple[str, str, str]:
    """Versão pública de ``_obter_estilo_posicao``.

    Args:
        pos: Posição (1-based).

    Returns:
        Tupla com código ANSI, ícone e rótulo.
    """
    return _obter_estilo_posicao(pos)


# ---------------------------------------------------------------------------
# Barra de sinal
# ---------------------------------------------------------------------------

def gerar_barra_sinal(nota_0_a_10: float) -> str:
    """Gera barra visual de intensidade de sinal.

    Args:
        nota_0_a_10: Nota de 0 a 10.

    Returns:
        String formatada com barra e nível.

    Examples:
        >>> gerar_barra_sinal(8.5)
        '[████████░░]  8.5/10 (SINAL FORTE)'
    """
    blocos = int(round(nota_0_a_10))
    barra = "█" * blocos + "░" * (10 - blocos)

    if nota_0_a_10 >= 8.0:
        nivel = "SINAL FORTE"
    elif nota_0_a_10 >= 5.5:
        nivel = "SINAL MÉDIO"
    elif nota_0_a_10 >= 3.0:
        nivel = "SINAL FRACO"
    else:
        nivel = "SINAL MÍNIMO"

    return f"[{barra}] {nota_0_a_10:4.1f}/10 ({nivel})"


# ---------------------------------------------------------------------------
# Helpers de renderização
# ---------------------------------------------------------------------------

def _calcular_altura_viewport(
    alt_t: int,
    linhas_extra: int,
) -> int:
    """Calcula altura do viewport.

    Args:
        alt_t: Altura do terminal.
        linhas_extra: Linhas reservadas para cabeçalho/rodapé.

    Returns:
        Altura do viewport (mínimo 5).
    """
    return max(5, alt_t - 6 - linhas_extra)


def _calcular_linhas_extra(
    subcabecalho_fixo: list[str],
    colunas_fixas_tabela: str | None,
    filtro_navegacao: str,
    comandos_rodape: list[str],
) -> int:
    """Calcula linhas reservadas para elementos fixos.

    Args:
        subcabecalho_fixo: Linhas de subcabeçalho.
        colunas_fixas_tabela: Linha de cabeçalho de tabela.
        filtro_navegacao: Texto do filtro (vazio = sem filtro).
        comandos_rodape: Linhas de comandos no rodapé.

    Returns:
        Número de linhas reservadas.
    """
    return (
        2
        + (len(subcabecalho_fixo) + 1 if subcabecalho_fixo else 0)
        + (2 if colunas_fixas_tabela else 0)
        + (1 if filtro_navegacao else 0)
        + (len(comandos_rodape) + 1 if comandos_rodape else 0)
        + 1
    )


def _montar_cabecalho_navegador(
    larg_box: int,
    miolo: int,
    titulo_janela: str,
    pagina_atual: int,
    total_paginas: int,
    total_linhas: int,
) -> list[str]:
    """Monta linhas do cabeçalho do navegador.

    Args:
        larg_box: Largura da caixa.
        miolo: Largura do miolo.
        titulo_janela: Título.
        pagina_atual: Página atual (1-based).
        total_paginas: Total de páginas.
        total_linhas: Total de registros.

    Returns:
        Lista de linhas formatadas.
    """
    info_pag = f"Pág {pagina_atual}/{total_paginas} ({total_linhas} reg.)"
    esq_t = str(titulo_janela).strip()
    max_esq = max(10, miolo - len(info_pag) - 2)

    if len(esq_t) > max_esq:
        esq_t = esq_t[:max_esq - 3] + "..."

    esp = max(1, miolo - len(esq_t) - len(info_pag))

    return [
        f"{CAIXA_BORDA}╭{'─' * (larg_box - 2)}╮{RESET}",
        f"{CAIXA_BORDA}│{BARRA_STATUS_TOPO} {esq_t}{' ' * esp}{info_pag} "
        f"{CAIXA_BORDA}│{RESET}",
    ]


def _montar_subcabecalho(
    larg_box: int,
    miolo: int,
    filtro_navegacao: str,
    subcabecalho_fixo: list[str],
    colunas_fixas_tabela: str | None,
) -> list[str]:
    """Monta linhas de subcabeçalho.

    Args:
        larg_box: Largura da caixa.
        miolo: Largura do miolo.
        filtro_navegacao: Texto do filtro.
        subcabecalho_fixo: Linhas de subcabeçalho.
        colunas_fixas_tabela: Linha de cabeçalho de tabela.

    Returns:
        Lista de linhas formatadas.
    """
    linhas: list[str] = []

    if filtro_navegacao:
        linhas.append(
            f"{CAIXA_BORDA}│ {CAIXA_CIANO}"
            f"{ajustar_texto_puro(f'FILTRO AO VIVO: /{filtro_navegacao}', miolo, _ALINHAMENTO_CENTRO)}"
            f"{CAIXA_BORDA} │{RESET}"
        )

    if subcabecalho_fixo:
        linhas.append(f"{CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{RESET}")
        for l_sub in subcabecalho_fixo:
            linhas.append(
                f"{CAIXA_BORDA}│ {CAIXA_CIANO}"
                f"{ajustar_texto_puro(l_sub, miolo)}"
                f"{CAIXA_BORDA} │{RESET}"
            )

    if colunas_fixas_tabela:
        linhas.append(f"{CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{RESET}")
        linhas.append(
            f"{CAIXA_BORDA}│ {CAIXA_TITULO}"
            f"{ajustar_texto_puro(colunas_fixas_tabela, miolo)}"
            f"{CAIXA_BORDA} │{RESET}"
        )
        linhas.append(f"{CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{RESET}")
    else:
        linhas.append(f"{CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{RESET}")

    return linhas


def _calcular_caractere_scroll(
    i: int,
    altura_viewport: int,
    offset_scroll: int,
    max_scroll: int,
    total_linhas: int,
    pos_thumb: int,
) -> str:
    """Calcula caractere da barra de scroll.

    Args:
        i: Índice da linha.
        altura_viewport: Altura do viewport.
        offset_scroll: Offset de scroll.
        max_scroll: Máximo de scroll.
        total_linhas: Total de linhas.
        pos_thumb: Posição do thumb.

    Returns:
        Caractere da barra.
    """
    if total_linhas <= altura_viewport:
        return "│"
    if i == 0:
        return "▲" if offset_scroll > 0 else "│"
    if i == altura_viewport - 1:
        return "▼" if offset_scroll < max_scroll else "│"
    return "█" if (i - 1) == pos_thumb else "░"


def _montar_linhas_viewport(
    larg_box: int,
    miolo: int,
    altura_viewport: int,
    offset_scroll: int,
    idx_dest: int,
    itens_atuais: list[dict[str, Any]],
    total_linhas: int,
    max_scroll: int,
) -> list[str]:
    """Monta linhas do viewport (área de conteúdo).

    Args:
        larg_box: Largura da caixa.
        miolo: Largura do miolo.
        altura_viewport: Altura do viewport.
        offset_scroll: Offset de scroll.
        idx_dest: Índice do item destacado.
        itens_atuais: Lista de itens.
        total_linhas: Total de linhas.
        max_scroll: Máximo de scroll.

    Returns:
        Lista de linhas formatadas.
    """
    linhas: list[str] = []

    pos_thumb = 0
    if max_scroll > 0 and altura_viewport > 2:
        pos_thumb = int(round((offset_scroll / max_scroll) * (altura_viewport - 3)))

    for i in range(altura_viewport):
        idx_item = offset_scroll + i
        ch_sc = _calcular_caractere_scroll(
            i, altura_viewport, offset_scroll, max_scroll, total_linhas, pos_thumb
        )

        if idx_item < total_linhas:
            item = itens_atuais[idx_item]
            if item.get("divisor"):
                linhas.append(f"{CAIXA_BORDA}├{'─' * (larg_box - 2)}{ch_sc}{RESET}")
            elif idx_item == idx_dest:
                txt = ajustar_texto_puro(
                    f"► {item['texto']}", miolo,
                    item.get("alinhamento", _ALINHAMENTO_ESQ)
                )
                linhas.append(
                    f"{CAIXA_BORDA}│{CAIXA_SELECAO} {txt} "
                    f"{CAIXA_BORDA}{ch_sc}{RESET}"
                )
            else:
                pref = "  " if item.get("selecionavel") else ""
                txt = ajustar_texto_puro(
                    f"{pref}{item['texto']}", miolo,
                    item.get("alinhamento", _ALINHAMENTO_ESQ)
                )
                cor = item.get("cor", CAIXA_TEXTO)
                if "48;5;" not in cor:
                    cor = CAIXA_TEXTO
                linhas.append(
                    f"{CAIXA_BORDA}│ {cor}{txt}{CAIXA_BORDA} {ch_sc}{RESET}"
                )
        else:
            linhas.append(f"{CAIXA_BORDA}│ {' ' * miolo} {ch_sc}{RESET}")

    return linhas


def _montar_rodape_navegador(
    larg_box: int,
    miolo: int,
    comandos_rodape: list[str],
) -> list[str]:
    """Monta linhas do rodapé.

    Args:
        larg_box: Largura da caixa.
        miolo: Largura do miolo.
        comandos_rodape: Linhas de comandos.

    Returns:
        Lista de linhas formatadas.
    """
    linhas: list[str] = []

    if comandos_rodape:
        linhas.append(f"{CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{RESET}")
        for cmd in comandos_rodape:
            linhas.append(
                f"{CAIXA_BORDA}│ {CAIXA_CIANO}"
                f"{ajustar_texto_puro(cmd, miolo, _ALINHAMENTO_CENTRO)}"
                f"{CAIXA_BORDA} │{RESET}"
            )

    linhas.append(f"{CAIXA_BORDA}╰{'─' * (larg_box - 2)}╯{RESET}")
    return linhas


# ---------------------------------------------------------------------------
# Tratamento de teclas
# ---------------------------------------------------------------------------

def _tratar_tecla_menu(
    acao: str,
    modulo: str,
    teclas_rapidas: set[str],
) -> tuple[str, Any] | None:
    """Trata ação de menu.

    Args:
        acao: Nome da ação.
        modulo: Nome do módulo.
        teclas_rapidas: Conjunto de teclas rápidas.

    Returns:
        Tupla ``(tipo, valor)`` ou None.
    """
    from .menus import menu_dropdown_ancorado_tui, executar_acao_menu_comum

    acao_menu = menu_dropdown_ancorado_tui(
        modulo, habilitadas=ACOES_MENU_NAVEGADOR
    )

    if acao_menu == "QUIT":
        raise KeyboardInterrupt

    if acao_menu == "LOGO":
        return (_ACAO_LOGO, None)

    if acao_menu in ACOES_MENU_PARA_TECLA:
        return ("PENDENTE", ACOES_MENU_PARA_TECLA[acao_menu])

    if acao_menu == "ABOUT":
        executar_acao_menu_comum(acao_menu, modulo)
        return None

    if acao_menu == "GLOBAL_SEARCH":
        from ..pesquisa_global import pesquisa_global_tui
        pesquisa_global_tui()
        return None

    return ("ACAO_MENU", acao_menu)


def _tratar_tecla_navegacao(
    tecla: str,
    indices_sel: list[int],
    pos_cursor_lista: int,
    offset_scroll: int,
    max_scroll: int,
    altura_viewport: int,
    idx_dest: int,
) -> tuple[int, int]:
    """Trata tecla de navegação.

    Args:
        tecla: Tecla pressionada.
        indices_sel: Índices selecionáveis.
        pos_cursor_lista: Posição atual do cursor.
        offset_scroll: Offset de scroll.
        max_scroll: Máximo de scroll.
        altura_viewport: Altura do viewport.
        idx_dest: Índice do item destacado.

    Returns:
        Tupla ``(novo_pos_cursor, novo_offset_scroll)``.
    """
    if tecla in ("UP", "W", "w", "K", "k", "-"):
        if indices_sel:
            if pos_cursor_lista > 0:
                return pos_cursor_lista - 1, offset_scroll
            return pos_cursor_lista, max(0, offset_scroll - 1)
        return pos_cursor_lista, max(0, offset_scroll - 1)

    if tecla in ("DOWN", "S", "s", "J", "j", "+"):
        if indices_sel:
            if pos_cursor_lista < len(indices_sel) - 1:
                return pos_cursor_lista + 1, offset_scroll
            return pos_cursor_lista, min(max_scroll, offset_scroll + 1)
        return pos_cursor_lista, min(max_scroll, offset_scroll + 1)

    if tecla in ("PGDN", " ", "P", "p", "RIGHT", "PGUP", "A", "a", "LEFT"):
        descer = tecla in ("PGDN", " ", "P", "p", "RIGHT")
        passo = max(1, altura_viewport - 1)
        novo_off = (
            min(max_scroll, offset_scroll + passo) if descer
            else max(0, offset_scroll - passo)
        )
        if indices_sel:
            if novo_off == offset_scroll:
                novo_pos = len(indices_sel) - 1 if descer else 0
            else:
                rel = max(0, min(altura_viewport - 1, idx_dest - offset_scroll))
                alvo = novo_off + rel
                novo_pos = min(
                    range(len(indices_sel)),
                    key=lambda p: abs(indices_sel[p] - alvo),
                )
            return novo_pos, novo_off
        return pos_cursor_lista, novo_off

    if tecla == "HOME":
        return 0, 0

    if tecla == "END":
        novo_pos = len(indices_sel) - 1 if indices_sel else pos_cursor_lista
        return novo_pos, max_scroll

    return pos_cursor_lista, offset_scroll


# ---------------------------------------------------------------------------
# Navegador principal
# ---------------------------------------------------------------------------

def navegador_tui(
    modulo: str,
    titulo_janela: str,
    itens_conteudo: list[dict[str, Any]],
    subcabecalho_fixo: list[str] | None = None,
    colunas_fixas_tabela: str | None = None,
    comandos_rodape: list[str] | None = None,
    teclas_rapidas: set[str] | None = None,
    dica_teclas: str = (
        "↑/↓=Mover | PgUp/PgDn=Página | ENTER=Expandir | ESC=Voltar | X=Sair"
    ),
    cursor_inicial: int = 0,
    scroll_inicial: int = 0,
    permitir_esc_voltar: bool = True,
) -> tuple[str, Any, int, int]:
    """Navegador genérico de listas.

    Args:
        modulo: Nome do módulo.
        titulo_janela: Título da janela.
        itens_conteudo: Lista de itens.
        subcabecalho_fixo: Linhas de subcabeçalho (opcional).
        colunas_fixas_tabela: Cabeçalho de tabela (opcional).
        comandos_rodape: Linhas de comandos (opcional).
        teclas_rapidas: Teclas rápidas (opcional).
        dica_teclas: Dica de teclas no rodapé.
        cursor_inicial: Posição inicial do cursor.
        scroll_inicial: Offset inicial de scroll.
        permitir_esc_voltar: Se True, ESC volta.

    Returns:
        Tupla ``(acao, dados, pos_cursor, offset_scroll)``.

    Raises:
        AbrirMenuOutroModo: Se usuário pressionar F12.
        KeyboardInterrupt: Se usuário pressionar X.
    """
    INFO.modulo_atual = modulo

    if subcabecalho_fixo is None:
        subcabecalho_fixo = []
    if comandos_rodape is None:
        comandos_rodape = []
    if teclas_rapidas is None:
        teclas_rapidas = set()

    pos_cursor_lista = max(0, cursor_inicial)
    offset_scroll = scroll_inicial
    filtro_navegacao = ""
    filtro_ativo = False
    tecla_pendente: str | None = None

    logger.debug("Abrindo navegador: %s (%d itens)", modulo, len(itens_conteudo))

    while True:
        larg_t, alt_t = obter_dimensoes_terminal()

        # Aplica filtro
        if filtro_navegacao:
            f_norm = normalizar_texto(filtro_navegacao)
            itens_atuais = [
                it for it in itens_conteudo
                if f_norm in normalizar_texto(it.get("texto", ""))
            ]
        else:
            itens_atuais = list(itens_conteudo)

        indices_sel = [
            i for i, it in enumerate(itens_atuais)
            if it.get("selecionavel")
        ]
        pos_cursor_lista = (
            max(0, min(pos_cursor_lista, len(indices_sel) - 1))
            if indices_sel else -1
        )

        larg_box = max(66, larg_t - 4)
        miolo = larg_box - 4
        total_linhas = len(itens_atuais)
        idx_dest = (
            indices_sel[pos_cursor_lista]
            if (indices_sel and pos_cursor_lista >= 0) else -1
        )

        linhas_extra = _calcular_linhas_extra(
            subcabecalho_fixo, colunas_fixas_tabela,
            filtro_navegacao, comandos_rodape
        )
        altura_viewport = _calcular_altura_viewport(alt_t, linhas_extra)

        # Ajusta scroll para manter cursor visível
        if idx_dest >= 0:
            if idx_dest < offset_scroll:
                offset_scroll = idx_dest
            elif idx_dest >= offset_scroll + altura_viewport:
                offset_scroll = idx_dest - altura_viewport + 1

        max_scroll = max(0, total_linhas - altura_viewport)
        offset_scroll = max(0, min(offset_scroll, max_scroll))

        pagina_atual = (offset_scroll // altura_viewport) + 1
        total_paginas = max(1, (total_linhas + altura_viewport - 1) // altura_viewport)

        # Monta linhas
        linhas = _montar_cabecalho_navegador(
            larg_box, miolo, titulo_janela,
            pagina_atual, total_paginas, total_linhas
        )
        linhas += _montar_subcabecalho(
            larg_box, miolo, filtro_navegacao,
            subcabecalho_fixo, colunas_fixas_tabela
        )
        linhas += _montar_linhas_viewport(
            larg_box, miolo, altura_viewport, offset_scroll,
            idx_dest, itens_atuais, total_linhas, max_scroll
        )
        linhas += _montar_rodape_navegador(larg_box, miolo, comandos_rodape)

        # Dica de teclas
        dica = dica_teclas
        if "ALT+" not in dica:
            dica += " | ALT+letra/F10=Menu"
        if "/" not in dica:
            dica += " | /=Filtro"
        if "X" not in dica:
            dica += " | X=Sair"

        # Renderiza
        canvas = desenhar_desktop_base(larg_t, alt_t, msg_rodape=dica)
        sobrepor_janela_no_canvas(canvas, larg_t, alt_t, linhas, larg_box, sombra=True)
        renderizar_quadro_completo(canvas)

        # Lê tecla
        if tecla_pendente is not None:
            tecla, tecla_pendente = tecla_pendente, None
        else:
            tecla = ler_tecla()

        if tecla is None or tecla == "IGNORE":
            continue

        # Easter egg: F12
        if tecla in ("F12", "CTRL_F12"):
            raise AbrirMenuOutroModo()

        t_up = tecla.upper() if len(tecla) == 1 else tecla

        if t_up == "X" and "X" not in teclas_rapidas:
            raise KeyboardInterrupt

        # Menu de contexto
        cat = indice_menu_por_tecla(t_up, modulo)
        if cat is None and t_up.startswith("ALT_"):
            continue

        if cat is not None:
            resultado = _tratar_tecla_menu(t_up, modulo, teclas_rapidas)
            if resultado is not None:
                tipo, valor = resultado
                if tipo == _ACAO_LOGO:
                    return (_ACAO_LOGO, None, pos_cursor_lista, offset_scroll)
                if tipo == "PENDENTE":
                    tecla_pendente = valor
                    continue
                if tipo == "ACAO_MENU":
                    _tratar_acao_menu(
                        valor, modulo, indices_sel, altura_viewport,
                        max_scroll, total_linhas
                    )
                    continue

        # Pesquisa global
        if tecla == "/":
            from ..pesquisa_global import pesquisa_global_tui
            pesquisa_global_tui()
            continue

        # Filtro ativo
        if filtro_ativo:
            if tecla in ("BACKSPACE", "DEL"):
                filtro_navegacao = filtro_navegacao[:-1]
                pos_cursor_lista = 0
                offset_scroll = 0
                continue
            if len(tecla) == 1 and tecla.isprintable():
                filtro_navegacao += tecla.upper()
                pos_cursor_lista = 0
                offset_scroll = 0
                continue

        # Teclas rápidas
        if t_up in teclas_rapidas or tecla in teclas_rapidas:
            chave = t_up if t_up in teclas_rapidas else tecla
            return (_ACAO_KEY, chave, pos_cursor_lista, offset_scroll)

        # Navegação
        if tecla in ("UP", "W", "w", "K", "k", "-", "DOWN", "S", "s", "J", "j", "+",
                     "PGDN", " ", "P", "p", "RIGHT", "PGUP", "A", "a", "LEFT",
                     "HOME", "END"):
            pos_cursor_lista, offset_scroll = _tratar_tecla_navegacao(
                tecla, indices_sel, pos_cursor_lista, offset_scroll,
                max_scroll, altura_viewport, idx_dest
            )
            continue

        # ENTER
        if tecla == "ENTER":
            if idx_dest >= 0:
                return (
                    _ACAO_SELECT, itens_atuais[idx_dest].get("dados"),
                    pos_cursor_lista, offset_scroll
                )
            return (_ACAO_VOLTAR, None, pos_cursor_lista, offset_scroll)

        # ESC
        if tecla == "ESC":
            if filtro_navegacao:
                filtro_navegacao = ""
                pos_cursor_lista = 0
                offset_scroll = 0
            elif permitir_esc_voltar:
                return (_ACAO_VOLTAR, None, pos_cursor_lista, offset_scroll)

        # 0/V/v
        if tecla in ("0", "V", "v"):
            return (_ACAO_VOLTAR, None, pos_cursor_lista, offset_scroll)


def _tratar_acao_menu(
    acao: str,
    modulo: str,
    indices_sel: list[int],
    altura_viewport: int,
    max_scroll: int,
    total_linhas: int,
) -> None:
    """Trata ação de menu (efeitos colaterais).

    Args:
        acao: Nome da ação.
        modulo: Nome do módulo.
        indices_sel: Índices selecionáveis.
        altura_viewport: Altura do viewport.
        max_scroll: Máximo de scroll.
        total_linhas: Total de linhas.
    """
    from .menus import executar_acao_menu_comum

    if acao == "CLEAR":
        INFO.modulo_atual = modulo
    elif acao == "FIRST":
        pass
    elif acao == "LAST":
        pass
    elif acao == "FILTER":
        pass
    elif acao == "PODIO":
        mostrar_podio_completo_tui()
    elif acao == "HELP":
        caixa_notificacao_tui(
            modulo=modulo,
            titulo="ATALHOS DA NAVEGAÇÃO",
            linhas_mensagem=[
                "ALT+letra / F10 = abre o menu suspenso pull-down",
                "/ = pesquisa GLOBAL na base inteira",
                "↑/↓ = move | PgUp/PgDn = página",
                "ENTER = abre o registro selecionado",
                "ESC = limpa o filtro; novamente, volta",
                "X = encerra o programa",
            ],
            botoes=[("ENTER", "Fechar", "OK")],
        )


# ---------------------------------------------------------------------------
# Pódio completo (popup)
# ---------------------------------------------------------------------------

def mostrar_podio_completo_tui() -> None:
    """Exibe popup com ranking completo das operadoras.

    Usa ``INFO.podio_completo`` e ``INFO.podio_contexto``.
    """
    ranking = INFO.podio_completo or []

    if not ranking:
        from .janelas import alerta_tui
        alerta_tui(
            "RANKING", "SEM PODIO",
            ["Não há colocações de operadoras disponíveis nesta tela."]
        )
        return

    larg_t, alt_t = obter_dimensoes_terminal()
    larg_box = min(max(64, larg_t - 10), 96)
    miolo = larg_box - 4
    cursor = 0
    offset = 0

    logger.debug("Abrindo pódio completo: %d colocações", len(ranking))

    while True:
        altura = max(4, min(len(ranking), alt_t - 10))
        cursor = max(0, min(cursor, len(ranking) - 1))

        if cursor < offset:
            offset = cursor
        if cursor >= offset + altura:
            offset = cursor - altura + 1

        linhas = _montar_linhas_podio(larg_box, miolo, ranking, cursor, offset, altura)

        canvas = desenhar_desktop_base(
            larg_t, alt_t,
            msg_rodape="Lista completa das colocações das operadoras",
        )
        sobrepor_janela_no_canvas(canvas, larg_t, alt_t, linhas, larg_box, sombra=True)
        renderizar_quadro_completo(canvas)

        tecla = ler_tecla()

        if tecla in ("ESC", "ENTER"):
            return
        if tecla == "UP":
            cursor = max(0, cursor - 1)
        elif tecla == "DOWN":
            cursor = min(len(ranking) - 1, cursor + 1)
        elif tecla == "PGUP":
            cursor = max(0, cursor - altura)
        elif tecla == "PGDN":
            cursor = min(len(ranking) - 1, cursor + altura)
        elif tecla == "HOME":
            cursor = 0
        elif tecla == "END":
            cursor = len(ranking) - 1


def _montar_linhas_podio(
    larg_box: int,
    miolo: int,
    ranking: list[str],
    cursor: int,
    offset: int,
    altura: int,
) -> list[str]:
    """Monta linhas do popup de pódio.

    Args:
        larg_box: Largura da caixa.
        miolo: Largura do miolo.
        ranking: Lista de colocações.
        cursor: Posição do cursor.
        offset: Offset de scroll.
        altura: Altura do viewport.

    Returns:
        Lista de linhas formatadas.
    """
    linhas = [f"{CAIXA_BORDA}╭{'─' * (larg_box - 2)}╮{RESET}"]

    tit = f" {INFO.podio_contexto or 'PÓDIO'} — LISTA COMPLETA "
    linhas.append(
        f"{CAIXA_BORDA}│{CAIXA_TITULO}"
        f"{ajustar_texto_puro(tit, larg_box - 2, _ALINHAMENTO_CENTRO)}"
        f"{CAIXA_BORDA}│{RESET}"
    )
    linhas.append(f"{CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{RESET}")

    for i in range(altura):
        idx = offset + i
        if idx < len(ranking):
            cor = CAIXA_SELECAO if idx == cursor else CAIXA_TEXTO
            linhas.append(
                f"{CAIXA_BORDA}│ {cor}"
                f"{ajustar_texto_puro(ranking[idx], miolo)}"
                f"{CAIXA_BORDA} │{RESET}"
            )
        else:
            linhas.append(f"{CAIXA_BORDA}│ {' ' * miolo} │{RESET}")

    linhas += [
        f"{CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{RESET}",
        f"{CAIXA_BORDA}│ {CAIXA_CIANO}"
        f"{ajustar_texto_puro('↑/↓ navegar | PgUp/PgDn página | ENTER/ESC fechar', miolo, _ALINHAMENTO_CENTRO)}"
        f"{CAIXA_BORDA} │{RESET}",
        f"{CAIXA_BORDA}╰{'─' * (larg_box - 2)}╯{RESET}",
    ]

    return linhas