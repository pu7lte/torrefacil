"""Configurações do usuário persistidas em JSON.

Este módulo gerencia as preferências do usuário, armazenadas em um arquivo
JSON no diretório de dados do Torre Fácil.

Configurações disponíveis:
    - paleta: Paleta de cores da TUI (ex: "classic", "green", "amber").
    - modo: Modo de operação padrão ("loja" ou "analista"), ou None.
    - favoritos: Lista de endereços favoritos (modo loja).
    - fundo: Padrão de fundo do desktop ("nu", "xadrez", "grade").

Example:
    >>> from torre_facil.config_usuario import obter_modo, definir_modo
    >>> obter_modo()
    'analista'
    >>> definir_modo("loja")
    True
    >>> obter_modo()
    'loja'
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

from .config import DADOS_DIR

logger = logging.getLogger(__name__)

__all__ = [
    "ARQUIVO_CONFIG_USUARIO",
    "FUNDOS_VALIDOS",
    "MODOS_VALIDOS",
    "carregar_config",
    "salvar_config",
    "obter_paleta",
    "definir_paleta",
    "obter_modo",
    "definir_modo",
    "esquecer_modo",
    "obter_fundo",
    "definir_fundo",
    "listar_favoritos",
    "adicionar_favorito",
    "remover_favorito",
]


# ---------------------------------------------------------------------------
# Tipos e constantes
# ---------------------------------------------------------------------------

class Favorito(TypedDict):
    """Estrutura de um endereço favorito."""
    endereco: str
    apelido: str


@dataclass
class ConfigUsuario:
    """Schema das configurações do usuário.
    
    Attributes:
        paleta: Nome da paleta de cores (ex: "classic").
        modo: Modo de operação padrão, ou None se não definido.
        favoritos: Lista de endereços favoritos.
        fundo: Padrão de fundo do desktop.
    """
    paleta: str = "classic"
    modo: str | None = None
    favoritos: list[Favorito] = field(default_factory=list)
    fundo: str = "nu"


ARQUIVO_CONFIG_USUARIO: Path = DADOS_DIR / "torre_facil_config.json"
"""Caminho absoluto do arquivo de configuração do usuário."""

FUNDOS_VALIDOS: tuple[str, ...] = ("nu", "xadrez", "grade")
"""Padrões de fundo válidos para o desktop."""

MODOS_VALIDOS: tuple[str, ...] = ("loja", "analista")
"""Modos de operação válidos."""

_DEFAULTS: ConfigUsuario = ConfigUsuario()
"""Configurações padrão (usadas quando o arquivo não existe ou está corrompido)."""


# ---------------------------------------------------------------------------
# Carga e persistência
# ---------------------------------------------------------------------------

def carregar_config() -> ConfigUsuario:
    """Carrega configurações do arquivo JSON.

    Se o arquivo não existir ou estiver corrompido, retorna os defaults.

    Returns:
        Objeto ConfigUsuario com as configurações carregadas.
    """
    if not ARQUIVO_CONFIG_USUARIO.exists():
        logger.debug("Arquivo de configuração não encontrado; usando defaults.")
        return ConfigUsuario()

    try:
        with ARQUIVO_CONFIG_USUARIO.open("r", encoding="utf-8") as f:
            dados_brutos = json.load(f)

        # Valida e normaliza os dados
        config = ConfigUsuario(
            paleta=str(dados_brutos.get("paleta", _DEFAULTS.paleta)),
            modo=dados_brutos.get("modo") if dados_brutos.get("modo") in MODOS_VALIDOS else None,
            favoritos=_validar_favoritos(dados_brutos.get("favoritos", [])),
            fundo=dados_brutos.get("fundo") if dados_brutos.get("fundo") in FUNDOS_VALIDOS else _DEFAULTS.fundo,
        )
        logger.debug("Configuração carregada: paleta=%s, modo=%s", config.paleta, config.modo)
        return config

    except (json.JSONDecodeError, TypeError, KeyError) as e:
        logger.warning("Arquivo de configuração corrompido (%s); usando defaults.", e)
        return ConfigUsuario()

    except Exception:
        logger.exception("Erro inesperado ao carregar configuração; usando defaults.")
        return ConfigUsuario()


def salvar_config(config: ConfigUsuario) -> bool:
    """Salva configurações no arquivo JSON.

    Args:
        config: Objeto ConfigUsuario com as configurações a salvar.

    Returns:
        True se salvou com sucesso, False caso contrário.
    """
    try:
        # Garante que o diretório existe
        ARQUIVO_CONFIG_USUARIO.parent.mkdir(parents=True, exist_ok=True)

        dados = {
            "paleta": config.paleta,
            "modo": config.modo,
            "favoritos": config.favoritos,
            "fundo": config.fundo,
        }

        with ARQUIVO_CONFIG_USUARIO.open("w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)

        logger.debug("Configuração salva com sucesso.")
        return True

    except Exception:
        logger.exception("Falha ao salvar configuração em %s", ARQUIVO_CONFIG_USUARIO)
        return False


def _validar_favoritos(favoritos_brutos: list) -> list[Favorito]:
    """Valida e normaliza a lista de favoritos.

    Args:
        favoritos_brutos: Lista bruta vinda do JSON.

    Returns:
        Lista validada de dicionários com chaves 'endereco' e 'apelido'.
    """
    if not isinstance(favoritos_brutos, list):
        return []

    validos: list[Favorito] = []
    for item in favoritos_brutos:
        if not isinstance(item, dict):
            continue
        endereco = str(item.get("endereco", "")).strip()
        if not endereco:
            continue
        apelido = str(item.get("apelido", endereco)).strip() or endereco
        validos.append({"endereco": endereco, "apelido": apelido})

    return validos


# ---------------------------------------------------------------------------
# Paleta de cores
# ---------------------------------------------------------------------------

def obter_paleta() -> str:
    """Retorna o nome da paleta de cores atual.

    Returns:
        Nome da paleta (ex: "classic").
    """
    return carregar_config().paleta


def definir_paleta(nome: str) -> bool:
    """Define a paleta de cores.

    Args:
        nome: Nome da paleta (ex: "classic", "green", "amber").

    Returns:
        True se salvou com sucesso, False caso contrário.
    """
    config = carregar_config()
    config.paleta = nome
    return salvar_config(config)


# ---------------------------------------------------------------------------
# Modo de uso
# ---------------------------------------------------------------------------

def obter_modo() -> str | None:
    """Retorna o modo de operação salvo.

    Returns:
        "loja", "analista", ou None se não definido.
    """
    return carregar_config().modo


def definir_modo(nome: str) -> bool:
    """Define o modo de operação padrão.

    Args:
        nome: Modo a definir ("loja" ou "analista").

    Returns:
        True se salvou com sucesso, False se o modo for inválido ou falhar.
    """
    if nome not in MODOS_VALIDOS:
        logger.warning("Modo inválido: %r. Use %s.", nome, MODOS_VALIDOS)
        return False

    config = carregar_config()
    config.modo = nome
    return salvar_config(config)


def esquecer_modo() -> bool:
    """Remove o modo salvo (voltará a perguntar na próxima execução).

    Returns:
        True se salvou com sucesso, False caso contrário.
    """
    config = carregar_config()
    config.modo = None
    return salvar_config(config)


# ---------------------------------------------------------------------------
# Padrão de fundo
# ---------------------------------------------------------------------------

def obter_fundo() -> str:
    """Retorna o padrão de fundo do desktop.

    Returns:
        Padrão de fundo ("nu", "xadrez", ou "grade").
    """
    return carregar_config().fundo


def definir_fundo(nome: str) -> bool:
    """Define o padrão de fundo do desktop.

    Args:
        nome: Padrão a definir ("nu", "xadrez", ou "grade").

    Returns:
        True se salvou com sucesso, False se o padrão for inválido ou falhar.
    """
    if nome not in FUNDOS_VALIDOS:
        logger.warning("Fundo inválido: %r. Use %s.", nome, FUNDOS_VALIDOS)
        return False

    config = carregar_config()
    config.fundo = nome
    return salvar_config(config)


# ---------------------------------------------------------------------------
# Favoritos
# ---------------------------------------------------------------------------

def listar_favoritos() -> list[Favorito]:
    """Retorna a lista de endereços favoritos.

    Returns:
        Lista de dicionários com chaves 'endereco' e 'apelido'.
    """
    return carregar_config().favoritos


def adicionar_favorito(endereco: str, apelido: str = "") -> bool:
    """Adiciona ou atualiza um endereço favorito.

    Se o endereço já existir, atualiza o apelido (se fornecido).

    Args:
        endereco: Endereço a favoritar.
        apelido: Apelido opcional (default: o próprio endereço).

    Returns:
        True se salvou com sucesso, False se o endereço for vazio ou falhar.
    """
    endereco = endereco.strip()
    if not endereco:
        logger.warning("Endereço vazio; favorito não adicionado.")
        return False

    config = carregar_config()

    # Verifica se já existe (case-insensitive)
    for fav in config.favoritos:
        if fav["endereco"].upper() == endereco.upper():
            if apelido:
                fav["apelido"] = apelido.strip() or endereco
            logger.debug("Favorito atualizado: %s", endereco)
            return salvar_config(config)

    # Adiciona novo
    config.favoritos.append({
        "endereco": endereco,
        "apelido": apelido.strip() or endereco,
    })
    logger.debug("Favorito adicionado: %s", endereco)
    return salvar_config(config)


def remover_favorito(endereco: str) -> bool:
    """Remove um endereço favorito.

    Args:
        endereco: Endereço a remover.

    Returns:
        True se removeu, False se não encontrou ou falhar.
    """
    config = carregar_config()
    endereco_upper = endereco.strip().upper()

    novo_favoritos = [
        fav for fav in config.favoritos
        if fav["endereco"].upper() != endereco_upper
    ]

    if len(novo_favoritos) == len(config.favoritos):
        logger.debug("Favorito não encontrado: %s", endereco)
        return False

    config.favoritos = novo_favoritos
    logger.debug("Favorito removido: %s", endereco)
    return salvar_config(config)