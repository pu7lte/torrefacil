"""Constantes globais, caminhos e configuração do Torre Fácil.

Este módulo centraliza todas as constantes do projeto:
    - URLs de dados externos (Anatel).
    - Caminhos de arquivos (cache, dicionários, snapshots).
    - Versão do esquema de cache binário.
    - Configurações de comportamento (expiração, splash).

Todos os caminhos são absolutos, baseados no diretório onde o pacote
está instalado, garantindo funcionamento independente do CWD.

Example:
    >>> from torre_facil.config import ARQUIVO_CACHE, VERSAO_CACHE
    >>> print(ARQUIVO_CACHE)
    /home/user/.local/share/torre_facil/torre_facil_cache.pkl
    >>> print(VERSAO_CACHE)
    5
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

__all__ = [
    # URLs
    "URL_ANATEL",
    # Caminhos
    "DADOS_DIR",
    "ARQUIVO_ZIP",
    "ARQUIVO_CSV_EXTRAIDO",
    "ARQUIVO_CACHE",
    "ARQUIVO_DICIONARIOS",
    "ARQUIVO_CACHE_BAIRROS",
    "ARQUIVO_SNAPSHOT",
    "ARQUIVO_SNAPSHOT_ANTERIOR",
    # Cache
    "VERSAO_CACHE",
    "DIAS_EXPIRACAO_CACHE",
    # Configurações
    "ORDEM_TEC",
    "DIAS_SEMANA",
    "SPLASH_DELAY",
]


# ---------------------------------------------------------------------------
# Diretórios base
# ---------------------------------------------------------------------------

# Diretório onde o pacote está instalado
_PACOTE_DIR: Final[Path] = Path(__file__).parent.resolve()

# Diretório de dados do usuário (cache, snapshots, dicionários)
# Usa XDG_DATA_HOME se disponível, senão ~/.local/share/torre_facil
_DADOS_BASE: Final[Path] = Path(
    os.environ.get(
        "TORRE_FACIL_DADOS_DIR",
        str(Path.home() / ".local" / "share" / "torre_facil"),
    )
).expanduser().resolve()

# Cria o diretório de dados se não existir
_DADOS_BASE.mkdir(parents=True, exist_ok=True)

DADOS_DIR: Final[Path] = _DADOS_BASE
"""Diretório onde arquivos de dados são armazenados (cache, snapshots, etc.)."""


# ---------------------------------------------------------------------------
# URLs de dados externos
# ---------------------------------------------------------------------------

URL_ANATEL: Final[str] = (
    "https://www.anatel.gov.br/dadosabertos/paineis_de_dados/"
    "outorga_e_licenciamento/estacoes_smp.zip"
)
"""URL do arquivo ZIP com dados de estações SMP da Anatel."""


# ---------------------------------------------------------------------------
# Caminhos de arquivos (todos absolutos)
# ---------------------------------------------------------------------------

ARQUIVO_ZIP: Final[Path] = DADOS_DIR / "estacoes_smp.zip"
"""Caminho do ZIP baixado da Anatel."""

ARQUIVO_CSV_EXTRAIDO: Final[Path] = DADOS_DIR / "estacoes_smp_extraido.csv"
"""Caminho do CSV extraído do ZIP (usado durante processamento)."""

ARQUIVO_CACHE: Final[Path] = DADOS_DIR / "torre_facil_cache.pkl"
"""Caminho do cache binário (pickle) do DataFrame processado."""

ARQUIVO_DICIONARIOS: Final[Path] = DADOS_DIR / "torre_facil_dicionarios.json"
"""Caminho do JSON com dicionários de normalização (regex de bairros, etc.)."""

ARQUIVO_CACHE_BAIRROS: Final[Path] = DADOS_DIR / "torre_facil_bairros_unificados.json"
"""Caminho do JSON com bairros unificados (cache de limpeza)."""

ARQUIVO_SNAPSHOT: Final[Path] = DADOS_DIR / "torre_facil_snapshot.json"
"""Caminho do snapshot atual da base (para detecção de novidades)."""

ARQUIVO_SNAPSHOT_ANTERIOR: Final[Path] = DADOS_DIR / "torre_facil_snapshot_anterior.json"
"""Caminho do snapshot anterior (usado para diff)."""


# ---------------------------------------------------------------------------
# Versão do cache binário
# ---------------------------------------------------------------------------

VERSAO_CACHE: Final[int] = 5
"""Versão do esquema do cache binário (.pkl).

Incremente este valor quando o ESQUEMA do DataFrame mudar:
    - Nova coluna adicionada
    - Coluna removida
    - Tipo de coluna alterado

Ao detectar versão diferente, o app recompila a base automaticamente
no próximo boot.

Histórico:
    3 → adiciona __BUSCA_GLOBAL, MUNICIPIO_NORM, ENDERECO_BUSCA
    4 → adiciona __BUSCA_GLOBAL pré-compilada no .pkl (evita lentidão na 1ª busca)
    5 → (versão atual)
"""

DIAS_EXPIRACAO_CACHE: Final[int] = 7
"""Número de dias após o qual o cache é considerado expirado."""


# ---------------------------------------------------------------------------
# Configurações de domínio
# ---------------------------------------------------------------------------

ORDEM_TEC: Final[dict[str, int]] = {
    "E": 1,   # GSM (2G)
    "H": 2,   # HSPA/HSPA+ (3G)
    "L": 3,   # LTE (4G)
    "5": 4,   # 5G NR
}
"""Ordem de exibição das tecnologias (para ordenação em listas e rankings).

Nota: A chave vazia `""` foi removida. Se precisar de uma ordem para
tecnologias desconhecidas, use `ORDEM_TEC.get(tec, 9)`.
"""

DIAS_SEMANA: Final[tuple[str, ...]] = (
    "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom",
)
"""Dias da semana em português (abreviados), para exibição na TUI."""


# ---------------------------------------------------------------------------
# Configurações de comportamento
# ---------------------------------------------------------------------------

def _obter_splash_delay() -> float:
    """Lê o delay da splash screen da variável de ambiente.

    Returns:
        Delay em segundos (0.08 por padrão).
    """
    try:
        valor = float(os.environ.get("TORRE_FACIL_SPLASH_DELAY", "0.08"))
        if valor < 0:
            logger.warning(
                "TORRE_FACIL_SPLASH_DELAY negativo (%s); usando 0.0", valor
            )
            return 0.0
        return valor
    except (ValueError, TypeError):
        logger.warning(
            "TORRE_FACIL_SPLASH_DELAY inválido; usando padrão 0.08"
        )
        return 0.08


SPLASH_DELAY: Final[float] = _obter_splash_delay()
"""Delay entre quadros da animação de splash (em segundos).

Permite acelerar a splash em testes/CI definindo a variável de ambiente
``TORRE_FACIL_SPLASH_DELAY=0``.
"""