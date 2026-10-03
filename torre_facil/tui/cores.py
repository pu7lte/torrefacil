"""Paleta ANSI 256 — suporta 8 temas retrô trocáveis.

Uso:
    >>> from torre_facil.tui.cores import aplicar_paleta
    >>> aplicar_paleta("norton")   # muda todas as cores no próximo render

A paleta padrão é "classic" (Classic ERP). As demais são aplicadas
durante o boot, a partir do arquivo ``torre_facil_config.json``.

Arquitetura:
    - ``PALETAS``: dicionário com todas as paletas disponíveis
    - ``ORDEM_PALETAS``: ordem de exibição no seletor
    - ``aplicar_paleta(nome)``: troca variáveis globais de cor
    - Variáveis de módulo (``BARRA_STATUS_TOPO``, ``CAIXA_TEXTO``, etc.)
      são atualizadas dinamicamente pela função ``aplicar_paleta``

Nota:
    Todas as paletas devem ter as mesmas chaves para garantir
    compatibilidade. A função ``_validar_paletas`` verifica isso no import.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes que NÃO mudam com a paleta
# ---------------------------------------------------------------------------

RESET = "\033[0m"
NEGRITO = "\033[1m"
CIANO = "\033[38;5;51m"


# ---------------------------------------------------------------------------
# Definição das paletas (nome interno → cores)
# ---------------------------------------------------------------------------
# Cada chave é uma variável de módulo. Cores no formato ANSI 256:
#   \033[<estilo>;38;5;<fg>;48;5;<bg>m
#
# Todas as paletas devem ter as mesmas chaves para garantir compatibilidade.

PALETAS: dict[str, dict[str, str]] = {
    # --- 1) Classic ERP (padrão) -----------------------------------------
    "classic": {
        "label": "Classic ERP (azul-noite + cinza claro)",
        "BARRA_STATUS_TOPO": "\033[38;5;232;48;5;250m",
        "BARRA_SUB_TOPO": "\033[1;38;5;231;48;5;24m",
        "FUNDO_DESKTOP": "\033[38;5;252;48;5;17m",
        "CAIXA_BORDA": "\033[1;38;5;252;48;5;17m",
        "CAIXA_TITULO": "\033[1;38;5;231;48;5;17m",
        "CAIXA_TEXTO": "\033[38;5;253;48;5;17m",
        "CAIXA_CIANO": "\033[1;38;5;159;48;5;17m",
        "CAIXA_VERDE": "\033[1;38;5;120;48;5;17m",
        "CAIXA_AMARELO": "\033[1;38;5;227;48;5;17m",
        "CAIXA_SELECAO": "\033[1;38;5;232;48;5;250m",
        "CAIXA_BOTAO_ATIVO": "\033[1;38;5;232;48;5;255m",
        "CAIXA_BOTAO_INATIVO": "\033[38;5;250;48;5;238m",
        "CAIXA_CAMPO_ATIVO": "\033[1;38;5;232;48;5;250m",
        "CAIXA_CAMPO_INATIVO": "\033[38;5;250;48;5;236m",
        "BARRA_ALERTA": "\033[1;38;5;232;48;5;222m",
        "BARRA_VERDE": "\033[1;38;5;232;48;5;120m",
        "BARRA_ERRO": "\033[1;38;5;231;48;5;124m",
        "SOMBRA_3D": "\033[38;5;236;48;5;236m",
        "DROPLIST_BORDA": "\033[38;5;232;48;5;250m",
        "DROPLIST_ITEM": "\033[38;5;232;48;5;250m",
        "DROPLIST_SEL": "\033[1;38;5;231;48;5;24m",
        "COR_OURO": "\033[1;38;5;220;48;5;17m",
        "COR_PRATA": "\033[1;38;5;253;48;5;17m",
        "COR_BRONZE": "\033[1;38;5;215;48;5;17m",
        "COR_DEMAIS": "\033[38;5;250;48;5;17m",
        "MENU_BARRA": "\033[38;5;232;48;5;250m",
        "MENU_BARRA_HOT": "\033[1;4;38;5;24;48;5;250m",
        "MENU_BARRA_ATIVO": "\033[1;38;5;231;48;5;232m",
        "MENU_BARRA_ATIVO_HOT": "\033[1;4;38;5;231;48;5;232m",
        "MENU_ITEM": "\033[38;5;232;48;5;250m",
        "MENU_ITEM_HOT": "\033[1;4;38;5;24;48;5;250m",
        "MENU_ITEM_SEL": "\033[1;38;5;231;48;5;232m",
        "MENU_ITEM_SEL_HOT": "\033[1;4;38;5;231;48;5;232m",
        "MENU_ITEM_OFF": "\033[38;5;245;48;5;250m",
        "MENU_BORDA": "\033[38;5;232;48;5;250m",
        "LOGO_AZUL": "\033[1;38;5;117;48;5;17m",
        "LOGO_CIANO": "\033[1;38;5;159;48;5;17m",
        "LOGO_CINZA": "\033[38;5;245;48;5;17m",
        "LOGO_VERDE": "\033[1;38;5;120;48;5;17m",
    },
    # --- 2) Norton Commander --------------------------------------------
    "norton": {
        "label": "Norton Commander (azul forte + ciano)",
        "BARRA_STATUS_TOPO": "\033[1;38;5;231;48;5;25m",
        "BARRA_SUB_TOPO": "\033[1;38;5;231;48;5;24m",
        "FUNDO_DESKTOP": "\033[38;5;253;48;5;17m",
        "CAIXA_BORDA": "\033[1;38;5;51;48;5;17m",
        "CAIXA_TITULO": "\033[1;38;5;231;48;5;17m",
        "CAIXA_TEXTO": "\033[38;5;253;48;5;17m",
        "CAIXA_CIANO": "\033[1;38;5;51;48;5;17m",
        "CAIXA_VERDE": "\033[1;38;5;120;48;5;17m",
        "CAIXA_AMARELO": "\033[1;38;5;227;48;5;17m",
        "CAIXA_SELECAO": "\033[1;38;5;232;48;5;51m",
        "CAIXA_BOTAO_ATIVO": "\033[1;38;5;232;48;5;51m",
        "CAIXA_BOTAO_INATIVO": "\033[38;5;51;48;5;17m",
        "CAIXA_CAMPO_ATIVO": "\033[1;38;5;232;48;5;51m",
        "CAIXA_CAMPO_INATIVO": "\033[38;5;51;48;5;17m",
        "BARRA_ALERTA": "\033[1;38;5;232;48;5;227m",
        "BARRA_VERDE": "\033[1;38;5;232;48;5;120m",
        "BARRA_ERRO": "\033[1;38;5;231;48;5;124m",
        "SOMBRA_3D": "\033[38;5;236;48;5;236m",
        "DROPLIST_BORDA": "\033[38;5;232;48;5;51m",
        "DROPLIST_ITEM": "\033[38;5;232;48;5;51m",
        "DROPLIST_SEL": "\033[1;38;5;231;48;5;24m",
        "COR_OURO": "\033[1;38;5;227;48;5;17m",
        "COR_PRATA": "\033[1;38;5;231;48;5;17m",
        "COR_BRONZE": "\033[1;38;5;215;48;5;17m",
        "COR_DEMAIS": "\033[38;5;51;48;5;17m",
        "MENU_BARRA": "\033[1;38;5;231;48;5;25m",
        "MENU_BARRA_HOT": "\033[1;4;38;5;227;48;5;25m",
        "MENU_BARRA_ATIVO": "\033[1;38;5;232;48;5;51m",
        "MENU_BARRA_ATIVO_HOT": "\033[1;4;38;5;232;48;5;51m",
        "MENU_ITEM": "\033[38;5;253;48;5;17m",
        "MENU_ITEM_HOT": "\033[1;4;38;5;227;48;5;17m",
        "MENU_ITEM_SEL": "\033[1;38;5;232;48;5;51m",
        "MENU_ITEM_SEL_HOT": "\033[1;4;38;5;232;48;5;51m",
        "MENU_ITEM_OFF": "\033[38;5;245;48;5;17m",
        "MENU_BORDA": "\033[38;5;51;48;5;17m",
        "LOGO_AZUL": "\033[1;38;5;51;48;5;17m",
        "LOGO_CIANO": "\033[1;38;5;231;48;5;17m",
        "LOGO_CINZA": "\033[38;5;245;48;5;17m",
        "LOGO_VERDE": "\033[1;38;5;120;48;5;17m",
    },
    # --- 3) Turbo Vision (Borland) --------------------------------------
    "turbo": {
        "label": "Turbo Vision / Borland (azul acinzentado)",
        "BARRA_STATUS_TOPO": "\033[1;38;5;232;48;5;250m",
        "BARRA_SUB_TOPO": "\033[1;38;5;231;48;5;24m",
        "FUNDO_DESKTOP": "\033[38;5;250;48;5;24m",
        "CAIXA_BORDA": "\033[1;38;5;231;48;5;24m",
        "CAIXA_TITULO": "\033[1;38;5;231;48;5;24m",
        "CAIXA_TEXTO": "\033[38;5;253;48;5;24m",
        "CAIXA_CIANO": "\033[1;38;5;159;48;5;24m",
        "CAIXA_VERDE": "\033[1;38;5;120;48;5;24m",
        "CAIXA_AMARELO": "\033[1;38;5;227;48;5;24m",
        "CAIXA_SELECAO": "\033[1;38;5;232;48;5;250m",
        "CAIXA_BOTAO_ATIVO": "\033[1;38;5;232;48;5;231m",
        "CAIXA_BOTAO_INATIVO": "\033[38;5;250;48;5;238m",
        "CAIXA_CAMPO_ATIVO": "\033[1;38;5;232;48;5;250m",
        "CAIXA_CAMPO_INATIVO": "\033[38;5;250;48;5;238m",
        "BARRA_ALERTA": "\033[1;38;5;232;48;5;222m",
        "BARRA_VERDE": "\033[1;38;5;232;48;5;120m",
        "BARRA_ERRO": "\033[1;38;5;231;48;5;124m",
        "SOMBRA_3D": "\033[38;5;236;48;5;236m",
        "DROPLIST_BORDA": "\033[38;5;232;48;5;250m",
        "DROPLIST_ITEM": "\033[38;5;232;48;5;250m",
        "DROPLIST_SEL": "\033[1;38;5;231;48;5;24m",
        "COR_OURO": "\033[1;38;5;220;48;5;24m",
        "COR_PRATA": "\033[1;38;5;253;48;5;24m",
        "COR_BRONZE": "\033[1;38;5;215;48;5;24m",
        "COR_DEMAIS": "\033[38;5;250;48;5;24m",
        "MENU_BARRA": "\033[38;5;232;48;5;250m",
        "MENU_BARRA_HOT": "\033[1;4;38;5;24;48;5;250m",
        "MENU_BARRA_ATIVO": "\033[1;38;5;231;48;5;232m",
        "MENU_BARRA_ATIVO_HOT": "\033[1;4;38;5;231;48;5;232m",
        "MENU_ITEM": "\033[38;5;232;48;5;250m",
        "MENU_ITEM_HOT": "\033[1;4;38;5;24;48;5;250m",
        "MENU_ITEM_SEL": "\033[1;38;5;231;48;5;232m",
        "MENU_ITEM_SEL_HOT": "\033[1;4;38;5;231;48;5;232m",
        "MENU_ITEM_OFF": "\033[38;5;245;48;5;250m",
        "MENU_BORDA": "\033[38;5;232;48;5;250m",
        "LOGO_AZUL": "\033[1;38;5;231;48;5;24m",
        "LOGO_CIANO": "\033[1;38;5;159;48;5;24m",
        "LOGO_CINZA": "\033[38;5;250;48;5;24m",
        "LOGO_VERDE": "\033[1;38;5;120;48;5;24m",
    },
    # --- 4) DOS Azul ----------------------------------------------------
    "dos_azul": {
        "label": "DOS Azul (fundo azul, texto branco)",
        "BARRA_STATUS_TOPO": "\033[1;38;5;232;48;5;250m",
        "BARRA_SUB_TOPO": "\033[1;38;5;231;48;5;18m",
        "FUNDO_DESKTOP": "\033[38;5;253;48;5;18m",
        "CAIXA_BORDA": "\033[1;38;5;231;48;5;18m",
        "CAIXA_TITULO": "\033[1;38;5;231;48;5;18m",
        "CAIXA_TEXTO": "\033[38;5;253;48;5;18m",
        "CAIXA_CIANO": "\033[1;38;5;51;48;5;18m",
        "CAIXA_VERDE": "\033[1;38;5;120;48;5;18m",
        "CAIXA_AMARELO": "\033[1;38;5;227;48;5;18m",
        "CAIXA_SELECAO": "\033[1;38;5;232;48;5;250m",
        "CAIXA_BOTAO_ATIVO": "\033[1;38;5;232;48;5;250m",
        "CAIXA_BOTAO_INATIVO": "\033[38;5;250;48;5;18m",
        "CAIXA_CAMPO_ATIVO": "\033[1;38;5;232;48;5;250m",
        "CAIXA_CAMPO_INATIVO": "\033[38;5;250;48;5;18m",
        "BARRA_ALERTA": "\033[1;38;5;232;48;5;222m",
        "BARRA_VERDE": "\033[1;38;5;232;48;5;120m",
        "BARRA_ERRO": "\033[1;38;5;231;48;5;124m",
        "SOMBRA_3D": "\033[38;5;236;48;5;236m",
        "DROPLIST_BORDA": "\033[38;5;232;48;5;250m",
        "DROPLIST_ITEM": "\033[38;5;232;48;5;250m",
        "DROPLIST_SEL": "\033[1;38;5;231;48;5;18m",
        "COR_OURO": "\033[1;38;5;220;48;5;18m",
        "COR_PRATA": "\033[1;38;5;231;48;5;18m",
        "COR_BRONZE": "\033[1;38;5;215;48;5;18m",
        "COR_DEMAIS": "\033[38;5;250;48;5;18m",
        "MENU_BARRA": "\033[38;5;232;48;5;250m",
        "MENU_BARRA_HOT": "\033[1;4;38;5;18;48;5;250m",
        "MENU_BARRA_ATIVO": "\033[1;38;5;231;48;5;232m",
        "MENU_BARRA_ATIVO_HOT": "\033[1;4;38;5;231;48;5;232m",
        "MENU_ITEM": "\033[38;5;232;48;5;250m",
        "MENU_ITEM_HOT": "\033[1;4;38;5;18;48;5;250m",
        "MENU_ITEM_SEL": "\033[1;38;5;231;48;5;232m",
        "MENU_ITEM_SEL_HOT": "\033[1;4;38;5;231;48;5;232m",
        "MENU_ITEM_OFF": "\033[38;5;245;48;5;250m",
        "MENU_BORDA": "\033[38;5;232;48;5;250m",
        "LOGO_AZUL": "\033[1;38;5;51;48;5;18m",
        "LOGO_CIANO": "\033[1;38;5;231;48;5;18m",
        "LOGO_CINZA": "\033[38;5;250;48;5;18m",
        "LOGO_VERDE": "\033[1;38;5;120;48;5;18m",
    },
    # --- 5) DOS Cinza (Clipper / dBase) ---------------------------------
    "dos_cinza": {
        "label": "DOS Cinza / Clipper (cinza claro + preto)",
        "BARRA_STATUS_TOPO": "\033[1;38;5;232;48;5;250m",
        "BARRA_SUB_TOPO": "\033[1;38;5;231;48;5;232m",
        "FUNDO_DESKTOP": "\033[38;5;232;48;5;250m",
        "CAIXA_BORDA": "\033[1;38;5;232;48;5;250m",
        "CAIXA_TITULO": "\033[1;38;5;231;48;5;232m",
        "CAIXA_TEXTO": "\033[38;5;232;48;5;250m",
        "CAIXA_CIANO": "\033[1;38;5;18;48;5;250m",
        "CAIXA_VERDE": "\033[1;38;5;22;48;5;250m",
        "CAIXA_AMARELO": "\033[1;38;5;130;48;5;250m",
        "CAIXA_SELECAO": "\033[1;38;5;231;48;5;232m",
        "CAIXA_BOTAO_ATIVO": "\033[1;38;5;231;48;5;232m",
        "CAIXA_BOTAO_INATIVO": "\033[38;5;232;48;5;250m",
        "CAIXA_CAMPO_ATIVO": "\033[1;38;5;231;48;5;18m",
        "CAIXA_CAMPO_INATIVO": "\033[38;5;232;48;5;250m",
        "BARRA_ALERTA": "\033[1;38;5;232;48;5;222m",
        "BARRA_VERDE": "\033[1;38;5;232;48;5;120m",
        "BARRA_ERRO": "\033[1;38;5;231;48;5;124m",
        "SOMBRA_3D": "\033[38;5;240;48;5;240m",
        "DROPLIST_BORDA": "\033[38;5;232;48;5;250m",
        "DROPLIST_ITEM": "\033[38;5;232;48;5;250m",
        "DROPLIST_SEL": "\033[1;38;5;231;48;5;18m",
        "COR_OURO": "\033[1;38;5;130;48;5;250m",
        "COR_PRATA": "\033[1;38;5;232;48;5;250m",
        "COR_BRONZE": "\033[1;38;5;94;48;5;250m",
        "COR_DEMAIS": "\033[38;5;232;48;5;250m",
        "MENU_BARRA": "\033[1;38;5;231;48;5;232m",
        "MENU_BARRA_HOT": "\033[1;4;38;5;250;48;5;232m",
        "MENU_BARRA_ATIVO": "\033[1;38;5;231;48;5;18m",
        "MENU_BARRA_ATIVO_HOT": "\033[1;4;38;5;231;48;5;18m",
        "MENU_ITEM": "\033[38;5;232;48;5;250m",
        "MENU_ITEM_HOT": "\033[1;4;38;5;18;48;5;250m",
        "MENU_ITEM_SEL": "\033[1;38;5;231;48;5;18m",
        "MENU_ITEM_SEL_HOT": "\033[1;4;38;5;231;48;5;18m",
        "MENU_ITEM_OFF": "\033[38;5;245;48;5;250m",
        "MENU_BORDA": "\033[38;5;232;48;5;250m",
        "LOGO_AZUL": "\033[1;38;5;18;48;5;250m",
        "LOGO_CIANO": "\033[1;38;5;232;48;5;250m",
        "LOGO_CINZA": "\033[38;5;240;48;5;250m",
        "LOGO_VERDE": "\033[1;38;5;22;48;5;250m",
    },
    # --- 6) Terminal Verde (fósforo) ------------------------------------
    "verde": {
        "label": "Terminal Verde (fósforo P1)",
        "BARRA_STATUS_TOPO": "\033[1;38;5;16;48;5;118m",
        "BARRA_SUB_TOPO": "\033[1;38;5;118;48;5;16m",
        "FUNDO_DESKTOP": "\033[38;5;118;48;5;16m",
        "CAIXA_BORDA": "\033[1;38;5;118;48;5;16m",
        "CAIXA_TITULO": "\033[1;38;5;231;48;5;16m",
        "CAIXA_TEXTO": "\033[38;5;118;48;5;16m",
        "CAIXA_CIANO": "\033[1;38;5;156;48;5;16m",
        "CAIXA_VERDE": "\033[1;38;5;231;48;5;16m",
        "CAIXA_AMARELO": "\033[1;38;5;190;48;5;16m",
        "CAIXA_SELECAO": "\033[1;38;5;16;48;5;118m",
        "CAIXA_BOTAO_ATIVO": "\033[1;38;5;16;48;5;118m",
        "CAIXA_BOTAO_INATIVO": "\033[38;5;22;48;5;16m",
        "CAIXA_CAMPO_ATIVO": "\033[1;38;5;16;48;5;118m",
        "CAIXA_CAMPO_INATIVO": "\033[38;5;22;48;5;16m",
        "BARRA_ALERTA": "\033[1;38;5;16;48;5;190m",
        "BARRA_VERDE": "\033[1;38;5;16;48;5;118m",
        "BARRA_ERRO": "\033[1;38;5;231;48;5;124m",
        "SOMBRA_3D": "\033[38;5;22;48;5;22m",
        "DROPLIST_BORDA": "\033[38;5;16;48;5;118m",
        "DROPLIST_ITEM": "\033[38;5;16;48;5;118m",
        "DROPLIST_SEL": "\033[1;38;5;16;48;5;231m",
        "COR_OURO": "\033[1;38;5;190;48;5;16m",
        "COR_PRATA": "\033[1;38;5;118;48;5;16m",
        "COR_BRONZE": "\033[1;38;5;148;48;5;16m",
        "COR_DEMAIS": "\033[38;5;70;48;5;16m",
        "MENU_BARRA": "\033[1;38;5;16;48;5;118m",
        "MENU_BARRA_HOT": "\033[1;4;38;5;16;48;5;118m",
        "MENU_BARRA_ATIVO": "\033[1;38;5;118;48;5;16m",
        "MENU_BARRA_ATIVO_HOT": "\033[1;4;38;5;118;48;5;16m",
        "MENU_ITEM": "\033[38;5;118;48;5;16m",
        "MENU_ITEM_HOT": "\033[1;4;38;5;231;48;5;16m",
        "MENU_ITEM_SEL": "\033[1;38;5;16;48;5;118m",
        "MENU_ITEM_SEL_HOT": "\033[1;4;38;5;16;48;5;118m",
        "MENU_ITEM_OFF": "\033[38;5;22;48;5;16m",
        "MENU_BORDA": "\033[38;5;118;48;5;16m",
        "LOGO_AZUL": "\033[1;38;5;118;48;5;16m",
        "LOGO_CIANO": "\033[1;38;5;156;48;5;16m",
        "LOGO_CINZA": "\033[38;5;70;48;5;16m",
        "LOGO_VERDE": "\033[1;38;5;231;48;5;16m",
    },
    # --- 7) Terminal Âmbar ----------------------------------------------
    "ambar": {
        "label": "Terminal Âmbar (fósforo P3)",
        "BARRA_STATUS_TOPO": "\033[1;38;5;16;48;5;214m",
        "BARRA_SUB_TOPO": "\033[1;38;5;214;48;5;16m",
        "FUNDO_DESKTOP": "\033[38;5;214;48;5;16m",
        "CAIXA_BORDA": "\033[1;38;5;214;48;5;16m",
        "CAIXA_TITULO": "\033[1;38;5;231;48;5;16m",
        "CAIXA_TEXTO": "\033[38;5;214;48;5;16m",
        "CAIXA_CIANO": "\033[1;38;5;227;48;5;16m",
        "CAIXA_VERDE": "\033[1;38;5;231;48;5;16m",
        "CAIXA_AMARELO": "\033[1;38;5;227;48;5;16m",
        "CAIXA_SELECAO": "\033[1;38;5;16;48;5;214m",
        "CAIXA_BOTAO_ATIVO": "\033[1;38;5;16;48;5;214m",
        "CAIXA_BOTAO_INATIVO": "\033[38;5;130;48;5;16m",
        "CAIXA_CAMPO_ATIVO": "\033[1;38;5;16;48;5;214m",
        "CAIXA_CAMPO_INATIVO": "\033[38;5;130;48;5;16m",
        "BARRA_ALERTA": "\033[1;38;5;16;48;5;227m",
        "BARRA_VERDE": "\033[1;38;5;16;48;5;214m",
        "BARRA_ERRO": "\033[1;38;5;231;48;5;124m",
        "SOMBRA_3D": "\033[38;5;94;48;5;94m",
        "DROPLIST_BORDA": "\033[38;5;16;48;5;214m",
        "DROPLIST_ITEM": "\033[38;5;16;48;5;214m",
        "DROPLIST_SEL": "\033[1;38;5;16;48;5;231m",
        "COR_OURO": "\033[1;38;5;227;48;5;16m",
        "COR_PRATA": "\033[1;38;5;214;48;5;16m",
        "COR_BRONZE": "\033[1;38;5;180;48;5;16m",
        "COR_DEMAIS": "\033[38;5;130;48;5;16m",
        "MENU_BARRA": "\033[1;38;5;16;48;5;214m",
        "MENU_BARRA_HOT": "\033[1;4;38;5;16;48;5;214m",
        "MENU_BARRA_ATIVO": "\033[1;38;5;214;48;5;16m",
        "MENU_BARRA_ATIVO_HOT": "\033[1;4;38;5;214;48;5;16m",
        "MENU_ITEM": "\033[38;5;214;48;5;16m",
        "MENU_ITEM_HOT": "\033[1;4;38;5;231;48;5;16m",
        "MENU_ITEM_SEL": "\033[1;38;5;16;48;5;214m",
        "MENU_ITEM_SEL_HOT": "\033[1;4;38;5;16;48;5;214m",
        "MENU_ITEM_OFF": "\033[38;5;94;48;5;16m",
        "MENU_BORDA": "\033[38;5;214;48;5;16m",
        "LOGO_AZUL": "\033[1;38;5;214;48;5;16m",
        "LOGO_CIANO": "\033[1;38;5;227;48;5;16m",
        "LOGO_CINZA": "\033[38;5;130;48;5;16m",
        "LOGO_VERDE": "\033[1;38;5;231;48;5;16m",
    },
    # --- 8) Clássico Claro (WordPerfect / Lotus) ------------------------
    "claro": {
        "label": "Clássico Claro (branco + preto)",
        "BARRA_STATUS_TOPO": "\033[1;38;5;16;48;5;252m",
        "BARRA_SUB_TOPO": "\033[1;38;5;231;48;5;18m",
        "FUNDO_DESKTOP": "\033[38;5;16;48;5;255m",
        "CAIXA_BORDA": "\033[1;38;5;16;48;5;255m",
        "CAIXA_TITULO": "\033[1;38;5;18;48;5;255m",
        "CAIXA_TEXTO": "\033[38;5;16;48;5;255m",
        "CAIXA_CIANO": "\033[1;38;5;18;48;5;255m",
        "CAIXA_VERDE": "\033[1;38;5;22;48;5;255m",
        "CAIXA_AMARELO": "\033[1;38;5;130;48;5;255m",
        "CAIXA_SELECAO": "\033[1;38;5;231;48;5;18m",
        "CAIXA_BOTAO_ATIVO": "\033[1;38;5;231;48;5;18m",
        "CAIXA_BOTAO_INATIVO": "\033[38;5;16;48;5;250m",
        "CAIXA_CAMPO_ATIVO": "\033[1;38;5;231;48;5;18m",
        "CAIXA_CAMPO_INATIVO": "\033[38;5;16;48;5;252m",
        "BARRA_ALERTA": "\033[1;38;5;16;48;5;222m",
        "BARRA_VERDE": "\033[1;38;5;16;48;5;120m",
        "BARRA_ERRO": "\033[1;38;5;231;48;5;124m",
        "SOMBRA_3D": "\033[38;5;245;48;5;245m",
        "DROPLIST_BORDA": "\033[38;5;16;48;5;255m",
        "DROPLIST_ITEM": "\033[38;5;16;48;5;255m",
        "DROPLIST_SEL": "\033[1;38;5;231;48;5;18m",
        "COR_OURO": "\033[1;38;5;130;48;5;255m",
        "COR_PRATA": "\033[1;38;5;16;48;5;255m",
        "COR_BRONZE": "\033[1;38;5;94;48;5;255m",
        "COR_DEMAIS": "\033[38;5;16;48;5;255m",
        "MENU_BARRA": "\033[38;5;16;48;5;252m",
        "MENU_BARRA_HOT": "\033[1;4;38;5;18;48;5;252m",
        "MENU_BARRA_ATIVO": "\033[1;38;5;231;48;5;18m",
        "MENU_BARRA_ATIVO_HOT": "\033[1;4;38;5;231;48;5;18m",
        "MENU_ITEM": "\033[38;5;16;48;5;255m",
        "MENU_ITEM_HOT": "\033[1;4;38;5;18;48;5;255m",
        "MENU_ITEM_SEL": "\033[1;38;5;231;48;5;18m",
        "MENU_ITEM_SEL_HOT": "\033[1;4;38;5;231;48;5;18m",
        "MENU_ITEM_OFF": "\033[38;5;245;48;5;255m",
        "MENU_BORDA": "\033[38;5;16;48;5;255m",
        "LOGO_AZUL": "\033[1;38;5;18;48;5;255m",
        "LOGO_CIANO": "\033[1;38;5;24;48;5;255m",
        "LOGO_CINZA": "\033[38;5;240;48;5;255m",
        "LOGO_VERDE": "\033[1;38;5;22;48;5;255m",
    },
}


# ---------------------------------------------------------------------------
# Ordem de exibição no seletor
# ---------------------------------------------------------------------------

ORDEM_PALETAS: list[str] = [
    "classic",
    "norton",
    "turbo",
    "dos_azul",
    "dos_cinza",
    "verde",
    "ambar",
    "claro",
]


# ---------------------------------------------------------------------------
# Chaves obrigatórias em todas as paletas
# ---------------------------------------------------------------------------

_CHAVES_OBRIGATORIAS: frozenset[str] = frozenset({
    "label",
    "BARRA_STATUS_TOPO", "BARRA_SUB_TOPO", "FUNDO_DESKTOP",
    "CAIXA_BORDA", "CAIXA_TITULO", "CAIXA_TEXTO", "CAIXA_CIANO",
    "CAIXA_VERDE", "CAIXA_AMARELO", "CAIXA_SELECAO",
    "CAIXA_BOTAO_ATIVO", "CAIXA_BOTAO_INATIVO",
    "CAIXA_CAMPO_ATIVO", "CAIXA_CAMPO_INATIVO",
    "BARRA_ALERTA", "BARRA_VERDE", "BARRA_ERRO", "SOMBRA_3D",
    "DROPLIST_BORDA", "DROPLIST_ITEM", "DROPLIST_SEL",
    "COR_OURO", "COR_PRATA", "COR_BRONZE", "COR_DEMAIS",
    "MENU_BARRA", "MENU_BARRA_HOT", "MENU_BARRA_ATIVO", "MENU_BARRA_ATIVO_HOT",
    "MENU_ITEM", "MENU_ITEM_HOT", "MENU_ITEM_SEL", "MENU_ITEM_SEL_HOT",
    "MENU_ITEM_OFF", "MENU_BORDA",
    "LOGO_AZUL", "LOGO_CIANO", "LOGO_CINZA", "LOGO_VERDE",
})


# ---------------------------------------------------------------------------
# Validação de paletas
# ---------------------------------------------------------------------------

def _validar_paletas() -> None:
    """Valida que todas as paletas têm as chaves obrigatórias.

    Raises:
        ValueError: Se alguma paleta estiver faltando chaves.

    Note:
        Chamada automaticamente no import do módulo.
    """
    for nome, paleta in PALETAS.items():
        faltando = _CHAVES_OBRIGATORIAS - set(paleta.keys())
        if faltando:
            raise ValueError(
                f"Paleta '{nome}' está faltando chaves: {faltando}"
            )

        # Verifica se não há espaços nas chaves ou valores
        for chave, valor in paleta.items():
            if chave != chave.strip():
                logger.warning(
                    "Paleta '%s': chave '%s' tem espaços extras",
                    nome, chave,
                )
            if isinstance(valor, str) and valor != valor.strip():
                logger.warning(
                    "Paleta '%s': valor de '%s' tem espaços extras",
                    nome, chave,
                )


# ---------------------------------------------------------------------------
# Aplicação da paleta — troca as variáveis do módulo
# ---------------------------------------------------------------------------

_PALETA_ATUAL: str = "classic"


def aplicar_paleta(nome: str) -> bool:
    """Troca as variáveis globais de cor para a paleta indicada.

    Args:
        nome: Nome da paleta (ex: "classic", "norton", "turbo").

    Returns:
        True se aplicou com sucesso, False se o nome não existe.

    Examples:
        >>> aplicar_paleta("norton")
        True
        >>> aplicar_paleta("inexistente")
        False
    """
    global _PALETA_ATUAL

    if nome not in PALETAS:
        logger.warning("Paleta '%s' não encontrada", nome)
        return False

    paleta = PALETAS[nome]
    g = globals()

    for chave, valor in paleta.items():
        if chave == "label":
            continue
        g[chave] = valor

    _PALETA_ATUAL = nome
    logger.info("Paleta aplicada: %s", nome)
    return True


def paleta_atual() -> str:
    """Retorna o nome da paleta atualmente em uso.

    Returns:
        Nome da paleta atual (ex: "classic").
    """
    return _PALETA_ATUAL


# ---------------------------------------------------------------------------
# Aplicar a paleta padrão no import
# ---------------------------------------------------------------------------
# Garante que todas as variáveis existam mesmo antes de o usuário escolher.

_validar_paletas()
aplicar_paleta("classic")


# ---------------------------------------------------------------------------
# Helper de formatação
# ---------------------------------------------------------------------------

def pinta(texto: str, estilo: str) -> str:
    """Envolve o texto com o estilo ANSI e reseta no final.

    Args:
        texto: Texto a ser formatado.
        estilo: Código ANSI de estilo (ex: CAIXA_TEXTO).

    Returns:
        Texto formatado com reset no final.

    Examples:
        >>> pinta("Olá", CAIXA_TEXTO)
        '\\033[38;5;253;48;5;17mOlá\\033[0m'
    """
    return f"{estilo}{texto}{RESET}"