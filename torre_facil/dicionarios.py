"""Dicionários externos em JSON + regex de bairros compiladas.

Este módulo gerencia:
    - Dicionários de dados estáticos (UFs, operadoras, cores KML).
    - Regex de substituição para normalização de bairros.

Estratégia de estado (IMPORTANTE):
    As variáveis globais ``REGEX_BAIRROS_COMPILADOS`` e ``DICIONARIOS``
    são MUTADAS in-place (``clear()`` + ``extend()``/``update()``), nunca
    reatribuídas. Isso garante que consumidores que fizeram
    ``from .dicionarios import X`` continuem vendo a lista/dict atualizado.

    ``carregar_ou_criar_dicionarios`` sempre compila as regex antes de retornar.
    ``carregar_globais`` atualiza as duas variáveis e devolve ``DICIONARIOS``.

Example:
    >>> from torre_facil.dicionarios import carregar_globais, DICIONARIOS
    >>> dados = carregar_globais()
    >>> print(DICIONARIOS["operadoras_padrao"])
    {'CLARO': ['CLARO'], 'VIVO': ['TELEFONICA', ...]}
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Final

from .config import ARQUIVO_DICIONARIOS

logger = logging.getLogger(__name__)

__all__ = [
    "REGEX_BAIRROS_COMPILADOS",
    "DICIONARIOS",
    "gerar_dicionarios_padrao",
    "compilar_regex_dicionarios",
    "carregar_ou_criar_dicionarios",
    "carregar_globais",
    "obter_opcoes_uf",
]


# ---------------------------------------------------------------------------
# Estado do módulo — MUTADO in-place, nunca reatribuído
# ---------------------------------------------------------------------------

REGEX_BAIRROS_COMPILADOS: list[tuple[re.Pattern[str], str]] = []
"""Lista de tuplas (regex compilada, substituição) para normalização de bairros.

Esta lista é mutada in-place por ``compilar_regex_dicionarios``.
Não reatribua este nome, apenas use ``clear()`` + ``extend()``.
"""

DICIONARIOS: dict[str, object] = {}
"""Dicionário principal com todos os dados estáticos.

Chaves esperadas:
    - ufs_brasil: list[str]
    - mapa_ufs_br: dict[str, list[str]]
    - substituicoes_bairros: list[tuple[str, str]]
    - operadoras_padrao: dict[str, list[str]]
    - cores_kml: dict[str, str]

Este dict é mutado in-place por ``carregar_globais``.
Não reatribua este nome, apenas use ``clear()`` + ``update()``.
"""


# ---------------------------------------------------------------------------
# Dados padrão (separados para legibilidade)
# ---------------------------------------------------------------------------

_UFS_BRASIL: Final[list[str]] = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA",
    "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN",
    "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]

_MAPA_UFS_BR: Final[dict[str, list[str]]] = {
    "010": ["DF", "GO", "TO", "MA", "PA"],
    "020": ["DF", "GO", "BA", "PI", "CE"],
    "030": ["DF", "GO", "MG", "BA"],
    "040": ["DF", "GO", "MG", "RJ"],
    "050": ["DF", "GO", "MG", "SP"],
    "060": ["DF", "GO", "MS"],
    "070": ["DF", "GO", "MT"],
    "080": ["DF", "GO", "MT"],
    "101": ["RN", "PB", "PE", "AL", "SE", "BA", "ES", "RJ", "SP", "PR", "SC", "RS"],
    "104": ["RN", "PB", "PE", "AL"],
    "110": ["RN", "PB", "PE", "AL", "BA"],
    "116": ["CE", "PB", "PE", "BA", "MG", "RJ", "SP", "PR", "SC", "RS"],
    "122": ["CE", "PE", "BA", "MG"],
    "135": ["MA", "PI", "BA", "MG"],
    "153": ["PA", "TO", "GO", "MG", "SP", "PR", "SC", "RS"],
    "158": ["PA", "MT", "GO", "MS", "SP", "PR", "SC", "RS"],
    "163": ["PA", "MT", "MS", "PR", "SC", "RS"],
    "174": ["MT", "RO", "AM", "RR"],
    "222": ["CE", "PI", "MA", "PA"],
    "226": ["RN", "CE", "PI", "MA", "TO"],
    "230": ["PB", "CE", "PI", "MA", "TO", "PA", "AM"],
    "232": ["PE"],
    "235": ["SE", "BA", "PE", "PI", "MA", "TO", "PA"],
    "242": ["BA", "TO", "MT"],
    "251": ["BA", "MG", "DF", "GO", "MT"],
    "262": ["ES", "MG", "SP", "MS"],
    "267": ["MG", "SP", "MS"],
    "272": ["SP", "PR"],
    "277": ["PR"],
    "280": ["SC"],
    "282": ["SC"],
    "285": ["SC", "RS"],
    "290": ["RS"],
    "293": ["RS"],
    "304": ["RN", "CE"],
    "316": ["PA", "MA", "PI", "PE", "AL"],
    "319": ["AM", "RO"],
    "324": ["BA"],
    "343": ["PI"],
    "364": ["SP", "MG", "GO", "MT", "RO", "AC"],
    "365": ["MG"],
    "369": ["MG", "SP", "PR"],
    "376": ["PR", "MS"],
    "381": ["ES", "MG", "SP"],
    "386": ["RS", "SC"],
    "392": ["RS"],
    "405": ["RN", "PB"],
    "406": ["RN"],
    "407": ["PI", "PE", "BA"],
    "427": ["RN", "PB"],
    "453": ["RS"],
    "470": ["SC", "RS"],
    "471": ["RS"],
}

_OPERADORAS_PADRAO: Final[dict[str, list[str]]] = {
    "CLARO": ["CLARO"],
    "VIVO": ["TELEFONICA", "TELEFÔNICA", "VIVO"],
    "TIM": ["TIM"],
    "BRISANET": ["BRISANET"],
    "ALGAR": ["ALGAR"],
    "UNIFIQUE": ["UNIFIQUE"],
}

_CORES_KML: Final[dict[str, str]] = {
    "VIVO": "ff990099",
    "CLARO": "ff0000ff",
    "TIM": "ffff6600",
    "BRISANET": "ff0080ff",
    "OUTRA": "ff00ff00",
}

_SUBSTITUICOES_BAIRROS: Final[list[tuple[str, str]]] = [
    # --- Abreviações comuns ---
    (r"\bN\.?\s*SRA\.?\b", "NOSSA SENHORA"),
    (r"\bNOSSA\s+SRA\.?\b", "NOSSA SENHORA"),
    (r"\bN\.?\s*S\.?\s+(?=[DAEO]\b)", "NOSSA SENHORA "),
    (r"\bSTA\b\.?", "SANTA"),
    (r"\bSTO\b\.?", "SANTO"),
    (r"\bS\.?\s+(?=[A-ZÀ-Ÿ]{3,})", "SÃO "),
    (r"\bJD\b\.?", "JARDIM"),
    (r"\bJRD\b\.?", "JARDIM"),
    (r"\bJARDIN\b", "JARDIM"),
    (r"\bPQ\b\.?", "PARQUE"),
    (r"\bPRQ\b\.?", "PARQUE"),
    (r"\bVL\b\.?", "VILA"),
    (r"\bCJ\b\.?", "CONJUNTO"),
    (r"\bCONJ\b\.?", "CONJUNTO"),
    (r"\bCONJ\.?\s*HAB\b\.?", "CONJUNTO HABITACIONAL"),
    (r"\bCOHAB\b", "CONJUNTO HABITACIONAL"),
    (r"\bLOT\b\.?", "LOTEAMENTO"),
    (r"\bRES\b\.?", "RESIDENCIAL"),
    (r"\bRESID\b\.?", "RESIDENCIAL"),
    (r"\bCHAC\b\.?", "CHÁCARA"),
    (r"\bBALN\b\.?", "BALNEÁRIO"),
    (r"\bBAL\b\.?", "BALNEÁRIO"),
    # --- Industriais / rurais ---
    (r"\bDIST\.?\s*IND\.?\b", "DISTRITO INDUSTRIAL"),
    (r"\bD\.?\s*I\.?\b", "DISTRITO INDUSTRIAL"),
    (r"\bSET\.?\s*IND\.?\b", "SETOR INDUSTRIAL"),
    (r"\bZ\.?\s*RURAL\b", "ZONA RURAL"),
    (r"\bA\.?\s*RURAL\b", "ZONA RURAL"),
    (r"\bAREA\s+RURAL\b", "ZONA RURAL"),
    (r"\bÁREA\s+RURAL\b", "ZONA RURAL"),
    # --- Títulos ---
    (r"\bPRES\b\.?", "PRESIDENTE"),
    (r"\bGOV\b\.?", "GOVERNADOR"),
    (r"\bSEN\b\.?", "SENADOR"),
    (r"\bDEP\b\.?", "DEPUTADO"),
    (r"\bMAL\b\.?", "MARECHAL"),
    (r"\bGEN\b\.?", "GENERAL"),
    (r"\bCEL\b\.?", "CORONEL"),
    (r"\bBRIG\b\.?", "BRIGADEIRO"),
    (r"\bPROF\b\.?", "PROFESSOR"),
    (r"\bENG\b\.?", "ENGENHEIRO"),
    (r"\bDR\b\.?", "DOUTOR"),
    (r"\bDRA\b\.?", "DOUTORA"),
    (r"\bPE\b\.?", "PADRE"),
    (r"\bMONS\b\.?", "MONSENHOR"),
    (r"\bALM\b\.?", "ALMIRANTE"),
    (r"\bVISC\b\.?", "VISCONDE"),
    (r"\bMARQ\b\.?", "MARQUÊS"),
    # --- Acentuação ---
    (r"\bAPRESENTCAO\b", "APRESENTAÇÃO"),
    (r"\bAPRESENTACAO\b", "APRESENTAÇÃO"),
    (r"\bCONCEICAO\b", "CONCEIÇÃO"),
    (r"\bASSUNCAO\b", "ASSUNÇÃO"),
    (r"\bCONSOLACAO\b", "CONSOLAÇÃO"),
    (r"\bABOLICAO\b", "ABOLIÇÃO"),
    (r"\bLIBERTACAO\b", "LIBERTAÇÃO"),
    (r"\bREDENCAO\b", "REDENÇÃO"),
    (r"\bRESSURREICAO\b", "RESSURREIÇÃO"),
    (r"\bRENASCENCA\b", "RENASCENÇA"),
    (r"\bESPERANCA\b", "ESPERANÇA"),
    (r"\bBONANCA\b", "BONANÇA"),
    (r"\bALIANCA\b", "ALIANÇA"),
    (r"\bMUDANCA\b", "MUDANÇA"),
    (r"\bCRIANCA\b", "CRIANÇA"),
    (r"\bSAO\b", "SÃO"),
    (r"\bJOAO\b", "JOÃO"),
    (r"\bJOSE\b", "JOSÉ"),
    (r"\bINES\b", "INÊS"),
    (r"\bMONICA\b", "MÔNICA"),
    (r"\bLUCIA\b", "LÚCIA"),
    (r"\bCECILIA\b", "CECÍLIA"),
    (r"\bEFIGENIA\b", "EFIGÊNIA"),
    (r"\bIFIGENIA\b", "IFIGÊNIA"),
    (r"\bSEBASTIAO\b", "SEBASTIÃO"),
    (r"\bCRISTOVAO\b", "CRISTÓVÃO"),
    (r"\bSIMAO\b", "SIMÃO"),
    (r"\bDAMIAO\b", "DAMIÃO"),
    (r"\bANTONIO\b", "ANTÔNIO"),
    (r"\bGERONIMO\b", "GERÔNIMO"),
    (r"\bJERONIMO\b", "JERÔNIMO"),
    (r"\bLOURENCO\b", "LOURENÇO"),
    (r"\bGONCALO\b", "GONÇALO"),
    (r"\bUNIAO\b", "UNIÃO"),
    (r"\bESTACAO\b", "ESTAÇÃO"),
    (r"\bFUNDACAO\b", "FUNDAÇÃO"),
    (r"\bAVIACAO\b", "AVIAÇÃO"),
    (r"\bAMERICA\b", "AMÉRICA"),
    (r"\bBRASILIA\b", "BRASÍLIA"),
    (r"\bVITORIA\b", "VITÓRIA"),
    (r"\bGLORIA\b", "GLÓRIA"),
    (r"\bINDEPENDENCIA\b", "INDEPENDÊNCIA"),
    (r"\bPROVIDENCIA\b", "PROVIDÊNCIA"),
    (r"\bUNIVERSITARIO\b", "UNIVERSITÁRIO"),
    (r"\bINDUSTRIARIO\b", "INDUSTRIÁRIOS"),
    (r"\bCOMERCIO\b", "COMÉRCIO"),
    (r"\bCENTENARIO\b", "CENTENÁRIO"),
    (r"\bBANCARIOS\b", "BANCÁRIOS"),
    (r"\bFUNCIONARIOS\b", "FUNCIONÁRIOS"),
    (r"\bOPERARIOS\b", "OPERÁRIOS"),
    (r"\bFERROVIARIOS\b", "FERROVIÁRIOS"),
    (r"\bDESCOBERT\b", "DESCOBERTA"),
    # --- Casos especiais (RN) ---
    (r"\bCIDADE\s+DA\s+ESPE\b", "CIDADE DA ESPERANÇA"),
    (r"\bCIDADE\s+ESPERANCA\b", "CIDADE DA ESPERANÇA"),
    (r"\bCIDADE\s+ESPERANÇA\b", "CIDADE DA ESPERANÇA"),
    (r"\bPARQUE\s+DUNAS\b", "PARQUE DAS DUNAS"),
    (r"\bDIX\s SEPT\s ROSADO\b", "DIX-SEPT ROSADO"),
    (r"^DIX[\s\-]*SEPT$", "DIX-SEPT ROSADO"),
    (r"\bRENDINHA\b", "REDINHA"),
]


# ---------------------------------------------------------------------------
# Geração de dicionários padrão
# ---------------------------------------------------------------------------

def gerar_dicionarios_padrao() -> dict[str, object]:
    """Gera o dicionário padrão completo.

    Returns:
        Dict com todas as chaves esperadas (ufs_brasil, mapa_ufs_br, etc.).

    Example:
        >>> dados = gerar_dicionarios_padrao()
        >>> "ufs_brasil" in dados
        True
        >>> len(dados["substituicoes_bairros"]) > 30
        True
    """
    return {
        "ufs_brasil": list(_UFS_BRASIL),
        "mapa_ufs_br": dict(_MAPA_UFS_BR),
        "substituicoes_bairros": [list(item) for item in _SUBSTITUICOES_BAIRROS],
        "operadoras_padrao": dict(_OPERADORAS_PADRAO),
        "cores_kml": dict(_CORES_KML),
    }


# ---------------------------------------------------------------------------
# Compilação de regex
# ---------------------------------------------------------------------------

def compilar_regex_dicionarios(dic: dict[str, object]) -> int:
    """Compila ``substituicoes_bairros`` para dentro de REGEX_BAIRROS_COMPILADOS.

    Muta a lista global in-place (``clear()`` + ``extend()``).

    Args:
        dic: Dicionário com a chave ``substituicoes_bairros``.

    Returns:
        Número de regexes compiladas com sucesso.

    Example:
        >>> dados = gerar_dicionarios_padrao()
        >>> n = compilar_regex_dicionarios(dados)
        >>> n > 0
        True
        >>> len(REGEX_BAIRROS_COMPILADOS) == n
        True
    """
    substituicoes = dic.get("substituicoes_bairros", [])
    compiladas: list[tuple[re.Pattern[str], str]] = []
    erros = 0

    for item in substituicoes:
        try:
            padrao, novo = item[0], item[1]
        except (TypeError, IndexError, KeyError):
            logger.warning("Item inválido em substituicoes_bairros: %r", item)
            erros += 1
            continue

        try:
            compiladas.append((re.compile(padrao), str(novo)))
        except re.error as e:
            logger.warning("Regex inválida '%s': %s", padrao, e)
            erros += 1
            continue

    # Mutação in-place para não quebrar consumidores com import congelado
    REGEX_BAIRROS_COMPILADOS.clear()
    REGEX_BAIRROS_COMPILADOS.extend(compiladas)

    logger.info(
        "Compiladas %d regexes de bairro (%d erros).",
        len(compiladas), erros
    )
    return len(compiladas)


# ---------------------------------------------------------------------------
# Carga e persistência
# ---------------------------------------------------------------------------

def _mesclar_dicionarios_antigos(
    dados_disco: dict[str, object],
    dados_padrao: dict[str, object],
) -> dict[str, object]:
    """Mescla dicionários antigos com o padrão (adiciona substituições faltantes).

    Args:
        dados_disco: Dados carregados do disco (possivelmente antigos).
        dados_padrao: Dados padrão completos.

    Returns:
        Dados mesclados (mutação in-place em ``dados_disco``).
    """
    existentes = {
        str(p): str(n)
        for p, n in dados_disco.get("substituicoes_bairros", [])
    }

    novas = []
    for p, n in dados_padrao["substituicoes_bairros"]:
        if str(p) not in existentes:
            novas.append([str(p), str(n)])

    if novas:
        dados_disco.setdefault("substituicoes_bairros", []).extend(novas)
        logger.info("Mescladas %d substituições faltantes.", len(novas))

    return dados_disco


def carregar_ou_criar_dicionarios(forcar_recriacao: bool = False) -> dict[str, object]:
    """Carrega o JSON do disco (ou cria), compila regex e retorna o dict.

    Args:
        forcar_recriacao: Se True, recria o arquivo mesmo se existir.

    Returns:
        Dicionário carregado/criado.

    Example:
        >>> dados = carregar_ou_criar_dicionarios()
        >>> "operadoras_padrao" in dados
        True
    """
    caminho = Path(ARQUIVO_DICIONARIOS)

    # 1) Recriar do zero se solicitado ou se arquivo não existir
    if forcar_recriacao or not caminho.exists():
        logger.info("Criando arquivo de dicionários: %s", caminho)
        dados = gerar_dicionarios_padrao()
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with caminho.open("w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        compilar_regex_dicionarios(dados)
        return dados

    # 2) Tentar carregar do disco
    try:
        with caminho.open("r", encoding="utf-8") as f:
            dados = json.load(f)

        # Mescla se o arquivo em disco for antigo (poucas substituições)
        if len(dados.get("substituicoes_bairros", [])) < 30:
            padrao = gerar_dicionarios_padrao()
            dados = _mesclar_dicionarios_antigos(dados, padrao)
            with caminho.open("w", encoding="utf-8") as f_out:
                json.dump(dados, f_out, ensure_ascii=False, indent=2)

        compilar_regex_dicionarios(dados)
        return dados

    except (json.JSONDecodeError, OSError) as e:
        logger.warning(
            "Falha ao carregar dicionários (%s: %s); recriando padrão.",
            type(e).__name__, e
        )
        dados = gerar_dicionarios_padrao()
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with caminho.open("w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        compilar_regex_dicionarios(dados)
        return dados

    except Exception:
        logger.exception("Erro inesperado ao carregar dicionários; recriando padrão.")
        dados = gerar_dicionarios_padrao()
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with caminho.open("w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        compilar_regex_dicionarios(dados)
        return dados


def carregar_globais() -> dict[str, object]:
    """Popula DICIONARIOS e REGEX_BAIRROS_COMPILADOS (in-place) e devolve DICIONARIOS.

    Esta é a função principal para inicializar o estado global do módulo.

    Returns:
        O dict DICIONARIOS (mutado in-place).

    Example:
        >>> dados = carregar_globais()
        >>> dados is DICIONARIOS
        True
        >>> len(REGEX_BAIRROS_COMPILADOS) > 0
        True
    """
    dados = carregar_ou_criar_dicionarios()

    # Mutação in-place — substitui o conteúdo sem reatribuir o nome
    DICIONARIOS.clear()
    DICIONARIOS.update(dados)

    # compilar já foi chamado dentro de carregar_ou_criar_dicionarios
    return DICIONARIOS


# ---------------------------------------------------------------------------
# Funções utilitárias
# ---------------------------------------------------------------------------

def obter_opcoes_uf(
    incluir_todas: bool = True,
    rotulo_todas: str = "TODAS AS UFs (BRASIL)",
) -> list[tuple[str, str]]:
    """Retorna lista de opções de UF para menus/dropdowns.

    Args:
        incluir_todas: Se True, inclui opção "todas" no início.
        rotulo_todas: Rótulo da opção "todas".

    Returns:
        Lista de tuplas ``(valor, rótulo)``.

    Example:
        >>> opcoes = obter_opcoes_uf()
        >>> opcoes[0]
        ('', 'TODAS AS UFs (BRASIL)')
        >>> ('SP', 'SP') in opcoes
        True
    """
    # ✅ CORREÇÃO: auto-carrega os dicionários se necessário — evita listas
    # vazias quando o módulo é usado antes da carga global (ex.: análise por
    # faixa mostrava só "Brasil inteiro" e nenhum estado).
    if not DICIONARIOS.get("ufs_brasil"):
        try:
            carregar_globais()
        except Exception:  # pragma: no cover - nunca deve travar a UI
            pass
    ufs = sorted(str(u) for u in DICIONARIOS.get("ufs_brasil", []))
    opcoes: list[tuple[str, str]] = []

    if incluir_todas:
        opcoes.append(("", rotulo_todas))

    opcoes.extend((u, u) for u in ufs)
    return opcoes