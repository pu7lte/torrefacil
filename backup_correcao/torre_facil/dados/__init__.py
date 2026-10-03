"""Camada de dados: acesso, parsing e cache da base ANATEL SMP.

Este subpacote é responsável por toda a interação com os dados brutos:
    - ``anatel``: download do ZIP oficial, parsing do CSV e persistência em cache
    - ``bairros``: unificação de nomes de bairros por município
    - ``snapshot``: geração e comparação de snapshots para detectar novidades

Arquitetura:
    Os módulos desta camada são independentes da TUI (exceto por callbacks
    de progresso que serão desacoplados no futuro). Eles operam sobre
    ``pd.DataFrame`` e arquivos em disco, retornando dados prontos para
    consumo pelos módulos de negócio (``torre_facil.modulos``).

Uso típico:
    >>> from torre_facil.dados.anatel import inicializar_base_com_cache
    >>> df_erbs, status = inicializar_base_com_cache()
"""
from __future__ import annotations

__all__ = [
    "anatel",
    "bairros",
    "snapshot",
]