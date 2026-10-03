"""Motor de unificação de bairros por município.

Complementa ``texto.py`` (que faz limpeza/expansão por linha) com a
consolidação por cidade, usando:
    - Chave canônica (tokens ordenados sem stopwords)
    - ``SequenceMatcher`` para grafias próximas
    - Regras de "opostos" (NORTE/SUL, NOVO/VELHO, etc.)
    - Cache em JSON por ``UF|MUNICIPIO``

Arquitetura:
    1. ``unificar_bairros_por_municipio``: função principal, recebe DataFrame
       e devolve lista alinhada com nomes unificados.
    2. ``_unificar_uma_cidade``: unifica bairros de um município específico.
    3. ``_buscar_alvo_proximo``: encontra chave consolidada próxima para fusão.
    4. Cache em disco: JSON com mapeamento ``{UF|MUNICIPIO: {antigo: novo}}``.
"""
from __future__ import annotations

import difflib
import json
import logging
import os
import re
from typing import Any

from ..config import ARQUIVO_CACHE_BAIRROS
from ..estado import INFO
from ..texto import (
    RE_ESPACOS,
    RE_NAO_ALFANUM,
    chave_canonica_bairro,
    extrair_bairro_inteligente,
    limpar_e_expandir_bairro,
    normalizar_texto,
    validar_candidato_bairro,
)
from ..tui.janelas import desenhar_progresso_tui

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# API pública (re-export)
# ---------------------------------------------------------------------------

__all__ = [
    "limpar_e_expandir_bairro",
    "extrair_bairro_inteligente",
    "validar_candidato_bairro",
    "chave_canonica_bairro",
    "carregar_cache_bairros_disco",
    "salvar_cache_bairros_disco",
    "unificar_bairros_por_municipio",
]


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Prefixos que NÃO participam da unificação
_IGNORES: tuple[str, ...] = (
    "SEM BAIRRO",
    "ZONA RURAL",
    "RODOVIA",
    "BAIRRO NÃO",
)

# Palavras que, quando divergem entre dois candidatos, IMPEDEM a fusão
_OPOSTOS: frozenset[str] = frozenset({
    "NORTE", "SUL", "LESTE", "OESTE",
    "ALTO", "BAIXO",
    "NOVA", "VELHA", "NOVO", "VELHO",
    "CENTRO", "PRAIA", "PARQUE", "JARDIM", "VILA",
})

# Limiares do algoritmo de fusão
_LIMITE_BUSCA_RAPIDA = 200
_LIMITE_CANDIDATOS_CONSOLIDADAS = 220
_SIMILARIDADE_MINIMA = 0.84
_PROPORCAO_MINIMA_PREFIXO = 0.40
_TAMANHO_MINIMO_PREFIXO = 6
_TAMANHO_MINIMO_SEQUENCE = 5
_DIFERENCA_MAXIMA_TAMANHO = 2


# ---------------------------------------------------------------------------
# Cache de bairros em disco (JSON por cidade)
# ---------------------------------------------------------------------------

def carregar_cache_bairros_disco() -> dict[str, dict[str, str]]:
    """Carrega cache de bairros unificados do disco.

    Returns:
        Dicionário ``{"UF|MUNICIPIO": {"NOME ANTIGO": "NOME UNIFICADO", ...}}``.
        Retorna dict vazio se arquivo não existir ou for inválido.
    """
    if not os.path.exists(ARQUIVO_CACHE_BAIRROS):
        logger.debug("Cache de bairros não encontrado: %s", ARQUIVO_CACHE_BAIRROS)
        return {}

    try:
        with open(ARQUIVO_CACHE_BAIRROS, "r", encoding="utf-8") as f:
            cache = json.load(f)
        logger.debug(
            "Cache de bairros carregado: %d municípios",
            len(cache),
        )
        return cache
    except Exception:
        logger.exception("Falha ao carregar cache de bairros")
        INFO.ultimo_erro = f"Falha ao carregar cache de bairros"
        return {}


def salvar_cache_bairros_disco(mapa_cidades: dict[str, dict[str, str]]) -> None:
    """Salva cache de bairros unificados no disco.

    Args:
        mapa_cidades: Dicionário ``{"UF|MUNICIPIO": {"antigo": "novo"}}``.

    Side effects:
        - Cria/atualiza ``ARQUIVO_CACHE_BAIRROS``.
        - Define ``INFO.ultimo_erro`` em caso de falha.
    """
    try:
        with open(ARQUIVO_CACHE_BAIRROS, "w", encoding="utf-8") as f:
            json.dump(mapa_cidades, f, ensure_ascii=False, indent=2)
        logger.info(
            "Cache de bairros salvo: %d municípios",
            len(mapa_cidades),
        )
    except Exception:
        logger.exception("Falha ao salvar cache de bairros")
        INFO.ultimo_erro = f"Falha ao salvar cache de bairros"


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _reduzir_municipio(mun: str) -> str:
    """Remove sufixo de UF do nome do município.

    Args:
        mun: Nome do município (ex: "NATAL - RN").

    Returns:
        Nome sem sufixo de UF (ex: "NATAL").

    Examples:
        >>> _reduzir_municipio("NATAL - RN")
        'NATAL'
        >>> _reduzir_municipio("SAO PAULO-SP")
        'SAO PAULO'
    """
    return re.sub(r"\s*-\s*[A-Za-z]{2}$", "", mun).upper()


def _contar_bairros_por_cidade(
    ufs: list[str],
    muns: list[str],
    bairros: list[str],
) -> dict[str, dict[str, int]]:
    """Conta ocorrências de cada bairro por município.

    Args:
        ufs: Lista de UFs.
        muns: Lista de municípios.
        bairros: Lista de bairros.

    Returns:
        Dicionário ``{"UF|MUN": {"BAIRRO": contagem}}``.
    """
    contagem: dict[str, dict[str, int]] = {}
    for u, m, b in zip(ufs, muns, bairros):
        chave_cid = f"{u}|{m}"
        d_cid = contagem.setdefault(chave_cid, {})
        d_cid[b] = d_cid.get(b, 0) + 1
    return contagem


def _selecionar_cidades_pendentes(
    contagem_por_cidade: dict[str, dict[str, int]],
    cache_bairros_cidades: dict[str, dict[str, str]],
    forcar_recompilacao: bool,
) -> list[tuple[str, dict[str, int]]]:
    """Seleciona cidades que precisam de recompilação.

    Uma cidade precisa recompilação se:
        - Tem mais de 1 bairro único, E
        - Não está no cache, OU
        - Tem bairros novos não cobertos pelo cache

    Args:
        contagem_por_cidade: Contagem de bairros por cidade.
        cache_bairros_cidades: Cache atual de bairros.
        forcar_recompilacao: Se True, força recompilação de todas.

    Returns:
        Lista de ``(chave_cid, contagem)`` pendentes.
    """
    if forcar_recompilacao:
        return list(contagem_por_cidade.items())

    pendentes: list[tuple[str, dict[str, int]]] = []

    for chave_cid, cont in contagem_por_cidade.items():
        if len(cont) <= 1:
            continue

        cache_cid = cache_bairros_cidades.get(chave_cid)
        if cache_cid is None:
            pendentes.append((chave_cid, cont))
            continue

        # Se algum bairro novo apareceu, recompila
        faltando = any(
            b not in cache_cid
            and not b.startswith(_IGNORES)
            for b in cont
        )
        if faltando:
            pendentes.append((chave_cid, cont))

    return pendentes


def _aplicar_mapeamento(
    ufs: list[str],
    muns: list[str],
    bairros: list[str],
    cache_bairros_cidades: dict[str, dict[str, str]],
) -> list[str]:
    """Aplica mapeamento de unificação no DataFrame.

    Args:
        ufs: Lista de UFs.
        muns: Lista de municípios.
        bairros: Lista de bairros originais.
        cache_bairros_cidades: Mapeamento de unificação.

    Returns:
        Lista de bairros unificados (alinhada ao input).
    """
    resultado: list[str] = []
    for u, m, b in zip(ufs, muns, bairros):
        mapa_c = cache_bairros_cidades.get(f"{u}|{m}")
        if mapa_c and b in mapa_c:
            resultado.append(mapa_c[b])
        else:
            resultado.append(b)
    return resultado


# ---------------------------------------------------------------------------
# Unificação por município (função principal)
# ---------------------------------------------------------------------------

def unificar_bairros_por_municipio(
    df_erbs: Any,
    forcar_recompilacao: bool = False,
) -> list[str]:
    """Unifica bairros por município usando cache e heurísticas.

    Recebe o DataFrame já com coluna ``BAIRRO`` (limpa por linha) e devolve
    uma lista de strings alinhada ao DataFrame com o nome unificado.
    Não modifica o DataFrame — o chamador atribui a coluna.

    Estratégia:
        1. Conta bairros por cidade
        2. Seleciona cidades pendentes de recompilação
        3. Processa pendentes com barra de progresso
        4. Salva cache atualizado
        5. Aplica mapeamento no DataFrame

    Args:
        df_erbs: DataFrame com colunas ``UF``, ``MUNICIPIO``, ``BAIRRO``.
        forcar_recompilacao: Se True, força recompilação de todas as cidades.

    Returns:
        Lista de bairros unificados (alinhada ao DataFrame).

    Side effects:
        - Atualiza ``INFO.bairros_unificados``.
        - Salva cache em ``ARQUIVO_CACHE_BAIRROS``.
    """
    ufs_col = df_erbs["UF"].tolist()
    muns_col = df_erbs["MUNICIPIO"].tolist()
    bairros_col = df_erbs["BAIRRO"].tolist()

    cache_bairros_cidades = (
        {} if forcar_recompilacao else carregar_cache_bairros_disco()
    )

    # 1) Contagem de bairros por cidade
    contagem_por_cidade = _contar_bairros_por_cidade(
        ufs_col, muns_col, bairros_col
    )

    # 2) Seleciona cidades pendentes
    pendentes = _selecionar_cidades_pendentes(
        contagem_por_cidade,
        cache_bairros_cidades,
        forcar_recompilacao,
    )

    # 3) Processa pendentes com barra de progresso
    if pendentes:
        _processar_pendentes(pendentes, cache_bairros_cidades)
        salvar_cache_bairros_disco(cache_bairros_cidades)

    # 4) Estatística global
    INFO.bairros_unificados = sum(
        len(m_c) for m_c in cache_bairros_cidades.values()
    )

    # 5) Aplica mapeamento
    return _aplicar_mapeamento(
        ufs_col, muns_col, bairros_col, cache_bairros_cidades
    )


def _processar_pendentes(
    pendentes: list[tuple[str, dict[str, int]]],
    cache_bairros_cidades: dict[str, dict[str, str]],
) -> None:
    """Processa cidades pendentes de unificação.

    Args:
        pendentes: Lista de ``(chave_cid, contagem)``.
        cache_bairros_cidades: Cache a ser atualizado (modificado in-place).
    """
    total_pend = len(pendentes)
    passo_barra = max(1, total_pend // 50)

    for idx_c, (chave_cid, contagem) in enumerate(pendentes, start=1):
        uf, mun = chave_cid.split("|", 1)
        mun_limpo = _reduzir_municipio(mun)
        mun_norm = normalizar_texto(mun_limpo)

        # Atualiza barra de progresso
        if len(contagem) > 40 or idx_c % passo_barra == 0 or idx_c == total_pend:
            perc = 75.0 + (idx_c / total_pend) * 14.0
            desenhar_progresso_tui(
                perc,
                "COMPILANDO DICIONÁRIO NACIONAL DE BAIRROS",
                "Padronizando abreviações, acentos e grafias próximas...",
                detalhe_extra=(
                    f"Município {idx_c}/{total_pend}: "
                    f"{mun_limpo[:22]}/{uf} ({len(contagem)} locais)"
                ),
            )

        mapa_cid = _unificar_uma_cidade(
            contagem=contagem,
            mun_norm=mun_norm,
        )
        cache_bairros_cidades[chave_cid] = mapa_cid


# ---------------------------------------------------------------------------
# Unificação de uma cidade
# ---------------------------------------------------------------------------

def _unificar_uma_cidade(
    contagem: dict[str, int],
    mun_norm: str,
) -> dict[str, str]:
    """Unifica os bairros de UMA cidade.

    Estratégia:
        1. Agrupa por chave canônica
        2. Escolhe representante de cada grupo (mais frequente, com acento, mais longo)
        3. Tenta mesclar chaves próximas (grafia/abreviação)
        4. Atalho para bairros "SEM BAIRRO (...)" no nome do logradouro
        5. Monta mapa final ``{nome_orig: nome_final}``

    Args:
        contagem: Dicionário ``{bairro: contagem}`` da cidade.
        mun_norm: Nome normalizado do município (para evitar fusões erradas).

    Returns:
        Dicionário ``{nome_orig: nome_final}`` com bairros unificados.
    """
    # 1) Agrupa por chave canônica
    grupos, mapa_nome_chave = _agrupar_por_chave_canonica(contagem)
    if not grupos:
        return {}

    # 2) Escolhe representante de cada grupo
    rep_por_chave, freq_por_chave = _escolher_representantes(
        grupos, contagem
    )

    # 3) Mescla chaves próximas
    redir, consolidadas = _mesclar_chaves_proximas(
        rep_por_chave, freq_por_chave, mun_norm
    )

    # 4) Atalho para "SEM BAIRRO (...)"
    busca_rapida = _construir_busca_rapida(consolidadas, rep_por_chave, mun_norm)

    # 5) Monta mapa final
    return _montar_mapa_final(
        contagem, mapa_nome_chave, redir, rep_por_chave, busca_rapida
    )


def _agrupar_por_chave_canonica(
    contagem: dict[str, int],
) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Agrupa bairros por chave canônica.

    Args:
        contagem: Dicionário ``{bairro: contagem}``.

    Returns:
        Tupla ``(grupos, mapa_nome_chave)`` onde:
            - ``grupos``: ``{chave_canonica: [nomes]}``
            - ``mapa_nome_chave``: ``{nome: chave_canonica}``
    """
    grupos: dict[str, list[str]] = {}
    mapa_nome_chave: dict[str, str] = {}

    for nome in contagem:
        if nome.startswith(_IGNORES):
            continue
        ch = chave_canonica_bairro(nome)
        if not ch:
            continue
        mapa_nome_chave[nome] = ch
        grupos.setdefault(ch, []).append(nome)

    return grupos, mapa_nome_chave


def _escolher_representantes(
    grupos: dict[str, list[str]],
    contagem: dict[str, int],
) -> tuple[dict[str, str], dict[str, int]]:
    """Escolhe representante de cada grupo.

    Critério: mais frequente, com acento, mais longo.

    Args:
        grupos: ``{chave: [nomes]}``.
        contagem: ``{nome: contagem}``.

    Returns:
        Tupla ``(rep_por_chave, freq_por_chave)``.
    """
    rep_por_chave: dict[str, str] = {}
    freq_por_chave: dict[str, int] = {}

    for ch, lista in grupos.items():
        melhor = max(
            lista,
            key=lambda x: (
                contagem[x],
                any(ord(c) > 127 for c in x),
                len(x),
            ),
        )
        rep_por_chave[ch] = melhor
        freq_por_chave[ch] = sum(contagem[n] for n in lista)

    return rep_por_chave, freq_por_chave


def _mesclar_chaves_proximas(
    rep_por_chave: dict[str, str],
    freq_por_chave: dict[str, int],
    mun_norm: str,
) -> tuple[dict[str, str], list[str]]:
    """Mescla chaves canônicas próximas.

    Args:
        rep_por_chave: ``{chave: representante}``.
        freq_por_chave: ``{chave: frequência}``.
        mun_norm: Nome normalizado do município.

    Returns:
        Tupla ``(redir, consolidadas)`` onde:
            - ``redir``: ``{chave_orig: chave_destino}``
            - ``consolidadas``: lista de chaves finais
    """
    chaves_ord = sorted(
        rep_por_chave.keys(),
        key=lambda k: (freq_por_chave[k], len(k)),
        reverse=True,
    )

    redir: dict[str, str] = {}
    consolidadas: list[str] = []

    for ch in chaves_ord:
        alvo = _buscar_alvo_proximo(ch, consolidadas, mun_norm)
        if alvo is not None:
            redir[ch] = alvo
            # Promove representante se o novo for mais frequente/longo
            if (
                len(rep_por_chave[ch]) > len(rep_por_chave[alvo])
                and freq_por_chave[ch] >= freq_por_chave[alvo]
            ):
                rep_por_chave[alvo] = rep_por_chave[ch]
        else:
            consolidadas.append(ch)
            redir[ch] = ch

    return redir, consolidadas


def _construir_busca_rapida(
    consolidadas: list[str],
    rep_por_chave: dict[str, str],
    mun_norm: str,
) -> list[tuple[str, str]]:
    """Constrói lista de busca rápida para "SEM BAIRRO (...)".

    Args:
        consolidadas: Lista de chaves consolidadas.
        rep_por_chave: ``{chave: representante}``.
        mun_norm: Nome normalizado do município.

    Returns:
        Lista de ``(padrão, representante)`` ordenada por tamanho.
    """
    busca_rapida = [
        (f" {c} ", rep_por_chave[c])
        for c in consolidadas[:_LIMITE_BUSCA_RAPIDA]
        if len(c) >= 5 and c != mun_norm
    ]
    busca_rapida.sort(key=lambda x: len(x[0]), reverse=True)
    return busca_rapida


def _montar_mapa_final(
    contagem: dict[str, int],
    mapa_nome_chave: dict[str, str],
    redir: dict[str, str],
    rep_por_chave: dict[str, str],
    busca_rapida: list[tuple[str, str]],
) -> dict[str, str]:
    """Monta mapa final ``{nome_orig: nome_final}``.

    Args:
        contagem: ``{nome: contagem}``.
        mapa_nome_chave: ``{nome: chave_canonica}``.
        redir: ``{chave_orig: chave_destino}``.
        rep_por_chave: ``{chave: representante}``.
        busca_rapida: Lista de ``(padrão, representante)``.

    Returns:
        Dicionário de mapeamento final.
    """
    mapa_cid: dict[str, str] = {}

    for nome in contagem:
        if not nome.startswith(_IGNORES) and nome in mapa_nome_chave:
            ch_orig = mapa_nome_chave[nome]
            ch_dest = redir.get(ch_orig, ch_orig)
            novo = rep_por_chave[ch_dest]
            if novo != nome:
                mapa_cid[nome] = novo
        elif nome.startswith("SEM BAIRRO") and busca_rapida:
            texto_limpo = f" {RE_NAO_ALFANUM.sub(' ', normalizar_texto(nome))} "
            texto_limpo = RE_ESPACOS.sub(" ", texto_limpo)
            for padrao_b, rep_b in busca_rapida:
                if padrao_b in texto_limpo:
                    mapa_cid[nome] = rep_b
                    break

    return mapa_cid


# ---------------------------------------------------------------------------
# Busca de alvo próximo (SequenceMatcher)
# ---------------------------------------------------------------------------

def _buscar_alvo_proximo(
    ch: str,
    consolidadas: list[str],
    mun_norm: str,
) -> str | None:
    """Encontra uma chave já consolidada próxima o suficiente para mesclar.

    Estratégia (em ordem de prioridade):
        1. Idênticos após remover espaços
        2. Prefixo/sufixo comum (com proporção mínima)
        3. Tokens em comum (sem opostos)
        4. SequenceMatcher com similaridade >= 0.84

    Args:
        ch: Chave canônica a buscar.
        consolidadas: Lista de chaves já consolidadas.
        mun_norm: Nome normalizado do município.

    Returns:
        Chave alvo encontrada, ou None se não houver match.
    """
    ch_sem_esp = ch.replace(" ", "")
    tokens_ch = set(ch.split())

    for cand in consolidadas[:_LIMITE_CANDIDATOS_CONSOLIDADAS]:
        alvo = _tentar_match_com_candidato(
            ch, ch_sem_esp, tokens_ch, cand, mun_norm
        )
        if alvo is not None:
            return alvo

    return None


def _tentar_match_com_candidato(
    ch: str,
    ch_sem_esp: str,
    tokens_ch: set[str],
    cand: str,
    mun_norm: str,
) -> str | None:
    """Tenta encontrar match entre chave e candidato.

    Args:
        ch: Chave canônica original.
        ch_sem_esp: Chave sem espaços.
        tokens_ch: Tokens da chave.
        cand: Candidato a alvo.
        mun_norm: Nome normalizado do município.

    Returns:
        Candidato se houver match, None caso contrário.
    """
    cand_sem_esp = cand.replace(" ", "")

    # 1) Idênticos após remover espaços
    if ch_sem_esp == cand_sem_esp:
        return cand

    menor, maior = (ch, cand) if len(ch) <= len(cand) else (cand, ch)
    tam_menor = len(menor)
    proporcao = tam_menor / max(len(maior), 1)

    # 2) Prefixo/sufixo comum
    if tam_menor >= _TAMANHO_MINIMO_PREFIXO and proporcao >= _PROPORCAO_MINIMA_PREFIXO:
        if maior.startswith(menor) or maior.endswith(menor):
            resto = maior.replace(menor, "").strip()
            if menor != mun_norm and resto not in _OPOSTOS:
                return cand

        # 3) Tokens em comum
        tokens_cand = set(cand.split())
        if tokens_ch.issubset(tokens_cand) or tokens_cand.issubset(tokens_ch):
            dif = tokens_ch ^ tokens_cand
            if menor != mun_norm and not (dif & _OPOSTOS):
                return cand

    # 4) SequenceMatcher (passo caro)
    if (
        len(ch_sem_esp) >= _TAMANHO_MINIMO_SEQUENCE
        and abs(len(ch_sem_esp) - len(cand_sem_esp)) <= _DIFERENCA_MAXIMA_TAMANHO
    ):
        if ch_sem_esp[0] == cand_sem_esp[0] and ch_sem_esp[-1] == cand_sem_esp[-1]:
            sim = difflib.SequenceMatcher(None, ch_sem_esp, cand_sem_esp).ratio()
            if sim >= _SIMILARIDADE_MINIMA:
                tokens_cand = set(cand.split())
                if not ((tokens_ch ^ tokens_cand) & _OPOSTOS):
                    return cand

    return None