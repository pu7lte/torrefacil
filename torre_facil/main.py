"""Menu principal, manutenção de cache e loop de operação.

Este módulo é o hub central do Torre Fácil ERP. Responsabilidades:
    - ``menu_principal``: ponto de entrada do menu (loja/analista)
    - ``menu_gerenciar_cache``: manutenção do sistema
    - ``_menu_principal_interno``: loop do menu com navegação

Arquitetura:
    - Separação clara entre modo loja e analista
    - Sistema de despacho com dicionários (v10)
    - Easter egg F12 para trocar de modo
"""
from __future__ import annotations

import datetime
import logging
import os
from typing import Any

from .config import (
    ARQUIVO_CACHE,
    ARQUIVO_CSV_EXTRAIDO,
    ARQUIVO_DICIONARIOS,
    ARQUIVO_CACHE_BAIRROS,
)
from .config_usuario import (
    obter_modo, esquecer_modo, obter_fundo, definir_fundo,
)
from .dados.anatel import (
    baixar_zip_anatel,
    limpar_arquivos_cache,
    processar_base_e_salvar_cache,
)
from .dicionarios import carregar_ou_criar_dicionarios
from .estado import INFO, AbrirMenuOutroModo
from .tui.cores import CAIXA_TEXTO, CAIXA_TITULO, BARRA_VERDE, BARRA_ALERTA
from .tui.janelas import (
    criar_item_tui,
    menu_popup_centralizado,
    caixa_notificacao_tui,
    alerta_tui,
)
from .modulos import (
    avancada,
    chips,
    comparador,
    comparador_loja,
    consulta_rapida,
    explorador,
    faixas,
    favoritos,
    faq,
    kml,
    paletas,
    raio_x,
    rodovias,
    sobre,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Modos de operação
_MODO_LOJA = "loja"
_MODO_ANALISTA = "analista"

# Ações do menu
_ACAO_VOLTAR = "0"
_ACAO_LOGO = "V"
_ACAO_SAIR = "X"

# Título do módulo
_MODULO_MANUTENCAO = "MANUTENÇÃO DO SISTEMA"
_MODULO_MENU_LOJA = "MENU PRINCIPAL - MODO LOJA"
_MODULO_MENU_ANALISTA = "MENU PRINCIPAL - MODO ANALISTA"


# ---------------------------------------------------------------------------
# Easter egg F12
# ---------------------------------------------------------------------------

def _abrir_menu_do_outro_modo(
    df_erbs: Any, resumo_status: str, modo_atual: str
) -> str:
    """Abre o menu do modo oposto (F12).

    Args:
        df_erbs: DataFrame completo de ERBs.
        resumo_status: Texto de status da base.
        modo_atual: Modo atual ("loja" ou "analista").

    Returns:
        Novo modo selecionado, ou modo_atual se cancelado.
    """
    outro_modo = _MODO_ANALISTA if modo_atual == _MODO_LOJA else _MODO_LOJA
    modo_final = _menu_principal_interno(
        df_erbs, resumo_status, modo=outro_modo,
        empilhado=True,
        modo_original=modo_atual,
    )
    return modo_final or modo_atual


# ---------------------------------------------------------------------------
# Escolha de fundo
# ---------------------------------------------------------------------------

def _escolher_fundo_interativo() -> None:
    """Pergunta o padrão de fundo. Salva em config."""
    atual = obter_fundo()

    rotulos = {
        "nu": "Nu (só o fundo sólido)",
        "xadrez": "Xadrez (textura sutil de pontos)",
        "grade": "Grade (linhas pontilhadas)",
    }

    itens = [
        criar_item_tui(
            "Padrão de fundo do desktop",
            CAIXA_TITULO, "centro",
        ),
        criar_item_tui("", divisor=True),
    ]
    for chave in ("nu", "xadrez", "grade"):
        marca = "●" if chave == atual else " "
        itens.append(criar_item_tui(
            f" {marca} {rotulos[chave]}",
            CAIXA_TEXTO, "esq",
            selecionavel=True, dados=chave,
            atalho=str(("nu", "xadrez", "grade").index(chave) + 1),
        ))
    itens.append(criar_item_tui("", divisor=True))
    itens.append(criar_item_tui(
        " 0. Cancelar", CAIXA_TEXTO, "esq",
        selecionavel=True, dados="0", atalho="0",
    ))

    acao, escolha, _ = menu_popup_centralizado(
        modulo="PADRAO DE FUNDO",
        titulo_caixa="ESCOLHA O PADRÃO DE FUNDO",
        itens_menu=itens,
        largura_caixa=58,
    )
    if acao != "SELECT" or not escolha or escolha == "0":
        return

    if escolha == atual:
        alerta_tui(
            "PADRAO DE FUNDO", "PADRÃO ATUAL MANTIDO",
            [f"O padrão '{rotulos[escolha]}' já estava ativo."],
        )
        return

    if definir_fundo(escolha):
        alerta_tui(
            "PADRAO DE FUNDO", "PADRÃO SALVO",
            [
                f"Novo padrão: {rotulos[escolha]}",
                "",
                "Feche e reabra o Torre Fácil para ver o efeito.",
            ],
            cor_titulo=BARRA_VERDE,
        )
    else:
        alerta_tui(
            "PADRAO DE FUNDO", "FALHA AO SALVAR",
            ["Não foi possível gravar o arquivo de configuração."],
        )


# ---------------------------------------------------------------------------
# Manutenção do sistema
# ---------------------------------------------------------------------------

def _status_cache() -> str:
    """Retorna status do cache para exibição.

    Returns:
        String com status do cache.
    """
    if not os.path.exists(ARQUIVO_CACHE):
        return "AUSENTE"
    dt_c = datetime.datetime.fromtimestamp(os.path.getmtime(ARQUIVO_CACHE))
    tam_c = os.path.getsize(ARQUIVO_CACHE) / (1024 * 1024)
    return f"ATIVO ({tam_c:.1f} MB - {dt_c.strftime('%d/%m/%Y')})"


def _itens_menu_manutencao(modo: str) -> list[dict[str, Any]]:
    """Monta itens do menu de manutenção.

    Args:
        modo: Modo atual ("loja" ou "analista").

    Returns:
        Lista de itens para menu_popup_centralizado.
    """
    modo_legivel = "LOJA" if modo == _MODO_LOJA else "ANALISTA"
    fundo_legivel = obter_fundo()

    return [
        criar_item_tui(
            f"Cache: {_status_cache()} | Bairros Unif.: "
            f"{INFO.bairros_unificados:,}".replace(",", "."),
            CAIXA_TITULO, "centro",
        ),
        criar_item_tui(
            f"Modo: {modo_legivel}  |  Fundo: {fundo_legivel}",
            CAIXA_TITULO, "centro",
        ),
        criar_item_tui("", divisor=True),
        criar_item_tui("1. Baixar nova versão da Anatel e recriar Caches",
                       CAIXA_TEXTO, selecionavel=True, dados="1", atalho="1"),
        criar_item_tui("2. Recompilar Dicionário Nacional de Bairros",
                       CAIXA_TEXTO, selecionavel=True, dados="2", atalho="2"),
        criar_item_tui("3. Restaurar JSON de Regras Globais p/ fábrica",
                       CAIXA_TEXTO, selecionavel=True, dados="3", atalho="3"),
        criar_item_tui("4. Remover CSV bruto extraído (economizar disco)",
                       CAIXA_TEXTO, selecionavel=True, dados="4", atalho="4"),
        criar_item_tui("5. Ver estatísticas da base / cache / consumo",
                       CAIXA_TEXTO, selecionavel=True, dados="5", atalho="5"),
        criar_item_tui("6. Trocar paleta de cores (tema retrô)",
                       CAIXA_TEXTO, selecionavel=True, dados="6", atalho="6"),
        criar_item_tui("7. Esquecer escolha do modo (perguntar novamente)",
                       CAIXA_TEXTO, selecionavel=True, dados="7", atalho="7"),
        criar_item_tui("8. Padrão de fundo do desktop",
                       CAIXA_TEXTO, selecionavel=True, dados="8", atalho="8"),
        criar_item_tui("", divisor=True),
        criar_item_tui("0. Retornar ao Menu Principal",
                       CAIXA_TEXTO, selecionavel=True, dados="0", atalho="0"),
    ]


def _executar_acao_manutencao(
    op: str, df_erbs: Any, resumo_status: str, modo: str
) -> tuple[Any, str, str]:
    """Executa ação de manutenção.

    Args:
        op: Opção selecionada ("1" a "8").
        df_erbs: DataFrame completo de ERBs.
        resumo_status: Texto de status da base.
        modo: Modo atual.

    Returns:
        Tupla (df_erbs, resumo_status, modo) atualizados.
    """
    if op == "1":
        conf = caixa_notificacao_tui(
            modulo="CONFIRMAÇÃO DE DOWNLOAD",
            titulo="ATUALIZAR BASE DIRETO DA ANATEL",
            linhas_mensagem=[
                "Deseja conectar ao servidor da Anatel, baixar o ZIP atualizado "
                "e reconstruir o cache?"
            ],
            botoes=[
                ("S", "Sim, Baixar Agora", "SIM"),
                ("N", "Não, Cancelar", "NAO"),
            ],
        )
        if conf == "SIM" and baixar_zip_anatel():
            limpar_arquivos_cache(
                apagar_csv_extraido=True, apagar_cache_bairros=True
            )
            df_erbs, resumo_status = processar_base_e_salvar_cache(
                forcar_recompilacao_bairros=True
            )

    elif op == "2":
        carregar_ou_criar_dicionarios(forcar_recriacao=False)
        limpar_arquivos_cache(
            apagar_csv_extraido=False, apagar_cache_bairros=True
        )
        df_erbs, resumo_status = processar_base_e_salvar_cache(
            forcar_recompilacao_bairros=True
        )

    elif op == "3":
        carregar_ou_criar_dicionarios(forcar_recriacao=True)
        alerta_tui(
            "DICIONÁRIOS", "PADRÃO RESTAURADO",
            [f"O arquivo '{ARQUIVO_DICIONARIOS}' foi restaurado com sucesso!"],
            cor_titulo=BARRA_VERDE,
        )

    elif op == "4":
        if os.path.exists(ARQUIVO_CSV_EXTRAIDO):
            os.remove(ARQUIVO_CSV_EXTRAIDO)
            alerta_tui(
                "LIMPEZA DE DISCO", "CSV BRUTO REMOVIDO",
                [f"Arquivo '{ARQUIVO_CSV_EXTRAIDO}' apagado. Cache mantido!"],
                cor_titulo=BARRA_VERDE,
            )
        else:
            alerta_tui(
                "LIMPEZA DE DISCO", "ARQUIVO JÁ REMOVIDO",
                ["O arquivo CSV extraído já não estava no disco."],
            )

    elif op == "5":
        sobre.estatisticas_base_tui(df_erbs)

    elif op == "6":
        paletas.escolher_paleta(df_erbs)

    elif op == "7":
        if esquecer_modo():
            alerta_tui(
                "MODO DE USO", "ESCOLHA ESQUECIDA",
                [
                    "Na próxima abertura, o sistema vai perguntar",
                    "novamente qual modo usar.",
                ],
                cor_titulo=BARRA_VERDE,
            )
        else:
            alerta_tui(
                "MODO DE USO", "FALHA AO SALVAR",
                ["Não foi possível gravar o arquivo de configuração."],
            )

    elif op == "8":
        _escolher_fundo_interativo()

    return df_erbs, resumo_status, modo


def menu_gerenciar_cache(
    df_erbs: Any, resumo_status: str, modo: str = _MODO_ANALISTA
) -> tuple[Any, str, str]:
    """Menu de manutenção do sistema.

    Args:
        df_erbs: DataFrame completo de ERBs.
        resumo_status: Texto de status da base.
        modo: Modo atual.

    Returns:
        Tupla (df_erbs, resumo_status, modo) atualizados.
    """
    itens = _itens_menu_manutencao(modo)

    acao, op, _ = menu_popup_centralizado(
        modulo=_MODULO_MANUTENCAO,
        titulo_caixa="0. MANUTENÇÃO DE CACHE E DICIONÁRIOS",
        itens_menu=itens,
        largura_caixa=58,
    )
    if acao != "SELECT" or not op or op == _ACAO_VOLTAR:
        return df_erbs, resumo_status, modo

    return _executar_acao_manutencao(op, df_erbs, resumo_status, modo)


# ---------------------------------------------------------------------------
# Itens de menu por modo
# ---------------------------------------------------------------------------

def _itens_modo_loja() -> list[dict[str, Any]]:
    """Monta itens do menu do modo loja.

    Returns:
        Lista de itens para menu_popup_centralizado.
    """
    return [
        criar_item_tui("1. Consulta rápida por CEP / endereço",
                       CAIXA_TEXTO, selecionavel=True, dados="1", atalho="1"),
        criar_item_tui("2. Comparar duas operadoras",
                       CAIXA_TEXTO, selecionavel=True, dados="2", atalho="2"),
        criar_item_tui("3. Favoritos",
                       CAIXA_TEXTO, selecionavel=True, dados="3", atalho="3"),
        criar_item_tui("4. Perguntas frequentes",
                       CAIXA_TEXTO, selecionavel=True, dados="4", atalho="4"),
        criar_item_tui("", divisor=True),
        criar_item_tui("R. Raio-X de cidade e bairros",
                       CAIXA_TEXTO, selecionavel=True, dados="R", atalho="R"),
        criar_item_tui("I. Indicador de chip",
                       CAIXA_TEXTO, selecionavel=True, dados="I", atalho="I"),
        criar_item_tui("S. Sobre o Sistema / Estatísticas",
                       CAIXA_TEXTO, selecionavel=True, dados="S", atalho="S"),
        criar_item_tui("", divisor=True),
        criar_item_tui("0. Manutenção do sistema / Cache",
                       CAIXA_TEXTO, selecionavel=True, dados="0", atalho="0"),
        criar_item_tui("V. Voltar à tela de logo",
                       CAIXA_TEXTO, selecionavel=True, dados="V", atalho="V"),
        criar_item_tui("X. Fim de Operação",
                       CAIXA_TEXTO, selecionavel=True, dados="X", atalho="X"),
    ]


def _itens_modo_analista() -> list[dict[str, Any]]:
    """Monta itens do menu do modo analista.

    Returns:
        Lista de itens para menu_popup_centralizado.
    """
    return [
        criar_item_tui("1. Raio-X de cidade e bairros",
                       CAIXA_TEXTO, selecionavel=True, dados="1", atalho="1"),
        criar_item_tui("2. Ranking / Raio-X por estado",
                       CAIXA_TEXTO, selecionavel=True, dados="2", atalho="2"),
        criar_item_tui("3. Explorador guiado por operadora",
                       CAIXA_TEXTO, selecionavel=True, dados="3", atalho="3"),
        criar_item_tui("4. Comparador lado a lado cidades",
                       CAIXA_TEXTO, selecionavel=True, dados="4", atalho="4"),
        criar_item_tui("5. Consultor / Indicador de chip",
                       CAIXA_TEXTO, selecionavel=True, dados="5", atalho="5"),
        criar_item_tui("6. Consulta BRs e estradas locais",
                       CAIXA_TEXTO, selecionavel=True, dados="6", atalho="6"),
        criar_item_tui("", divisor=True),
        criar_item_tui("7. Pesquisa avançada (multi-filtros)",
                       CAIXA_TEXTO, selecionavel=True, dados="7", atalho="7"),
        criar_item_tui("8. Exportar mapa Google Earth (.kml)",
                       CAIXA_TEXTO, selecionavel=True, dados="8", atalho="8"),
        criar_item_tui("A. Análise por faixa de frequência",
                       CAIXA_TEXTO, selecionavel=True, dados="A", atalho="A"),
        criar_item_tui("9. Sobre o Sistema / Estatísticas",
                       CAIXA_TEXTO, selecionavel=True, dados="9", atalho="9"),
        criar_item_tui("", divisor=True),
        criar_item_tui("0. Manutenção do sistema / Cache",
                       CAIXA_TEXTO, selecionavel=True, dados="0", atalho="0"),
        criar_item_tui("V. Voltar à tela de logo",
                       CAIXA_TEXTO, selecionavel=True, dados="V", atalho="V"),
        criar_item_tui("X. Fim de Operação",
                       CAIXA_TEXTO, selecionavel=True, dados="X", atalho="X"),
    ]


# ---------------------------------------------------------------------------
# Despacho
# ---------------------------------------------------------------------------

def _despachar_analista(
    df_erbs: Any, resumo_status: str, opcao: str, modo: str
) -> tuple[Any, str, str]:
    """Despacha opção do menu analista.

    Args:
        df_erbs: DataFrame completo de ERBs.
        resumo_status: Texto de status da base.
        opcao: Opção selecionada.
        modo: Modo atual.

    Returns:
        Tupla (df_erbs, resumo_status, modo) atualizados.
    """
    if opcao == "1":
        raio_x.raio_x_cidade(df_erbs)
    elif opcao == "2":
        raio_x.raio_x_estado(df_erbs)
    elif opcao == "3":
        explorador.pesquisa_guiada_operadora(df_erbs)
    elif opcao == "4":
        comparador.comparador_cidades(df_erbs)
    elif opcao == "5":
        chips.indicador_de_chips(df_erbs)
    elif opcao == "6":
        rodovias.consultar_estradas(df_erbs)
    elif opcao == "7":
        avancada.pesquisa_avancada(df_erbs)
    elif opcao == "8":
        kml.exportar_kml(df_erbs)
    elif opcao == "A":
        faixas.analise_por_faixa(df_erbs)
    elif opcao == "9":
        sobre.sobre_sistema_tui(df_erbs)
    elif opcao == "0":
        df_erbs, resumo_status, modo = menu_gerenciar_cache(
            df_erbs, resumo_status, modo
        )
    return df_erbs, resumo_status, modo


def _despachar_loja(
    df_erbs: Any, resumo_status: str, opcao: str, modo: str
) -> tuple[Any, str, str]:
    """Despacha opção do menu loja.

    Args:
        df_erbs: DataFrame completo de ERBs.
        resumo_status: Texto de status da base.
        opcao: Opção selecionada.
        modo: Modo atual.

    Returns:
        Tupla (df_erbs, resumo_status, modo) atualizados.
    """
    if opcao == "1":
        consulta_rapida.consulta_rapida(df_erbs)
    elif opcao == "2":
        comparador_loja.comparador_loja(df_erbs)
    elif opcao == "3":
        favoritos.favoritos(df_erbs)
    elif opcao == "4":
        faq.faq(df_erbs)
    elif opcao == "R":
        raio_x.raio_x_cidade(df_erbs)
    elif opcao == "I":
        chips.indicador_de_chips(df_erbs)
    elif opcao == "S":
        sobre.sobre_sistema_tui(df_erbs)
    elif opcao == "0":
        df_erbs, resumo_status, modo = menu_gerenciar_cache(
            df_erbs, resumo_status, modo
        )
    return df_erbs, resumo_status, modo


# ---------------------------------------------------------------------------
# Loop principal
# ---------------------------------------------------------------------------

def _menu_principal_interno(
    df_erbs: Any,
    resumo_status: str,
    modo: str = _MODO_ANALISTA,
    empilhado: bool = False,
    modo_original: str | None = None,
) -> str | None:
    """Loop interno do menu principal.

    Args:
        df_erbs: DataFrame completo de ERBs.
        resumo_status: Texto de status da base.
        modo: Modo atual.
        empilhado: Se True, permite voltar ao menu anterior.
        modo_original: Modo original (para empilhamento).

    Returns:
        Novo modo selecionado, ou None para voltar ao logo.

    Raises:
        AbrirMenuOutroModo: Se usuário pressionar F12.
        KeyboardInterrupt: Se usuário pressionar X.
    """
    cursor_menu = 0

    while True:
        if modo == _MODO_LOJA:
            itens = _itens_modo_loja()
            titulo_menu = _MODULO_MENU_LOJA
        else:
            itens = _itens_modo_analista()
            titulo_menu = _MODULO_MENU_ANALISTA

        if empilhado:
            msg_rod = ("↑/↓ navega | ENTER confirma | ESC volta à tela anterior | "
                       "V assume este modo")
        else:
            msg_rod = "↑/↓ navega | ENTER confirma | V volta ao logo | X sai"

        try:
            acao, opcao, cursor_menu = menu_popup_centralizado(
                modulo=titulo_menu,
                titulo_caixa="",
                itens_menu=itens,
                largura_caixa=48,
                msg_rodape=msg_rod,
                cursor_inicial=cursor_menu,
                permitir_esc=empilhado,
            )
        except AbrirMenuOutroModo:
            novo = _abrir_menu_do_outro_modo(df_erbs, resumo_status, modo)
            if novo:
                modo = novo
            continue

        if acao == "VOLTAR" and empilhado:
            return modo_original

        if acao == "LOGO":
            return "logo"

        if opcao == _ACAO_LOGO:
            if empilhado:
                return modo
            return "logo"

        if opcao == _ACAO_SAIR:
            sair = caixa_notificacao_tui(
                modulo="ENCERRAMENTO",
                titulo="CONFIRMAÇÃO DE FIM DE OPERAÇÃO",
                linhas_mensagem=[
                    "Deseja realmente desligar os transmissores e "
                    "encerrar a sessão do Torre Fácil ERP?"
                ],
                botoes=[
                    ("S", "Sim, Encerrar Sessão", "SIM"),
                    ("N", "Não, Voltar ao Menu", "NAO"),
                ],
                cor_cabecalho=BARRA_ALERTA,
                botao_padrao=0,
            )
            if sair == "SIM":
                raise KeyboardInterrupt
            continue

        try:
            if modo == _MODO_LOJA:
                df_erbs, resumo_status, modo = _despachar_loja(
                    df_erbs, resumo_status, opcao, modo
                )
            else:
                df_erbs, resumo_status, modo = _despachar_analista(
                    df_erbs, resumo_status, opcao, modo
                )
        except AbrirMenuOutroModo:
            novo = _abrir_menu_do_outro_modo(df_erbs, resumo_status, modo)
            if novo:
                modo = novo
            continue
        except KeyboardInterrupt:
            logger.info("Operação cancelada pelo usuário (Ctrl+C).")
            INFO.ultimo_erro = "Operação cancelada pelo usuário (Ctrl+C)."
            continue
        except Exception as e:
            import traceback
            logger.exception("Erro no módulo")
            INFO.ultimo_erro = f"{type(e).__name__}: {e}"
            alerta_tui(
                "ERRO NO MÓDULO",
                f"FALHA EM: {opcao}",
                traceback.format_exc().splitlines()[-6:],
            )
            continue


def menu_principal(
    df_erbs: Any, resumo_status: str, modo: str = _MODO_ANALISTA
) -> None:
    """Ponto de entrada do menu principal.

    Args:
        df_erbs: DataFrame completo de ERBs.
        resumo_status: Texto de status da base.
        modo: Modo inicial.
    """
    _menu_principal_interno(df_erbs, resumo_status, modo=modo)