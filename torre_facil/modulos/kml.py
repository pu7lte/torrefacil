"""Exportação KML para Google Earth.

Gera arquivo .kml com pinos coloridos por operadora, agrupados em pastas.
Cada pino contém nome da estação, município, bairro, endereço, tecnologias
e coordenadas GPS.

Recursos:
    - Filtro por UF e município
    - Cores personalizáveis via dicionário (``cores_kml``)
    - Agrupamento por operadora em pastas do Google Earth
"""
from __future__ import annotations

import datetime
import logging
import os
from typing import Any
from xml.sax.saxutils import escape

import pandas as pd

from ..dicionarios import DICIONARIOS, obter_opcoes_uf
from ..painel import filtrar_municipios_exatos
from ..tui.cores import BARRA_VERDE
from ..tui.janelas import formulario_tui, alerta_tui

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Título do módulo
_MODULO = "EXPORTAR KML"

# Cores padrão KML (formato AABBGGRR do Google Earth)
_CORES_KML_PADRAO: dict[str, str] = {
    "VIVO": "ff990099",      # Roxo
    "CLARO": "ff0000ff",     # Vermelho
    "TIM": "ffff6600",       # Azul
    "BRISANET": "ff0080ff",  # Laranja
    "OUTRA": "ff00ff00",     # Verde
}

# URL do ícone padrão do Google Earth
_URL_ICONE = "http://maps.google.com/mapfiles/kml/paddle/wht-blank.png"

# Escala do ícone
_ESCALA_ICONE = 1.1


# ---------------------------------------------------------------------------
# Helpers para formulário
# ---------------------------------------------------------------------------

def _sugerir_cidades(df_erbs: pd.DataFrame, vals: dict[str, str]) -> list[tuple[str, str]]:
    """Gera lista de cidades sugeridas para o combobox.

    Args:
        df_erbs: DataFrame completo de ERBs.
        vals: Valores atuais do formulário.

    Returns:
        Lista de tuplas (cidade, cidade) para o combobox.
    """
    uf = vals.get("uf", "")
    sub = df_erbs[df_erbs["UF"] == uf] if uf else df_erbs
    return [(c, c) for c in sorted(sub["MUNICIPIO_LIMPO"].unique())]


def _gerar_nome_padrao() -> str:
    """Gera nome de arquivo padrão com timestamp.

    Returns:
        Nome do arquivo (ex: "mapa_erbs_20251004_143000.kml").
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"mapa_erbs_{timestamp}.kml"


# ---------------------------------------------------------------------------
# Geração do XML/KML
# ---------------------------------------------------------------------------

def _obter_cores_kml() -> dict[str, str]:
    """Obtém cores KML do dicionário ou usa padrão.

    Returns:
        Dicionário {operadora: cor_kml}.
    """
    return DICIONARIOS.get("cores_kml", _CORES_KML_PADRAO)


def _escrever_cabecalho_kml(f: Any, total_erbs: int) -> None:
    """Escreve o cabeçalho do arquivo KML.

    Args:
        f: Arquivo aberto para escrita.
        total_erbs: Número total de ERBs.
    """
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    f.write('<kml xmlns="http://www.opengis.net/kml/2.2">\n<Document>\n')
    f.write(f'  <name>Torre Fácil - ERBs ({total_erbs})</name>\n')


def _escrever_estilos_kml(f: Any, cores: dict[str, str]) -> None:
    """Escreve os estilos de ícone para cada operadora.

    Args:
        f: Arquivo aberto para escrita.
        cores: Dicionário {operadora: cor_kml}.
    """
    for op, cor in cores.items():
        f.write(f'  <Style id="estilo_{op}">\n')
        f.write(f'    <IconStyle><color>{cor}</color><scale>{_ESCALA_ICONE}</scale>\n')
        f.write(f'      <Icon><href>{_URL_ICONE}</href></Icon>\n')
        f.write('    </IconStyle>\n  </Style>\n')


def _escrever_placemark(
    f: Any,
    nome_pino: str,
    descricao: str,
    estilo: str,
    lon: float,
    lat: float,
) -> None:
    """Escreve um placemark individual no KML.

    Args:
        f: Arquivo aberto para escrita.
        nome_pino: Nome do pino.
        descricao: Descrição HTML do pino.
        estilo: ID do estilo (ex: "estilo_VIVO").
        lon: Longitude.
        lat: Latitude.
    """
    f.write('    <Placemark>\n')
    f.write(f'      <name>{escape(nome_pino)}</name>\n')
    f.write(f'      <description>{escape(descricao)}</description>\n')
    f.write(f'      <styleUrl>#{estilo}</styleUrl>\n')
    f.write(f'      <Point><coordinates>{lon},{lat},0</coordinates></Point>\n')
    f.write('    </Placemark>\n')


def _escrever_pasta_operadora(
    f: Any,
    operadora: str,
    grupo: pd.DataFrame,
    cores: dict[str, str],
) -> None:
    """Escreve uma pasta de operadora com todos os seus placemarks.

    Args:
        f: Arquivo aberto para escrita.
        operadora: Nome da operadora.
        grupo: DataFrame com ERBs da operadora.
        cores: Dicionário de cores.
    """
    estilo = f"estilo_{operadora}" if operadora in cores else "estilo_OUTRA"

    f.write(f'  <Folder>\n    <name>{escape(operadora)} ({len(grupo)} ERBs)</name>\n')

    # Iteração vetorizada (mais rápida que iterrows)
    operadoras = grupo["OPERADORA"].tolist()
    estacoes = grupo["NUM_ESTACAO"].tolist()
    tecnologias = grupo["TECNOLOGIA"].tolist()
    municipios = grupo["MUNICIPIO"].tolist()
    ufs = grupo["UF"].tolist()
    bairros = grupo["BAIRRO"].tolist()
    enderecos = grupo["ENDERECO"].tolist()
    gps_list = grupo["GPS"].tolist()
    lons = grupo["LON_NUM"].tolist()
    lats = grupo["LAT_NUM"].tolist()

    for i in range(len(grupo)):
        nome_pino = f"{operadoras[i]} - Estação {estacoes[i]} ({tecnologias[i]})"
        desc = (
            f"Município: {municipios[i]} ({ufs[i]})\n"
            f"Bairro/Local: {bairros[i]}\n"
            f"Endereço: {enderecos[i]}\n"
            f"Tecnologias: {tecnologias[i]}\n"
            f"GPS: {gps_list[i]}"
        )
        _escrever_placemark(f, nome_pino, desc, estilo, lons[i], lats[i])

    f.write('  </Folder>\n')


def _escrever_rodape_kml(f: Any) -> None:
    """Escreve o rodapé do arquivo KML.

    Args:
        f: Arquivo aberto para escrita.
    """
    f.write('</Document>\n</kml>\n')


def _gerar_arquivo_kml(df_kml: pd.DataFrame, nome_arq: str) -> None:
    """Gera o arquivo KML completo.

    Args:
        df_kml: DataFrame com ERBs e coordenadas válidas.
        nome_arq: Nome do arquivo de saída.
    """
    cores = _obter_cores_kml()

    with open(nome_arq, "w", encoding="utf-8") as f:
        _escrever_cabecalho_kml(f, len(df_kml))
        _escrever_estilos_kml(f, cores)

        for op, grupo in df_kml.groupby("OPERADORA"):
            _escrever_pasta_operadora(f, op, grupo, cores)

        _escrever_rodape_kml(f)

    logger.info("Arquivo KML gerado: %s (%d ERBs)", nome_arq, len(df_kml))


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def exportar_kml(df_erbs: pd.DataFrame) -> None:
    """Ponto de entrada do módulo de exportação KML.

    Args:
        df_erbs: DataFrame completo de ERBs.
    """
    padrao_arq = _gerar_nome_padrao()

    # 1) Formulário
    res = formulario_tui(
        modulo=_MODULO,
        titulo_janela="8. EXPORTAR MAPA GEORREFERENCIADO (.KML GOOGLE EARTH)",
        campos=[
            {
                "nome": "uf",
                "rotulo": "1. Estado/UF",
                "tipo": "droplist",
                "largura": 28,
                "padrao": "RS",
                "opcoes": obter_opcoes_uf(True, "QUALQUER UF"),
            },
            {
                "nome": "municipio",
                "rotulo": "2. Município(s)",
                "tipo": "combobox",
                "largura": 34,
                "opcoes": lambda vals: _sugerir_cidades(df_erbs, vals),
                "dica": "Vazio = Exportar UF inteira | [F2] Abre Droplist",
            },
            {
                "nome": "arquivo",
                "rotulo": "3. Nome do Arquivo KML",
                "largura": 38,
                "padrao": padrao_arq,
                "maiusculo": False,
            },
        ],
        instrucoes_topo=[
            "Gera arquivo KML com pinos coloridos por operadora para Google Earth:",
        ],
    )

    if not res or (not res["uf"] and not res["municipio"]):
        return

    # 2) Filtra base
    df_f = df_erbs.copy()
    if res["uf"]:
        ufs = [u.strip() for u in res["uf"].split(",") if u.strip()]
        df_f = df_f[df_f["UF"].isin(ufs)]
    if res["municipio"]:
        df_f = filtrar_municipios_exatos(df_f, res["municipio"])

    # 3) Filtra ERBs com GPS válido
    df_kml = df_f.dropna(subset=["LAT_NUM", "LON_NUM"]).copy()

    if df_kml.empty:
        alerta_tui(
            _MODULO,
            "SEM COORDENADAS GPS",
            ["Nenhuma ERB com coordenadas GPS válidas encontrada para este filtro."],
        )
        return

    # 4) Gera arquivo
    nome_arq = res["arquivo"] or padrao_arq
    if not nome_arq.lower().endswith(".kml"):
        nome_arq += ".kml"

    try:
        _gerar_arquivo_kml(df_kml, nome_arq)
    except Exception as e:
        logger.exception("Falha ao gerar arquivo KML")
        alerta_tui(
            _MODULO,
            "ERRO NA EXPORTAÇÃO",
            [f"Falha ao gerar o arquivo KML: {type(e).__name__}: {e}"],
        )
        return

    # 5) Confirmação
    alerta_tui(
        "MAPA KML GERADO",
        f"KML CRIADO COM {len(df_kml)} ERBs!",
        [f"Arquivo salvo em: {os.path.abspath(nome_arq)}"],
        cor_titulo=BARRA_VERDE,
    )