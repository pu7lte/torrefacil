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
# Registro central do contexto da aplicação (substitui estado global legado)
# ---------------------------------------------------------------------------

_CTX_ATIVO: AppContext | None = None


def definir_contexto(ctx: "AppContext | None") -> None:
    """Registra o ``AppContext`` ativo da aplicação.

    Deve ser chamado uma única vez, logo após o carregamento da base
    (ex.: em ``main``), e sempre que a base for recarregada/substituída.
    Todos os módulos que precisam da base sem recebê-la como parâmetro
    (busca global "/", menus, janelas, navegador) consultam este registro
    via :func:`obter_contexto`.

    Args:
        ctx: Instância de ``AppContext`` com ``df_erbs`` preenchido, ou
            ``None`` para desativar o contexto atual.
    """
    global _CTX_ATIVO
    _CTX_ATIVO = ctx
    if ctx is not None:
        # Espelha estatísticas no estado legado (INFO) para telas antigas.
        st = ctx.stats
        INFO.ufs = st.ufs
        INFO.municipios = st.municipios
        INFO.erbs = st.erbs
        INFO.setores = st.setores
        INFO.bairros_unificados = st.bairros_unificados
        INFO.data_atualizacao = st.data_atualizacao
        INFO.origem = st.origem
        INFO.podio_completo = st.podio_completo
        INFO.podio_contexto = st.podio_contexto
        INFO.base = ctx.df_erbs
        logger.info("Contexto da aplicação registrado (AppContext ativo).")


def obter_contexto() -> "AppContext | None":
    """Retorna o ``AppContext`` ativo, ou ``None`` se ainda não definido."""
    return _CTX_ATIVO


def base_do_contexto() -> "pd.DataFrame | None":
    """Retorna ``ctx.df_erbs`` do contexto ativo (ou ``None``).

    Helper para chamadas simples do tipo::

        df = base_do_contexto()
        if df is None or df.empty: ...

    Substitui as antigas funções deprecadas ``definir_base_global()`` /
    ``obter_base_global()``.
    """
    ctx = _CTX_ATIVO
    if ctx is not None and ctx.df_erbs is not None:
        return ctx.df_erbs
    # Fallback de compatibilidade: bases registradas diretamente em INFO.base
    # (ex.: carregadas por caminhos legados/caches antigos).
    return getattr(INFO, "base", None)


# ---------------------------------------------------------------------------
# Compatibilidade com código legado (shims — sem warnings de deprecação)
# ---------------------------------------------------------------------------

# ``EstadoSistema`` é o nome histórico da classe de estado global; hoje os
# campos vivem em ``EstatisticasBase``. Prefira ``AppContext`` em código novo.
EstadoSistema = EstatisticasBase

INFO = EstadoSistema()


def definir_base_global(df_erbs: pd.DataFrame) -> None:
    """Atualiza a base do contexto ativo (shim de compatibilidade).

    Se um ``AppContext`` estiver registrado via :func:`definir_contexto`,
    ``ctx.df_erbs`` (e ``INFO.base``) são atualizados. Caso contrário, a
    base fica registrada em ``INFO.base`` até o contexto ser criado.

    Args:
        df_erbs: DataFrame com a base de estações.
    """
    ctx = _CTX_ATIVO
    if ctx is not None:
        ctx.df_erbs = df_erbs
    INFO.base = df_erbs
    try:
        from .pesquisa_global import invalidar_cache_pesquisa
        invalidar_cache_pesquisa()
    except ImportError:
        logger.debug("pesquisa_global não disponível; cache não invalidado.")


def obter_base_global() -> "pd.DataFrame | None":
    """Retorna a base de estações (shim de compatibilidade).

    Equivalente a :func:`base_do_contexto`: prefira receber
    ``AppContext.df_erbs`` explicitamente em código novo.

    Returns:
        DataFrame com a base de estações, ou None se não carregada.
    """
    return base_do_contexto()