"""Torre Fácil ERP — pacote modular de análise de estações SMP/Anatel.

Este pacote fornece uma TUI (Text User Interface) para consulta,
análise e exportação de dados de torres de telecomunicações no Brasil.

Módulos principais:
    - torre_facil.dados: acesso e cache de dados da Anatel
    - torre_facil.modulos: funcionalidades de negócio (raio-x, comparador, etc.)
    - torre_facil.tui: camada de interface textual (menus, janelas, teclado)

Exemplo de uso:
    python -m torre_facil

Atributos:
    __version__ (str): Versão semântica do pacote.
    __author__ (str): Autor/mantenedor do projeto.
    __license__ (str): Licença de distribuição.
"""
from __future__ import annotations

__version__ = "10.0.0"
__author__ = "Seu Nome <seu.email@exemplo.com>"
__license__ = "MIT"  # ou "Proprietary", conforme seu caso

__all__ = [
    "__version__",
    "__author__",
    "__license__",
]