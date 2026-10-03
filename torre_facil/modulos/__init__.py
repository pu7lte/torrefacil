"""Módulos de negócio do Torre Fácil ERP.

Cada módulo deste subpacote implementa uma funcionalidade específica
da aplicação, expondo funções que recebem um ``AppContext`` e operam
sobre o DataFrame consolidado de estações ANATEL.

Arquitetura:
    - Cada módulo é **independente** dos demais (baixo acoplamento).
    - Todos recebem ``AppContext`` como parâmetro principal (v10),
      substituindo o padrão antigo de ``df_erbs, resumo_status, modo``.
    - Podem levantar ``AbrirMenuOutroModo`` para trocar de modo (F12).
    - Usam a TUI (``torre_facil.tui``) para renderização.

Módulos disponíveis:
    - ``consulta_rapida``: busca por CEP/endereço (modo loja)
    - ``comparador_loja``: comparação simples entre operadoras (loja)
    - ``comparador``: comparação avançada entre cidades (analista)
    - ``raio_x``: análise detalhada de cidade/estado
    - ``explorador``: navegação guiada por operadora
    - ``chips``: indicador/consultor de chip
    - ``avancada``: pesquisa com múltiplos filtros
    - ``faixas``: análise por faixa de frequência
    - ``kml``: exportação para Google Earth
    - ``rodovias``: consulta de BRs e estradas
    - ``favoritos``: gerenciamento de favoritos (loja)
    - ``faq``: perguntas frequentes (loja)
    - ``sobre``: informações do sistema e estatísticas
    - ``novidades``: tela de novidades após atualização da base
    - ``paletas``: escolha de tema de cores
    - ``_geo``: (privado) utilitários geográficos

Exemplo de uso:
    >>> from torre_facil.estado import AppContext
    >>> from torre_facil.modulos import raio_x
    >>> raio_x.raio_x_cidade(ctx)
"""
from __future__ import annotations

__all__ = [
    # Modo loja
    "consulta_rapida",
    "comparador_loja",
    "favoritos",
    "faq",
    # Modo analista
    "raio_x",
    "explorador",
    "comparador",
    "chips",
    "rodovias",
    "avancada",
    "faixas",
    "kml",
    # Compartilhados
    "sobre",
    "novidades",
    "paletas",
]