"""Janelas TUI: item genérico, splash, progresso, notificação, alerta,
droplist, formulário, menu popup centralizado, TELA DE LOGO e
TELA DE ESCOLHA DE MODO.
Usa `from . import cores as C` (paleta dinâmica) para que a troca de
tema valha em todos os elementos da tela.
Aplica `mostrar_menu=False` nas telas de abertura (logo, splash,
escolha de modo) — o menu superior não aparece nelas.
"""
from __future__ import annotations

import sys
import time

from ..config import SPLASH_DELAY
from ..estado import INFO, AbrirMenuOutroModo, base_do_contexto
from ..texto import normalizar_texto
from . import cores as C
from .motor import (
    obter_dimensoes_terminal,
    ajustar_texto_puro,
    quebrar_texto_puro,
    desenhar_desktop_base,
    sobrepor_janela_no_canvas,
    renderizar_quadro_completo,
)
from .menu_barra import ACOES_MENU_BASICAS, indice_menu_por_tecla
from .teclado import ler_tecla


# =========================================================================
# Item genérico
# =========================================================================

def criar_item_tui(texto, cor=None, alinhamento="esq",
                   selecionavel=False, dados=None, divisor=False, atalho=None):
    """Constrói um item consumível por navegador e popup.
    `cor=None` resolve para a cor de texto atual da paleta em tempo de
    execução — assim, mudar de paleta reflete em todos os itens.
    """
    if cor is None:
        cor = C.CAIXA_TEXTO
    return {
        "texto": texto,
        "cor": cor,
        "alinhamento": alinhamento,
        "selecionavel": selecionavel,
        "dados": dados,
        "divisor": divisor,
        "atalho": str(atalho).upper() if atalho is not None else None,
    }


# =========================================================================
# Logo (5 linhas, estilo bloco sólido moderno)
# =========================================================================

_LOGO_ART = [
    "██████  █████  ██████  ██████  ██████     ██████  █████  ██████ ██ ██",
    "  ██   ██   ██ ██   ██ ██   ██ ██         ██     ██   ██ ██     ██ ██",
    "  ██   ██   ██ ██████  ██████  █████      █████  ███████ ██     ██ ██",
    "  ██   ██   ██ ██   ██ ██   ██ ██         ██     ██   ██ ██     ██ ██",
    "  ██    █████  ██   ██ ██   ██ ██████     ██     ██   ██ ██████ ██████",
]


def _linhas_logo_formatadas(miolo):
    """Gera as 5 linhas da logo já com cor e centralização.
    Usa um degradê: 2 primeiras linhas em LOGO_AZUL, 2 seguintes em
    LOGO_CIANO, última em LOGO_VERDE.
    """
    linhas = []
    for i, linha_art in enumerate(_LOGO_ART):
        if i < 2:
            cor_logo = C.LOGO_AZUL
        elif i < 4:
            cor_logo = C.LOGO_CIANO
        else:
            cor_logo = C.LOGO_VERDE
        linhas.append(
            f"{C.CAIXA_BORDA}│ {cor_logo}"
            f"{ajustar_texto_puro(linha_art, miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}"
        )
    return linhas


# =========================================================================
# Tela de logo persistente (sem menu)
# =========================================================================

def tela_logo(on_enter=None):
    """Tela de abertura persistente.
    Sem menu superior. ENTER abre o menu; ESC fica no logo; X encerra.
    """
    INFO.modulo_atual = "TELA INICIAL"
    sys.stdout.write("\033[?25l")
    while True:
        larg_t, alt_t = obter_dimensoes_terminal()
        larg_box = min(larg_t - 6, 74)
        miolo = larg_box - 4
        linhas_logo = _linhas_logo_formatadas(miolo)
        linhas = [
            f"{C.CAIXA_BORDA}╭{'─' * (larg_box - 2)}╮{C.RESET}",
            f"{C.CAIXA_BORDA}│{C.BARRA_STATUS_TOPO}"
            f"{ajustar_texto_puro(' SISTEMA NACIONAL DE TELECOMUNICAÇÕES ', larg_box - 2, 'centro')}"
            f"{C.CAIXA_BORDA}│{C.RESET}",
            f"{C.CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{C.RESET}",
            f"{C.CAIXA_BORDA}│ {' ' * miolo} │{C.RESET}",
        ] + linhas_logo + [
            f"{C.CAIXA_BORDA}│ {' ' * miolo} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {C.LOGO_CINZA}"
            f"{ajustar_texto_puro('ENGENHARIA DE REDES MÓVEIS & ERBs ANATEL', miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {C.LOGO_CINZA}"
            f"{ajustar_texto_puro('vibecoded by @vivohans  ::  Classic ERP Edition', miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {' ' * miolo} │{C.RESET}",
            f"{C.CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{C.RESET}",
            f"{C.CAIXA_BORDA}│ {C.CAIXA_CIANO}"
            f"{ajustar_texto_puro('[ENTER] Abrir o menu principal    [ESC] Ficar no logo    [X] Sair', miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {' ' * miolo} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {C.CAIXA_TEXTO}"
            f"{ajustar_texto_puro(f'Base: {INFO.data_atualizacao}   │   {INFO.origem[:36]}', miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {C.CAIXA_TEXTO}"
            f"{ajustar_texto_puro(f'{INFO.erbs:,} ERBs  │  {INFO.municipios:,} municípios  │  {INFO.ufs} UFs'.replace(',', '.'), miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {' ' * miolo} │{C.RESET}",
            f"{C.CAIXA_BORDA}╰{'─' * (larg_box - 2)}╯{C.RESET}",
        ]
        rodape = "X = Sair  │  ESC = Ficar no logo  │  ENTER = Abrir o menu"
        canvas = desenhar_desktop_base(larg_t, alt_t, msg_rodape=rodape,
                                       mostrar_menu=False)
        sobrepor_janela_no_canvas(canvas, larg_t, alt_t, linhas, larg_box, sombra=True)
        renderizar_quadro_completo(canvas, lembrar=False)
        tecla = ler_tecla()
        if tecla is None or tecla == "IGNORE":
            continue
        if tecla in ("F12", "CTRL_F12"):
            raise AbrirMenuOutroModo()
        t_up = tecla.upper() if len(tecla) == 1 else tecla
        if t_up in ("X", "ALT_F4"):
            raise KeyboardInterrupt
        if tecla in ("ENTER", " "):
            if callable(on_enter):
                on_enter()
            continue
        if tecla == "ESC":
            continue


# =========================================================================
# Tela de escolha de modo (sem menu)
# =========================================================================

def tela_escolha_modo():
    """Pergunta o modo de uso. Sem menu superior."""
    INFO.modulo_atual = "TELA DE BOAS-VINDAS"
    sys.stdout.write("\033[?25l")
    while True:
        larg_t, alt_t = obter_dimensoes_terminal()
        larg_box = min(larg_t - 6, 76)
        miolo = larg_box - 4
        linhas = [
            f"{C.CAIXA_BORDA}╭{'─' * (larg_box - 2)}╮{C.RESET}",
            f"{C.CAIXA_BORDA}│{C.BARRA_STATUS_TOPO}"
            f"{ajustar_texto_puro(' COMO DESEJA ABRIR O TORRE FÁCIL ', larg_box - 2, 'centro')}"
            f"{C.CAIXA_BORDA}│{C.RESET}",
            f"{C.CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{C.RESET}",
            f"{C.CAIXA_BORDA}│ {' ' * miolo} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {C.CAIXA_TEXTO}"
            f"{ajustar_texto_puro('Escolha o modo de uso desta sessão:', miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {' ' * miolo} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {C.CAIXA_TITULO}"
            f"{ajustar_texto_puro('[1] MODO LOJA', miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {C.CAIXA_CIANO}"
            f"{ajustar_texto_puro('Consulta rápida, comparação, favoritos', miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {' ' * miolo} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {C.CAIXA_TITULO}"
            f"{ajustar_texto_puro('[2] MODO ANALISTA', miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {C.CAIXA_CIANO}"
            f"{ajustar_texto_puro('Análise completa, ranking, faixas, KML', miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {' ' * miolo} │{C.RESET}",
            f"{C.CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{C.RESET}",
            f"{C.CAIXA_BORDA}│ {C.CAIXA_TEXTO}"
            f"{ajustar_texto_puro('1 ou 2 = escolher só nesta sessão', miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {C.CAIXA_TEXTO}"
            f"{ajustar_texto_puro('L      = escolher e lembrar (não perguntar mais)', miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {C.CAIXA_TEXTO}"
            f"{ajustar_texto_puro('X      = fechar o programa', miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {' ' * miolo} │{C.RESET}",
            f"{C.CAIXA_BORDA}╰{'─' * (larg_box - 2)}╯{C.RESET}",
        ]
        rodape = "1 = Loja   |   2 = Analista   |   L = Lembrar   |   X = Sair"
        canvas = desenhar_desktop_base(larg_t, alt_t, msg_rodape=rodape,
                                       mostrar_menu=False)
        sobrepor_janela_no_canvas(canvas, larg_t, alt_t, linhas, larg_box, sombra=True)
        renderizar_quadro_completo(canvas, lembrar=False)
        tecla = ler_tecla()
        if tecla is None or tecla == "IGNORE":
            continue
        t_up = tecla.upper() if len(tecla) == 1 else tecla
        if t_up in ("X", "ALT_F4"):
            return None
        if tecla == "ESC":
            return None
        if t_up == "L":
            sub = caixa_notificacao_tui(
                modulo="LEMBRAR ESCOLHA",
                titulo="LEMBRAR QUAL MODO?",
                linhas_mensagem=[
                    "Qual modo deseja que o sistema use por padrão",
                    "nas próximas aberturas?",
                ],
                botoes=[
                    ("1", "Loja", "loja"),
                    ("2", "Analista", "analista"),
                    ("N", "Não lembrar agora", "NAO"),
                ],
            )
            if sub in ("loja", "analista"):
                return ("lembrar", sub)
            continue
        if t_up == "1":
            return ("modo", "loja")
        if t_up == "2":
            return ("modo", "analista")


# =========================================================================
# Splash e progresso (sem menu)
# =========================================================================

def mostrar_splash_screen():
    INFO.modulo_atual = "SPLASH SCREEN"
    etapas = [
        (15, "Inicializando núcleo gráfico TUI vDos/Clipper..."),
        (35, "Carregando tabela de frequências e operadoras SMP..."),
        (60, "Verificando dicionários nacionais de municípios e BRs..."),
        (85, "Inspecionando integridade de cache local (.pkl / .json)..."),
        (100, "Sistema pronto! Iniciando gerenciador de banco de dados..."),
    ]
    for perc, msg_status in etapas:
        larg_t, alt_t = obter_dimensoes_terminal()
        larg_box = min(larg_t - 6, 74)
        miolo = larg_box - 4
        tam_barra = miolo - 10
        preenchido = int(round((perc / 100.0) * tam_barra))
        barra_str = ("█" * preenchido) + ("░" * (tam_barra - preenchido))
        linha_prog = f"[{barra_str}] {perc:3d}%"
        linhas_logo_splash = _linhas_logo_formatadas(miolo)
        linhas_splash = [
            f"{C.CAIXA_BORDA}╭{'─' * (larg_box - 2)}╮{C.RESET}",
            f"{C.CAIXA_BORDA}│{C.BARRA_STATUS_TOPO}"
            f"{ajustar_texto_puro('TORRE FÁCIL ERP - SISTEMA NACIONAL DE TELECOMUNICAÇÕES', larg_box - 2, 'centro')}"
            f"{C.CAIXA_BORDA}│{C.RESET}",
            f"{C.CAIXA_BORDA}│ {' ' * miolo} │{C.RESET}",
        ] + linhas_logo_splash + [
            f"{C.CAIXA_BORDA}│ {' ' * miolo} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {C.CAIXA_TEXTO}"
            f"{ajustar_texto_puro('ENGENHARIA DE REDES MÓVEIS & MAPEAMENTO DE ERBs ANATEL', miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {C.CAIXA_TEXTO}"
            f"{ajustar_texto_puro('vibecoded by @vivohans  ::  Edição Classic ERP', miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}",
            f"{C.CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{C.RESET}",
            f"{C.CAIXA_BORDA}│ {C.CAIXA_TEXTO}"
            f"{ajustar_texto_puro(msg_status, miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}",
            f"{C.CAIXA_BORDA}│ {C.CAIXA_CAMPO_ATIVO}"
            f"{ajustar_texto_puro(linha_prog, miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}",
            f"{C.CAIXA_BORDA}╰{'─' * (larg_box - 2)}╯{C.RESET}",
        ]
        canvas = desenhar_desktop_base(
            larg_t, alt_t,
            msg_rodape="Inicializando Torre Fácil ERP. Aguarde...",
            mostrar_menu=False,
        )
        sobrepor_janela_no_canvas(canvas, larg_t, alt_t, linhas_splash, larg_box, sombra=True)
        renderizar_quadro_completo(canvas)
        time.sleep(SPLASH_DELAY)


def desenhar_progresso_tui(perc, titulo_etapa, subfrase_telecom, detalhe_extra=""):
    larg_t, alt_t = obter_dimensoes_terminal()
    larg_box = min(larg_t - 6, 72)
    miolo = larg_box - 4
    tam_barra = miolo - 10
    preenchido = int(round((min(100.0, max(0.0, perc)) / 100.0) * tam_barra))
    barra_str = ("█" * preenchido) + ("░" * (tam_barra - preenchido))
    linha_barra = f"[{barra_str}] {perc:5.1f}%"
    linhas_box = [
        f"{C.CAIXA_BORDA}{'─' * (larg_box - 2)}╮{C.RESET}",
        f"{C.CAIXA_BORDA}│{C.BARRA_STATUS_TOPO}"
        f"{ajustar_texto_puro('AGUARDE - PROCESSANDO BASE DE DADOS ANATEL', larg_box - 2, 'centro')}"
        f"{C.CAIXA_BORDA}│{C.RESET}",
        f"{C.CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{C.RESET}",
        f"{C.CAIXA_BORDA}│ {C.CAIXA_TITULO}"
        f"{ajustar_texto_puro(titulo_etapa, miolo, 'centro')}"
        f"{C.CAIXA_BORDA} │{C.RESET}",
        f"{C.CAIXA_BORDA}│ {C.CAIXA_TEXTO}"
        f"{ajustar_texto_puro(subfrase_telecom, miolo, 'centro')}"
        f"{C.CAIXA_BORDA} │{C.RESET}",
        f"{C.CAIXA_BORDA}│ {C.CAIXA_CAMPO_ATIVO}"
        f"{ajustar_texto_puro(linha_barra, miolo, 'centro')}"
        f"{C.CAIXA_BORDA} │{C.RESET}",
    ]
    if detalhe_extra:
        linhas_box.append(
            f"{C.CAIXA_BORDA}│ {C.CAIXA_CIANO}"
            f"{ajustar_texto_puro(detalhe_extra, miolo, 'centro')}"
            f"{C.CAIXA_BORDA} │{C.RESET}"
        )
    linhas_box.append(f"{C.CAIXA_BORDA}{'─' * (larg_box - 2)}╯{C.RESET}")
    canvas = desenhar_desktop_base(
        larg_t, alt_t,
        msg_rodape="Processando registros em memória. Aguarde...",
        mostrar_menu=False,
    )
    sobrepor_janela_no_canvas(canvas, larg_t, alt_t, linhas_box, larg_box, sombra=True)
    renderizar_quadro_completo(canvas)


# =========================================================================
# Notificação e alerta (com menu no fundo)
# =========================================================================

def caixa_notificacao_tui(modulo, titulo, linhas_mensagem, botoes=None,
                          cor_cabecalho=None, botao_padrao=0,
                          fechar_com_esc=True):
    INFO.modulo_atual = modulo
    if cor_cabecalho is None:
        cor_cabecalho = C.BARRA_STATUS_TOPO
    if not botoes:
        botoes = [("ENTER", "OK / Continuar", "OK")]
    idx_sel = max(0, min(botao_padrao, len(botoes) - 1))
    mapa_teclas = {}
    for i, (t_b, _, v_b) in enumerate(botoes):
        if t_b:
            mapa_teclas[str(t_b).upper()] = (i, v_b)
    sys.stdout.write("\033[?25l")
    while True:
        larg_t, alt_t = obter_dimensoes_terminal()
        larg_box = min(larg_t - 6, 72)
        miolo = larg_box - 4
        titulo_txt = f" [!] {titulo} "
        linhas_box = [
            f"{C.CAIXA_BORDA}╭{'─' * (larg_box - 2)}╮{C.RESET}",
            f"{C.CAIXA_BORDA}│{cor_cabecalho}"
            f"{ajustar_texto_puro(titulo_txt, larg_box - 2, 'centro')}"
            f"{C.CAIXA_BORDA}│{C.RESET}",
            f"{C.CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{C.RESET}",
            f"{C.CAIXA_BORDA}│ {' ' * miolo} │{C.RESET}",
        ]
        for ln in linhas_mensagem:
            for parte in quebrar_texto_puro(ln, miolo - 2):
                linhas_box.append(
                    f"{C.CAIXA_BORDA}│ {C.CAIXA_TEXTO}"
                    f"{ajustar_texto_puro(parte, miolo, 'centro')}"
                    f"{C.CAIXA_BORDA} │{C.RESET}"
                )
        linhas_box.append(f"{C.CAIXA_BORDA}│ {' ' * miolo} │{C.RESET}")
        linhas_box.append(f"{C.CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{C.RESET}")
        larg_total_botoes = sum(len(rot) + 8 for _, rot, _ in botoes)
        if len(botoes) <= 3 and larg_total_botoes <= miolo:
            partes = []
            texto_total = 0
            for i, (t_b, rot_b, _) in enumerate(botoes):
                if t_b not in ("ENTER", ""):
                    lbl = f" [{t_b}] {rot_b} "
                else:
                    lbl = f" {rot_b} "
                texto_total += len(lbl)
                if i == idx_sel:
                    partes.append(f"{C.CAIXA_BOTAO_ATIVO}►{lbl}◄{C.CAIXA_BORDA}")
                    texto_total += 2
                else:
                    partes.append(f"{C.CAIXA_BOTAO_INATIVO} {lbl} {C.CAIXA_BORDA}")
                    texto_total += 2
            esp = "   "
            texto_total += len(esp) * (len(botoes) - 1)
            pad_esq = max(0, (miolo - texto_total) // 2)
            pad_dir = max(0, miolo - texto_total - pad_esq)
            linha_botoes = f"{' ' * pad_esq}{esp.join(partes)}{' ' * pad_dir}"
            linhas_box.append(f"{C.CAIXA_BORDA}│ {linha_botoes} │{C.RESET}")
        else:
            for i, (t_b, rot_b, _) in enumerate(botoes):
                if t_b not in ("ENTER", ""):
                    lbl = f"[{t_b}] {rot_b}"
                else:
                    lbl = rot_b
                if i == idx_sel:
                    txt = ajustar_texto_puro(f"► {lbl} ◄", miolo, "centro")
                    linhas_box.append(
                        f"{C.CAIXA_BORDA}│ {C.CAIXA_BOTAO_ATIVO}{txt}{C.CAIXA_BORDA} │{C.RESET}"
                    )
                else:
                    txt = ajustar_texto_puro(f"  {lbl}  ", miolo, "centro")
                    linhas_box.append(
                        f"{C.CAIXA_BORDA}│ {C.CAIXA_TEXTO}{txt}{C.CAIXA_BORDA} │{C.RESET}"
                    )
        linhas_box.append(f"{C.CAIXA_BORDA}╰{'─' * (larg_box - 2)}╯{C.RESET}")
        rodape = "←/→ ou ↑/↓ seleciona o botão  │  ENTER confirma  │  X sai"
        canvas = desenhar_desktop_base(larg_t, alt_t, msg_rodape=rodape)
        sobrepor_janela_no_canvas(canvas, larg_t, alt_t, linhas_box, larg_box, sombra=True)
        renderizar_quadro_completo(canvas)
        tecla = ler_tecla()
        if tecla is None or tecla == "IGNORE":
            continue
        if tecla in ("F12", "CTRL_F12"):
            raise AbrirMenuOutroModo()
        t_up = tecla.upper() if len(tecla) == 1 else tecla
        if t_up == "X" and not any(b[0].upper() == "X" for b in botoes):
            raise KeyboardInterrupt
        if t_up in mapa_teclas:
            _, val = mapa_teclas[t_up]
            return val
        if tecla in ("LEFT", "UP", "W", "w", "A", "a"):
            idx_sel = (idx_sel - 1) % len(botoes)
        elif tecla in ("RIGHT", "DOWN", "S", "s", "D", "d", "TAB"):
            idx_sel = (idx_sel + 1) % len(botoes)
        elif tecla == "ENTER":
            return botoes[idx_sel][2]
        elif tecla == "ESC" and fechar_com_esc:
            return botoes[-1][2]


def alerta_tui(modulo, titulo, linhas_mensagem, cor_titulo=None):
    caixa_notificacao_tui(
        modulo=modulo,
        titulo=titulo,
        linhas_mensagem=linhas_mensagem,
        botoes=[("ENTER", "OK / Fechar Notificação", "OK")],
        cor_cabecalho=cor_titulo,
    )


# =========================================================================
# Droplist (com menu no fundo)
# =========================================================================

def abrir_droplist_popup(titulo, opcoes, valor_atual="", canvas_fundo=None,
                         pos_y=None, pos_x=None):
    lista_norm = []
    for item in opcoes:
        if isinstance(item, (tuple, list)) and len(item) >= 2:
            lista_norm.append((str(item[0]), str(item[1])))
        else:
            lista_norm.append((str(item), str(item)))
    if not lista_norm:
        return None
    pos_cursor = 0
    for i, (v, _) in enumerate(lista_norm):
        if v.upper() == str(valor_atual).upper():
            pos_cursor = i
            break
    offset_scroll = 0
    filtro_rapido = ""
    while True:
        larg_t, alt_t = obter_dimensoes_terminal()
        if filtro_rapido:
            f_norm = normalizar_texto(filtro_rapido)
            opcoes_vis = [
                (v, r) for v, r in lista_norm
                if f_norm in normalizar_texto(v) or f_norm in normalizar_texto(r)
            ]
            if not opcoes_vis:
                opcoes_vis = lista_norm
        else:
            opcoes_vis = lista_norm
        total_op = len(opcoes_vis)
        pos_cursor = max(0, min(pos_cursor, total_op - 1))
        altura_max = min(12, max(5, alt_t - 10))
        altura_vis = min(total_op, altura_max)
        if pos_cursor < offset_scroll:
            offset_scroll = pos_cursor
        elif pos_cursor >= offset_scroll + altura_vis:
            offset_scroll = pos_cursor - altura_vis + 1
        max_sc = max(0, total_op - altura_vis)
        offset_scroll = max(0, min(offset_scroll, max_sc))
        maior_texto = max((len(r) for _, r in opcoes_vis), default=20)
        larg_drop = min(larg_t - 8, max(34, len(titulo) + 8, maior_texto + 8))
        miolo = larg_drop - 4
        linhas = []
        tit = f" ▼ {titulo[:miolo - 4]} "
        tr_e = (larg_drop - 2 - len(tit)) // 2
        tr_d = (larg_drop - 2) - len(tit) - tr_e
        linhas.append(f"{C.DROPLIST_BORDA}╭{'─' * tr_e}{tit}{'─' * tr_d}╮{C.RESET}")
        if filtro_rapido:
            linhas.append(
                f"{C.DROPLIST_BORDA}│ "
                f"{ajustar_texto_puro(f'Filtro: [{filtro_rapido}]', miolo)} "
                f"│{C.RESET}"
            )
            linhas.append(f"{C.DROPLIST_BORDA}├{'─' * (larg_drop - 2)}┤{C.RESET}")
        pos_thumb = 0
        if max_sc > 0 and altura_vis > 2:
            pos_thumb = int(round((offset_scroll / max_sc) * (altura_vis - 3)))
        for i in range(altura_vis):
            idx = offset_scroll + i
            _, rot = opcoes_vis[idx]
            if total_op <= altura_vis:
                ch_sc = "│"
            elif i == 0:
                ch_sc = "▲" if offset_scroll > 0 else "│"
            elif i == altura_vis - 1:
                ch_sc = "▼" if offset_scroll < max_sc else "│"
            else:
                ch_sc = "█" if (i - 1) == pos_thumb else "░"
            if idx == pos_cursor:
                txt = ajustar_texto_puro(f"► {rot}", miolo, "esq")
                linhas.append(
                    f"{C.DROPLIST_BORDA}│{C.DROPLIST_SEL} {txt} "
                    f"{C.DROPLIST_BORDA}{ch_sc}{C.RESET}"
                )
            else:
                txt = ajustar_texto_puro(f"  {rot}", miolo, "esq")
                linhas.append(
                    f"{C.DROPLIST_BORDA}│{C.DROPLIST_ITEM} {txt} "
                    f"{C.DROPLIST_BORDA}{ch_sc}{C.RESET}"
                )
        linhas.append(f"{C.DROPLIST_BORDA}╰{'─' * (larg_drop - 2)}╯{C.RESET}")
        canvas = list(canvas_fundo) if canvas_fundo else desenhar_desktop_base(
            larg_t, alt_t,
            msg_rodape="DROPLIST: ↑/↓ move | digite p/ filtrar | ENTER confirma | ESC cancela",
        )
        sobrepor_janela_no_canvas(
            canvas, larg_t, alt_t, linhas, larg_drop,
            sombra=True, pos_y=pos_y, pos_x=pos_x,
        )
        renderizar_quadro_completo(canvas)
        t = ler_tecla()
        if t is None or t == "IGNORE":
            continue
        if t in ("F12", "CTRL_F12"):
            raise AbrirMenuOutroModo()
        if t == "ESC":
            if filtro_rapido:
                filtro_rapido = ""
                pos_cursor = 0
            else:
                return None
        elif t == "UP":
            pos_cursor = (pos_cursor - 1) % total_op
        elif t == "DOWN":
            pos_cursor = (pos_cursor + 1) % total_op
        elif t == "PGUP":
            pos_cursor = max(0, pos_cursor - altura_vis)
        elif t == "PGDN":
            pos_cursor = min(total_op - 1, pos_cursor + altura_vis)
        elif t == "HOME":
            pos_cursor = 0
        elif t == "END":
            pos_cursor = total_op - 1
        elif t == "ENTER":
            return opcoes_vis[pos_cursor][0]
        elif t in ("BACKSPACE", "DEL"):
            filtro_rapido = filtro_rapido[:-1]
            pos_cursor = 0
        elif len(t) == 1 and t.isprintable():
            filtro_rapido += t.upper()
            pos_cursor = 0


# =========================================================================
# Formulário (com menu)
# =========================================================================

def formulario_tui(modulo, titulo_janela, campos, instrucoes_topo=None,
                   msg_rodape="Digite ou use TAB | F2 abre lista | ENTER confirma | ESC cancela"):
    INFO.modulo_atual = modulo
    if instrucoes_topo is None:
        instrucoes_topo = []
    valores = {c["nome"]: str(c.get("padrao", "")) for c in campos}
    digitado = {c["nome"]: False for c in campos}
    idx_campo = 0
    total_campos = len(campos)

    def obter_opcoes(campo_cfg):
        opcoes = campo_cfg.get("opcoes", [])
        if callable(opcoes):
            opcoes = opcoes(valores)
        return opcoes

    def obter_rotulo_opcao(campo_cfg, val_atual):
        for item in obter_opcoes(campo_cfg):
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                if str(item[0]).upper() == str(val_atual).upper():
                    return str(item[1])
            elif str(item).upper() == str(val_atual).upper():
                return str(item)
        return str(val_atual) if val_atual else ""

    sys.stdout.write("\033[?25l")
    while True:
        larg_t, alt_t = obter_dimensoes_terminal()
        larg_box = min(larg_t - 6, 78)
        miolo = larg_box - 4
        linhas_box = []
        linhas_extra_topo = len(instrucoes_topo) + 1 if instrucoes_topo else 0
        altura_estimada = 6 + linhas_extra_topo + (total_campos * 2)
        area_util = max(4, alt_t - 3)
        topo_box = max(4, 4 + (area_util - altura_estimada) // 2)
        col_box = max(2, (larg_t - larg_box) // 2 + 1)
        tit_limpo = f" {titulo_janela.strip()[:larg_box - 6]} "
        tr_e = (larg_box - 2 - len(tit_limpo)) // 2
        tr_d = (larg_box - 2) - len(tit_limpo) - tr_e
        linhas_box.append(
            f"{C.CAIXA_BORDA}╭{'─' * tr_e}{C.CAIXA_TITULO}{tit_limpo}"
            f"{C.CAIXA_BORDA}{'─' * tr_d}╮{C.RESET}"
        )
        if instrucoes_topo:
            for inst in instrucoes_topo:
                linhas_box.append(
                    f"{C.CAIXA_BORDA}│ {C.CAIXA_TEXTO}"
                    f"{ajustar_texto_puro(inst, miolo)}"
                    f"{C.CAIXA_BORDA} │{C.RESET}"
                )
            linhas_box.append(f"{C.CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{C.RESET}")
        larg_rotulo = max(len(c["rotulo"]) for c in campos) + 2
        linha_y_por_campo = {}
        for i, c in enumerate(campos):
            linha_y_por_campo[i] = len(linhas_box)
            rot = c["rotulo"].ljust(larg_rotulo)
            val_atual = valores[c["nome"]]
            tipo_c = c.get("tipo", "texto")
            larg_inp = min(c.get("largura", 32), max(10, miolo - larg_rotulo - 4))
            cor_estilo = C.CAIXA_CAMPO_ATIVO if i == idx_campo else C.CAIXA_CAMPO_INATIVO
            seta = "►" if i == idx_campo else " "
            cor_rot = C.CAIXA_TITULO if i == idx_campo else C.CAIXA_TEXTO
            if tipo_c in ("droplist", "combobox"):
                if digitado[c["nome"]]:
                    exib = val_atual
                elif val_atual:
                    exib = obter_rotulo_opcao(c, val_atual)
                else:
                    exib = obter_rotulo_opcao(c, "")
                # ✅ CORREÇÃO: exibir o rótulo COMPLETO (ex.: "BRASIL INTEIRO
                # (CONSOLIDADO)") em vez de cortar a cabeça do texto. Se não
                # couber no campo, trunca com reticências preservando o início.
                if i == idx_campo:
                    disp = max(1, larg_inp - 5)  # [ + vis + █ + preench + ▼ ]
                    vis = ajustar_texto_puro(exib, disp, "esq")
                    caixa_inp = f"{cor_estilo}[{vis}█▼]{C.CAIXA_BORDA}"
                else:
                    disp = max(1, larg_inp - 4)
                    vis = ajustar_texto_puro(exib, disp, "esq")
                    caixa_inp = f"{cor_estilo}[{vis} ▼]{C.CAIXA_BORDA}"
            else:  # texto puro
                if len(val_atual) >= larg_inp:
                    val_vis = val_atual[-(larg_inp - 1):]
                else:
                    val_vis = val_atual
                if i == idx_campo:
                    preench = "_" * max(0, larg_inp - len(val_vis) - 1)
                    caixa_inp = f"{cor_estilo}[{val_vis}█{preench}]{C.CAIXA_BORDA}"
                else:
                    preench = "_" * max(0, larg_inp - len(val_vis))
                    caixa_inp = f"{cor_estilo}[{val_vis}{preench}]{C.CAIXA_BORDA}"
            sobra_dir = max(0, miolo - larg_rotulo - larg_inp - 4)
            linhas_box.append(
                f"{C.CAIXA_BORDA}│ {cor_rot}{seta}{rot}:{C.CAIXA_BORDA} "
                f"{caixa_inp}{' ' * sobra_dir} │{C.RESET}"
            )
            if c.get("dica"):
                dica_str = f"   ({c['dica']})"
                linhas_box.append(
                    f"{C.CAIXA_BORDA}│ {C.CAIXA_CIANO}"
                    f"{ajustar_texto_puro(dica_str, miolo)}"
                    f"{C.CAIXA_BORDA} │{C.RESET}"
                )
        linhas_box.append(f"{C.CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{C.RESET}")
        rodape_form = ajustar_texto_puro(
            "[ENTER] Confirma  [F2] Abre lista  [←/→] Navega  "
            "[TAB/↑/↓] Campo  [ESC] Cancela",
            miolo, "centro",
        )
        linhas_box.append(
            f"{C.CAIXA_BORDA}│ {C.CAIXA_TITULO}{rodape_form}{C.CAIXA_BORDA} │{C.RESET}"
        )
        linhas_box.append(f"{C.CAIXA_BORDA}╰{'─' * (larg_box - 2)}╯{C.RESET}")
        canvas = desenhar_desktop_base(larg_t, alt_t, msg_rodape=msg_rodape)
        sobrepor_janela_no_canvas(canvas, larg_t, alt_t, linhas_box, larg_box, sombra=True)
        renderizar_quadro_completo(canvas)
        tecla = ler_tecla()
        if tecla is None or tecla == "IGNORE":
            continue
        if tecla in ("F12", "CTRL_F12"):
            raise AbrirMenuOutroModo()
        campo_atual = campos[idx_campo]
        nome_c = campo_atual["nome"]
        tipo_atual = campo_atual.get("tipo", "texto")
        max_chars = campo_atual.get("max_chars", 80)
        t_up = tecla.upper() if len(tecla) == 1 else tecla
        # ✅ CORREÇÃO: X só fecha se NÃO estiver em campo de texto
        if t_up == "X" and tipo_atual != "texto":
            return None
        # ✅ CORREÇÃO: ESC volta ao campo anterior ou cancela se já no primeiro
        if tecla == "ESC":
            if idx_campo > 0:
                idx_campo -= 1
                continue
            else:
                return None
        if tecla == "UP":
            idx_campo = (idx_campo - 1) % total_campos
            continue
        if tecla in ("DOWN", "TAB"):
            idx_campo = (idx_campo + 1) % total_campos
            continue
        if tipo_atual in ("droplist", "combobox"):
            if tecla == "F2":
                opcoes_raw = obter_opcoes(campo_atual)
                if opcoes_raw:
                    linha_rel = linha_y_por_campo.get(idx_campo, 4)
                    # ✅ CORREÇÃO: Posicionamento correto da droplist
                    pos_y_drop = topo_box + linha_rel + 2
                    pos_x_drop = col_box + larg_rotulo + 2
                    escolhido = abrir_droplist_popup(
                        campo_atual["rotulo"], opcoes_raw, valores[nome_c],
                        canvas_fundo=canvas,
                        pos_y=pos_y_drop,
                        pos_x=pos_x_drop,
                    )
                    if escolhido is not None:
                        valores[nome_c] = escolhido
                        digitado[nome_c] = False
                continue
            if tecla in ("LEFT", "RIGHT"):
                opcoes_raw = obter_opcoes(campo_atual)
                vals = [
                    str(it[0]) if isinstance(it, (tuple, list)) else str(it)
                    for it in opcoes_raw
                ]
                if vals:
                    try:
                        pos = vals.index(valores[nome_c])
                    except ValueError:
                        pos = 0
                    passo = 1 if tecla == "RIGHT" else -1
                    valores[nome_c] = vals[(pos + passo) % len(vals)]
                    digitado[nome_c] = False
                continue
        if tecla == "ENTER":
            if idx_campo < total_campos - 1:
                idx_campo += 1
            else:
                for c in campos:
                    if c.get("tipo") == "droplist":
                        opcoes_raw = obter_opcoes(c)
                        v_atual = valores[c["nome"]]
                        for it in opcoes_raw:
                            if isinstance(it, (tuple, list)) and len(it) >= 2:
                                val_op, rot_op = str(it[0]), str(it[1])
                                if (v_atual.upper() == val_op.upper()
                                        or v_atual.upper() == rot_op.upper()):
                                    valores[c["nome"]] = val_op
                                    break
                return {k: v.strip() for k, v in valores.items()}
            continue
        if tecla in ("BACKSPACE", "DEL"):
            valores[nome_c] = valores[nome_c][:-1]
            digitado[nome_c] = True
            continue
        if len(tecla) == 1 and tecla.isprintable():
            if len(valores[nome_c]) < max_chars:
                if campo_atual.get("maiusculo", True):
                    valores[nome_c] += tecla.upper()
                else:
                    valores[nome_c] += tecla
                digitado[nome_c] = True
            continue


# =========================================================================
# Menu popup centralizado (com menu no fundo)
# =========================================================================

def menu_popup_centralizado(modulo, titulo_caixa, itens_menu,
                            largura_caixa=48,
                            msg_rodape="↑/↓ navega | ENTER confirma | ESC volta | X sai",
                            cursor_inicial=0, permitir_esc=True):
    INFO.modulo_atual = modulo
    indices_sel = [i for i, it in enumerate(itens_menu) if it.get("selecionavel")]
    pos_cursor = (max(0, min(cursor_inicial, len(indices_sel) - 1))
                  if indices_sel else -1)
    mapa_atalhos = {}
    for pos, idx_item in enumerate(indices_sel):
        at = itens_menu[idx_item].get("atalho")
        if at:
            mapa_atalhos[at] = (pos, itens_menu[idx_item].get("dados"))
    habilitadas_popup = set(ACOES_MENU_BASICAS) | ({"BACK"} if permitir_esc else set())
    tecla_pendente = None
    sys.stdout.write("\033[?25l")
    while True:
        larg_t, alt_t = obter_dimensoes_terminal()
        larg_box = min(larg_t - 6, max(36, largura_caixa))
        miolo = larg_box - 4
        idx_destaque = indices_sel[pos_cursor] if (indices_sel and pos_cursor >= 0) else -1
        linhas_box = []
        # (título tratado adiante, com largura exata da caixa)
        linhas_box.append("")
        for i, item in enumerate(itens_menu):
            if item.get("divisor"):
                linhas_box.append(f"{C.CAIXA_BORDA}├{'─' * (larg_box - 2)}┤{C.RESET}")
            elif i == idx_destaque:
                txt_puro = ajustar_texto_puro(item["texto"], miolo,
                                              item.get("alinhamento", "esq"))
                linhas_box.append(
                    f"{C.CAIXA_BORDA}│ {C.CAIXA_SELECAO}{txt_puro}{C.CAIXA_BORDA} │{C.RESET}"
                )
            else:
                txt_puro = ajustar_texto_puro(item["texto"], miolo,
                                              item.get("alinhamento", "esq"))
                cor_it = item.get("cor", C.CAIXA_TEXTO)
                linhas_box.append(
                    f"{C.CAIXA_BORDA}│ {cor_it}{txt_puro}{C.CAIXA_BORDA} │{C.RESET}"
                )
        linhas_box.append(f"{C.CAIXA_BORDA}╰{'─' * (larg_box - 2)}╯{C.RESET}")

        # ✅ CORREÇÃO: título centralizado com LARGURA EXATA — evita que a
        # linha fique mais curta/longa que as demais e "quebre" as bordas
        if titulo_caixa:
            tit_limpo = f" {titulo_caixa.strip()} "
            esp_interno = larg_box - 2
            if len(tit_limpo) > esp_interno - 2:
                tit_limpo = tit_limpo[:esp_interno - 2]
            tracos_esq = max(1, (esp_interno - len(tit_limpo)) // 2)
            tracos_dir = max(1, esp_interno - len(tit_limpo) - tracos_esq)
            linhas_box[0] = (
                f"{C.CAIXA_BORDA}╭{'─' * tracos_esq}{C.CAIXA_TITULO}{tit_limpo}"
                f"{C.CAIXA_BORDA}{'─' * tracos_dir}╮{C.RESET}"
            )
        else:
            linhas_box[0] = (
                f"{C.CAIXA_BORDA}╭{'─' * (larg_box - 2)}╮{C.RESET}"
            )

        canvas = desenhar_desktop_base(larg_t, alt_t, msg_rodape=msg_rodape)
        sobrepor_janela_no_canvas(canvas, larg_t, alt_t, linhas_box, larg_box, sombra=True)
        renderizar_quadro_completo(canvas)
        if tecla_pendente is not None:
            tecla, tecla_pendente = tecla_pendente, None
        else:
            tecla = ler_tecla()
        if tecla is None or tecla == "IGNORE":
            continue
        if tecla in ("F12", "CTRL_F12"):
            raise AbrirMenuOutroModo()
        # F10: alterna a visibilidade da barra de menu (não desenha outra)
        if tecla == "F10":
            from .menu_barra import alternar_barra_menu
            alternar_barra_menu()
            continue
        t_up = tecla.upper() if len(tecla) == 1 else tecla
        if t_up == "X" and not any(it.get("dados") == "X" for it in itens_menu):
            raise KeyboardInterrupt
        cat_menu = indice_menu_por_tecla(t_up, modulo)
        if cat_menu is None and t_up in ("F", "F2"):
            cat_menu = 0
        if cat_menu is None and t_up.startswith("ALT_"):
            continue
        if cat_menu is not None:
            from .menus import menu_dropdown_ancorado_tui, executar_acao_menu_comum
            acao_menu = menu_dropdown_ancorado_tui(
                modulo, cat_menu, habilitadas=habilitadas_popup
            )
            tecla_pendente = executar_acao_menu_comum(acao_menu, modulo)
            if tecla_pendente == "QUIT":
                raise KeyboardInterrupt
            if tecla_pendente == "LOGO":
                return ("LOGO", None, pos_cursor)
            continue
        if tecla == "/":
            from ..pesquisa_global import pesquisa_global_tui
            pesquisa_global_tui(base_do_contexto())
            continue
        if t_up in mapa_atalhos:
            nova_pos, dados_ret = mapa_atalhos[t_up]
            return ("SELECT", dados_ret, nova_pos)
        if tecla in ("UP", "W", "w", "K", "k"):
            if indices_sel:
                pos_cursor = (pos_cursor - 1) % len(indices_sel)
        elif tecla in ("DOWN", "S", "s", "J", "j"):
            if indices_sel:
                pos_cursor = (pos_cursor + 1) % len(indices_sel)
        elif tecla == "HOME" and indices_sel:
            pos_cursor = 0
        elif tecla == "END" and indices_sel:
            pos_cursor = len(indices_sel) - 1
        elif tecla == "ENTER":
            if idx_destaque >= 0:
                return ("SELECT", itens_menu[idx_destaque].get("dados"), pos_cursor)
            return ("VOLTAR", None, pos_cursor)
        elif permitir_esc and tecla in ("ESC", "0"):
            return ("VOLTAR", None, pos_cursor)