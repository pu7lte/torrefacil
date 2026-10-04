"""Pesquisa global com filtro ao vivo, scroll real e busca vetorizada.

Este módulo implementa busca global na base de estações da Anatel,
com as seguintes características:
    - Índice pré-compilado (`__BUSCA_GLOBAL`) persistido no .pkl.
    - Busca vetorizada com `np.char.find` (performance).
    - Cache de linhas de exibição por identidade do DataFrame.
    - Fallback para compreensão de lista se numpy falhar.
    - TUI com filtro ao vivo, scroll real e cursor sempre visível.

Estratégia de cache:
    O array de texto (`arr_texto`) é memoizado por identidade do DataFrame
    (`id(df)`). Quando a base é substituída (recompilação, novo download),
    `invalidar_cache_pesquisa()` é chamado para limpar o cache.

Example:
    >>> from torre_facil.pesquisa_global import pesquisa_global_tui
    >>> pesquisa_global_tui(df_erbs, consulta_inicial="São Paulo")
"""
from __future__ import annotations  # BUG CORRIGIDO: faltava __

import logging
import sys
from typing import Any, Final

import numpy as np
import pandas as pd

from .estado import base_do_contexto
from .texto import normalizar_texto
from .tui.cores import (
    RESET,
    CAIXA_BORDA,
    CAIXA_CIANO,
    CAIXA_TEXTO,
    CAIXA_SELECAO,
    BARRA_STATUS_TOPO,
)
from .tui.motor import (
    obter_dimensoes_terminal,
    ajustar_texto_puro,
    desenhar_desktop_base,
    sobrepor_janela_no_canvas,
    renderizar_quadro_completo,
)
from .tui.teclado import ler_tecla
from .tui.janelas import caixa_notificacao_tui, alerta_tui

logger = logging.getLogger(__name__)

__all__ = [
    "invalidar_cache_pesquisa",
    "pesquisa_global_tui",
]


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_COLUNAS_PREFERIDAS: Final[list[str]] = [
    "UF",
    "MUNICIPIO_LIMPO",
    "MUNICIPIO",
    "BAIRRO",
    "ENDERECO",
    "ENDERECO_BUSCA",
    "LOGR_RAW",
    "OPERADORA",
    "NUM_ESTACAO",
    "TECNOLOGIA",
    "TECS_RAW",
    "GPS",
]
"""Colunas preferidas para busca, em ordem de prioridade."""

_LIMITE_RESULTADOS_SEM_FILTRO: Final[int] = 5000
"""Limite de resultados exibidos quando não há filtro."""

_CODIGO_ESCONDER_CURSOR: Final[str] = "\033[?25l"
"""Código ANSI para esconder o cursor do terminal."""


# ---------------------------------------------------------------------------
# Cache de array de texto
# ---------------------------------------------------------------------------

_CACHE_ARR_TEXTO: dict[str, Any] = {
    "id": None,
    "arr": None,
}
"""Cache de array de texto por identidade do DataFrame.

Chaves:
    - "id": id(df) do último DataFrame processado.
    - "arr": numpy.ndarray de strings de exibição.
"""


def invalidar_cache_pesquisa() -> None:
    """Invalida o cache de pesquisa.

    Chamado quando a base global é substituída (recompilação, novo download).
    """
    _CACHE_ARR_TEXTO["id"] = None
    _CACHE_ARR_TEXTO["arr"] = None
    logger.debug("Cache de pesquisa invalidado.")


# ---------------------------------------------------------------------------
# Preparação de dados
# ---------------------------------------------------------------------------

def _colunas_pesquisa_global(df: pd.DataFrame) -> list[str]:
    """Retorna colunas disponíveis para busca.

    Args:
        df: DataFrame da base.

    Returns:
        Lista de nomes de colunas presentes em df.
    """
    return [c for c in _COLUNAS_PREFERIDAS if c in df.columns]


def _array_str(lista: list) -> np.ndarray:
    """Converte lista para numpy.ndarray de dtype string.

    Args:
        lista: Lista de valores (podem ser None).

    Returns:
        Array numpy de strings.
    """
    if not lista:
        return np.array([], dtype="<U1")
    limpos = [str(x) if x is not None else "" for x in lista]
    return np.array(limpos, dtype=str)


def _obter_coluna_str(
    df: pd.DataFrame,
    *nomes: str,
    padrao: str = "",
) -> pd.Series | None:
    """Retorna primeira coluna existente como Series de strings.

    Args:
        df: DataFrame.
        nomes: Nomes de colunas a tentar (em ordem).
        padrao: Valor padrão para NaN.

    Returns:
        Series de strings, ou None se nenhuma coluna existir.
    """
    for nome in nomes:
        if nome in df.columns:
            return df[nome].fillna(padrao).astype(str)
    return None


def _precomputar_linhas_pesquisa(df: pd.DataFrame) -> np.ndarray:
    """Pré-computa a string de exibição de cada registro (vetorizado).

    Args:
        df: DataFrame da base.

    Returns:
        Array numpy de strings de exibição.
    """
    n = len(df)
    if n == 0:
        return np.array([], dtype="<U1")

    def vazio(valor: str = "") -> pd.Series:
        return pd.Series([valor] * n, index=df.index)

    # Obtém colunas (com fallbacks)
    mun = _obter_coluna_str(df, "MUNICIPIO_LIMPO", "MUNICIPIO")
    if mun is None:
        mun = vazio("")

    uf = _obter_coluna_str(df, "UF")
    if uf is None:
        uf = vazio("")

    bairro = _obter_coluna_str(df, "BAIRRO")
    if bairro is None:
        bairro = vazio("BAIRRO N/I")

    end = _obter_coluna_str(df, "ENDERECO", "LOGR_RAW")
    if end is None:
        end = vazio("ENDEREÇO N/I")

    op = _obter_coluna_str(df, "OPERADORA")
    if op is None:
        op = vazio("")

    est = _obter_coluna_str(df, "NUM_ESTACAO")
    if est is None:
        est = vazio("")

    tec = _obter_coluna_str(df, "TECNOLOGIA", "TECS_RAW")
    if tec is None:
        tec = vazio("")

    # Constrói a string final em C, uma passada por coluna
    s = mun.str.cat(uf, sep=" - ")
    s = s.str.cat(bairro, sep=" | ")
    s = s.str.cat(end, sep=" | ")
    s = s.str.cat(op, sep=" | ")
    s = s.str.cat(est, sep=" | ERB ")
    s = s.str.cat(tec, sep=" | ")

    return _array_str(s.tolist())


def _precomputar_linhas_pesquisa_cached(df: pd.DataFrame) -> np.ndarray:
    """Versão memoizada — devolve o mesmo array se `df` não mudou de identidade.

    Args:
        df: DataFrame da base.

    Returns:
        Array numpy de strings de exibição (cacheado).
    """
    df_id = id(df)
    if _CACHE_ARR_TEXTO["id"] == df_id and _CACHE_ARR_TEXTO["arr"] is not None:
        return _CACHE_ARR_TEXTO["arr"]

    arr = _precomputar_linhas_pesquisa(df)
    _CACHE_ARR_TEXTO["id"] = df_id
    _CACHE_ARR_TEXTO["arr"] = arr
    return arr


def _preparar_indice(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """Prepara índice de busca e array de texto.

    Usa `__BUSCA_GLOBAL` se já existir (caso normal: veio do .pkl compilado).
    Senão, compila agora e memoiza no próprio DataFrame.

    Args:
        df: DataFrame da base.

    Returns:
        Tupla (df_base, arr_busca, arr_texto).
    """
    if "__BUSCA_GLOBAL" not in df.columns:
        colunas = _colunas_pesquisa_global(df)
        if not colunas:
            df["__BUSCA_GLOBAL"] = ""
        else:
            combinada = df[colunas[0]].fillna("").astype(str)
            for c in colunas[1:]:
                combinada = combinada.str.cat(
                    df[c].fillna("").astype(str), sep=" | "
                )
            df["__BUSCA_GLOBAL"] = combinada.map(normalizar_texto)
        logger.info("Índice __BUSCA_GLOBAL compilado (%d colunas).", len(colunas))

    base = df
    arr_busca = _array_str(base["__BUSCA_GLOBAL"].tolist())
    arr_texto = _precomputar_linhas_pesquisa_cached(base)
    return base, arr_busca, arr_texto


def _buscar_em_array(arr_busca: np.ndarray, q_norm: str) -> np.ndarray:
    """Retorna índices cujo texto contém `q_norm`.

    Args:
        arr_busca: Array de strings normalizadas.
        q_norm: Query normalizada.

    Returns:
        Array de índices (numpy.int64).
    """
    if arr_busca.size == 0 or not q_norm:
        return np.array([], dtype=np.int64)

    try:
        mask = np.char.find(arr_busca, q_norm) >= 0
        return np.flatnonzero(mask)
    except Exception:
        # Fallback: compreensão de lista (lento, mas correto)
        logger.warning("np.char.find falhou; usando fallback lento.")
        return np.fromiter(
            (i for i, s in enumerate(arr_busca.tolist())
             if q_norm in (s or "")),
            dtype=np.int64,
        )


# ---------------------------------------------------------------------------
# TUI de pesquisa global
# ---------------------------------------------------------------------------

def pesquisa_global_tui(
    df_erbs: pd.DataFrame | None = None,
    consulta_inicial: str = "",
) -> None:
    """Busca global com filtro ao vivo, scroll real e cursor sempre visível.

    Args:
        df_erbs: DataFrame da base (opcional; usa base global se None).
        consulta_inicial: Query inicial (opcional).
    """
    df = df_erbs if df_erbs is not None else base_do_contexto()

    if df is None or df.empty:
        alerta_tui(
            "PESQUISA GLOBAL", "BASE INDISPONÍVEL",
            ["A base de dados ainda não foi carregada."],
        )
        return

    if not _colunas_pesquisa_global(df):
        alerta_tui(
            "PESQUISA GLOBAL", "SEM CAMPOS DE BUSCA",
            ["Não existem campos pesquisáveis na base atual."],
        )
        return

    base, arr_busca, arr_texto = _preparar_indice(df)

    query = str(consulta_inicial or "")
    cursor = 0
    offset = 0

    # Esconde o cursor do terminal
    sys.stdout.write(_CODIGO_ESCONDER_CURSOR)

    while True:
        q_norm = normalizar_texto(query) if query else ""

        # Busca ou lista completa
        if q_norm:
            idx_visiveis = _buscar_em_array(arr_busca, q_norm)
        else:
            limite = min(_LIMITE_RESULTADOS_SEM_FILTRO, len(arr_texto))
            idx_visiveis = np.arange(limite, dtype=np.int64)

        total = len(idx_visiveis)
        cursor = max(0, min(cursor, max(0, total - 1)))

        # Dimensões da janela
        larg_t, alt_t = obter_dimensoes_terminal()
        larg_box = min(max(82, larg_t - 6), 120)
        miolo = larg_box - 4
        altura = max(5, min(alt_t - 12, 18))

        # Scroll
        if total <= 0:
            offset = 0
            max_scroll = 0
        else:
            if cursor < offset:
                offset = cursor
            elif cursor >= offset + altura:
                offset = cursor - altura + 1
            max_scroll = max(0, total - altura)
            offset = max(0, min(offset, max_scroll))

        # Posição do scrollbar
        pos_thumb = 0
        if max_scroll > 0 and altura > 2:
            pos_thumb = int(round((offset / max_scroll) * (altura - 3)))

        fim = min(offset + altura, total)

        # Constrói linhas da janela
        resumo_resultados = f"Buscar: /{query}  ({total} resultado(s))"
        linhas = _construir_linhas_janela(
            larg_box, miolo, altura, total, offset, cursor,
            idx_visiveis, arr_texto, resumo_resultados, max_scroll, pos_thumb,
        )

        # Renderiza
        canvas = desenhar_desktop_base(
            larg_t, alt_t,
            msg_rodape=(
                "PESQUISA GLOBAL: bairro, rua, município, endereço, ERB, "
                "operadora e tecnologia"
            ),
        )
        sobrepor_janela_no_canvas(canvas, larg_t, alt_t, linhas, larg_box, sombra=True)
        renderizar_quadro_completo(canvas)

        # Lê tecla
        tecla = ler_tecla()
        if tecla is None or tecla == "IGNORE":
            continue

        # F10: alterna a visibilidade da barra de menu (não desenha outra)
        if tecla == "F10":
            from .tui.menu_barra import alternar_barra_menu
            alternar_barra_menu()
            continue

        t_up = tecla.upper() if len(tecla) == 1 else tecla

        # Processa teclas
        if t_up == "X":
            raise KeyboardInterrupt
        elif tecla == "ESC":
            if query:
                query = ""
                cursor = 0
                offset = 0
                continue
            return
        elif tecla == "UP" and total:
            cursor = (cursor - 1) % total
        elif tecla == "DOWN" and total:
            cursor = (cursor + 1) % total
        elif tecla == "PGUP" and total:
            cursor = max(0, cursor - altura)
        elif tecla == "PGDN" and total:
            cursor = min(total - 1, cursor + altura)
        elif tecla == "HOME":
            cursor = 0
            offset = 0
        elif tecla == "END" and total:
            cursor = total - 1
        elif tecla in ("BACKSPACE", "DEL"):
            query = query[:-1]
            cursor = 0
            offset = 0
        elif tecla == "ENTER" and total:
            _mostrar_detalhe_registro(base, idx_visiveis, cursor)
        elif tecla == "/":
            query = ""
            cursor = 0
            offset = 0
        elif len(tecla) == 1 and tecla.isprintable():
            query += tecla.upper()
            cursor = 0
            offset = 0


def _construir_linhas_janela(
    larg_box: int,
    miolo: int,
    altura: int,
    total: int,
    offset: int,
    cursor: int,
    idx_visiveis: np.ndarray,
    arr_texto: np.ndarray,
    resumo_resultados: str,
    max_scroll: int,
    pos_thumb: int,
) -> list[str]:
    """Constrói linhas da janela de pesquisa.

    Args:
        (parâmetros de layout e dados)

    Returns:
        Lista de strings ANSI formatadas.
    """
    linhas = [
        f"{CAIXA_BORDA}╭{'─' * (larg_box - 2)}╮{RESET}",
        f"{CAIXA_BORDA}│{BARRA_STATUS_TOPO}"
        f"{ajustar_texto_puro(' PESQUISA GLOBAL — BASE INTEIRA ', larg_box - 2, 'centro')}"
        f"{CAIXA_BORDA}│{RESET}",
        f"{CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{RESET}",
        f"{CAIXA_BORDA}│ {CAIXA_CIANO}"
        f"{ajustar_texto_puro(resumo_resultados, miolo)}"
        f"{CAIXA_BORDA} │{RESET}",
        f"{CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{RESET}",
    ]

    if total == 0:
        msg_vazia = "Nenhum resultado. Continue digitando ou apague com BACKSPACE."
        linhas.append(
            f"{CAIXA_BORDA}│ {CAIXA_TEXTO}"
            f"{ajustar_texto_puro(msg_vazia, miolo, 'centro')}"
            f"{CAIXA_BORDA} │{RESET}"
        )
        for _ in range(altura - 1):
            linhas.append(f"{CAIXA_BORDA}│ {' ' * miolo} │{RESET}")
    else:
        for i in range(altura):
            idx = offset + i
            if idx >= total:
                linhas.append(f"{CAIXA_BORDA}│ {' ' * miolo} {CAIXA_BORDA}│{RESET}")
                continue

            real_idx = int(idx_visiveis[idx])

            # Caractere do scrollbar
            if total <= altura:
                ch_sc = "│"
            elif i == 0:
                ch_sc = "▲" if offset > 0 else "│"
            elif i == altura - 1:
                ch_sc = "▼" if offset < max_scroll else "│"
            else:
                ch_sc = "█" if (i - 1) == pos_thumb else "░"

            texto = str(arr_texto[real_idx])

            if idx == cursor:
                linhas.append(
                    f"{CAIXA_BORDA}│{CAIXA_SELECAO}"
                    f" {ajustar_texto_puro('► ' + texto, miolo)} "
                    f"{CAIXA_BORDA}{ch_sc}{RESET}"
                )
            else:
                linhas.append(
                    f"{CAIXA_BORDA}│ {CAIXA_TEXTO}"
                    f"{ajustar_texto_puro('  ' + texto, miolo)}"
                    f"{CAIXA_BORDA}{ch_sc}{RESET}"
                )

    rodape_dica = (
        "↑/↓ Navegar | PgUp/PgDn Página | digite p/ filtrar AO VIVO | "
        "ENTER detalhe | ESC sair | X encerra"
    )
    linhas += [
        f"{CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{RESET}",
        f"{CAIXA_BORDA}│ {CAIXA_CIANO}"
        f"{ajustar_texto_puro(rodape_dica, miolo, 'centro')}"
        f"{CAIXA_BORDA} │{RESET}",
        f"{CAIXA_BORDA}╰{'─' * (larg_box - 2)}╯{RESET}",
    ]

    return linhas


def _mostrar_detalhe_registro(
    base: pd.DataFrame,
    idx_visiveis: np.ndarray,
    cursor: int,
) -> None:
    """Mostra detalhes do registro selecionado.

    Args:
        base: DataFrame da base.
        idx_visiveis: Índices visíveis após filtro.
        cursor: Posição do cursor.
    """
    real_idx = int(idx_visiveis[cursor])
    row = base.iloc[real_idx]

    linhas_det = [
        f"UF: {row.get('UF', '')}",
        f"MUNICÍPIO: {row.get('MUNICIPIO_LIMPO', row.get('MUNICIPIO', ''))}",
        f"BAIRRO: {row.get('BAIRRO', '')}",
        f"ENDEREÇO/LOGRADOURO: {row.get('ENDERECO', row.get('LOGR_RAW', ''))}",
        f"OPERADORA: {row.get('OPERADORA', '')}",
        f"ESTAÇÃO: {row.get('NUM_ESTACAO', '')}",
        f"TECNOLOGIA: {row.get('TECNOLOGIA', row.get('TECS_RAW', ''))}",
        f"GPS: {row.get('GPS', '')}",
    ]

    caixa_notificacao_tui("PESQUISA GLOBAL", "REGISTRO ENCONTRADO", linhas_det)