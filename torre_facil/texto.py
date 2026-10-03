"""Normalização de texto e extração inteligente de bairros.

Este módulo fornece funções puras e testáveis para:
    - Normalização de strings (uppercase, remoção de acentos).
    - Limpeza e expansão de nomes de bairros.
    - Extração de bairros a partir de logradouros.
    - Formatação de listas de tecnologias (E, H, L, 5G).

Todas as funções são puras (sem efeitos colaterais) e usam cache
interno para performance.

Example:
    >>> from torre_facil.texto import normalizar_texto, extrair_bairro_inteligente
    >>> normalizar_texto("São Paulo")
    'SAO PAULO'
    >>> extrair_bairro_inteligente("Centro", "Rua A, 123")
    'CENTRO'
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Iterable

import pandas as pd

from . import dicionarios as dicionarios_module
from .config import ORDEM_TEC

# ---------------------------------------------------------------------------
# Constantes de domínio (evita strings mágicas espalhadas)
# ---------------------------------------------------------------------------

BAIRRO_NAO_INFORMADO = "BAIRRO NÃO INFORMADO"
ZONA_RURAL = "ZONA RURAL"
SEM_BAIRRO_PREFIX = "SEM BAIRRO"
RODOVIA_PREFIX = "RODOVIA / ESTRADA"

# Valores que indicam "sem bairro" em dados brutos
_VALORES_VAZIOS = frozenset({
    "", "NAN", "NONE", "S/N", "SN", "-", "0",
    "SEM BAIRRO", "NAO INFORMADO", "NÃO INFORMADO",
})

# Stopwords removidas na chave canônica
_STOPWORDS_BAIRRO = frozenset({
    "DE", "DA", "DO", "DAS", "DOS", "E",
    "BAIRRO", "CONJUNTO", "LOTEAMENTO",
})

# Sobrenomes comuns que NÃO devem ser tratados como bairro
_SOBRENOMES_COMUNS = frozenset({
    "MELO", "SILVA", "SOUZA", "SANTOS", "OLIVEIRA",
    "LIMA", "COSTA", "ALMEIDA",
})

# Palavras-chave que indicam zona rural
_INDICADORES_ZONA_RURAL = frozenset({
    "ZONA RURAL", "AREA RURAL", "ÁREA RURAL", "FAZENDA",
    "SITIO", "SÍTIO", "LINHA ", "CAPELA ", "ASSENTAMENTO",
    "GLEBA", "POVOADO", "COLONIA", "COLÔNIA",
})

# Tecnologias válidas para formatação
_TECNOLOGIAS_VALIDAS = frozenset({"E", "H", "L", "5"})


# ---------------------------------------------------------------------------
# Regex pré-compiladas (organizadas por categoria)
# ---------------------------------------------------------------------------

# --- Limpeza geral ---
RE_ESPACOS = re.compile(r"\s+")
RE_ASPAS = re.compile(r'["\']')
RE_NAO_ALFANUM = re.compile(r"[^A-Z0-9\s]")
RE_ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# --- CEP ---
RE_CEP = re.compile(r"\bCEP\s*:?\s*\d{5}[-.]?\d{3}\b")

# --- Condomínios e edifícios ---
RE_CONDOMINIO = re.compile(
    r"^(?:CONDOMINIO|COND.?|EDIFICIO|EDF.?|ED.?|RESIDENCIAL|RES.?)\s+"
    r".{1,50}\s+(?:DE|DO|DA|EM|NO|NA)\s+([A-ZÀ-Ÿ\s-]{4,35})$"
)

# --- Romanos no final (ex: "Centro II" → "Centro") ---
# Nota: removido "1|2|3|4|5" que parecia ser bug (números arábicos)
RE_ROMANO_FINAL = re.compile(r"\s+(?:I|II|III|IV|V|VI|A|B)$")

# --- Prefixos que NÃO são bairros ---
RE_NAO_BAIRRO = re.compile(
    r"^(?:LOTE|LT|QUADRA|QD|BLOCO|BL|APTO|AP|SALA|SL|ANDAR|LOJA|LJ|KM|CX|CAIXA|"
    r"GLEBA|FAZENDA|SITIO|SÍTIO|CHACARA|CHÁCARA|TORRE|ESTACAO|ESTAÇÃO|CONTENE|"
    r"CONTAINER|TERRENO|PARTE)\b"
)

# --- Prefixos de bairro (ex: "BAIRRO CENTRO" → "CENTRO") ---
RE_PREFIXO_BAIRRO = re.compile(
    r"^(?:BAIRRO|BR|B\.|DISTRITO|DIST\.|CONJ\.|CONJUNTO)\s+"
)

# --- Bairro explícito no logradouro ---
RE_BAIRRO_EXPLICITO = re.compile(
    r"\b(?:BAIRRO|DISTRITO(?:\s+DE)?)\s+([A-ZÀ-Ÿ0-9\s-]{3,35})$"
)

# --- Bairro após número (ex: "Rua A, 123 - Centro") ---
RE_BAIRRO_POS_NUM = re.compile(
    r"(?:,\s*|\s+N[º°.]?\s*|-\s*|\s+)"
    r"(?:\d+[A-Z]?|S/?N[º°.]?|SN|S\.N\.)\s*[.,-/]+\s*"
    r"([A-ZÀ-Ÿ][A-ZÀ-Ÿ0-9\s'-]{2,35})$"
)

# --- Separadores ---
RE_SPLIT_PONTOS = re.compile(r"[.,-/]")
RE_SPLIT_TRACO = re.compile(r"[.-]")

# --- Logradouros (para evitar confundir com bairro) ---
RE_LOGRADOURO_INICIO = re.compile(
    r"^(?:RUA|AV|AVENIDA|TRAVESSA|TV|ALAMEDA|AL|ESTRADA|EST|RODOVIA|ROD|PRACA|"
    r"PRAÇA|PCA|LARGO|BECO|SERVIDAO|SERVIDÃO|VIA|BR|RN|RS|SP|GO|MG|PR|SC|BA|"
    r"PE|CE|RJ|ES|MT|MS|PA|AM|TO|MA|PI|AL|SE|PB|DF)\b"
)

# --- Rodovias ---
RE_RODOVIA_GERAL = re.compile(
    r"\b(?:RODOVIA|ROD\.|BR[\s-]\d+|ERS[\s-]\d+|RSC[\s-]\d+|SP[\s-]\d+|"
    r"MG[\s-]\d+|GO[\s-]\d+|PR[\s-]\d+|SC[\s-]\d+)\b"
)


# ---------------------------------------------------------------------------
# Normalização básica
# ---------------------------------------------------------------------------

@lru_cache(maxsize=200_000)
def _normalizar_str(s: str) -> str:
    """Normaliza string: uppercase + remoção de acentos + BOM.

    Args:
        s: String bruta.

    Returns:
        String normalizada (uppercase, sem acentos, sem BOM).
    """
    limpo = s.replace("\ufeff", "").strip().upper()
    return "".join(
        c for c in unicodedata.normalize("NFD", limpo)
        if unicodedata.category(c) != "Mn"
    )


def normalizar_texto(txt: str | float | pd.Series | None) -> str:
    """Normaliza texto para busca/comparação.

    Converte para uppercase, remove acentos e faz strip.
    Seguro contra None, NaN, float e Series do pandas.

    Args:
        txt: Valor a normalizar (pode ser str, float, Series, None).

    Returns:
        String normalizada, ou "" se o valor for inválido/vazio.

    Example:
        >>> normalizar_texto("São Paulo")
        'SAO PAULO'
        >>> normalizar_texto(None)
        ''
        >>> normalizar_texto(float('nan'))
        ''
    """
    if txt is None:
        return ""

    if isinstance(txt, float):
        try:
            if pd.isna(txt):
                return ""
        except (TypeError, ValueError):
            pass
        return _normalizar_str(str(txt))

    if isinstance(txt, pd.Series):
        # Se passar uma Series, normaliza o primeiro elemento
        if txt.empty:
            return ""
        return normalizar_texto(txt.iloc[0])

    return _normalizar_str(str(txt))


def tecla_upper(tecla: str) -> str:
    """Converte tecla única para uppercase, preservando teclas especiais.

    Args:
        tecla: Caractere ou nome de tecla (ex: "a", "F2", "UP").

    Returns:
        Tecla em uppercase se for caractere único, senão retorna intacta.

    Example:
        >>> tecla_upper("a")
        'A'
        >>> tecla_upper("F2")
        'F2'
        >>> tecla_upper("UP")
        'UP'
    """
    return tecla.upper() if isinstance(tecla, str) and len(tecla) == 1 else tecla


# ---------------------------------------------------------------------------
# Limpeza e expansão de bairros
# ---------------------------------------------------------------------------

@lru_cache(maxsize=120_000)
def limpar_e_expandir_bairro(nome: str) -> str:
    """Limpa e expande nome de bairro aplicando regras de normalização.

    Aplica:
        1. Uppercase e remoção de espaços extras.
        2. Detecção de condomínios/edifícios.
        3. Substituições via dicionário de regex (dinâmico).
        4. Remoção de sufixos romanos (ex: "Centro II" → "Centro").

    Args:
        nome: Nome bruto do bairro.

    Returns:
        Nome do bairro limpo e normalizado, ou "BAIRRO NÃO INFORMADO" se vazio.

    Example:
        >>> limpar_e_expandir_bairro("  centro  ")
        'CENTRO'
        >>> limpar_e_expandir_bairro("Condomínio Alpha Ville")
        'ALPHA VILLE'
    """
    if not nome:
        return BAIRRO_NAO_INFORMADO

    s_orig = str(nome)
    s = RE_ESPACOS.sub(" ", s_orig.upper()).strip(" .,;-/\"'")

    # Casos especiais que não precisam de processamento adicional
    if s.startswith(("SEM BAIRRO", "ZONA RURAL", "RODOVIA", "BAIRRO NÃO")):
        return s

    # Detecta condomínios/edifícios e extrai o nome
    if s.startswith(("CONDOMINIO", "COND", "EDIFICIO", "EDF", "ED.", "RESIDENCIAL", "RES.")):
        m_cond = RE_CONDOMINIO.match(s)
        if m_cond:
            cand = m_cond.group(1).strip()
            # Evita confundir sobrenomes comuns com bairros
            if cand not in _SOBRENOMES_COMUNS:
                s = cand

    # Aplica substituições dinâmicas do dicionário de regex
    for regex_comp, novo in dicionarios_module.REGEX_BAIRROS_COMPILADOS:
        s = regex_comp.sub(novo, s)

    # Remove sufixos romanos (ex: "Centro II" → "Centro")
    s_sem_romano = RE_ROMANO_FINAL.sub("", s).strip()
    if len(s_sem_romano) >= 4 and not s_sem_romano.endswith(
        ("ZONA", "DISTRITO", "SETOR", "ETAPA", "GLEBA", "QUADRA")
    ):
        s = s_sem_romano

    return RE_ESPACOS.sub(" ", s).strip()


def validar_candidato_bairro(cand: str) -> str | None:
    """Valida se uma string é um candidato válido a nome de bairro.

    Args:
        cand: String candidata (ex: extraída de logradouro).

    Returns:
        Nome do bairro validado e limpo, ou None se não for válido.

    Example:
        >>> validar_candidato_bairro("Centro")
        'CENTRO'
        >>> validar_candidato_bairro("S/N")
        None
        >>> validar_candidato_bairro("Lote 5")
        None
    """
    cand = cand.strip(" .,;-/()")
    cand = RE_PREFIXO_BAIRRO.sub("", cand).strip()

    # Rejeita strings muito curtas ou puramente numéricas
    if len(cand) < 3 or cand.isdigit():
        return None

    # Casos especiais de zona rural
    if cand in ("S/N", "SN", "S.N.", "ZONA RURAL", "AREA RURAL", "ÁREA RURAL",
                "CENTRO/ZONA RURAL"):
        return ZONA_RURAL if "RURAL" in cand else None

    # Rejeita se começar com prefixo de não-bairro
    if RE_NAO_BAIRRO.match(cand):
        return None

    return limpar_e_expandir_bairro(cand)


# ---------------------------------------------------------------------------
# Extração inteligente de bairros
# ---------------------------------------------------------------------------

def _extrair_de_bairro_explicito(logradouro_up: str) -> str | None:
    """Tenta extrair bairro quando há menção explícita ('BAIRRO X', 'DISTRITO X')."""
    if "BAIRRO" not in logradouro_up and "DISTRITO" not in logradouro_up:
        return None

    m_exp = RE_BAIRRO_EXPLICITO.search(logradouro_up)
    if m_exp:
        return validar_candidato_bairro(m_exp.group(1))
    return None


def _extrair_de_pos_numero(logradouro_up: str) -> str | None:
    """Tenta extrair bairro após número (ex: 'Rua A, 123 - Centro')."""
    m_num = RE_BAIRRO_POS_NUM.search(logradouro_up)
    if not m_num:
        return None

    trecho_final = m_num.group(1).strip()
    subpartes = [p.strip() for p in RE_SPLIT_PONTOS.split(trecho_final) if p.strip()]

    # Tenta da última parte para a primeira (mais provável ser bairro)
    for parte in reversed(subpartes):
        res = validar_candidato_bairro(parte)
        if res:
            return res
    return None


def _extrair_de_separador_traco(logradouro_up: str) -> str | None:
    """Tenta extrair bairro após separador (ex: 'Rua A - Centro')."""
    if "." not in logradouro_up and "-" not in logradouro_up:
        return None

    partes = [p.strip() for p in RE_SPLIT_TRACO.split(logradouro_up) if p.strip()]
    if len(partes) < 2:
        return None

    ultima = partes[-1]
    # Evita confundir logradouro com bairro
    if RE_LOGRADOURO_INICIO.match(ultima):
        return None

    return validar_candidato_bairro(ultima)


def _detectar_zona_rural(logradouro_up: str) -> str | None:
    """Detecta se o logradouro indica zona rural."""
    if any(indicador in logradouro_up for indicador in _INDICADORES_ZONA_RURAL):
        return f"ZONA RURAL ({logradouro_up[:35]})"
    return None


def _detectar_rodovia(logradouro_up: str) -> str | None:
    """Detecta se o logradouro é uma rodovia/estrada."""
    if RE_RODOVIA_GERAL.search(logradouro_up):
        return f"RODOVIA / ESTRADA ({logradouro_up[:35]})"
    return None


def extrair_bairro_inteligente(
    bairro: str | None,
    logradouro: str | None,
) -> str:
    """Extrai bairro de forma inteligente, usando campo bairro ou logradouro.

    Algoritmo:
        1. Se campo bairro for válido, usa ele diretamente.
        2. Senão, tenta extrair do logradouro usando múltiplas heurísticas:
           a. Menção explícita ("BAIRRO X", "DISTRITO X").
           b. Após número ("Rua A, 123 - Centro").
           c. Após separador ("Rua A - Centro").
           d. Detecção de zona rural.
           e. Detecção de rodovia.
        3. Se nada funcionar, retorna "SEM BAIRRO (...)" com trecho do logradouro.

    Args:
        bairro: Campo bairro bruto (pode ser None, vazio, ou inválido).
        logradouro: Campo logradouro bruto (usado como fallback).

    Returns:
        Nome do bairro extraído, ou "BAIRRO NÃO INFORMADO" se não for possível.

    Example:
        >>> extrair_bairro_inteligente("Centro", "Rua A, 123")
        'CENTRO'
        >>> extrair_bairro_inteligente(None, "Rua A, 123 - Centro")
        'CENTRO'
        >>> extrair_bairro_inteligente(None, "BR-101, KM 50")
        'RODOVIA / ESTRADA (BR-101, KM 50)'
    """
    # 1) Tenta usar o campo bairro diretamente
    b = str(bairro).strip().strip(' "\'.,;-') if bairro else ""
    if b.upper() not in _VALORES_VAZIOS:
        return limpar_e_expandir_bairro(b)

    # 2) Fallback: extrair do logradouro
    l = str(logradouro).strip().strip('"\'.,;-') if logradouro else ""
    if l.upper() in _VALORES_VAZIOS:
        return BAIRRO_NAO_INFORMADO

    # Limpa o logradouro para processamento
    l_up = RE_ASPAS.sub("", l.upper()).strip()
    if "CEP" in l_up:
        l_up = RE_CEP.sub("", l_up).strip(" .,;-")

    # 2a) Menção explícita de bairro
    if res := _extrair_de_bairro_explicito(l_up):
        return res

    # 2b) Bairro após número
    if res := _extrair_de_pos_numero(l_up):
        return res

    # 2c) Bairro após separador (traço/ponto)
    if res := _extrair_de_separador_traco(l_up):
        return res

    # 2d) Zona rural
    if res := _detectar_zona_rural(l_up):
        return res

    # 2e) Rodovia
    if res := _detectar_rodovia(l_up):
        return res

    # 3) Nada funcionou — retorna com prefixo
    return f"SEM BAIRRO ({l_up[:38]})"


# ---------------------------------------------------------------------------
# Chave canônica e formatação
# ---------------------------------------------------------------------------

def chave_canonica_bairro(nome: str) -> str:
    """Gera chave canônica para comparação de bairros.

    Remove stopwords e normaliza para permitir comparação fuzzy.

    Args:
        nome: Nome do bairro.

    Returns:
        Chave canônica (uppercase, sem acentos, sem stopwords).

    Example:
        >>> chave_canonica_bairro("Bairro Centro")
        'CENTRO'
        >>> chave_canonica_bairro("Conjunto Vila Nova")
        'VILA NOVA'
    """
    n = normalizar_texto(limpar_e_expandir_bairro(nome))
    n = RE_NAO_ALFANUM.sub(" ", n)
    return " ".join(t for t in n.split() if t not in _STOPWORDS_BAIRRO)


def formatar_lista_tec(siglas: Iterable[str]) -> str:
    """Formata lista de tecnologias em string legível.

    Args:
        siglas: Iterável de siglas de tecnologia (ex: ["E", "H", "5"]).

    Returns:
        String formatada e ordenada, ou "TODAS" se todas as tecnologias estiverem presentes.

    Example:
        >>> formatar_lista_tec(["E", "H"])
        'E, H'
        >>> formatar_lista_tec(["E", "H", "L", "5"])
        'TODAS'
        >>> formatar_lista_tec([])
        '-'
    """
    unicas = sorted(
        {s for s in siglas if s in _TECNOLOGIAS_VALIDAS},
        key=lambda x: ORDEM_TEC[x],
    )

    if len(unicas) == 4:
        return "TODAS"

    return ", ".join(unicas) if unicas else "-"