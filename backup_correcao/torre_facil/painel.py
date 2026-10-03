"""Hub de inspeção de municípios, métricas de operadora e navegação.

Este módulo é usado pelos 8 módulos de negócio (raio_x, explorador,
comparador, chips, rodovias, avancada, kml, sobre, faixas).

Arquitetura:
    - ``painel_interativo_municipio``: painel principal com 4 visões
    - ``abrir_inspecao_detalhada_erbs``: inspeção detalhada de ERBs
    - ``selecionar_bairro_interativo``: seleção de bairro
    - ``calcular_metricas_operadoras``: métricas por operadora
    - ``diagnosticar_melhor_cobertura``: diagnóstico de cobertura
    - ``dataframe_para_itens_tui``: conversão DataFrame → itens TUI
    - ``salvar_csv_tui``: exportação CSV
    - ``filtrar_municipios_exatos``: filtro de municípios
    - ``filtrar_erbs_rodovia``: filtro de rodovias
"""
from __future__ import annotations

import datetime
import logging
import os
import re
import webbrowser
from typing import Any

import pandas as pd

from .config import ORDEM_TEC
from .dicionarios import DICIONARIOS
from .estado import INFO
from .texto import (
    normalizar_texto,
    formatar_lista_tec,
    RE_NAO_ALFANUM,
)
from .tui.cores import (
    CAIXA_TEXTO, CAIXA_TITULO, CAIXA_BORDA,
    BARRA_VERDE, BARRA_ALERTA,
)
from .tui.janelas import (
    criar_item_tui,
    alerta_tui,
    caixa_notificacao_tui,
    abrir_droplist_popup,
    formulario_tui,
)
from .tui.motor import obter_dimensoes_terminal
from .tui.navegador import (
    navegador_tui,
    mostrar_podio_completo_tui,
    obter_estilo_posicao,
    gerar_barra_sinal,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Larguras fixas das colunas da Visão [1]
_LARG_OP = 13
_LARG_CFG = 13
_LARG_ERBS = 5
_LARG_BAIRROS = 8
_ESPACO = "   "

# Ações de inspeção
_ACAO_MAPS = "M"
_ACAO_PODIO = "P"
_ACAO_CSV = "6"


# ---------------------------------------------------------------------------
# Google Maps
# ---------------------------------------------------------------------------

def _abrir_maps_uma(lat: float, lon: float) -> bool:
    """Abre Google Maps para uma coordenada específica.

    Args:
        lat: Latitude.
        lon: Longitude.

    Returns:
        True se abriu com sucesso, False caso contrário.
    """
    try:
        url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        webbrowser.open(url, new=2)
        return True
    except Exception as e:
        logger.exception("Falha ao abrir Google Maps")
        INFO.ultimo_erro = f"Falha ao abrir Google Maps: {type(e).__name__}: {e}"
        return False


def _extrair_coords_da_linha(registro: dict[str, Any]) -> tuple[float | None, float | None]:
    """Extrai coordenadas de um registro.

    Args:
        registro: Dicionário com dados do registro.

    Returns:
        Tupla (lat, lon) ou (None, None) se inválido.
    """
    lat = registro.get("LAT_NUM")
    lon = registro.get("LON_NUM")

    if (lat is not None and lon is not None
            and not pd.isna(lat) and not pd.isna(lon)):
        return float(lat), float(lon)

    gps = str(registro.get("GPS", ""))
    if "," in gps and "sem" not in gps.lower():
        try:
            a, b = gps.split(",", 1)
            return float(a.strip()), float(b.strip())
        except ValueError:
            return None, None

    return None, None


# ---------------------------------------------------------------------------
# Filtro e seleção
# ---------------------------------------------------------------------------

def filtrar_municipios_exatos(df_atual: pd.DataFrame, mun_input: str) -> pd.DataFrame:
    """Filtra DataFrame por municípios exatos (com sugestões de similares).

    Args:
        df_atual: DataFrame completo.
        mun_input: Input do usuário (pode ter vírgulas para múltiplos).

    Returns:
        DataFrame filtrado.
    """
    termos = [normalizar_texto(m) for m in mun_input.split(",") if m.strip()]
    df_resultado = df_atual[df_atual["MUNICIPIO_NORM"].isin(termos)]

    encontrados = set(df_resultado["MUNICIPIO_NORM"].unique())
    faltando = [t for t in termos if t not in encontrados]

    if faltando:
        for termo in faltando:
            parecidos = sorted(
                df_atual[df_atual["MUNICIPIO_NORM"]
                         .str.contains(re.escape(termo), na=False)]
                ["MUNICIPIO_LIMPO"].unique()
            )
            if parecidos:
                op_sug = [(p, p) for p in parecidos[:40]]
                esc = abrir_droplist_popup(
                    f"NÃO ACHOU '{termo}'. ESCOLHA SIMILAR:", op_sug
                )
                if esc:
                    extra = df_atual[df_atual["MUNICIPIO_LIMPO"] == esc]
                    df_resultado = pd.concat(
                        [df_resultado, extra], ignore_index=True
                    )
            else:
                alerta_tui(
                    "VALIDAÇÃO DE MUNICÍPIO",
                    "MUNICÍPIO NÃO LOCALIZADO",
                    [f"Nenhum município encontrado para '{termo}'."],
                )

    return df_resultado


def selecionar_bairro_interativo(
    df_cidade: pd.DataFrame, nome_cidade: str
) -> pd.DataFrame | None:
    """Permite ao usuário selecionar um bairro interativamente.

    Args:
        df_cidade: DataFrame da cidade.
        nome_cidade: Nome da cidade.

    Returns:
        DataFrame filtrado pelo bairro, ou None se cancelado.
    """
    contagem = (df_cidade.groupby("BAIRRO")["ID_ERB"]
                .nunique().sort_values(ascending=False))
    lista = list(contagem.index)

    itens = _montar_itens_bairros(df_cidade, contagem, lista)

    while True:
        acao, valor, _, _ = navegador_tui(
            modulo=f"CATÁLOGO DE BAIRROS - {nome_cidade}",
            titulo_janela=(f"SELECIONE UM BAIRRO COM ↑/↓ E ENTER "
                           f"({len(itens)} LOCAIS)"),
            itens_conteudo=itens,
            colunas_fixas_tabela=(
                f"   {'#':<5} {'BAIRRO / DISTRITO':<34} │ "
                f"{'ERBs':<10} │ {'TECNOLOGIAS':<15} │ OPERADORAS"
            ),
            comandos_rodape=[
                "[ENTER] Abrir Bairro   |   [D] Filtrar via Droplist   |   "
                "[ESC/0] Voltar"
            ],
            teclas_rapidas={"D"},
            dica_teclas=("↑/↓=Mover | PgUp/PgDn=Página | "
                         "ENTER=Selecionar | D=Pesquisar | ESC=Voltar"),
        )

        if acao == "SELECT" and valor:
            return df_cidade[df_cidade["BAIRRO"] == valor].copy()

        if acao == "KEY" and valor == "D":
            ops = [(b, f"{b} ({contagem[b]} ERBs)") for b in lista]
            esc = abrir_droplist_popup(
                f"BAIRROS DE {nome_cidade} (DIGITE P/ FILTRAR)", ops
            )
            if esc:
                return df_cidade[df_cidade["BAIRRO"] == esc].copy()

        return None


def _montar_itens_bairros(
    df_cidade: pd.DataFrame,
    contagem: pd.Series,
    lista: list[str],
) -> list[dict[str, Any]]:
    """Monta itens para seleção de bairro.

    Args:
        df_cidade: DataFrame da cidade.
        contagem: Contagem de ERBs por bairro.
        lista: Lista de bairros.

    Returns:
        Lista de itens para navegador.
    """
    itens: list[dict[str, Any]] = []

    for idx, b in enumerate(lista, start=1):
        qtd = contagem[b]
        tecs = formatar_lista_tec(
            ",".join(df_cidade[df_cidade["BAIRRO"] == b]["TECS_RAW"]).split(",")
        )
        ops = ", ".join(sorted(
            df_cidade[df_cidade["BAIRRO"] == b]["OPERADORA"].unique()
        ))
        linha = (f"[{idx:3d}] {b:<34} │ {qtd:3d} ERB(s) │ "
                 f"TECS: {tecs:<9} │ {ops}")
        itens.append(
            criar_item_tui(linha, CAIXA_TEXTO, "esq",
                           selecionavel=True, dados=b)
        )

    return itens


# ---------------------------------------------------------------------------
# Exportação CSV
# ---------------------------------------------------------------------------

def salvar_csv_tui(
    df_dados: pd.DataFrame,
    padrao_arq: str,
    titulo_modal: str = "EXPORTAR RELATÓRIO PARA CSV",
) -> None:
    """Exporta DataFrame para CSV com confirmação TUI.

    Args:
        df_dados: DataFrame a exportar.
        padrao_arq: Nome padrão do arquivo.
        titulo_modal: Título do modal de confirmação.
    """
    conf = caixa_notificacao_tui(
        modulo="EXPORTAR ARQUIVO",
        titulo=titulo_modal,
        linhas_mensagem=[
            f"Deseja exportar os {len(df_dados)} registros atuais para CSV?",
            f"Nome sugerido: {padrao_arq}",
        ],
        botoes=[
            ("S", "Sim, Salvar CSV", "SIM"),
            ("N", "Não, Cancelar", "NAO"),
        ],
    )

    if conf != "SIM":
        return

    res = formulario_tui(
        modulo="EXPORTAÇÃO CSV",
        titulo_janela=titulo_modal,
        campos=[{
            "nome": "arquivo", "rotulo": "Nome do Arquivo CSV",
            "largura": 42, "padrao": padrao_arq, "maiusculo": False,
        }],
        instrucoes_topo=["Confirme o nome do arquivo ou altere abaixo:"],
    )

    if not (res and res["arquivo"]):
        return

    nome_arq = res["arquivo"]
    if not nome_arq.lower().endswith(".csv"):
        nome_arq += ".csv"

    df_dados.to_csv(nome_arq, sep=";", index=False, encoding="utf-8-sig")

    alerta_tui(
        "EXPORTAÇÃO CONCLUÍDA", "ARQUIVO SALVO COM SUCESSO",
        [f"Caminho: {os.path.abspath(nome_arq)}"],
        cor_titulo=BARRA_VERDE,
    )


# ---------------------------------------------------------------------------
# Filtros de rodovia
# ---------------------------------------------------------------------------

def filtrar_erbs_rodovia(df_erbs: pd.DataFrame, entrada: str) -> pd.DataFrame:
    """Filtra ERBs por rodovia (BR-xxx, RS-xxx, etc.).

    Args:
        df_erbs: DataFrame completo de ERBs.
        entrada: Entrada do usuário (ex: "BR-101", "101", "RS-122").

    Returns:
        DataFrame filtrado.
    """
    limpo = normalizar_texto(entrada)

    if limpo.isdigit():
        limpo = f"BR-{limpo}"

    match = re.match(r"^([A-Z]{2,4})[\s\-]*0*(\d+)$", limpo)

    anti_urbano = (r"(?<!QD\s)(?<!QD\-\s)(?<!QUADRA\s)(?<!LOTE\s)"
                   r"(?<!LT\s)(?<!RUA\s)(?<!AV\s)(?<!BLOCO\s)(?<!CONJ\s)")

    ufs_validas = set(DICIONARIOS.get("ufs_brasil", []))
    mapa_br = DICIONARIOS.get("mapa_ufs_br", {})

    df_busca = df_erbs.copy()

    if match:
        prefixo = match.group(1)
        num_sem_zero = match.group(2).lstrip("0") or "0"
        num_3 = num_sem_zero.zfill(3)

        if prefixo == "BR":
            if num_3 in mapa_br:
                df_busca = df_busca[df_busca["UF"].isin(set(mapa_br[num_3]))]
            padrao = rf"{anti_urbano}\bBR[\s\-\.]*0*{num_sem_zero}\b"
        else:
            uf_det = None
            if prefixo in ufs_validas:
                uf_det = prefixo
            elif len(prefixo) == 3 and prefixo.startswith("E") and prefixo[1:] in ufs_validas:
                uf_det = prefixo[1:]
            elif len(prefixo) == 3 and prefixo[:2] in ufs_validas:
                uf_det = prefixo[:2]

            if uf_det:
                df_busca = df_busca[df_busca["UF"] == uf_det]
                padrao = (rf"{anti_urbano}\b(?:E?{uf_det}[A-Z]?|"
                          rf"RODOVIA\s+{uf_det})[\s\-\.]*0*{num_sem_zero}\b")
            else:
                padrao = rf"{anti_urbano}\b{prefixo}[\s\-\.]*0*{num_sem_zero}\b"
    else:
        padrao = re.escape(limpo)

    df_res = df_busca[
        df_busca["ENDERECO_BUSCA"].str.contains(padrao, regex=True, na=False)
    ].copy()

    if not df_res.empty and match:
        num = match.group(2).lstrip("0") or "0"
        falso = (rf"\b(?:QD|QUADRA|Q\.|ARSO|ARNE|ACSU|ARSE|ASR|LOTE|LT|"
                 rf"APTO|SALA)[\s\-\.]*0*{num}\b")
        tem_rod = rf"\b(?:RODOVIA|ROD\.|BR[\s\-]*0*{num}|KM\s*\d+)\b"

        m_q = df_res["ENDERECO_BUSCA"].str.contains(falso, regex=True, na=False)
        m_r = df_res["ENDERECO_BUSCA"].str.contains(tem_rod, regex=True, na=False)

        df_res = df_res[~(m_q & ~m_r)]

    return df_res


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------

def calcular_metricas_operadoras(
    df_recorte: pd.DataFrame, perfil_uso: str = "2"
) -> pd.DataFrame:
    """Calcula métricas de operadoras para um recorte.

    Args:
        df_recorte: DataFrame filtrado.
        perfil_uso: Perfil de uso ("1"=velocidade, "2"=geral, "3"=mobilidade).

    Returns:
        DataFrame com métricas por operadora.
    """
    if df_recorte.empty:
        return pd.DataFrame()

    total_local = df_recorte["ID_ERB"].nunique()
    stats: list[dict[str, Any]] = []

    for op, grp in df_recorte.groupby("OPERADORA"):
        total_op = grp["NUM_ESTACAO"].nunique()
        erbs_5g = grp[grp["TECS_RAW"].str.contains("5", na=False)]["NUM_ESTACAO"].nunique()
        erbs_4g = grp[grp["TECS_RAW"].str.contains("L", na=False)]["NUM_ESTACAO"].nunique()
        erbs_3g = grp[grp["TECS_RAW"].str.contains("H", na=False)]["NUM_ESTACAO"].nunique()
        erbs_2g = grp[grp["TECS_RAW"].str.contains("E", na=False)]["NUM_ESTACAO"].nunique()
        bairros = grp["BAIRRO"].nunique()
        tecs_str = formatar_lista_tec(",".join(grp["TECS_RAW"]).split(","))

        if perfil_uso == "1":
            score = (erbs_5g * 120) + (erbs_4g * 45) + (total_op * 25) + (bairros * 10)
        elif perfil_uso == "3":
            score = (bairros * 70) + (erbs_4g * 60) + (erbs_3g * 35) \
                    + (erbs_2g * 25) + (total_op * 40)
        else:
            score = (total_op * 80) + (erbs_4g * 55) + (erbs_5g * 45) \
                    + (bairros * 30) + (erbs_3g * 10)

        stats.append({
            "OPERADORA": op, "TOTAL": total_op,
            "SHARE": (total_op / total_local * 100) if total_local > 0 else 0.0,
            "5G": erbs_5g, "4G": erbs_4g, "3G": erbs_3g, "2G": erbs_2g,
            "BAIRROS": bairros, "TECS": tecs_str, "SCORE": max(1, score),
        })

    df_s = pd.DataFrame(stats)
    max_score = df_s["SCORE"].max()
    teto = 9.8 if df_s["5G"].max() > 0 else (9.2 if df_s["4G"].max() > 0 else 8.0)
    df_s["NOTA"] = df_s["SCORE"].apply(
        lambda s: round((s / max_score) * teto, 1) if max_score > 0 else 0.0
    )

    return df_s


def diagnosticar_melhor_cobertura(
    df_recorte: pd.DataFrame, largura_linha: int = 94
) -> tuple[dict[str, str], list[str]]:
    """Diagnostica melhor cobertura por tecnologia.

    Args:
        df_recorte: DataFrame filtrado.
        largura_linha: Largura máxima da linha de diagnóstico.

    Returns:
        Tupla (resumo_tecnologias, linhas_diagnostico).
    """
    df_s = calcular_metricas_operadoras(df_recorte)

    if df_s.empty:
        INFO.podio_completo = []
        INFO.podio_contexto = ""
        return {"GERAL": "-", "5G": "-", "4G": "-", "3G": "-"}, []

    def lider(col_tec: str) -> str:
        mx = df_s[col_tec].max()
        if mx == 0:
            return "Sem cobertura"
        l = df_s[df_s[col_tec] == mx]["OPERADORA"].tolist()
        return f"{'/'.join(l)} ({mx})"

    resumo = {"GERAL": lider("TOTAL"), "5G": lider("5G"),
              "4G": lider("4G"), "3G": lider("3G")}

    df_ativos = (df_s[df_s["TOTAL"] > 0]
                 .sort_values(by=["TOTAL", "BAIRROS"], ascending=False)
                 .reset_index(drop=True))

    ranking = [f"{i + 1}º {row['OPERADORA']} ({int(row['TOTAL'])} ERBs)"
               for i, row in df_ativos.iterrows()]

    INFO.podio_completo = ranking
    INFO.podio_contexto = "COLOCAÇÕES DAS OPERADORAS"

    if not ranking:
        return resumo, ["SEM OPERADORAS ATIVAS"]

    # Monta linha de diagnóstico
    top3 = ranking[:3]
    resto = len(ranking) - len(top3)
    separador = "  │  "
    sufixo = f"  │  +{resto} operadora(s) [P] ranking completo" if resto > 0 else ""

    partes = list(top3)
    linha = separador.join(partes) + sufixo

    if len(linha) > largura_linha and resto > 0:
        sufixo = f"  │  +{resto} [P]"
        linha = separador.join(partes) + sufixo

    removidos = 0
    while len(linha) > largura_linha and partes:
        partes.pop()
        removidos += 1
        if resto > 0 or removidos > 0:
            total_ocultas = resto + removidos
            sufixo = (f"  │  +{total_ocultas} [P]" if partes
                      else f"+{total_ocultas} [P]")
        else:
            sufixo = ""
        linha = (separador.join(partes) + sufixo) if partes else sufixo.lstrip("  │")

    if not linha.strip():
        linha = "SEM OPERADORAS ATIVAS"

    return resumo, [linha]


# ---------------------------------------------------------------------------
# DataFrame → itens
# ---------------------------------------------------------------------------

def dataframe_para_itens_tui(
    df_tab: pd.DataFrame, selecionavel: bool = False
) -> tuple[str | None, list[dict[str, Any]]]:
    """Converte DataFrame em itens para navegador TUI.

    Args:
        df_tab: DataFrame a converter.
        selecionavel: Se os itens são selecionáveis.

    Returns:
        Tupla (cabecalho, itens).
    """
    larg, _ = obter_dimensoes_terminal()
    miolo = max(20, larg - 10)

    if df_tab.empty:
        return None, [
            criar_item_tui(
                "NENHUM REGISTRO ENCONTRADO PARA OS PARÂMETROS INFORMADOS.",
                CAIXA_TITULO, "centro",
            )
        ]

    max_col = max(12, miolo // max(1, len(df_tab.columns)))
    linhas = df_tab.to_string(index=False, max_colwidth=max_col).split("\n")
    cabecalho = linhas[0]

    itens: list[dict[str, Any]] = []
    for idx_df, ln in enumerate(linhas[1:]):
        dado = df_tab.iloc[idx_df].to_dict() if idx_df < len(df_tab) else None
        itens.append(
            criar_item_tui(ln, CAIXA_TEXTO, "esq",
                           selecionavel=selecionavel, dados=dado)
        )

    return cabecalho, itens


# ---------------------------------------------------------------------------
# Construtores de visão
# ---------------------------------------------------------------------------

def _truncar(txt: Any, largura: int) -> str:
    """Trunca texto para largura máxima.

    Args:
        txt: Texto a truncar.
        largura: Largura máxima.

    Returns:
        Texto truncado.
    """
    txt = str(txt)
    if len(txt) <= largura:
        return txt
    if largura <= 1:
        return txt[:largura]
    return txt[:largura - 1] + "…"


def _montar_cabecalho_visao1(largura_bairros: int) -> str:
    """Monta cabeçalho da Visão [1].

    Args:
        largura_bairros: Largura da coluna de bairros.

    Returns:
        String do cabeçalho.
    """
    return (
        f"   {'OPERADORA':<{_LARG_OP}}{_ESPACO} "
        f"{'CONFIG.':<{_LARG_CFG}}{_ESPACO} "
        f"{'ERBs':>{_LARG_ERBS}}{_ESPACO} "
        f"{'BAIRROS':>{_LARG_BAIRROS}}   "
        f"{'BAIRROS ATENDIDOS':<{largura_bairros}} "
    )


def _linha_tabela(
    op: str, cfg: str, erbs: int, bairros: int, bairros_txt: str,
    largura_bairros: int, incluir_marcador: bool = False
) -> str:
    """Monta uma linha da tabela.

    Args:
        op: Operadora.
        cfg: Configuração.
        erbs: Número de ERBs.
        bairros: Número de bairros.
        bairros_txt: Texto dos bairros.
        largura_bairros: Largura da coluna de bairros.
        incluir_marcador: Se inclui marcador de seleção.

    Returns:
        String da linha.
    """
    op_s = _truncar(op if op else "", _LARG_OP).ljust(_LARG_OP)
    cfg_s = _truncar(cfg, _LARG_CFG).ljust(_LARG_CFG)
    erbs_s = str(int(erbs)).rjust(_LARG_ERBS)
    bairros_s = str(int(bairros)).rjust(_LARG_BAIRROS)
    bairros_txt_s = _truncar(bairros_txt, largura_bairros).ljust(largura_bairros)

    prefixo = "► " if incluir_marcador else "  "

    return (
        f"{prefixo}{op_s}{_ESPACO}"
        f"{cfg_s}{_ESPACO}"
        f"{erbs_s}{_ESPACO}"
        f"{bairros_s}  "
        f"{bairros_txt_s}"
    )


def _linha_divisoria(largura_total: int) -> str:
    """Monta linha divisória.

    Args:
        largura_total: Largura total.

    Returns:
        String da divisória.
    """
    return "   " + "─" * (largura_total - 3)


def construir_itens_por_operadora(
    df_cidade: pd.DataFrame
) -> tuple[str, list[dict[str, Any]], pd.Series]:
    """Visão [1] — tabela agrupada por operadora.

    Args:
        df_cidade: DataFrame da cidade.

    Returns:
        Tupla (cabecalho, itens, totais_op).
    """
    larg_term, _ = obter_dimensoes_terminal()
    largura_total = max(78, larg_term - 6)
    largura_bairros = max(
        24,
        largura_total - 3
        - (_LARG_OP + len(_ESPACO))
        - (_LARG_CFG + len(_ESPACO))
        - (_LARG_ERBS + len(_ESPACO))
        - (_LARG_BAIRROS + 2)
    )

    cabecalho = _montar_cabecalho_visao1(largura_bairros)
    itens: list[dict[str, Any]] = []

    totais_op = (df_cidade.groupby("OPERADORA")["ID_ERB"].nunique()
                 .sort_values(ascending=False))

    primeira_op = True

    for op, total_op in totais_op.items():
        grupo_op = df_cidade[df_cidade["OPERADORA"] == op]
        bairros_tot = grupo_op["BAIRRO"].nunique()
        tecs_tot = formatar_lista_tec(",".join(grupo_op["TECS_RAW"]).split(","))

        bairros_exemplos = ", ".join(sorted(grupo_op["BAIRRO"].unique())[:4])
        if grupo_op["BAIRRO"].nunique() > 4:
            bairros_exemplos += "…"

        if not primeira_op:
            itens.append(criar_item_tui(
                _linha_divisoria(largura_total + 6),
                CAIXA_BORDA, "esq", selecionavel=False,
            ))
        primeira_op = False

        linha_total = _linha_tabela(
            op=op, cfg="TOTAL", erbs=total_op,
            bairros=bairros_tot, bairros_txt=bairros_exemplos,
            largura_bairros=largura_bairros,
        )
        itens.append(criar_item_tui(
            linha_total, CAIXA_TITULO, "esq",
            selecionavel=True,
            dados={"tipo": "OPERADORA", "operadora": op},
        ))

        resumo_cfg = (grupo_op.groupby("TECNOLOGIA", as_index=False)
                      .agg(QTD_ERBS=("NUM_ESTACAO", "count"),
                           QTD_BAIRROS=("BAIRRO", "nunique"))
                      .sort_values(by=["QTD_ERBS", "QTD_BAIRROS"],
                                   ascending=[False, False]))

        for _, row in resumo_cfg.iterrows():
            tec = row["TECNOLOGIA"]
            qtd_erbs = int(row["QTD_ERBS"])
            qtd_bairros = int(row["QTD_BAIRROS"])

            grupo_cfg = grupo_op[grupo_op["TECNOLOGIA"] == tec]
            bairros_cfg = ", ".join(sorted(grupo_cfg["BAIRRO"].unique())[:4])
            if grupo_cfg["BAIRRO"].nunique() > 4:
                bairros_cfg += "…"

            linha_cfg = _linha_tabela(
                op="", cfg=f"· {tec}", erbs=qtd_erbs,
                bairros=qtd_bairros, bairros_txt=bairros_cfg,
                largura_bairros=largura_bairros,
            )
            itens.append(criar_item_tui(
                linha_cfg, CAIXA_TEXTO, "esq",
                selecionavel=True,
                dados={"tipo": "OP_TEC",
                       "operadora": op,
                       "tecnologia": tec},
            ))

    return cabecalho, itens, totais_op


def construir_itens_por_tecnologia(
    df_cidade: pd.DataFrame
) -> tuple[str, list[dict[str, Any]], pd.DataFrame]:
    """Visão [2] — resumo por tecnologia.

    Args:
        df_cidade: DataFrame da cidade.

    Returns:
        Tupla (cabecalho, itens, resumo_mix).
    """
    itens: list[dict[str, Any]] = [
        criar_item_tui(
            "RESUMO POR GERAÇÃO TECNOLÓGICA INDIVIDUAL "
            "([ENTER] FILTRA A GERAÇÃO):",
            CAIXA_TITULO,
        )
    ]

    geracoes = [("5G (NR)", "5"), ("4G (LTE)", "L"),
                ("3G (HSPA/WCDMA)", "H"), ("2G (GSM/EDGE)", "E")]

    for nome_g, sigla_g in geracoes:
        df_g = df_cidade[df_cidade["TECS_RAW"].str.contains(sigla_g, na=False)]
        tot = df_g["ID_ERB"].nunique()

        if tot > 0:
            bairros = df_g["BAIRRO"].nunique()
            ops = (df_g.groupby("OPERADORA")["NUM_ESTACAO"]
                   .nunique().sort_values(ascending=False))
            str_ops = ", ".join(f"{op} ({q})" for op, q in ops.items())
            itens.append(criar_item_tui(
                f"■ {nome_g:<16}: {tot:3d} ERB(s) em {bairros:2d} bairro(s)  "
                f"-> {str_ops}",
                CAIXA_TEXTO, "esq", selecionavel=True,
                dados={"tipo": "GERACAO", "sigla": sigla_g, "nome": nome_g},
            ))
        else:
            itens.append(criar_item_tui(
                f"■ {nome_g:<16}:   0 ERBs (Ausente na localidade)",
                CAIXA_TEXTO,
            ))

    resumo_mix = (df_cidade.groupby(["TECNOLOGIA", "OPERADORA"], as_index=False)
                  .agg(
                      QTD_ERBS=("NUM_ESTACAO", "count"),
                      QTD_BAIRROS=("BAIRRO", "nunique"),
                      BAIRROS_LISTA=("BAIRRO",
                                     lambda s: ", ".join(sorted(set(s))[:4])
                                     + ("..." if len(set(s)) > 4 else "")),
                  )
                  .sort_values(by=["TECNOLOGIA", "QTD_ERBS"],
                               ascending=[True, False]))

    itens.append(criar_item_tui("", divisor=True))
    itens.append(criar_item_tui(
        "DETALHAMENTO POR COMBINAÇÃO NA TORRE "
        "([ENTER] PARA VER BAIRROS E GPS):",
        CAIXA_TITULO,
    ))

    for tec, grp in resumo_mix.groupby("TECNOLOGIA"):
        itens.append(criar_item_tui("", divisor=True))
        tot_t = grp["QTD_ERBS"].sum()
        itens.append(criar_item_tui(
            f"» PADRÃO DE TORRE: [{tec}] — {tot_t} ERB(s)",
            CAIXA_TITULO, "esq", selecionavel=True,
            dados={"tipo": "TEC_MIX", "tecnologia": tec},
        ))

        for _, row in grp.iterrows():
            ln = (f"{row['TECNOLOGIA']:<15} {row['OPERADORA']:<12} "
                  f"{row['QTD_ERBS']:^10} {row['QTD_BAIRROS']:^9} "
                  f"{row['BAIRROS_LISTA']}")
            itens.append(criar_item_tui(
                ln, CAIXA_TEXTO, "esq", selecionavel=True,
                dados={"tipo": "OP_TEC", "operadora": row["OPERADORA"],
                       "tecnologia": row["TECNOLOGIA"]},
            ))

    cab = (f"   {'CONFIG. TORRE':<15} {'OPERADORA':<12} {'QTD ERBS':^10} "
           f"{'BAIRROS':^9} {'BAIRROS ATENDIDOS'}")

    return cab, itens, resumo_mix


def construir_itens_ranking_bairros(
    df_cidade: pd.DataFrame
) -> tuple[str, list[dict[str, Any]], pd.DataFrame]:
    """Visão [3] — ranking por bairros.

    Args:
        df_cidade: DataFrame da cidade.

    Returns:
        Tupla (cabecalho, itens, df_rb).
    """
    linhas: list[dict[str, Any]] = []

    for bairro, grp in df_cidade.groupby("BAIRRO"):
        total = grp["ID_ERB"].nunique()
        tecs = formatar_lista_tec(",".join(grp["TECS_RAW"]).split(","))
        cont_op = (grp.groupby("OPERADORA")["NUM_ESTACAO"]
                   .nunique().sort_values(ascending=False))
        detalhe = ", ".join(f"{op}({qtd})" for op, qtd in cont_op.items())
        max_op = cont_op.max()
        lideres = cont_op[cont_op == max_op].index.tolist()
        lider = f"{'/'.join(lideres)} ({max_op})"

        linhas.append({
            "BAIRRO": bairro, "ERBs": total, "TECS": tecs,
            "LÍDER LOCAL": lider, "OPERADORAS": detalhe,
        })

    df_rb = (pd.DataFrame(linhas)
             .sort_values(by=["ERBs", "BAIRRO"], ascending=[False, True])
             .reset_index(drop=True))

    cab = (f"   {'BAIRRO / LOCALIDADE':<34} {'ERBs':^6} {'TECS':<10} "
           f"{'LÍDER LOCAL':<18} {'OPERADORAS ([ENTER] DETALHA)'}")

    itens: list[dict[str, Any]] = []

    for _, row in df_rb.iterrows():
        ln = (f"{row['BAIRRO'][:33]:<34} {row['ERBs']:^6} {row['TECS']:<10} "
              f"{row['LÍDER LOCAL'][:17]:<18} {row['OPERADORAS']}")
        itens.append(criar_item_tui(
            ln, CAIXA_TEXTO, "esq", selecionavel=True,
            dados={"tipo": "BAIRRO", "bairro": row["BAIRRO"]},
        ))

    return cab, itens, df_rb


def construir_itens_blocos_bairros_gps(
    df_cidade: pd.DataFrame
) -> tuple[str, list[dict[str, Any]], pd.DataFrame]:
    """Visão [4] — todos os bairros + GPS.

    Args:
        df_cidade: DataFrame da cidade.

    Returns:
        Tupla (cabecalho, itens, resumo).
    """
    resumo = (df_cidade.groupby(["BAIRRO", "OPERADORA", "TECNOLOGIA"],
                                as_index=False)
              .agg(
                  QTD_ERBS=("NUM_ESTACAO", "count"),
                  GPS=("GPS", lambda s: " | ".join(dict.fromkeys(s))),
              )
              .sort_values(by=["BAIRRO", "OPERADORA", "QTD_ERBS"]))

    cab = (f"   {'OPERADORA':<12} {'QTD ERBS':^10} {'TECNOLOGIA':<12} "
           f"{'COORDENADAS GPS (SELECIONE E TECLE [ENTER] P/ ENDEREÇOS)'}")

    itens: list[dict[str, Any]] = []

    for idx_b, (bairro, grupo) in enumerate(resumo.groupby("BAIRRO")):
        if idx_b > 0:
            itens.append(criar_item_tui("", divisor=True))

        itens.append(criar_item_tui(
            f"====== [ BAIRRO/LOCAL: {bairro} ] ======",
            CAIXA_TITULO, "centro", selecionavel=True,
            dados={"tipo": "BAIRRO", "bairro": bairro},
        ))

        for _, row in grupo.iterrows():
            ln = (f"{row['OPERADORA']:<12} {row['QTD_ERBS']:^10} "
                  f"{row['TECNOLOGIA']:<12} {row['GPS']}")
            itens.append(criar_item_tui(
                ln, CAIXA_TEXTO, "esq", selecionavel=True,
                dados={"tipo": "BAIRRO_OP_TEC", "bairro": bairro,
                       "operadora": row["OPERADORA"],
                       "tecnologia": row["TECNOLOGIA"]},
            ))

    return cab, itens, resumo


# ---------------------------------------------------------------------------
# Inspeção detalhada de ERBs
# ---------------------------------------------------------------------------

def abrir_inspecao_detalhada_erbs(
    df_recorte: pd.DataFrame,
    titulo_inspecao: str,
    nome_limpo: str,
    uf: str,
) -> None:
    """Abre inspeção detalhada de ERBs.

    Args:
        df_recorte: DataFrame com ERBs.
        titulo_inspecao: Título da inspeção.
        nome_limpo: Nome limpo do município.
        uf: UF do município.
    """
    df_ord = df_recorte.sort_values(
        by=["BAIRRO", "OPERADORA", "NUM_ESTACAO"]
    ).copy()

    cab = (f"   {'OPERADORA':<10} {'ESTAÇÃO':<10} {'TECS':<10} "
           f"{'GPS':<23} {'ENDEREÇO CADASTRADO NA ANATEL'}")

    itens: list[dict[str, Any]] = []

    for idx_b, (bairro, grp) in enumerate(df_ord.groupby("BAIRRO")):
        if idx_b > 0:
            itens.append(criar_item_tui("", divisor=True))

        itens.append(criar_item_tui(
            f"» BAIRRO/LOCAL: {bairro} "
            f"({len(grp)} ERB{'s' if len(grp) > 1 else ''})",
            CAIXA_TITULO, "esq",
        ))

        for _, r in grp.iterrows():
            ln = (f"{r['OPERADORA']:<10} {r['NUM_ESTACAO']:<10} "
                  f"{r['TECNOLOGIA']:<10} {r['GPS']:<23} {r['ENDERECO']}")
            itens.append(criar_item_tui(
                ln, CAIXA_TEXTO, "esq", selecionavel=True, dados=r.to_dict()
            ))

    _, linhas_diag = diagnosticar_melhor_cobertura(df_ord)

    rodape_cmds = [
        "[↑/↓] Linha   [PgUp/PgDn] Página   [M] Google Maps (ERB)   "
        "[P] Pódio   [6] CSV   [ESC/0] Voltar",
    ]

    cursor = 0
    scroll = 0

    while True:
        acao, tecla_s, cursor, scroll = navegador_tui(
            modulo=f"INSPEÇÃO DE ERBs - {nome_limpo}/{uf}",
            titulo_janela=(f"{titulo_inspecao} — {len(df_ord)} ERB(s) "
                           f"em {df_ord['BAIRRO'].nunique()} bairro(s)"),
            itens_conteudo=itens,
            subcabecalho_fixo=linhas_diag,
            colunas_fixas_tabela=cab,
            comandos_rodape=rodape_cmds,
            teclas_rapidas={_ACAO_CSV, _ACAO_PODIO, _ACAO_MAPS},
            dica_teclas=("↑/↓=Linha | PgUp/PgDn=Página | M=Maps (ERB) | "
                         "P=Pódio | 6=CSV | ESC=Voltar"),
            cursor_inicial=cursor,
            scroll_inicial=scroll,
        )

        if acao == "KEY" and tecla_s == _ACAO_MAPS:
            _tratar_acao_maps(itens, cursor)

        elif acao == "KEY" and tecla_s == _ACAO_PODIO:
            mostrar_podio_completo_tui()

        elif acao == "KEY" and tecla_s == _ACAO_CSV:
            cols = ["UF", "MUNICIPIO", "BAIRRO", "OPERADORA", "NUM_ESTACAO",
                    "TECNOLOGIA", "ENDERECO", "GPS"]
            padrao = (f"detalhe_erbs_"
                      f"{normalizar_texto(nome_limpo).lower()}_{uf.lower()}.csv")
            salvar_csv_tui(df_ord[cols], padrao,
                           "EXPORTAR DETALHAMENTO DE ERBs")

        else:
            break


def _tratar_acao_maps(
    itens: list[dict[str, Any]], cursor: int
) -> None:
    """Trata ação de abrir Google Maps.

    Args:
        itens: Lista de itens.
        cursor: Posição do cursor.
    """
    selecionaveis = [i for i, it in enumerate(itens)
                     if it.get("selecionavel")]
    idx_dest = None

    if 0 <= cursor < len(selecionaveis):
        idx_dest = selecionaveis[cursor]

    if idx_dest is None:
        alerta_tui("GOOGLE MAPS", "NENHUMA ERB SELECIONADA",
                   ["Mova o cursor até uma ERB antes de teclar [M]."])
        return

    registro = itens[idx_dest].get("dados") or {}
    lat, lon = _extrair_coords_da_linha(registro)

    if lat is None or lon is None:
        alerta_tui(
            "GOOGLE MAPS", "ERB SEM COORDENADAS",
            [
                "Esta ERB não possui GPS válido no cadastro da Anatel.",
                f"Estação: {registro.get('NUM_ESTACAO', 'N/D')}",
                f"Operadora: {registro.get('OPERADORA', 'N/D')}",
            ],
        )
        return

    if _abrir_maps_uma(lat, lon):
        op = registro.get("OPERADORA", "")
        est = registro.get("NUM_ESTACAO", "")
        alerta_tui(
            "GOOGLE MAPS", "ABRINDO NO NAVEGADOR",
            [
                f"Coordenadas: {lat:.6f}, {lon:.6f}",
                f"Operadora: {op}   │   Estação: {est}",
                "Se o navegador não abrir, verifique as permissões.",
            ],
            cor_titulo=BARRA_VERDE,
        )
    else:
        alerta_tui(
            "GOOGLE MAPS", "FALHA AO ABRIR O NAVEGADOR",
            ["O sistema não conseguiu abrir o navegador padrão."],
            cor_titulo=BARRA_ALERTA,
        )


# ---------------------------------------------------------------------------
# Painel interativo de município
# ---------------------------------------------------------------------------

def painel_interativo_municipio(
    grp_cid: pd.DataFrame,
    nome_limpo: str,
    uf: str,
    filtro_extra_info: str = "",
) -> None:
    """Painel interativo de município com 4 visões.

    Args:
        grp_cid: DataFrame do município.
        nome_limpo: Nome limpo do município.
        uf: UF do município.
        filtro_extra_info: Informação extra de filtro (opcional).
    """
    modo_atual = "1"
    cursor_mem = 0
    scroll_mem = 0

    while True:
        total_erbs = grp_cid["ID_ERB"].nunique()
        total_bairros = grp_cid["BAIRRO"].nunique()
        _, linhas_diag = diagnosticar_melhor_cobertura(grp_cid)

        sufixo_filtro = f" │ FILTRO: {filtro_extra_info}" if filtro_extra_info else ""
        resumo_topo = [
            f"MUNICÍPIO: {nome_limpo} ({uf}) │ TOTAL: {total_erbs} ERB(s) │ "
            f"BAIRROS/LOCAIS: {total_bairros}{sufixo_filtro}"
        ] + linhas_diag

        # Seleciona visão
        if modo_atual == "1":
            titulo = ("VISÃO [1]: POR OPERADORA "
                      "(USE ↑/↓ E [ENTER] P/ EXPANDIR)")
            cab, itens, df_export = construir_itens_por_operadora(grp_cid)
        elif modo_atual == "2":
            titulo = ("VISÃO [2]: POR TECNOLOGIA "
                      "(USE ↑/↓ E [ENTER] P/ FILTRAR E VER BAIRROS)")
            cab, itens, df_export = construir_itens_por_tecnologia(grp_cid)
        elif modo_atual == "3":
            titulo = ("VISÃO [3]: RANKING POR BAIRROS "
                      "(USE ↑/↓ E [ENTER] P/ ABRIR O BAIRRO)")
            cab, itens, df_export = construir_itens_ranking_bairros(grp_cid)
        else:
            titulo = ("VISÃO [4]: TODOS OS BAIRROS + GPS "
                      "(USE ↑/↓ E [ENTER] P/ VER ENDEREÇOS)")
            cab, itens, df_export = construir_itens_blocos_bairros_gps(grp_cid)

        comandos = [
            "[1] Operadora  [2] Tecnologia  [3] Ranking Bairros  "
            "[4] Todos Bairros + GPS",
            "[5] Catálogo de Bairros  [6] Salvar CSV  [P] Pódio completo  "
            "[ENTER] Expandir  [PgUp/PgDn] Página  [ESC/0] Voltar",
        ]

        acao, dados, cursor_mem, scroll_mem = navegador_tui(
            modulo=f"PAINEL - {nome_limpo}/{uf}",
            titulo_janela=titulo,
            itens_conteudo=itens,
            subcabecalho_fixo=resumo_topo,
            colunas_fixas_tabela=cab,
            comandos_rodape=comandos,
            teclas_rapidas={"1", "2", "3", "4", "5", "6", "7", "P"},
            dica_teclas=("↑/↓=Mover | PgUp/PgDn=Página | ENTER=Expandir | "
                         "1-4=Trocar Visão | 5=Bairros | P=Pódio | "
                         "ESC/0=Voltar"),
            cursor_inicial=cursor_mem,
            scroll_inicial=scroll_mem,
        )

        if acao == "KEY" and dados == "P":
            mostrar_podio_completo_tui()
            continue

        if acao == "KEY":
            if dados in ("1", "2", "3", "4"):
                modo_atual = dados
                cursor_mem = 0
                scroll_mem = 0
            elif dados == "5":
                df_b = selecionar_bairro_interativo(grp_cid, nome_limpo)
                if df_b is not None and not df_b.empty:
                    b_nomes = ", ".join(sorted(df_b["BAIRRO"].unique()))
                    abrir_inspecao_detalhada_erbs(
                        df_b, f"BAIRRO: {b_nomes}", nome_limpo, uf
                    )
            elif dados == "6" and df_export is not None:
                padrao = (f"relatorio_"
                          f"{normalizar_texto(nome_limpo).lower()}_"
                          f"{uf.lower()}_visao{modo_atual}.csv")
                salvar_csv_tui(
                    df_export, padrao,
                    f"EXPORTAR VISÃO [{modo_atual}] DE {nome_limpo}",
                )
            elif dados == "7":
                break

        elif acao == "SELECT" and isinstance(dados, dict):
            _tratar_selecao_painel(dados, grp_cid, nome_limpo, uf)

        else:
            break


def _tratar_selecao_painel(
    dados: dict[str, Any],
    grp_cid: pd.DataFrame,
    nome_limpo: str,
    uf: str,
) -> None:
    """Trata seleção no painel interativo.

    Args:
        dados: Dados da seleção.
        grp_cid: DataFrame do município.
        nome_limpo: Nome limpo do município.
        uf: UF do município.
    """
    tipo = dados.get("tipo")

    if tipo == "OPERADORA":
        op = dados["operadora"]
        sub = grp_cid[grp_cid["OPERADORA"] == op]
        abrir_inspecao_detalhada_erbs(
            sub, f"TODAS AS ERBs DA {op}", nome_limpo, uf
        )

    elif tipo == "OP_TEC":
        op = dados["operadora"]
        tec = dados["tecnologia"]
        sub = grp_cid[(grp_cid["OPERADORA"] == op)
                      & (grp_cid["TECNOLOGIA"] == tec)]
        abrir_inspecao_detalhada_erbs(
            sub, f"OPERADORA: {op} | CONFIGURAÇÃO: [{tec}]",
            nome_limpo, uf,
        )

    elif tipo == "GERACAO":
        sig = dados["sigla"]
        nom = dados["nome"]
        sub = grp_cid[grp_cid["TECS_RAW"].str.contains(sig, na=False)]
        abrir_inspecao_detalhada_erbs(
            sub, f"TODAS AS ERBs COM {nom}", nome_limpo, uf
        )

    elif tipo == "TEC_MIX":
        tec = dados["tecnologia"]
        sub = grp_cid[grp_cid["TECNOLOGIA"] == tec]
        abrir_inspecao_detalhada_erbs(
            sub, f"PADRÃO DE TORRE: [{tec}]", nome_limpo, uf
        )

    elif tipo == "BAIRRO":
        b = dados["bairro"]
        sub = grp_cid[grp_cid["BAIRRO"] == b]
        abrir_inspecao_detalhada_erbs(
            sub, f"BAIRRO: {b}", nome_limpo, uf
        )

    elif tipo == "BAIRRO_OP_TEC":
        b = dados["bairro"]
        op = dados["operadora"]
        tec = dados["tecnologia"]
        sub = grp_cid[(grp_cid["BAIRRO"] == b)
                      & (grp_cid["OPERADORA"] == op)
                      & (grp_cid["TECNOLOGIA"] == tec)]
        abrir_inspecao_detalhada_erbs(
            sub, f"BAIRRO: {b} | {op} [{tec}]", nome_limpo, uf
        )