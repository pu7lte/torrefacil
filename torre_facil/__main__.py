"""Entrypoint: ``python -m torre_facil``.

Fluxo de inicialização:
    1. Verificar ambiente (terminal real)
    2. Aplicar paleta de cores
    3. Decidir modo de operação (loja / analista)
    4. Bootstrap da base de dados Anatel (com cache)
    5. Exibir novidades (se a base mudou desde a última execução)
    6. Loop principal: tela de logo → menu → logo

Encerramento:
    - ``X`` no menu ou ``Alt+F4`` na janela.
    - ``Ctrl+C`` encerra com código 130.
"""
from __future__ import annotations

import logging
import sys
from typing import NoReturn

from .estado import AbrirMenuOutroModo
from .tui.cores import CIANO, NEGRITO, RESET
from .tui.motor import iniciar_modo_tui, encerrar_modo_tui

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes internas
# ---------------------------------------------------------------------------

_MODO_LOJA = "loja"
_MODO_ANALISTA = "analista"
_MODOS_VALIDOS = frozenset({_MODO_LOJA, _MODO_ANALISTA})

# Código de saída padrão para encerramento limpo via menu
_EXIT_LIMPO = 0
_EXIT_ERRO = 1
_EXIT_KEYBOARD_INTERRUPT = 130
_EXIT_AMBIENTE_INVALIDO = 2


# ---------------------------------------------------------------------------
# Verificação de ambiente
# ---------------------------------------------------------------------------
def _verificar_ambiente() -> None:
    """Garante que o programa roda em um terminal interativo real."""
    if not sys.stdin.isatty():
        print(
            "\n[AVISO] O Torre Fácil precisa de um terminal real.\n"
            "         Notebooks (Jupyter, IPython) e redirecionamentos "
            "não são suportados.\n"
        )
        raise SystemExit(_EXIT_AMBIENTE_INVALIDO)
# ---------------------------------------------------------------------------
# Decisão de modo
# ---------------------------------------------------------------------------

def _decidir_modo() -> str:
    """Lê o modo salvo na configuração. Se não houver, pergunta via TUI.

    Returns:
        O modo escolhido: ``"loja"`` ou ``"analista"``.

    Raises:
        KeyboardInterrupt: Se o usuário cancelar a escolha.
    """
    from .config_usuario import obter_modo, definir_modo
    from .tui.janelas import tela_escolha_modo

    salvo = obter_modo()
    if salvo in _MODOS_VALIDOS:
        logger.debug("Modo restaurado da configuração: %s", salvo)
        return salvo

    while True:
        escolha = tela_escolha_modo()
        if escolha is None:
            raise KeyboardInterrupt("Usuário cancelou a escolha de modo.")

        tipo, modo = escolha
        if modo not in _MODOS_VALIDOS:
            logger.warning("Modo inválido retornado pela TUI: %r", modo)
            continue

        if tipo == "lembrar":
            definir_modo(modo)
            logger.info("Modo '%s' salvo como padrão.", modo)

        return modo


# ---------------------------------------------------------------------------
# Novidades da base
# ---------------------------------------------------------------------------

def _mostrar_novidades_se_houver() -> None:
    """Compara snapshots da base e exibe novidades relevantes.

    Falhas aqui são logadas mas não impedem a inicialização.
    """
    try:
        from .dados import snapshot as snap_mod
        from .modulos import novidades as nov_mod

        snap_atual = snap_mod.carregar_snapshot()
        snap_anterior = snap_mod.carregar_snapshot_anterior()

        if not snap_anterior or not snap_atual:
            logger.debug("Snapshot ausente; pulando novidades.")
            return

        diff = snap_mod.comparar(snap_anterior, snap_atual)
        if diff and snap_mod.tem_novidade_relevante(diff):
            nov_mod.mostrar_novidades(diff)
            logger.info("Novidades exibidas ao usuário.")
        else:
            logger.debug("Nenhuma novidade relevante detectada.")

    except Exception:
        logger.exception("Falha ao mostrar novidades (não fatal).")


# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------

def _loop_principal(df_erbs, texto_status: str, modo: str) -> None:
    """Loop principal: tela de logo → menu → tela de logo.

    Args:
        df_erbs: DataFrame com a base de estações.
        texto_status: Resumo textual do status da base.
        modo: Modo de operação inicial.

    Raises:
        AbrirMenuOutroModo: Quando o usuário pressiona F12 para trocar de modo.
        KeyboardInterrupt: Quando o usuário encerra a sessão.
    """
    from .main import menu_principal, _abrir_menu_do_outro_modo
    from .tui.janelas import tela_logo

    while True:
        try:
            # Usa closure explícita para evitar captura stale de variáveis
            def _on_enter() -> None:
                menu_principal(df_erbs, texto_status, modo)

            tela_logo(on_enter=_on_enter)

        except AbrirMenuOutroModo:
            novo_modo = _abrir_menu_do_outro_modo(
                df_erbs, texto_status, modo_atual=modo
            )
            if novo_modo and novo_modo in _MODOS_VALIDOS:
                modo = novo_modo
                logger.info("Modo alterado para '%s' via F12.", modo)
            continue


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """Função principal do Torre Fácil.

    Returns:
        Código de saída do processo.
    """
    _verificar_ambiente()

    # Configura logging básico (pode ser customizado via config)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Torre Fácil iniciando (v%s).", __import__(
        "torre_facil", fromlist=["__version__"]
    ).__version__)

    # Aplica paleta ANTES de qualquer desenho na tela
    from .config_usuario import obter_paleta
    from .tui.cores import aplicar_paleta
    aplicar_paleta(obter_paleta())

    iniciar_modo_tui()
    try:
        # 1) Decidir o modo (pergunta se ainda não foi lembrado)
        modo = _decidir_modo()

        # 2) Bootstrap da base
        from .dados.anatel import inicializar_base_com_cache
        df_erbs, texto_status = inicializar_base_com_cache()
        logger.info("Base carregada: %d registros.", len(df_erbs))

        # 2.1) Registra o AppContext ativo — módulos que precisam da base
        # sem recebê-la como parâmetro (busca global "/", menus, janelas)
        # consultam ctx.df_erbs via estado.obter_contexto().
        from .estado import AppContext, definir_contexto, INFO as _INFO
        ctx = AppContext(
            df_erbs=df_erbs,
            resumo_status=texto_status,
            modo=modo,
            stats=_INFO,
        )
        definir_contexto(ctx)

        # 3) Novidades (se a base mudou desde a última compilação)
        _mostrar_novidades_se_houver()

        # 4) Loop logo → menu → logo
        _loop_principal(df_erbs, texto_status, modo)

    except KeyboardInterrupt:
        logger.info("Encerrado pelo usuário (Ctrl+C).")
        return _EXIT_KEYBOARD_INTERRUPT

    except SystemExit as exc:
        # SystemExit com código 0 ou None = encerramento limpo
        if exc.code is None or exc.code == 0:
            return _EXIT_LIMPO
        # Qualquer outro código é tratado como erro
        logger.warning("SystemExit com código: %r", exc.code)
        return _EXIT_ERRO

    except Exception:
        logger.exception("Erro fatal não tratado.")
        return _EXIT_ERRO

    finally:
        try:
            encerrar_modo_tui()
        except Exception:
            logger.debug("Falha ao encerrar modo TUI (ignorando).")

        # Mensagem final de despedida
        msg = (
            f"{CIANO}{NEGRITO}📡 Transmissores desligados. "
            f"Sessão do Torre Fácil finalizada! 👋{RESET}"
        )
        try:
            print(msg)
        except (UnicodeEncodeError, OSError):
            # Fallback ASCII para terminais sem suporte Unicode
            print("Transmissores desligados. Sessao do Torre Facil finalizada.")

    return _EXIT_LIMPO


if __name__ == "__main__":
    sys.exit(main())
