"""Comparador lado a lado de municípios (modo analista).

Módulos:
    - construir_cesta_cidades_tui: tela interativa para montar cesta de municípios
    - comparador_cidades: fluxo principal (formulário → cesta → quadro comparativo)

Recursos:
    - Construtor de cesta com múltiplos atalhos (U, A, T, R, G, ESPAÇO, /)
    - Filtro por UF ao vivo
    - Top 5 cidades por UF
    - Exportação CSV do quadro comparativo
    - Integração com painel_interativo_municipio
"""
from __future__ import annotations

import datetime
import logging
import re
from typing import Any

import pandas as pd

from ..dicionarios import obter_opcoes_uf
from ..painel import (
    painel_interativo_municipio,
    salvar_csv_tui,
    dataframe_para_itens_tui,
    diagnosticar_melhor_cobertura,
)
from ..texto import normalizar_texto
from ..tui.cores import (
    RESET,
    CAIXA_BORDA,
    CAIXA_TEXTO,
    CAIXA_CIANO,
    CAIXA_SELECAO,
    BARRA_STATUS_TOPO,
)
from ..tui.janelas import (
    criar_item_tui,
    formulario_tui,
    alerta_tui,
    abrir_droplist_popup,
)
from ..tui.menu_barra import (
    indice_menu_por_tecla,
    ACOES_MENU_CESTA,
)
from ..tui.motor import (
    obter_dimensoes_terminal,
    ajustar_texto_puro,
    desenhar_desktop_base,
    sobrepor_janela_no_canvas,
    renderizar_quadro_completo,
)
from ..tui.navegador import navegador_tui
from ..tui.teclado import ler_tecla

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Título do módulo
_MODULO = "COMPARADOR DE CIDADES"

# Limites da cesta
_MINIMO_CIDADES = 2
_MAXIMO_CIDADES = 12

# Colunas usadas para identificar cidades
_COLUNAS_CIDADES = ["UF", "MUNICIPIO", "MUNICIPIO_LIMPO"]

# Separador para chave composta (UF + Município)
_SEPARADOR_CHAVE = "\x1f"


# ---------------------------------------------------------------------------
# Estado do construtor de cesta
# ---------------------------------------------------------------------------

class _EstadoCesta:
    """Estado mutável do construtor de cesta.

    Attributes:
        cesta: Lista de chaves (UF, MUNICIPIO) selecionadas.
        conjunto: Conjunto de chaves para busca rápida.
        cursor: Posição do cursor na lista de cidades disponíveis.
        uf_atual: UF atualmente filtrada (vazio = todas).
        filtro: Texto de filtro ao vivo.
    """

    def __init__(self, uf_inicial: str = "") -> None:
        self.cesta: list[tuple[str, str]] = []
        self.conjunto: set[tuple[str, str]] = set()
        self.cursor: int = 0
        self.uf_atual: str = self._normalizar_uf(uf_inicial)
        self.filtro: str = ""

    @staticmethod
    def _normalizar_uf(uf: str) -> str:
        """Normaliza UF para uppercase sem espaços.

        Args:
            uf: UF bruta.

        Returns:
            UF normalizada.
        """
        return str(uf or "").strip().upper()

    def adicionar(self, chave: tuple[str, str]) -> bool:
        """Adiciona cidade à cesta.

        Args:
            chave: Tupla (UF, MUNICIPIO).

        Returns:
            True se adicionou, False se já existia ou atingiu limite.
        """
        if chave in self.conjunto:
            return False
        if len(self.cesta) >= _MAXIMO_CIDADES:
            alerta_tui(
                "COMPARADOR",
                "LIMITE DA CESTA",
                [f"O limite desta comparação é de {_MAXIMO_CIDADES} municípios."],
            )
            return False
        self.conjunto.add(chave)
        self.cesta.append(chave)
        logger.debug("Cidade adicionada à cesta: %s", chave)
        return True

    def remover(self, chave: tuple[str, str]) -> None:
        """Remove cidade da cesta.

        Args:
            chave: Tupla (UF, MUNICIPIO).
        """
        if chave in self.conjunto:
            self.conjunto.discard(chave)
            if chave in self.cesta:
                self.cesta.remove(chave)
            logger.debug("Cidade removida da cesta: %s", chave)

    def remover_ultima(self) -> None:
        """Remove a última cidade adicionada."""
        if self.cesta:
            chave = self.cesta.pop()
            self.conjunto.discard(chave)
            logger.debug("Última cidade removida: %s", chave)


# ---------------------------------------------------------------------------
# Helpers para construtor de cesta
# ---------------------------------------------------------------------------

def _listar_cidades_disponiveis(
    df_base: pd.DataFrame,
    uf_atual: str,
    filtro: str,
) -> list[dict[str, Any]]:
    """Lista cidades disponíveis para seleção.

    Args:
        df_base: DataFrame base filtrado.
        uf_atual: UF atualmente filtrada (vazio = todas).
        filtro: Texto de filtro ao vivo.

    Returns:
        Lista de dicionários com {chave, uf, mun, nome}.
    """
    base = df_base
    if uf_atual:
        base = base[base["UF"].astype(str).str.upper() == uf_atual]

    colunas = [c for c in _COLUNAS_CIDADES if c in base.columns]
    if len(colunas) < 2:
        return []

    tmp = base[colunas].drop_duplicates().copy()

    # Iteração vetorizada (mais rápida que iterrows)
    ufs = tmp["UF"].fillna("").astype(str).str.strip().str.upper().tolist()
    municipios = tmp["MUNICIPIO"].fillna("").astype(str).str.strip().tolist()

    if "MUNICIPIO_LIMPO" in tmp.columns:
        nomes = tmp["MUNICIPIO_LIMPO"].fillna("").astype(str).str.strip().str.upper().tolist()
    else:
        nomes = [m.upper() for m in municipios]

    saida: list[dict[str, Any]] = []
    vistos: set[tuple[str, str]] = set()

    for i in range(len(tmp)):
        uf = ufs[i]
        mun = municipios[i]
        nome = nomes[i]
        chave = (uf, mun)

        if chave in vistos or not mun:
            continue
        vistos.add(chave)

        saida.append({
            "chave": chave,
            "uf": uf,
            "mun": mun,
            "nome": nome,
        })

    saida.sort(key=lambda x: (x["nome"], x["uf"]))

    # Aplica filtro
    if filtro:
        f_norm = normalizar_texto(filtro)
        saida = [
            c for c in saida
            if f_norm in normalizar_texto(c["nome"])
            or f_norm in normalizar_texto(c["mun"])
        ]

    return saida


def _adicionar_top5(
    estado: _EstadoCesta,
    df_base: pd.DataFrame,
) -> None:
    """Adiciona Top 5 cidades da UF atual à cesta.

    Args:
        estado: Estado do construtor.
        df_base: DataFrame base.
    """
    if not estado.uf_atual:
        alerta_tui(
            "COMPARADOR",
            "UF NECESSÁRIA",
            ["Escolha uma UF com [U] antes de carregar o Top 5."],
        )
        return

    base = df_base[df_base["UF"].astype(str).str.upper() == estado.uf_atual]
    if base.empty:
        return

    chave = "ID_ERB" if "ID_ERB" in base.columns else "NUM_ESTACAO"
    top = (
        base.groupby(["UF", "MUNICIPIO"])[chave]
        .nunique()
        .sort_values(ascending=False)
        .head(5)
        .reset_index()
    )

    # Iteração vetorizada
    ufs = top["UF"].astype(str).str.upper().tolist()
    municipios = top["MUNICIPIO"].astype(str).tolist()

    for i in range(len(top)):
        estado.adicionar((ufs[i], municipios[i]))

    logger.info("Top 5 cidades adicionadas à cesta")


def _renderizar_construtor_cesta(
    estado: _EstadoCesta,
    df_base: pd.DataFrame,
    cidades: list[dict[str, Any]],
) -> list[str]:
    """Renderiza o construtor de cesta como lista de linhas.

    Args:
        estado: Estado do construtor.
        df_base: DataFrame base.
        cidades: Lista de cidades disponíveis.

    Returns:
        Lista de linhas formatadas para renderização.
    """
    larg_t, alt_t = obter_dimensoes_terminal()
    larg_box = min(max(70, larg_t - 8), 100)
    miolo = larg_box - 4
    altura = max(6, min(12, alt_t - 12))

    uf_txt = estado.uf_atual or "TODAS"
    linha_status = (
        f"UF: {uf_txt}   |   Filtro: [{estado.filtro}]   |   "
        f"Cesta: {len(estado.cesta)}/{_MAXIMO_CIDADES}"
    )

    linhas = [
        f"{CAIXA_BORDA}╔{'═' * (larg_box - 2)}╗{RESET}",
        f"{CAIXA_BORDA}║{BARRA_STATUS_TOPO}"
        f"{ajustar_texto_puro(' CONSTRUTOR DE CESTA DE CIDADES ', larg_box - 2, 'centro')}"
        f"{CAIXA_BORDA}║{RESET}",
        f"{CAIXA_BORDA}╟{'─' * (larg_box - 2)}╢{RESET}",
        f"{CAIXA_BORDA}║ {CAIXA_CIANO}"
        f"{ajustar_texto_puro(linha_status, miolo)}"
        f"{CAIXA_BORDA} ║{RESET}",
        f"{CAIXA_BORDA}╠{'═' * (larg_box - 2)}╣{RESET}",
    ]

    w_esq = max(28, (miolo - 3) // 2)
    w_dir = miolo - w_esq - 3

    # Painel esquerdo: cesta
    cesta_linhas = ["CESTA DE COMPARAÇÃO"]
    for i, ch in enumerate(estado.cesta):
        sub = df_base[
            df_base["UF"].eq(ch[0]) & df_base["MUNICIPIO"].eq(ch[1])
        ]
        if "MUNICIPIO_LIMPO" in df_base.columns and not sub.empty:
            nome = sub["MUNICIPIO_LIMPO"].iloc[0]
        else:
            nome = ch[1]
        cesta_linhas.append(f"{i + 1:02d}. {nome} - {ch[0]}")

    cesta_linhas += ["", "[R]/[DEL] remove item destacado"]

    # Renderiza linhas
    for i in range(altura):
        le = cesta_linhas[i] if i < len(cesta_linhas) else ""

        if cidades and i < len(cidades):
            c = cidades[i]
            marca = "✓" if c["chave"] in estado.conjunto else " "
            ld = f"{marca} {c['nome']} - {c['uf']}"
            if i == estado.cursor:
                ld = "► " + ld
                cor_dir = CAIXA_SELECAO
            else:
                ld = "  " + ld
                cor_dir = CAIXA_TEXTO
        else:
            ld = ""
            cor_dir = CAIXA_TEXTO

        linhas.append(
            f"{CAIXA_BORDA}║ {CAIXA_TEXTO}"
            f"{ajustar_texto_puro(le, w_esq)}"
            f"{CAIXA_BORDA} │ {cor_dir}"
            f"{ajustar_texto_puro(ld, w_dir)}"
            f"{CAIXA_BORDA} ║{RESET}"
        )

    linhas += [
        f"{CAIXA_BORDA}╟{'─' * (larg_box - 2)}╢{RESET}",
        f"{CAIXA_BORDA}║ {CAIXA_CIANO}"
        f"{ajustar_texto_puro('↑/↓ Nav  [ESPAÇO] Seleciona  [U] UF  [A]/[F2] Adiciona  [T] Top5  [R] Remove  [G] Gera  [/] Busca  [ESC] Volta', miolo, 'centro')}"
        f"{CAIXA_BORDA} ║{RESET}",
        f"{CAIXA_BORDA}╚{'═' * (larg_box - 2)}╝{RESET}",
    ]

    return linhas


def _tratar_tecla_construtor(
    tecla: str,
    estado: _EstadoCesta,
    df_base: pd.DataFrame,
    cidades: list[dict[str, Any]],
    altura: int,
) -> str | None:
    """Trata uma tecla pressionada no construtor de cesta.

    Args:
        tecla: Tecla pressionada.
        estado: Estado do construtor.
        df_base: DataFrame base.
        cidades: Lista de cidades disponíveis.
        altura: Altura da área de conteúdo.

    Returns:
        "GERAR" se deve gerar a cesta, None caso contrário.
    """
    if tecla == "ESC":
        if estado.filtro:
            estado.filtro = ""
            return None
        return None

    t_up = tecla.upper() if len(tecla) == 1 else tecla

    # F10: alterna a visibilidade da barra de menu (não desenha outra)
    if tecla == "F10":
        from ..tui.menu_barra import alternar_barra_menu
        alternar_barra_menu()
        return None

    # Menu de contexto
    cat = indice_menu_por_tecla(t_up, _MODULO)
    if cat is None and t_up == "F":
        cat = 0
    if cat is None and t_up.startswith("ALT_"):
        return None

    if cat is not None:
        from ..tui.menus import (
            menu_dropdown_ancorado_tui,
            executar_acao_menu_comum,
        )
        acao = menu_dropdown_ancorado_tui(
            _MODULO, cat, habilitadas=ACOES_MENU_CESTA
        )
        tecla_pendente = executar_acao_menu_comum(acao, _MODULO)
        if tecla_pendente:
            return _tratar_tecla_construtor(
                tecla_pendente, estado, df_base, cidades, altura
            )
        return None

    # Atalhos
    if t_up == "U":
        opcoes = obter_opcoes_uf(True, "TODAS AS UFs (BRASIL)")
        esc = abrir_droplist_popup("FILTRAR POR UF", opcoes, estado.uf_atual)
        if esc is not None:
            estado.uf_atual = _EstadoCesta._normalizar_uf(esc)
            estado.filtro = ""
            estado.cursor = 0

    elif t_up in ("A", "F2"):
        opts = [
            (f"{c['uf']}{_SEPARADOR_CHAVE}{c['mun']}", f"{c['nome']} - {c['uf']}")
            for c in cidades if c["chave"] not in estado.conjunto
        ]
        esc = abrir_droplist_popup("ADICIONAR MUNICÍPIO", opts, "")
        if esc is not None:
            try:
                uf_e, mun_e = str(esc).split(_SEPARADOR_CHAVE, 1)
                estado.adicionar((uf_e, mun_e))
            except ValueError:
                pass

    elif t_up == "T":
        _adicionar_top5(estado, df_base)

    elif t_up in ("R", "DEL"):
        if cidades and 0 <= estado.cursor < len(cidades):
            chave = cidades[estado.cursor]["chave"]
            if chave in estado.conjunto:
                estado.remover(chave)
        else:
            estado.remover_ultima()
        estado.cursor = max(0, min(estado.cursor, max(0, len(cidades) - 1)))

    elif tecla == " ":
        if cidades:
            chave = cidades[estado.cursor]["chave"]
            if chave in estado.conjunto:
                estado.remover(chave)
            else:
                estado.adicionar(chave)

    elif tecla == "/":
        from ..pesquisa_global import pesquisa_global_tui
        pesquisa_global_tui(df_base)

    elif t_up in ("G", "ENTER"):
        if len(estado.cesta) >= _MINIMO_CIDADES:
            return "GERAR"
        alerta_tui(
            "COMPARADOR",
            "CESTA INCOMPLETA",
            [
                f"Selecione pelo menos {_MINIMO_CIDADES} municípios. "
                "Use [ESPAÇO] para marcar, [A]/[F2] para adicionar "
                "via Droplist, ou [T]op 5."
            ],
        )

    elif tecla == "UP" and cidades:
        estado.cursor = (estado.cursor - 1) % len(cidades)

    elif tecla == "DOWN" and cidades:
        estado.cursor = (estado.cursor + 1) % len(cidades)

    elif tecla == "PGUP" and cidades:
        estado.cursor = max(0, estado.cursor - altura)

    elif tecla == "PGDN" and cidades:
        estado.cursor = min(len(cidades) - 1, estado.cursor + altura)

    elif tecla == "HOME":
        estado.cursor = 0

    elif tecla == "END" and cidades:
        estado.cursor = len(cidades) - 1

    return None


# ---------------------------------------------------------------------------
# Construtor de cesta (tela própria)
# ---------------------------------------------------------------------------

def construir_cesta_cidades_tui(
    df_base: pd.DataFrame,
    minimo: int = _MINIMO_CIDADES,
    maximo: int = _MAXIMO_CIDADES,
    uf_inicial: str = "",
) -> list[tuple[str, str]] | None:
    """Tela interativa para montar a cesta de municípios.

    Atalhos:
        - [U] UF
        - [A]/[F2] adicionar (Droplist com filtro ao vivo)
        - [T] Top 5
        - [R]/[DEL] remover
        - [G]/[ENTER] gerar
        - [ESPAÇO] marcar/desmarcar destacado
        - [/] busca global
        - [ESC] voltar

    Args:
        df_base: DataFrame base filtrado.
        minimo: Número mínimo de cidades na cesta.
        maximo: Número máximo de cidades na cesta.
        uf_inicial: UF inicial (opcional).

    Returns:
        Lista de chaves (UF, MUNICIPIO) selecionadas, ou None se cancelado.
    """
    if df_base.empty:
        return None

    ufs = (
        sorted(
            str(x).strip().upper()
            for x in df_base["UF"].dropna().unique()
        )
        if "UF" in df_base
        else []
    )

    estado = _EstadoCesta(uf_inicial)
    if estado.uf_atual not in ufs:
        estado.uf_atual = ""

    tecla_pendente: str | None = None

    while True:
        larg_t, alt_t = obter_dimensoes_terminal()
        cidades = _listar_cidades_disponiveis(df_base, estado.uf_atual, estado.filtro)
        estado.cursor = max(0, min(estado.cursor, len(cidades) - 1)) if cidades else 0

        altura = max(6, min(12, alt_t - 12))
        linhas = _renderizar_construtor_cesta(estado, df_base, cidades)

        canvas = desenhar_desktop_base(
            larg_t, alt_t,
            msg_rodape=(
                "Cesta: ↑/↓ navega | ESPAÇO seleciona | A/F2 adiciona | "
                "R remove | U UF | T Top 5 | G/ENTER gera | / busca global"
            ),
        )
        sobrepor_janela_no_canvas(
            canvas, larg_t, alt_t, linhas, min(max(70, larg_t - 8), 100), sombra=True
        )
        renderizar_quadro_completo(canvas)

        if tecla_pendente is not None:
            tecla, tecla_pendente = tecla_pendente, None
        else:
            tecla = ler_tecla()

        if tecla == "IGNORE":
            continue

        resultado = _tratar_tecla_construtor(
            tecla, estado, df_base, cidades, altura
        )
        if resultado == "GERAR":
            return list(estado.cesta)

        if tecla == "ESC" and not estado.filtro:
            return None


# ---------------------------------------------------------------------------
# Helpers para comparador
# ---------------------------------------------------------------------------

def _opcoes_operadoras(vals: dict[str, str], df_erbs: pd.DataFrame) -> list[tuple[str, str]]:
    """Gera opções de operadoras para o formulário.

    Args:
        vals: Valores atuais do formulário.
        df_erbs: DataFrame completo de ERBs.

    Returns:
        Lista de tuplas (valor, rótulo).
    """
    base = df_erbs
    uf = vals.get("uf", "")
    if uf:
        base = base[base["UF"] == uf]

    ops = sorted(str(x) for x in base["OPERADORA"].dropna().unique())
    return [("", "TODAS AS OPERADORAS")] + [(x, x) for x in ops]


def _opcoes_tecnologias(vals: dict[str, str], df_erbs: pd.DataFrame) -> list[tuple[str, str]]:
    """Gera opções de tecnologias para o formulário.

    Args:
        vals: Valores atuais do formulário.
        df_erbs: DataFrame completo de ERBs.

    Returns:
        Lista de tuplas (valor, rótulo).
    """
    base = df_erbs
    uf = vals.get("uf", "")
    op = vals.get("operadora", "")

    if uf:
        base = base[base["UF"] == uf]
    if op:
        base = base[base["OPERADORA"] == op]

    tecs = sorted(str(x) for x in base["TECNOLOGIA"].dropna().unique())
    return [("", "TODAS AS TECNOLOGIAS")] + [(x, x) for x in tecs]


def _montar_quadro_comparativo(
    df_f: pd.DataFrame,
    selecionadas: list[tuple[str, str]],
) -> pd.DataFrame:
    """Monta quadro comparativo das cidades selecionadas.

    Args:
        df_f: DataFrame filtrado com as cidades selecionadas.
        selecionadas: Lista de chaves (UF, MUNICIPIO) na ordem desejada.

    Returns:
        DataFrame com quadro comparativo.
    """
    ordem = {ch: i for i, ch in enumerate(selecionadas)}

    linhas: list[dict[str, Any]] = []

    for (uf, mun), grp in df_f.groupby(["UF", "MUNICIPIO"], sort=False):
        nome_limpo = re.sub(r"\s*-\s*[A-Za-z]{2}$", "", mun).upper()
        cont_op = grp.groupby("OPERADORA")["NUM_ESTACAO"].nunique().to_dict()
        total = grp["ID_ERB"].nunique()
        resumo_tec, _ = diagnosticar_melhor_cobertura(grp)

        linhas.append({
            "ORDEM": ordem.get((uf, mun), 999),
            "UF": uf,
            "MUNICIPIO_ORIG": mun,
            "MUNICÍPIO": nome_limpo[:20],
            "CLARO": cont_op.get("CLARO", 0),
            "VIVO": cont_op.get("VIVO", 0),
            "TIM": cont_op.get("TIM", 0),
            "OUTRAS": sum(
                v for k, v in cont_op.items()
                if k not in ["CLARO", "VIVO", "TIM"]
            ),
            "TOTAL": total,
            "MAIOR 5G": resumo_tec["5G"][:14],
            "MAIOR 4G": resumo_tec["4G"][:14],
            "MAIOR 3G": resumo_tec["3G"][:14],
        })

    return (
        pd.DataFrame(linhas)
        .sort_values("ORDEM")
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------------
# Comparador principal
# ---------------------------------------------------------------------------

def comparador_cidades(df_erbs: pd.DataFrame) -> None:
    """Fluxo: formulário de filtros → construtor de cesta → quadro comparativo.

    Args:
        df_erbs: DataFrame completo de ERBs.
    """
    # 1) Formulário de filtros
    res = formulario_tui(
        modulo=_MODULO,
        titulo_janela="4. COMPARADOR LADO A LADO DE MUNICÍPIOS",
        campos=[
            {
                "nome": "uf",
                "rotulo": "UF inicial",
                "tipo": "droplist",
                "largura": 28,
                "padrao": "",
                "opcoes": obter_opcoes_uf(True, "TODAS AS UFs"),
                "dica": "Opcional. Depois use [U] para trocar a UF no construtor.",
            },
            {
                "nome": "operadora",
                "rotulo": "Operadora",
                "tipo": "droplist",
                "largura": 30,
                "padrao": "",
                "opcoes": lambda vals: _opcoes_operadoras(vals, df_erbs),
                "dica": "Filtro opcional da base.",
            },
            {
                "nome": "tecnologia",
                "rotulo": "Tecnologia",
                "tipo": "droplist",
                "largura": 30,
                "padrao": "",
                "opcoes": lambda vals: _opcoes_tecnologias(vals, df_erbs),
                "dica": "Filtro opcional da base.",
            },
        ],
        instrucoes_topo=[
            "Após confirmar, o Construtor de Cesta permite montar a comparação.",
            "Atalhos: [U] UF | [A]/[F2] adicionar | [T] Top 5 | [R]/[DEL] remover "
            "| [G]/[ENTER] gerar.",
        ],
    )

    if not res:
        return

    # 2) Filtra base
    df_base = df_erbs.copy()
    if res.get("uf"):
        df_base = df_base[df_base["UF"] == res["uf"]]
    if res.get("operadora"):
        df_base = df_base[df_base["OPERADORA"] == res["operadora"]]
    if res.get("tecnologia"):
        df_base = df_base[df_base["TECNOLOGIA"] == res["tecnologia"]]

    if df_base.empty:
        alerta_tui(
            "COMPARADOR",
            "NENHUM REGISTRO",
            ["Os filtros escolhidos não retornaram registros."],
        )
        return

    # 3) Construtor de cesta
    selecionadas = construir_cesta_cidades_tui(
        df_base, minimo=_MINIMO_CIDADES, maximo=_MAXIMO_CIDADES, uf_inicial=res.get("uf", "")
    )

    if not selecionadas:
        return

    # 4) Filtra cidades selecionadas
    mask = pd.Series(False, index=df_base.index)
    for uf_c, mun_orig in selecionadas:
        mask |= (df_base["UF"] == uf_c) & (df_base["MUNICIPIO"] == mun_orig)

    df_f = df_base.loc[mask].copy()

    if df_f.empty:
        alerta_tui(
            "COMPARADOR",
            "SELEÇÃO SEM DADOS",
            ["As cidades selecionadas não possuem registros após os filtros."],
        )
        return

    # 5) Monta quadro comparativo
    df_comp = _montar_quadro_comparativo(df_f, selecionadas)

    cols = [
        "UF", "MUNICÍPIO", "CLARO", "VIVO", "TIM", "OUTRAS", "TOTAL",
        "MAIOR 5G", "MAIOR 4G", "MAIOR 3G",
    ]
    cab, itens_tab = dataframe_para_itens_tui(
        df_comp[cols], selecionavel=True
    )

    for i, it in enumerate(itens_tab):
        it["dados"] = (
            df_comp.iloc[i]["UF"],
            df_comp.iloc[i]["MUNICIPIO_ORIG"],
            df_comp.iloc[i]["MUNICÍPIO"],
        )

    # 6) Loop do navegador
    while True:
        acao, dados, _, _ = navegador_tui(
            modulo=_MODULO,
            titulo_janela=(
                "QUADRO COMPARATIVO DE MUNICÍPIOS ([ENTER] ABRE A CIDADE)"
            ),
            itens_conteudo=itens_tab,
            colunas_fixas_tabela=("   " + cab) if cab else None,
            comandos_rodape=[
                "[ENTER] Inspecionar | [6] Exportar CSV | [/] Filtro ao vivo | "
                "[ESC/0] Voltar"
            ],
            teclas_rapidas={"6"},
            dica_teclas=(
                "↑/↓=Mover | ENTER=Abrir Cidade | /=Filtro | "
                "6=CSV | ESC/0=Voltar"
            ),
        )

        if acao == "SELECT" and dados:
            uf_c, mun_orig, nome_c = dados
            grp = df_f[
                (df_f["UF"] == uf_c) & (df_f["MUNICIPIO"] == mun_orig)
            ]
            painel_interativo_municipio(grp, nome_c, uf_c)

        elif acao == "KEY" and dados == "6":
            nome_arq = (
                f"comparativo_cidades_"
                f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )
            salvar_csv_tui(df_comp[cols], nome_arq, "SALVAR QUADRO COMPARATIVO")

        else:
            break