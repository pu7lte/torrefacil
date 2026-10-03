"""Camada TUI (Text User Interface) — motor de interface textual.

Este subpacote implementa toda a interface textual do Torre Fácil ERP,
sem depender de curses ou bibliotecas externas de TUI.

Arquitetura:
    - ``motor``: renderização em canvas ANSI, alternate screen buffer
    - ``teclado``: captura atômica de teclas (stdin bruto)
    - ``cores``: paletas de cores retrô e constantes ANSI
    - ``janelas``: componentes de janela (caixas, formulários, alertas)
    - ``menus``: menus dropdown ancorados
    - ``menu_barra``: barra de menu superior
    - ``navegador``: navegador de listas longas com rolagem
    - ``navegador``: também expõe helpers de pódio e barras de sinal

Estilo:
    - ANSI puro + Alternate Screen Buffer
    - Teclado atômico via termios/ctypes
    - Canvas em memória → renderização única por frame
    - Paletas retrô (Classic, Matrix, Ocean, etc.)

Uso típico:
    >>> from torre_facil.tui.motor import iniciar_modo_tui, encerrar_modo_tui
    >>> from torre_facil.tui.janelas import alerta_tui
    >>> iniciar_modo_tui()
    >>> alerta_tui("TESTE", "MENSAGEM", ["Olá, mundo!"])
    >>> encerrar_modo_tui()
"""
from __future__ import annotations

__all__ = [
    "motor",
    "teclado",
    "cores",
    "janelas",
    "menus",
    "menu_barra",
    "navegador",
]