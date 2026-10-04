"""Estado da sessão e contexto da aplicação.

Este módulo define:
    - ``EstatisticasBase``: contadores e metadados da base carregada.
    - ``AppContext``: contexto principal passado entre módulos.
    - ``AbrirMenuOutroModo``: exceção de controle de fluxo (F12).

O ``AppContext`` substitui o padrão antigo de passar
``df_erbs, resumo_status, modo`` como parâmetros soltos.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceções de controle de fluxo
# ---------------------------------------------------------------------------

class AbrirMenuOutroModo(Exception):
    """Levantada quando o usuário pressiona F12 para trocar de modo.

    Esta exceção é usada para controle de fluxo, não para indicar erro.
    Ela sinaliza que a TUI deve abrir o menu do modo oposto (loja ↔ analista).

    Quem captura:
        - ``_menu_principal_interno`` em ``main.py``
        - ``_loop_principal`` em ``__main__.py``

    Quem levanta:
        - Qualquer tela da TUI que suporte empilhamento de menu
          (consulta_rapida, comparador_loja, raio_x, chips, etc.)

    Example:
        >>> try:
        ...     consulta_rapida(ctx)
        ... except AbrirMenuOutroModo:
        ...     ctx.modo = _alternar_modo(ctx.modo)
    """


# ---------------------------------------------------------------------------
# Estatísticas da base
# ---------------------------------------------------------------------------

@dataclass
class EstatisticasBase:
    """Contadores e metadados da base de estações carregada.

    Attributes:
        ufs: Número de unidades federativas presentes na base.
        municipios: Número de municípios únicos.
        erbs: Número total de estações (ERBs).
        setores: Número total de setores.
        bairros_unificados: Número de bairros após unificação.
        data_atualizacao: Data da última atualização dos dados (string).
        origem: Origem dos dados (ex: "ANATEL", "CACHE LOCAL").
        podio_completo: Lista de operadoras no pódio (ordenadas).
        podio_contexto: Contexto do pódio (ex: "Nacional", "SP").
    """

    ufs: int = 0
    municipios: int = 0
    erbs: int = 0
    setores: int = 0
    bairros_unificados: int = 0
    data_atualizacao: str = "N/D"
    origem: str = "AGUARDANDO CARGA..."
    podio_completo: list[str] = field(default_factory=list)
    podio_contexto: str = ""
    modulo_atual: str = "INICIALIZAÇÃO"
    ultimo_erro: str = ""
    base: pd.DataFrame | None = None

    def resumo_formatado(self) -> str:
        """Retorna resumo legível das estatísticas para exibição na TUI."""
        return (
            f"UFs: {self.ufs:,} | Municípios: {self.municipios:,} | "
            f"ERBs: {self.erbs:,} | Setores: {self.setores:,} | "
            f"Bairros: {self.bairros_unificados:,}"
        ).replace(",", ".")


# ---------------------------------------------------------------------------
# Contexto da aplicação
# ---------------------------------------------------------------------------

@dataclass
class AppContext:
    """Contexto principal da aplicação, passado entre todos os módulos.

    Substitui o padrão antigo de passar ``df_erbs, resumo_status, modo``
    como parâmetros soltos em todas as funções.

    Attributes:
        df_erbs: DataFrame com a base de estações da Anatel.
        resumo_status: Texto de status da base (ex: "Cache válido (2.3 MB)").
        modo: Modo de operação atual ("loja" ou "analista").
        stats: Estatísticas da base carregada.
        modulo_atual: Nome do módulo em execução (para breadcrumb na TUI).

    Example:
        >>> ctx = AppContext(
        ...     df_erbs=df,
        ...     resumo_status="Cache válido",
        ...     modo="analista",
        ... )
        >>> raio_x.raio_x_cidade(ctx)
    """

    df_erbs: pd.DataFrame
    resumo_status: str
    modo: str = "analista"
    stats: EstatisticasBase = field(default_factory=EstatisticasBase)
    modulo_atual: str = "INICIALIZAÇÃO"

    def __post_init__(self) -> None:
        """Valida o modo de operação após inicialização."""
        if self.modo not in ("loja", "analista"):
            raise ValueError(f"Modo inválido: {self.modo!r}. Use 'loja' ou 'analista'.")

    def alternar_modo(self) -> str:
        """Alterna entre modo loja e analista.

        Returns:
            O novo modo após a alternância.
        """
        self.modo = "analista" if self.modo == "loja" else "loja"
        logger.info("Modo alternado para '%s'.", self.modo)
        return self.modo

    def atualizar_stats(
        self,
        *,
        ufs: int | None = None,
        municipios: int | None = None,
        erbs: int | None = None,
        setores: int | None = None,
        bairros_unificados: int | None = None,
        data_atualizacao: str | None = None,
        origem: str | None = None,
    ) -> None:
        """Atualiza estatísticas da base de forma parcial.

        Args:
            ufs: Novo valor para UFs (opcional).
            municipios: Novo valor para municípios (opcional).
            erbs: Novo valor para ERBs (opcional).
            setores: Novo valor para setores (opcional).
            bairros_unificados: Novo valor para bairros (opcional).
            data_atualizacao: Nova data de atualização (opcional).
            origem: Nova origem dos dados (opcional).
        """
        if ufs is not None:
            self.stats.ufs = ufs
        if municipios is not None:
            self.stats.municipios = municipios
        if erbs is not None:
            self.stats.erbs = erbs
        if setores is not None:
            self.stats.setores = setores
        if bairros_unificados is not None:
            self.stats.bairros_unificados = bairros_unificados
        if data_atualizacao is not None:
            self.stats.data_atualizacao = data_atualizacao
        if origem is not None:
            self.stats.origem = origem


# ---------------------------------------------------------------------------
# Compatibilidade com código legado (REMOVER após migração completa)
# ---------------------------------------------------------------------------

# ⚠️ DEPRECATED: Mantido apenas para compatibilidade durante a migração.
# ``EstadoSistema`` é o nome histórico da classe de estado global; hoje os
# campos vivem em ``EstatisticasBase``. Use AppContext em vez disso.
EstadoSistema = EstatisticasBase

INFO = EstadoSistema()

_DF_BASE_GLOBAL: pd.DataFrame | None = None


def definir_base_global(df_erbs: pd.DataFrame) -> None:
    """Define a base global de dados.

    .. deprecated:: 10.0
        Use ``AppContext`` em vez de estado global.

    Args:
        df_erbs: DataFrame com a base de estações.
    """
    global _DF_BASE_GLOBAL
    _DF_BASE_GLOBAL = df_erbs
    INFO.base = df_erbs  # Backup da base no estado global (pesquisa global)
    logger.debug(
        "definir_base_global() está deprecated. Use AppContext em vez disso."
    )
    try:
        from .pesquisa_global import invalidar_cache_pesquisa
        invalidar_cache_pesquisa()
    except ImportError:
        logger.debug("pesquisa_global não disponível; cache não invalidado.")


def obter_base_global() -> pd.DataFrame | None:
    """Retorna a base global de dados.

    .. deprecated:: 10.0
        Use ``AppContext.df_erbs`` em vez disso.

    Returns:
        DataFrame com a base de estações, ou None se não carregada.
    """
    if _DF_BASE_GLOBAL is not None:
        return _DF_BASE_GLOBAL
    # Fallback: a base pode ter sido registrada apenas em INFO.base
    # (ex.: carregada via cache/CSV sem passar por definir_base_global).
    base_info = getattr(INFO, "base", None)
    if base_info is not None:
        logger.debug(
            "obter_base_global(): usando fallback INFO.base "
            "(definir_base_global() não foi chamado)."
        )
    return base_info