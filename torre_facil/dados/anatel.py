"""Download, parsing e cache da base ANATEL SMP.

Este módulo é responsável por:
    - Baixar o ZIP oficial da Anatel com estações SMP
    - Extrair e processar o CSV bruto em um DataFrame consolidado
    - Persistir o resultado em cache binário (.pkl) para inicialização rápida
    - Gerar snapshots para comparação entre versões

Colunas enriquecidas além das usadas originalmente:
    FREQ_MHZ, FAIXA_NOMINAL, LARGURA_CANAL, CARATER, INFRA,
    TEC5G_TIPO, IBGE, CEP, DATA_LIC, DATA_PRIM_LIC

Arquitetura:
    - Funções puras de parsing: ``_parse_float_br``, ``_limpar_ibge``, etc.
    - Pipeline de processamento dividido em etapas menores
    - Callbacks de progresso para desacoplar da TUI (futuro)
    - Estado global ``INFO`` mantido como deprecated (migrar para AppContext)
"""
from __future__ import annotations

import datetime
import gc
import json
import logging
import os
import pickle
import time
import traceback
import zipfile
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd
import requests
import urllib3

from .. import dicionarios as _dic_mod
from ..config import (
    ARQUIVO_CACHE,
    ARQUIVO_CACHE_BAIRROS,
    ARQUIVO_CSV_EXTRAIDO,
    ARQUIVO_ZIP,
    DIAS_EXPIRACAO_CACHE,
    ORDEM_TEC,
    URL_ANATEL,
    VERSAO_CACHE,
)
from ..coordenadas import (
    converter_coord_anatel,
    mapear_sigla_tecnologia,
    padronizar_operadora,
)
from ..dicionarios import carregar_globais
from ..estado import INFO
from ..texto import extrair_bairro_inteligente, normalizar_texto
from ..tui.cores import BARRA_ALERTA, BARRA_STATUS_TOPO
from ..tui.janelas import (
    alerta_tui,
    caixa_notificacao_tui,
    desenhar_progresso_tui,
    mostrar_splash_screen,
)
from ..tui.motor import encerrar_modo_tui
from . import snapshot as snap_mod
from .bairros import unificar_bairros_por_municipio

logger = logging.getLogger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Origens da base (usadas em ``INFO.origem``)
ORIGEM_CACHE_RECENTE = "Cache Recém-Indexado"
ORIGEM_CACHE_RAPIDO = "Cache Rápido"
ORIGEM_CACHE_INVALIDO = "Cache Inválido"

# Faixas nominais para agrupar frequências (MHz)
# Tuplas: (limite_inferior, limite_superior, nome_da_faixa)
_FAIXAS_NOMINAIS: list[tuple[int, int, str]] = [
    (400, 500, "450"),
    (600, 800, "700"),
    (800, 900, "850"),
    (900, 1000, "900"),
    (1700, 1800, "1700"),
    (1800, 1900, "1800"),
    (1900, 2000, "1900"),
    (2000, 2200, "2100"),
    (2300, 2400, "2300"),
    (2500, 2700, "2600"),
    (3300, 3600, "3500"),    # 5G principal
    (3600, 4000, "3700"),
    (24000, 28000, "26000"),  # mmWave
]

# Colunas usadas no índice de busca global
_COLUNAS_BUSCA_GLOBAL: tuple[str, ...] = (
    "UF", "MUNICIPIO_LIMPO", "MUNICIPIO", "BAIRRO", "ENDERECO",
    "ENDERECO_BUSCA", "LOGR_RAW", "OPERADORA", "NUM_ESTACAO",
    "TECNOLOGIA", "TECS_RAW", "GPS",
    "FAIXA_NOMINAL", "CARATER", "INFRA", "TEC5G_TIPO",
)

# Sequência de progresso ao carregar do cache
_SEQUENCIA_PROGRESSO_CACHE: tuple[tuple[int, str, str], ...] = (
    (25, "CONSOLIDANDO TECNOLOGIAS", "Subindo portadoras 4G e 5G..."),
    (45, "CARREGANDO BAIRROS E GPS", "Ajustando o azimute e tilt das antenas..."),
    (70, "UNIFICANDO BAIRROS", "Consultando dicionário nacional compilado..."),
    (90, "CONSOLIDANDO ERBs", "Medindo VSWR e integrando BBUs..."),
    (100, "UFA, PRONTO! SITE CONSTRUÍDO!", "Liberando tráfego nos setores..."),
)


# ---------------------------------------------------------------------------
# Callback de progresso (abstração para desacoplar da TUI no futuro)
# ---------------------------------------------------------------------------

def _progresso(perc: int, titulo: str, frase: str, detalhe_extra: str = "") -> None:
    """Reporta progresso do pipeline.

    Atualmente delega para ``desenhar_progresso_tui``. No futuro, poderá
    ser substituído por um callback injetado, permitindo reuso em contextos
    sem TUI (CLI, web, testes).

    Args:
        perc: Percentual de conclusão (0-100).
        titulo: Título da etapa atual.
        frase: Descrição curta da etapa.
        detalhe_extra: Informação adicional (ex: velocidade de download).
    """
    desenhar_progresso_tui(perc, titulo, frase, detalhe_extra=detalhe_extra)


# ---------------------------------------------------------------------------
# Funções puras de parsing
# ---------------------------------------------------------------------------

def _faixa_nominal(freq_mhz: Any) -> str:
    """Mapeia frequência em MHz para faixa nominal.

    Args:
        freq_mhz: Valor em MHz (str, int, float ou None).

    Returns:
        Nome da faixa nominal (ex: '700', '3500') ou 'outra'/''.

    Examples:
        >>> _faixa_nominal(1850)
        '1800'
        >>> _faixa_nominal(3500)
        '3500'
        >>> _faixa_nominal(None)
        ''
    """
    try:
        f = float(freq_mhz)
    except (TypeError, ValueError):
        return ""
    for lo, hi, nome in _FAIXAS_NOMINAIS:
        if lo <= f < hi:
            return nome
    return "outra"


def _parse_float_br(valor: Any) -> float | None:
    """Converte string com vírgula decimal em float.

    Args:
        valor: Valor a converter (ex: '1875,00', 1875.0, None).

    Returns:
        Float convertido, ou None se inválido.

    Examples:
        >>> _parse_float_br('1875,00')
        1875.0
        >>> _parse_float_br(None) is None
        True
    """
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    s = str(valor).strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _limpar_ibge(valor: Any) -> str:
    """Normaliza código IBGE para string de 7 dígitos.

    Args:
        valor: Código IBGE (pode vir como float '2401008.0').

    Returns:
        String com 7 dígitos, ou string vazia se inválido.

    Examples:
        >>> _limpar_ibge(2401008.0)
        '2401008'
        >>> _limpar_ibge(None)
        ''
    """
    try:
        if valor is None or pd.isna(valor):
            return ""
        return str(int(float(valor)))
    except (TypeError, ValueError):
        return ""


def _limpar_cep(valor: Any) -> str:
    """Normaliza CEP para string de 8 dígitos.

    Args:
        valor: CEP (pode vir como '59420000' ou '59420-000').

    Returns:
        String com 8 dígitos, ou string vazia se inválido.

    Examples:
        >>> _limpar_cep('59420000')
        '59420000'
        >>> _limpar_cep(None)
        ''
    """
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    s = "".join(c for c in str(valor) if c.isdigit())
    return s if len(s) == 8 else ""


# ---------------------------------------------------------------------------
# Identificação de colunas
# ---------------------------------------------------------------------------

def _identificar_coluna(
    colunas: Iterable[str],
    termos_exatos: Iterable[str],
    termos_parciais: Iterable[str] | None = None,
    ignorar: set[str] | None = None,
) -> str | None:
    """Identifica coluna do CSV por termos exatos ou parciais.

    Estratégia:
        1. Tenta match exato (após normalização) com ``termos_exatos``.
        2. Se falhar, tenta match parcial (substring) com ``termos_parciais``.

    Args:
        colunas: Nomes das colunas disponíveis no CSV.
        termos_exatos: Termos para match exato (prioridade alta).
        termos_parciais: Termos para match parcial (fallback). Se None, usa ``termos_exatos``.
        ignorar: Colunas já mapeadas (evita reuso).

    Returns:
        Nome da coluna identificada, ou None se não encontrada.
    """
    if termos_parciais is None:
        termos_parciais = termos_exatos
    if ignorar is None:
        ignorar = set()

    mapa = {c: normalizar_texto(c) for c in colunas if c not in ignorar}

    # Match exato
    for termo in termos_exatos:
        t = normalizar_texto(termo)
        for col, col_n in mapa.items():
            if col_n == t:
                return col

    # Match parcial
    for termo in termos_parciais:
        t = normalizar_texto(termo)
        for col, col_n in mapa.items():
            if t in col_n:
                return col

    return None


# ---------------------------------------------------------------------------
# Download e extração
# ---------------------------------------------------------------------------

def baixar_zip_anatel() -> bool:
    """Baixa o ZIP oficial de estações SMP do servidor da Anatel.

    Exibe barra de progresso com velocidade e ETA.

    Returns:
        True se download bem-sucedido, False caso contrário.

    Side effects:
        - Cria/atualiza ``ARQUIVO_ZIP`` no diretório atual.
        - Remove ``ARQUIVO_CSV_EXTRAIDO`` se existir (para forçar reextração).
        - Define ``INFO.modulo_atual = "DOWNLOAD ANATEL"``.
    """
    INFO.modulo_atual = "DOWNLOAD ANATEL"
    logger.info("Iniciando download de %s", URL_ANATEL)

    try:
        with requests.get(URL_ANATEL, stream=True, verify=False, timeout=120) as r:
            r.raise_for_status()
            total_bytes = int(r.headers.get("content-length", 0))
            baixado = 0
            ultimo_desenho = 0.0
            t_inicio = time.time()

            with open(ARQUIVO_ZIP, "wb") as f:
                for chunk in r.iter_content(chunk_size=512 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    baixado += len(chunk)

                    agora = time.time()
                    if agora - ultimo_desenho > 0.12 or baixado == total_bytes:
                        ultimo_desenho = agora
                        mb_atual = baixado / (1024 * 1024)
                        mb_tot = (
                            total_bytes / (1024 * 1024) if total_bytes > 0 else mb_atual
                        )
                        perc = (
                            (baixado / total_bytes * 100.0) if total_bytes > 0 else 50.0
                        )
                        decorrido = max(0.001, agora - t_inicio)
                        vel_mb_s = mb_atual / decorrido

                        if total_bytes > 0 and vel_mb_s > 0:
                            restante_s = max(0.0, (mb_tot - mb_atual) / vel_mb_s)
                            eta_txt = (
                                f"{int(restante_s // 60):02d}:"
                                f"{int(restante_s % 60):02d}"
                            )
                        else:
                            eta_txt = "--:--"

                        detalhe = (
                            f"{mb_atual:5.1f}/{mb_tot:.1f} MB  •  "
                            f"{vel_mb_s:5.1f} MB/s  •  ETA {eta_txt}"
                        )
                        _progresso(
                            int(perc),
                            "TRANSFERÊNCIA DE ARQUIVO - SERVIDOR ANATEL",
                            "Recebendo pacote oficial de estações licenciadas...",
                            detalhe_extra=detalhe,
                        )

        # Remove CSV extraído antigo para forçar reextração
        if os.path.exists(ARQUIVO_CSV_EXTRAIDO):
            os.remove(ARQUIVO_CSV_EXTRAIDO)

        logger.info("Download concluído: %d bytes", baixado)
        return True

    except Exception as e:
        logger.exception("Falha no download ANATEL")
        INFO.ultimo_erro = f"Falha no download ANATEL: {type(e).__name__}: {e}"
        alerta_tui("ERRO DE REDE", "FALHA NO DOWNLOAD DA ANATEL", [str(e)])
        return False


def extrair_csv_do_zip() -> None:
    """Extrai o CSV de dentro do ZIP da Anatel.

    Raises:
        FileNotFoundError: Se ``ARQUIVO_ZIP`` não existir.
        ValueError: Se nenhum CSV for encontrado dentro do ZIP.
    """
    if not os.path.exists(ARQUIVO_ZIP):
        raise FileNotFoundError(f"Arquivo {ARQUIVO_ZIP} não encontrado.")

    _progresso(
        5,
        "DESCOMPACTANDO PACOTE ZIP",
        f"Extraindo {ARQUIVO_ZIP} em disco (operação única)...",
    )

    with zipfile.ZipFile(ARQUIVO_ZIP, "r") as z:
        csvs = [f for f in z.namelist() if f.lower().endswith(".csv")]
        if not csvs:
            raise ValueError("Nenhum arquivo CSV encontrado dentro do ZIP.")

        nome_interno = csvs[0]
        with z.open(nome_interno) as origem, open(ARQUIVO_CSV_EXTRAIDO, "wb") as destino:
            while True:
                bloco = origem.read(1024 * 1024)
                if not bloco:
                    break
                destino.write(bloco)


# ---------------------------------------------------------------------------
# Índice de busca global
# ---------------------------------------------------------------------------

def _compilar_indice_busca_global(df_erbs: pd.DataFrame) -> None:
    """Compila coluna ``__BUSCA_GLOBAL`` para busca rápida.

    Concatena colunas relevantes em uma única string normalizada,
    evitando lentidão na primeira consulta.

    Args:
        df_erbs: DataFrame de ERBs (modificado in-place).
    """
    colunas = [c for c in _COLUNAS_BUSCA_GLOBAL if c in df_erbs.columns]
    if not colunas:
        df_erbs["__BUSCA_GLOBAL"] = ""
        return

    combinada = df_erbs[colunas[0]].fillna("").astype(str)
    for c in colunas[1:]:
        combinada = combinada.str.cat(
            df_erbs[c].fillna("").astype(str), sep=" | "
        )
    df_erbs["__BUSCA_GLOBAL"] = combinada.map(normalizar_texto)


# ---------------------------------------------------------------------------
# Etapas do pipeline de processamento
# ---------------------------------------------------------------------------

def _etapa_inspecionar_cabecalho(
    csv_path: str,
) -> tuple[pd.DataFrame, str, list[str]]:
    """Etapa 1: Inspeciona cabeçalho do CSV e detecta encoding.

    Args:
        csv_path: Caminho para o CSV extraído.

    Returns:
        Tupla com (df_head vazio, codificação detectada, lista de colunas).
    """
    _progresso(
        10, "INSPECIONANDO CABEÇALHO DO ARQUIVO",
        "Conectando os cabos e mapeando colunas...",
    )

    try:
        df_head = pd.read_csv(csv_path, sep=";", encoding="utf-8-sig", nrows=0)
        codificacao = "utf-8-sig"
    except UnicodeDecodeError:
        df_head = pd.read_csv(csv_path, sep=";", encoding="latin-1", nrows=0)
        codificacao = "latin-1"

    return df_head, codificacao, list(df_head.columns)


def _etapa_mapear_colunas(todas_colunas: list[str]) -> dict[str, str | None]:
    """Etapa 2: Mapeia colunas do CSV para nomes canônicos.

    Args:
        todas_colunas: Lista de colunas disponíveis no CSV.

    Returns:
        Dicionário ``{nome_canonico: nome_original}`` com colunas identificadas.

    Raises:
        ValueError: Se colunas essenciais não forem encontradas.
    """
    usadas: set[str] = set()

    def _pick(exatos: list[str], parciais: list[str]) -> str | None:
        c = _identificar_coluna(todas_colunas, exatos, parciais, usadas)
        if c:
            usadas.add(c)
        return c

    mapa: dict[str, str | None] = {}

    # Essenciais
    mapa["uf"] = _pick(["UF", "SIGLAUF", "SIGLA_UF"], ["SIGLA_UF", "SIGLAUF", "UF"])
    mapa["mun"] = _pick(
        ["Município-UF", "MUNICIPIO", "NOMEMUNICIPIO"],
        ["MUNICIPIO", "CIDADE", "MUNICÍPIO"],
    )
    mapa["estacao"] = _pick(
        ["Número Estação", "NUMESTACAO", "NUMEROESTACAO"],
        ["ESTACAO", "ESTAÇÃO"],
    )
    mapa["empresa"] = _pick(
        ["Empresa Estação", "NOMEENTIDADE", "Entidade"],
        ["EMPRESA ESTAÇÃO", "ENTIDADE", "EMPRESA"],
    )
    mapa["entidade"] = _pick(["Entidade", "NOMEENTIDADE"], ["ENTIDADE"])

    # Tecnologias
    mapa["tec"] = _pick(["Tecnologia", "TECNOLOGIA"], ["TECNOLOGIA"])
    mapa["ger"] = _pick(["Geração", "GERACAO"], ["GERACAO", "GERAÇÃO"])
    mapa["tec5g"] = _pick(["Tipo de Tecnologia 5G"], ["TIPO DE TECNOLOGIA 5G"])

    # Endereços
    mapa["bairro"] = _pick(["EndBairro", "BAIRRO", "NOMEBAIRRO"], ["BAIRRO"])
    mapa["logr"] = _pick(
        ["EnderecoEstacao", "LOGRADOURO", "ENDERECO"],
        ["LOGRADOURO", "ENDERECO", "ENDEREÇO"],
    )
    mapa["num"] = _pick(["EndNumero"], ["ENDNUMERO", "NÚMERO", "NUMERO"])
    mapa["compl"] = _pick(["EndComplemento", "COMPLEMENTO"], ["COMPLEMENTO"])
    mapa["cep"] = _pick(["Cep", "CEP"], ["CEP"])

    # Coordenadas
    mapa["lat_dec"] = _pick(["Latitude decimal"], ["LATITUDE DECIMAL"])
    mapa["lon_dec"] = _pick(["Longitude decimal"], ["LONGITUDE DECIMAL"])
    mapa["lat"] = _pick(["Latitude", "LATITUDE"], ["LATITUDE"])
    mapa["lon"] = _pick(["Longitude", "LONGITUDE"], ["LONGITUDE"])

    # Frequência
    mapa["freq"] = _pick(["Frequência (MHz)", "Frequência"], ["FREQUÊNCIA", "FREQUENCIA"])
    mapa["freq_tx"] = _pick(["FreqTxMHz"], ["FREQTX"])
    mapa["freq_rx"] = _pick(["FreqRxMHz"], ["FREQRX"])
    mapa["largura"] = _pick(["Banda_MHZ", "Banda"], ["BANDA"])

    # Classificações
    mapa["carater"] = _pick(["Caráter", "Carater"], ["CARÁTER", "CARATER"])
    mapa["infra"] = _pick(["ClassInfraFisica"], ["CLASSINFRA", "INFRA"])

    # Datas
    mapa["data_lic"] = _pick(["Data Licenciamento"], ["DATA LICENCIAMENTO"])
    mapa["data_prim"] = _pick(["Data Primeiro Licenciamento"], ["DATA PRIMEIRO"])
    mapa["ibge"] = _pick(["Código IBGE", "Codigo IBGE"], ["IBGE"])

    # Validação
    if not (mapa["mun"] and mapa["estacao"]):
        raise ValueError(
            f"Colunas essenciais não identificadas. Disponíveis: {todas_colunas}"
        )
    if not (mapa["empresa"] or mapa["entidade"]):
        raise ValueError("Nenhuma coluna de empresa/entidade encontrada.")

    return mapa


def _etapa_carregar_csv(
    csv_path: str,
    codificacao: str,
    colunas_necessarias: list[str],
) -> pd.DataFrame:
    """Etapa 3: Carrega CSV em baixa memória.

    Args:
        csv_path: Caminho para o CSV.
        codificacao: Encoding detectado.
        colunas_necessarias: Colunas a carregar.

    Returns:
        DataFrame com todas as linhas, apenas colunas necessárias.
    """
    _progresso(
        15, "CARREGANDO BASE DE SETORES",
        "Iluminando a fibra óptica (modo de baixa memória)...",
    )
    return pd.read_csv(
        csv_path,
        sep=";",
        encoding=codificacao,
        usecols=colunas_necessarias,
        dtype=str,
        low_memory=False,
    )


def _etapa_processar_tecnologias(df: pd.DataFrame, mapa: dict[str, str | None]) -> pd.DataFrame:
    """Etapa 4: Consolida tecnologias (2G/3G/4G/5G).

    Args:
        df: DataFrame com setores brutos.
        mapa: Mapeamento de colunas.

    Returns:
        DataFrame com coluna ``TEC_SIGLA`` adicionada e tecnologias inválidas removidas.
    """
    _progresso(
        25, "CONSOLIDANDO TECNOLOGIAS (2G/3G/4G/5G)",
        "Provisionando setores e subindo portadoras...",
    )

    col_tec = mapa["tec"]
    col_ger = mapa["ger"]

    if col_tec and col_ger:
        tec_combinada = df[col_tec].fillna("") + " " + df[col_ger].fillna("")
    elif col_tec:
        tec_combinada = df[col_tec].fillna("")
    elif col_ger:
        tec_combinada = df[col_ger].fillna("")
    else:
        tec_combinada = pd.Series([""] * len(df))

    mapa_tec = {v: mapear_sigla_tecnologia(v) for v in tec_combinada.unique()}
    df["TEC_SIGLA"] = tec_combinada.map(mapa_tec)
    del tec_combinada

    df = df[df["TEC_SIGLA"] != ""].copy()
    for c_drop in (col_tec, col_ger):
        if c_drop and c_drop in df.columns:
            df.drop(columns=[c_drop], inplace=True)

    return df


def _etapa_processar_municipio_operadora_uf(
    df: pd.DataFrame, mapa: dict[str, str | None]
) -> pd.DataFrame:
    """Etapa 5: Processa município, operadora e UF.

    Args:
        df: DataFrame com setores.
        mapa: Mapeamento de colunas.

    Returns:
        DataFrame com colunas ``MUNICIPIO``, ``NUM_ESTACAO``, ``OPERADORA``, ``UF``.
    """
    df["MUNICIPIO"] = df[mapa["mun"]].fillna("").str.strip()
    df["NUM_ESTACAO"] = df[mapa["estacao"]].fillna("").str.strip()

    # Operadora: prefere "Empresa Estação" (curta e normalizada)
    if mapa["empresa"]:
        df["OPERADORA"] = df[mapa["empresa"]].fillna("").str.strip().str.upper()
    elif mapa["entidade"]:
        entidade = df[mapa["entidade"]].fillna("").str.strip()
        mapa_op = {v: padronizar_operadora(v) for v in entidade.unique()}
        df["OPERADORA"] = entidade.map(mapa_op)

    if mapa["uf"]:
        df["UF"] = df[mapa["uf"]].fillna("").str.strip().str.upper()
    else:
        df["UF"] = (
            df["MUNICIPIO"]
            .str.extract(r"-\s*([A-Za-z]{2})$")[0]
            .fillna("")
            .str.upper()
        )

    return df


def _etapa_desduplicar(df: pd.DataFrame) -> pd.DataFrame:
    """Etapa 6: Remove setores duplicados por ERB+tecnologia.

    Args:
        df: DataFrame com setores.

    Returns:
        DataFrame desduplicado.
    """
    _progresso(
        35, "DESDUPLICANDO SETORES POR ERB",
        "Alinhando os enlaces de micro-ondas...",
    )
    df.drop_duplicates(
        subset=["UF", "MUNICIPIO", "OPERADORA", "NUM_ESTACAO", "TEC_SIGLA"],
        inplace=True,
    )
    gc.collect()
    return df


def _etapa_preparar_enderecos_coordenadas(
    df: pd.DataFrame, mapa: dict[str, str | None]
) -> pd.DataFrame:
    """Etapa 7: Prepara endereços e coordenadas brutas.

    Args:
        df: DataFrame com setores.
        mapa: Mapeamento de colunas.

    Returns:
        DataFrame com colunas ``BAIRRO_RAW``, ``LOGR_RAW``, ``LAT_RAW``, ``LON_RAW``.
    """
    _progresso(
        45, "PREPARANDO ENDEREÇOS E COORDENADAS",
        "Ajustando o azimute e tilt das antenas...",
    )

    def _col_ou_vazio(nome: str | None) -> pd.Series:
        return df[nome].fillna("").str.strip() if nome else pd.Series([""] * len(df), index=df.index)

    s_bairro = _col_ou_vazio(mapa["bairro"])
    s_logr = _col_ou_vazio(mapa["logr"])
    s_num = _col_ou_vazio(mapa["num"])
    s_compl = _col_ou_vazio(mapa["compl"])

    logr_full = (s_logr + " " + s_num + " " + s_compl).str.strip()
    logr_full = logr_full.str.replace(r"\s+", " ", regex=True)

    df["BAIRRO_RAW"] = s_bairro
    df["LOGR_RAW"] = logr_full

    # Coordenadas: prioriza decimal; senão usa GMS como fallback
    df["LAT_RAW"] = df[mapa["lat_dec"]] if mapa["lat_dec"] else (df[mapa["lat"]] if mapa["lat"] else "")
    df["LON_RAW"] = df[mapa["lon_dec"]] if mapa["lon_dec"] else (df[mapa["lon"]] if mapa["lon"] else "")

    del s_bairro, s_logr, s_num, s_compl, logr_full
    return df


def _etapa_agrupar_erbs(
    df: pd.DataFrame, mapa: dict[str, str | None]
) -> pd.DataFrame:
    """Etapa 8: Agrupa setores por ERB física.

    Args:
        df: DataFrame com setores.
        mapa: Mapeamento de colunas.

    Returns:
        DataFrame agrupado por ERB (uma linha por ERB+operadora).
    """
    _progresso(
        60, "AGRUPANDO ESTAÇÕES FÍSICAS (ERBs)",
        "Medindo VSWR e integrando BBUs...",
    )

    df["ORDEM"] = df["TEC_SIGLA"].map(ORDEM_TEC)
    df.sort_values(
        by=["UF", "MUNICIPIO", "OPERADORA", "NUM_ESTACAO", "ORDEM"],
        inplace=True,
    )

    df_erbs = df.groupby(
        ["UF", "MUNICIPIO", "OPERADORA", "NUM_ESTACAO"],
        as_index=False, sort=False,
    ).agg(
        TECS_RAW=("TEC_SIGLA", ",".join),
        TECNOLOGIA=("TEC_SIGLA", lambda s: "TODAS" if len(s) == 4 else ", ".join(s)),
        BAIRRO_RAW=("BAIRRO_RAW", "first"),
        LOGR_RAW=("LOGR_RAW", "first"),
        LAT_RAW=("LAT_RAW", "first"),
        LON_RAW=("LON_RAW", "first"),
    )

    # Colunas extras que vêm por setor → pega a primeira
    col_freq_tx = mapa["freq_tx"]
    col_freq = mapa["freq"]
    col_largura = mapa["largura"]
    col_carater = mapa["carater"]
    col_infra = mapa["infra"]
    col_tec5g = mapa["tec5g"]
    col_ibge = mapa["ibge"]
    col_cep = mapa["cep"]
    col_data_lic = mapa["data_lic"]
    col_data_prim = mapa["data_prim"]

    if col_freq_tx or col_freq:
        df_extra = df.groupby(
            ["UF", "MUNICIPIO", "OPERADORA", "NUM_ESTACAO"],
            as_index=False, sort=False,
        ).agg(
            FREQ_MHZ=(col_freq_tx or col_freq or col_largura, "first"),
            LARGURA_CANAL=(col_largura, "first"),
            CARATER=(col_carater, "first"),
            INFRA=(col_infra, "first"),
            TEC5G_TIPO=(col_tec5g, "first"),
            IBGE=(col_ibge, "first"),
            CEP=(col_cep, "first"),
            DATA_LIC=(col_data_lic, "first"),
            DATA_PRIM_LIC=(col_data_prim, "first"),
        )
        df_erbs = df_erbs.merge(
            df_extra,
            on=["UF", "MUNICIPIO", "OPERADORA", "NUM_ESTACAO"],
            how="left",
        )
        del df_extra

    del df
    gc.collect()
    return df_erbs


def _etapa_normalizar_colunas_extras(df_erbs: pd.DataFrame) -> pd.DataFrame:
    """Etapa 9: Normaliza colunas extras (frequência, IBGE, CEP, datas).

    Args:
        df_erbs: DataFrame de ERBs.

    Returns:
        DataFrame com colunas normalizadas.
    """
    _progresso(
        68, "NORMALIZANDO FAIXAS E CLASSIFICAÇÕES",
        "Organizando frequências, infraestrutura e datas...",
    )

    # FREQ_MHZ → float
    if "FREQ_MHZ" in df_erbs.columns:
        df_erbs["FREQ_MHZ"] = df_erbs["FREQ_MHZ"].map(_parse_float_br)
        df_erbs["FAIXA_NOMINAL"] = df_erbs["FREQ_MHZ"].map(_faixa_nominal)
    else:
        df_erbs["FREQ_MHZ"] = None
        df_erbs["FAIXA_NOMINAL"] = ""

    # LARGURA_CANAL → float
    if "LARGURA_CANAL" in df_erbs.columns:
        df_erbs["LARGURA_CANAL"] = df_erbs["LARGURA_CANAL"].map(_parse_float_br)
    else:
        df_erbs["LARGURA_CANAL"] = None

    # CARATER → upper, sem acento
    if "CARATER" in df_erbs.columns:
        df_erbs["CARATER"] = df_erbs["CARATER"].fillna("").map(normalizar_texto)
    else:
        df_erbs["CARATER"] = ""

    # INFRA → upper
    if "INFRA" in df_erbs.columns:
        df_erbs["INFRA"] = df_erbs["INFRA"].fillna("").str.upper().str.strip()
    else:
        df_erbs["INFRA"] = ""

    # TEC5G_TIPO → 'SA-NSA' / 'NSA' / ''
    if "TEC5G_TIPO" in df_erbs.columns:
        df_erbs["TEC5G_TIPO"] = df_erbs["TEC5G_TIPO"].fillna("").str.upper().str.strip()
    else:
        df_erbs["TEC5G_TIPO"] = ""

    # IBGE → str 7 dígitos
    if "IBGE" in df_erbs.columns:
        df_erbs["IBGE"] = df_erbs["IBGE"].map(_limpar_ibge)
    else:
        df_erbs["IBGE"] = ""

    # CEP → str 8 dígitos
    if "CEP" in df_erbs.columns:
        df_erbs["CEP"] = df_erbs["CEP"].map(_limpar_cep)
    else:
        df_erbs["CEP"] = ""

    # Datas → datetime
    for col_dt in ("DATA_LIC", "DATA_PRIM_LIC"):
        if col_dt in df_erbs.columns:
            df_erbs[col_dt] = pd.to_datetime(
                df_erbs[col_dt], format="%d/%m/%Y", errors="coerce"
            )
        else:
            df_erbs[col_dt] = pd.NaT

    return df_erbs


def _etapa_extrair_bairros(df_erbs: pd.DataFrame) -> pd.DataFrame:
    """Etapa 10: Extrai bairros de logradouros quando necessário.

    Args:
        df_erbs: DataFrame de ERBs.

    Returns:
        DataFrame com coluna ``BAIRRO`` preenchida.
    """
    _progresso(
        72, "EXTRAINDO BAIRROS DE LOGRADOUROS",
        "Calibrando a potência das RRUs...",
    )

    cache_pares: dict[tuple[str, str], str] = {}
    bairros_extraidos: list[str] = []

    for b, l in zip(df_erbs["BAIRRO_RAW"], df_erbs["LOGR_RAW"]):
        par = (b, l)
        if par not in cache_pares:
            cache_pares[par] = extrair_bairro_inteligente(b, l)
        bairros_extraidos.append(cache_pares[par])

    df_erbs["BAIRRO"] = bairros_extraidos
    del cache_pares, bairros_extraidos
    return df_erbs


def _etapa_unificar_bairros(
    df_erbs: pd.DataFrame, forcar_recompilacao: bool
) -> pd.DataFrame:
    """Etapa 11: Unifica bairros por município usando dicionário nacional.

    Args:
        df_erbs: DataFrame de ERBs.
        forcar_recompilacao: Se True, força recompilação do cache de bairros.

    Returns:
        DataFrame com coluna ``BAIRRO`` unificada.
    """
    df_erbs["BAIRRO"] = unificar_bairros_por_municipio(
        df_erbs, forcar_recompilacao=forcar_recompilacao
    )
    return df_erbs


def _etapa_indexar_endereco_busca(df_erbs: pd.DataFrame) -> pd.DataFrame:
    """Etapa 12: Indexa endereço combinado para busca.

    Args:
        df_erbs: DataFrame de ERBs.

    Returns:
        DataFrame com colunas ``ENDERECO`` e ``ENDERECO_BUSCA``.
    """
    _progresso(
        88, "INDEXANDO MALHA RODOVIÁRIA (BRs/ESTADUAIS)",
        "Mapeando rodovias e filtrando quadras urbanas...",
    )

    df_erbs["ENDERECO"] = [
        l.upper() if l.upper() not in ("", "NAN", "NONE") else "ENDEREÇO NÃO INFORMADO"
        for l in df_erbs["LOGR_RAW"]
    ]
    end_comb = df_erbs["ENDERECO"] + " " + df_erbs["BAIRRO"]
    mapa_end = {v: normalizar_texto(v) for v in end_comb.unique()}
    df_erbs["ENDERECO_BUSCA"] = end_comb.map(mapa_end)
    del end_comb, mapa_end
    return df_erbs


def _etapa_converter_gps(df_erbs: pd.DataFrame) -> pd.DataFrame:
    """Etapa 13: Converte coordenadas GPS para formato legível.

    Args:
        df_erbs: DataFrame de ERBs.

    Returns:
        DataFrame com coluna ``GPS`` formatada.
    """
    _progresso(
        92, "CONVERTENDO COORDENADAS GPS",
        "Sincronizando handovers na rede...",
    )

    try:
        df_erbs["LAT_NUM"] = pd.to_numeric(df_erbs["LAT_RAW"], errors="coerce")
        df_erbs["LON_NUM"] = pd.to_numeric(df_erbs["LON_RAW"], errors="coerce")
        # Se falhou em >50%, cai para o parser GMS
        if df_erbs["LAT_NUM"].isna().sum() > len(df_erbs) * 0.5:
            raise ValueError("muitos NaN, tentando GMS")
    except Exception:
        mapa_lat = {v: converter_coord_anatel(v) for v in df_erbs["LAT_RAW"].unique()}
        mapa_lon = {v: converter_coord_anatel(v) for v in df_erbs["LON_RAW"].unique()}
        df_erbs["LAT_NUM"] = df_erbs["LAT_RAW"].map(mapa_lat)
        df_erbs["LON_NUM"] = df_erbs["LON_RAW"].map(mapa_lon)

    lats = df_erbs["LAT_NUM"].tolist()
    lons = df_erbs["LON_NUM"].tolist()
    df_erbs["GPS"] = [
        f"{lat:.6f}, {lon:.6f}"
        if (lat is not None and lon is not None and not pd.isna(lat) and not pd.isna(lon))
        else "Sem GPS"
        for lat, lon in zip(lats, lons)
    ]

    df_erbs.drop(columns=["BAIRRO_RAW", "LOGR_RAW", "LAT_RAW", "LON_RAW"], inplace=True)
    return df_erbs


def _etapa_finalizar_identificadores(df_erbs: pd.DataFrame) -> pd.DataFrame:
    """Etapa 14: Finaliza identificadores (ID_ERB, MUNICIPIO_LIMPO, MUNICIPIO_NORM).

    Args:
        df_erbs: DataFrame de ERBs.

    Returns:
        DataFrame com identificadores finais.
    """
    df_erbs["ID_ERB"] = df_erbs["OPERADORA"] + "_" + df_erbs["NUM_ESTACAO"]

    mun_limpo = (
        df_erbs["MUNICIPIO"]
        .str.replace(r"\s*-\s*[A-Za-z]{2}$", "", regex=True)
        .str.strip()
    )
    df_erbs["MUNICIPIO_LIMPO"] = mun_limpo.str.upper()
    mapa_mun = {v: normalizar_texto(v) for v in mun_limpo.unique()}
    df_erbs["MUNICIPIO_NORM"] = mun_limpo.map(mapa_mun)

    gc.collect()
    return df_erbs


def _etapa_indexar_busca_global(df_erbs: pd.DataFrame) -> pd.DataFrame:
    """Etapa 15: Compila índice de busca global.

    Args:
        df_erbs: DataFrame de ERBs.

    Returns:
        DataFrame com coluna ``__BUSCA_GLOBAL``.
    """
    _progresso(
        96, "INDEXANDO PESQUISA GLOBAL",
        "Compilando coluna única de busca (evita lentidão na 1ª consulta)...",
    )
    _compilar_indice_busca_global(df_erbs)
    return df_erbs


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def processar_base_e_salvar_cache(forcar_recompilacao_bairros: bool = False) -> tuple[pd.DataFrame, str]:
    """Pipeline completo: lê CSV bruto, produz DataFrame consolidado e salva cache.

    Este é o ponto de entrada principal para processamento da base.
    O pipeline é dividido em etapas menores para facilitar manutenção e debug.

    Args:
        forcar_recompilacao_bairros: Se True, força recompilação do cache de bairros.

    Returns:
        Tupla ``(df_erbs, origem)`` onde ``origem`` é uma string descritiva.

    Raises:
        SystemExit: Se ocorrer erro crítico (após exibir alerta na TUI).

    Side effects:
        - Cria/atualiza ``ARQUIVO_CACHE`` (.pkl).
        - Atualiza ``INFO`` com estatísticas da base.
        - Gera snapshot para comparação futura.
    """
    carregar_globais()

    if not os.path.exists(ARQUIVO_CSV_EXTRAIDO):
        extrair_csv_do_zip()

    try:
        # 1) Cabeçalho e encoding
        _, codificacao, todas_colunas = _etapa_inspecionar_cabecalho(ARQUIVO_CSV_EXTRAIDO)

        # 2) Mapear colunas
        mapa = _etapa_mapear_colunas(todas_colunas)

        colunas_necessarias = [
            c for c in [
                mapa["uf"], mapa["mun"], mapa["estacao"], mapa["empresa"], mapa["entidade"],
                mapa["tec"], mapa["ger"], mapa["tec5g"],
                mapa["bairro"], mapa["logr"], mapa["num"], mapa["compl"], mapa["cep"],
                mapa["lat_dec"], mapa["lon_dec"], mapa["lat"], mapa["lon"],
                mapa["freq"], mapa["freq_tx"], mapa["freq_rx"], mapa["largura"],
                mapa["carater"], mapa["infra"],
                mapa["data_lic"], mapa["data_prim"], mapa["ibge"],
            ] if c
        ]

        # 3) Carregar CSV
        df = _etapa_carregar_csv(ARQUIVO_CSV_EXTRAIDO, codificacao, colunas_necessarias)
        total_setores = len(df)

        # 4-7) Processamento incremental
        df = _etapa_processar_tecnologias(df, mapa)
        df = _etapa_processar_municipio_operadora_uf(df, mapa)
        df = _etapa_desduplicar(df)
        df = _etapa_preparar_enderecos_coordenadas(df, mapa)

        # 8) Agrupar ERBs
        df_erbs = _etapa_agrupar_erbs(df, mapa)

        # 9-15) Normalização e indexação
        df_erbs = _etapa_normalizar_colunas_extras(df_erbs)
        df_erbs = _etapa_extrair_bairros(df_erbs)
        df_erbs = _etapa_unificar_bairros(df_erbs, forcar_recompilacao_bairros)
        df_erbs = _etapa_indexar_endereco_busca(df_erbs)
        df_erbs = _etapa_converter_gps(df_erbs)
        df_erbs = _etapa_finalizar_identificadores(df_erbs)
        df_erbs = _etapa_indexar_busca_global(df_erbs)

        # 16) Persistir cache
        _progresso(
            100, "UFA, PRONTO! SITE CONSTRUÍDO!",
            "Gravando cache binário de alta velocidade...",
        )
        agora_dt = datetime.datetime.now()
        pacote = {
            "versao": VERSAO_CACHE,
            "df_erbs": df_erbs,
            "total_setores": total_setores,
            "bairros_unificados": INFO.bairros_unificados,
            "data_geracao": agora_dt,
        }
        with open(ARQUIVO_CACHE, "wb") as f_cache:
            pickle.dump(pacote, f_cache, protocol=pickle.HIGHEST_PROTOCOL)

        # 17) Snapshot para comparação futura
        _progresso(
            99, "GERANDO SNAPSHOT DE NOVIDADES",
            "Guardando resumo da base para comparar na próxima atualização...",
        )
        try:
            snap_novo = snap_mod.gerar_snapshot(
                df_erbs,
                total_setores=total_setores,
                data_base=agora_dt.strftime("%d/%m/%Y"),
            )
            snap_mod.salvar_snapshot(snap_novo)
        except Exception as e:
            logger.exception("Falha ao gerar snapshot")
            INFO.ultimo_erro = f"Falha ao gerar snapshot: {type(e).__name__}: {e}"

        time.sleep(0.25)
        return _atualizar_telemetria_global(
            df_erbs, total_setores, ORIGEM_CACHE_RECENTE,
            agora_dt.strftime("%d/%m/%Y"),
        )

    except Exception as erro:
        logger.exception("Erro crítico no processamento da base")
        INFO.ultimo_erro = f"{type(erro).__name__}: {erro}"
        alerta_tui(
            "ERRO CRÍTICO", "FALHA NO PROCESSAMENTO DA BASE",
            traceback.format_exc().splitlines()[-6:],
        )
        encerrar_modo_tui()
        raise SystemExit(1) from erro


# ---------------------------------------------------------------------------
# Carga a partir do cache .pkl
# ---------------------------------------------------------------------------

def carregar_do_cache() -> tuple[pd.DataFrame, str]:
    """Carrega base de dados do cache binário (.pkl).

    Returns:
        Tupla ``(df_erbs, origem)`` onde ``origem`` indica idade do cache.

    Raises:
        ValueError: Se versão do cache for incompatível.
        FileNotFoundError: Se arquivo de cache não existir.
    """
    _progresso(10, "CARREGANDO BASE DE DADOS", "Conectando os cabos...")
    time.sleep(0.12)
    _progresso(15, "CARREGANDO BASE DE DADOS", "Iluminando a fibra óptica...")

    with open(ARQUIVO_CACHE, "rb") as f_cache:
        pacote = pickle.load(f_cache)

    if pacote.get("versao") != VERSAO_CACHE:
        raise ValueError(
            f"Cache v{pacote.get('versao')} incompatível com v{VERSAO_CACHE}."
        )

    df_erbs = pacote["df_erbs"]

    # Rede de segurança: caches antigos sem __BUSCA_GLOBAL
    if "__BUSCA_GLOBAL" not in df_erbs.columns:
        _compilar_indice_busca_global(df_erbs)

    total_setores = pacote.get("total_setores", len(df_erbs))
    INFO.bairros_unificados = pacote.get("bairros_unificados", 0)

    data_ger = pacote.get(
        "data_geracao",
        datetime.datetime.fromtimestamp(os.path.getmtime(ARQUIVO_CACHE)),
    )
    dias = (datetime.datetime.now() - data_ger).days

    for perc, titulo, frase in _SEQUENCIA_PROGRESSO_CACHE:
        _progresso(perc, titulo, frase)
        time.sleep(0.12)

    return _atualizar_telemetria_global(
        df_erbs, total_setores,
        f"Cache Rápido (há {dias}d)",
        data_ger.strftime("%d/%m/%Y"),
    )


# ---------------------------------------------------------------------------
# Telemetria global
# ---------------------------------------------------------------------------

def _atualizar_telemetria_global(
    df_erbs: pd.DataFrame,
    total_setores: int,
    origem_str: str,
    data_atualizacao: str | None = None,
) -> tuple[pd.DataFrame, str]:
    """Atualiza estatísticas globais da base no ``INFO``.

    .. deprecated:: 10.0
        Migrar para ``AppContext.stats`` na próxima onda.

    Args:
        df_erbs: DataFrame de ERBs.
        total_setores: Número total de setores antes da agregação.
        origem_str: Descrição da origem dos dados.
        data_atualizacao: Data de atualização (opcional).

    Returns:
        Tupla ``(df_erbs, origem_str)`` para compatibilidade com chamadores.
    """
    INFO.ufs = df_erbs["UF"].nunique()
    INFO.municipios = df_erbs[["UF", "MUNICIPIO_NORM"]].drop_duplicates().shape[0]
    INFO.erbs = len(df_erbs)
    INFO.setores = total_setores
    INFO.origem = origem_str

    if data_atualizacao:
        INFO.data_atualizacao = data_atualizacao

    if INFO.bairros_unificados == 0 and os.path.exists(ARQUIVO_CACHE_BAIRROS):
        try:
            with open(ARQUIVO_CACHE_BAIRROS, "r", encoding="utf-8") as f:
                d_b = json.load(f)
            INFO.bairros_unificados = sum(len(v) for v in d_b.values())
        except Exception as e:
            logger.exception("Falha ao ler cache de bairros")
            INFO.ultimo_erro = f"Falha ao ler cache de bairros: {type(e).__name__}: {e}"

    return df_erbs, origem_str


# ---------------------------------------------------------------------------
# Limpeza e bootstrap
# ---------------------------------------------------------------------------

def limpar_arquivos_cache(
    apagar_csv_extraido: bool = True,
    apagar_cache_bairros: bool = False,
) -> None:
    """Remove arquivos de cache do disco.

    Args:
        apagar_csv_extraido: Se True, remove também o CSV bruto extraído.
        apagar_cache_bairros: Se True, remove também o cache de bairros unificados.
    """
    if os.path.exists(ARQUIVO_CACHE):
        os.remove(ARQUIVO_CACHE)
    if apagar_csv_extraido and os.path.exists(ARQUIVO_CSV_EXTRAIDO):
        os.remove(ARQUIVO_CSV_EXTRAIDO)
    if apagar_cache_bairros and os.path.exists(ARQUIVO_CACHE_BAIRROS):
        os.remove(ARQUIVO_CACHE_BAIRROS)


def inicializar_base_com_cache() -> tuple[pd.DataFrame, str]:
    """Bootstrap completo: splash → decisão (cache/csv/zip/download) → base pronta.

    Esta é a função de entrada principal para inicialização da base.
    Ela decide automaticamente qual caminho seguir baseado nos arquivos
    disponíveis em disco.

    Returns:
        Tupla ``(df_erbs, texto_status)`` com a base carregada e descrição.

    Raises:
        SystemExit: Se usuário cancelar ou ocorrer erro fatal.
    """
    mostrar_splash_screen()

    tem_cache = os.path.exists(ARQUIVO_CACHE)
    tem_csv = os.path.exists(ARQUIVO_CSV_EXTRAIDO)
    tem_zip = os.path.exists(ARQUIVO_ZIP)

    if tem_cache:
        return _inicializar_com_cache_existente(tem_zip)
    if tem_csv or tem_zip:
        return _inicializar_com_arquivo_local(tem_zip)
    return _inicializar_sem_arquivos()


def _inicializar_com_cache_existente(tem_zip: bool) -> tuple[pd.DataFrame, str]:
    """Inicializa quando já existe cache .pkl.

    Args:
        tem_zip: Se True, também existe ZIP da Anatel em disco.

    Returns:
        Tupla ``(df_erbs, texto_status)``.
    """
    ts_ref = os.path.getmtime(ARQUIVO_ZIP) if tem_zip else os.path.getmtime(ARQUIVO_CACHE)
    data_ref = datetime.datetime.fromtimestamp(ts_ref)
    dias_idade = (datetime.datetime.now() - data_ref).days
    tam_cache = os.path.getsize(ARQUIVO_CACHE) / (1024 * 1024)
    INFO.data_atualizacao = data_ref.strftime("%d/%m/%Y")

    if dias_idade >= DIAS_EXPIRACAO_CACHE:
        esc = caixa_notificacao_tui(
            modulo="NOTIFICAÇÃO DE SISTEMA",
            titulo="ATUALIZAÇÃO RECOMENDADA (BASE >= 7 DIAS)",
            linhas_mensagem=[
                f"O cache local ({ARQUIVO_CACHE}) foi atualizado em "
                f"{data_ref.strftime('%d/%m/%Y')} ({dias_idade} dias atrás).",
                "Deseja baixar uma versão atualizada da Anatel agora ou "
                "carregar o cache existente?",
            ],
            botoes=[
                ("1", "Baixar Nova Base da Anatel", "2"),
                ("2", "Usar Cache Atual (Rápido)", "1"),
                ("3", "Recompilar Bairros", "3"),
            ],
            cor_cabecalho=BARRA_ALERTA,
            botao_padrao=0,
        )
    else:
        esc = caixa_notificacao_tui(
            modulo="NOTIFICAÇÃO DE SISTEMA",
            titulo="BANCO DE DADOS EM CACHE LOCALIZADO",
            linhas_mensagem=[
                f"Arquivo de cache pronto: {ARQUIVO_CACHE} ({tam_cache:.1f} MB).",
                f"Última sincronização: {data_ref.strftime('%d/%m/%Y às %H:%M')} "
                f"(há {dias_idade} dia(s)).",
                "Como deseja iniciar a sessão do Torre Fácil?",
            ],
            botoes=[
                ("1", "Abrir via Cache (Instantâneo)", "1"),
                ("2", "Baixar da Anatel", "2"),
                ("3", "Recompilar Bairros", "3"),
            ],
            cor_cabecalho=BARRA_STATUS_TOPO,
            botao_padrao=0,
        )

    if esc == "2":
        if baixar_zip_anatel():
            limpar_arquivos_cache(apagar_csv_extraido=True, apagar_cache_bairros=True)
            return processar_base_e_salvar_cache(forcar_recompilacao_bairros=True)
        return carregar_do_cache()

    if esc == "3":
        limpar_arquivos_cache(apagar_csv_extraido=False, apagar_cache_bairros=True)
        return processar_base_e_salvar_cache(forcar_recompilacao_bairros=True)

    try:
        return carregar_do_cache()
    except Exception as e:
        logger.warning("Cache inválido, recompilando: %s", e)
        INFO.ultimo_erro = f"Cache inválido ({type(e).__name__}: {e}); recompilando."
        limpar_arquivos_cache(apagar_csv_extraido=False, apagar_cache_bairros=False)
        return processar_base_e_salvar_cache()


def _inicializar_com_arquivo_local(tem_zip: bool) -> tuple[pd.DataFrame, str]:
    """Inicializa quando existe CSV ou ZIP, mas não cache .pkl.

    Args:
        tem_zip: Se True, usa ZIP; caso contrário, usa CSV.

    Returns:
        Tupla ``(df_erbs, texto_status)``.
    """
    arq_base = ARQUIVO_ZIP if tem_zip else ARQUIVO_CSV_EXTRAIDO
    ts_ref = os.path.getmtime(arq_base)
    data_ref = datetime.datetime.fromtimestamp(ts_ref)
    dias = (datetime.datetime.now() - data_ref).days
    INFO.data_atualizacao = data_ref.strftime("%d/%m/%Y")

    esc = caixa_notificacao_tui(
        modulo="PRIMEIRA INDEXAÇÃO",
        titulo="ARQUIVO LOCAL ENCONTRADO (SEM CACHE .PKL)",
        linhas_mensagem=[
            f"Arquivo localizado: {arq_base} "
            f"(de {data_ref.strftime('%d/%m/%Y')} - há {dias} dias).",
            "O sistema irá compilar o índice rápido (.pkl) e unificar os bairros.",
            "Deseja usar este arquivo local ou baixar uma versão nova da Anatel?",
        ],
        botoes=[
            ("1", "Usar Arquivo Local", "1"),
            ("2", "Baixar Nova Versão da Anatel", "2"),
        ],
    )

    if esc == "2":
        baixar_zip_anatel()

    return processar_base_e_salvar_cache()


def _inicializar_sem_arquivos() -> tuple[pd.DataFrame, str]:
    """Inicializa quando não há nenhum arquivo em disco.

    Returns:
        Tupla ``(df_erbs, texto_status)`` após download.

    Raises:
        SystemExit: Se usuário cancelar.
    """
    esc = caixa_notificacao_tui(
        modulo="DOWNLOAD INICIAL",
        titulo="BANCO DE DADOS NÃO ENCONTRADO",
        linhas_mensagem=[
            f"O pacote '{ARQUIVO_ZIP}' ainda não foi baixado nesta pasta.",
            "Deseja conectar ao servidor da Anatel agora para baixar e construir a base?",
        ],
        botoes=[
            ("S", "Sim, Baixar Base Agora", "1"),
            ("N", "Não, Sair do Sistema", "X"),
        ],
        cor_cabecalho=BARRA_ALERTA,
        fechar_com_esc=False,
    )

    if esc == "1" and baixar_zip_anatel():
        return processar_base_e_salvar_cache()

    encerrar_modo_tui()
    raise SystemExit("Encerrado pelo operador.")