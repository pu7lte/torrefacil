"""Motor TUI: inicialização, dimensões, ajuste de texto, desktop base."""
from __future__ import annotations

import datetime
import os
import re
import select
import shutil
import sys
import time

from ..config import DIAS_SEMANA
from ..estado import INFO
from . import cores as C
from .menu_barra import renderizar_menu_superior_fixo, barra_visivel

# ✅ CORREÇÃO: regex ANSI correta (sem colchetes duplos)
RE_ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

_ULTIMO_QUADRO = {"dim": None, "cmds": []}


def iniciar_modo_tui():
    sys.stdout.write("\033[?1049h\033[?25l\033[2J")
    sys.stdout.flush()


def encerrar_modo_tui():
    sys.stdout.write(f"{C.RESET}\033[?25h\033[?1049l")
    sys.stdout.flush()


def obter_dimensoes_terminal():
    tam = shutil.get_terminal_size(fallback=(100, 30))
    return max(72, tam.columns), max(22, tam.lines)


# ✅ CORREÇÃO: alinhamentos sem espaços, padding com 1 espaço, regex substitui por ""
def _cortar_largura(texto, largura):
    """Trunca texto preservando a LARGURA VISUAL.

    Caracteres de largura dupla (CJK e similares, classificados como
    "Wide"/"Fullwidth" pela Unicode) contam 2 colunas; os demais contam 1.
    O resultado nunca excede ``largura`` colunas visuais.
    """
    import unicodedata as _ud
    acum = 0
    saida = []
    for ch in texto:
        w = 2 if _ud.east_asian_width(ch) in ("W", "F") else 1
        if acum + w > largura:
            if acum < largura:
                saida.append(" ")  # preenche a coluna restante
            break
        saida.append(ch)
        acum += w
    return "".join(saida)


def ajustar_texto_puro(texto, largura, alinhamento="esq", truncar=True):
    # Remove códigos ANSI para calcular tamanho real
    limpo = RE_ANSI.sub("", str(texto))

    if len(limpo) > largura:
        if truncar and largura > 3:
            # Truncamento simples: mantém exatamente `largura` caracteres,
            # com sufixo "..." sempre ao final (sem cortar em limite de
            # palavra nem completar com espaços).
            limpo = _cortar_largura(limpo[:largura - 3], largura - 3) + "..."
        else:
            limpo = _cortar_largura(limpo, largura)
    
    faltam = max(0, largura - len(limpo))
    
    # ✅ CORREÇÃO: alinhamentos corretos (sem espaços no final)
    if alinhamento == "centro":
        esq = faltam // 2
        return (" " * esq) + limpo + (" " * (faltam - esq))
    if alinhamento == "dir":
        return (" " * faltam) + limpo
    # Default: esquerda
    return limpo + (" " * faltam)


def quebrar_texto_puro(texto, max_cols):
    limpo = RE_ANSI.sub("", str(texto))
    if len(limpo) <= max_cols:
        return [limpo]
    palavras = limpo.split(" ")
    linhas, atual = [], ""
    for p in palavras:
        if len(atual) + len(p) + (1 if atual else 0) <= max_cols:
            atual = f"{atual} {p}" if atual else p
        else:
            if atual:
                linhas.append(atual)
            atual = p[:max_cols]
    if atual:
        linhas.append(atual)
    return linhas if linhas else [""]


# =========================================================================
# Padrões de fundo
# =========================================================================

def _linha_fundo_nu(larg):
    return " " * larg


def _linha_fundo_xadrez(larg, linha_idx):
    if linha_idx % 2 == 0:
        padrao = " · "
    else:
        padrao = "·  "
    repeticoes = (larg // len(padrao)) + 1
    return (padrao * repeticoes)[:larg]


def _linha_fundo_grade(larg, linha_idx):
    if linha_idx % 2 == 0:
        padrao = "· "
        repeticoes = (larg // len(padrao)) + 1
        return (padrao * repeticoes)[:larg]
    return " " * larg


def _linha_fundo(larg, linha_idx, modo):
    if modo == "xadrez":
        return _linha_fundo_xadrez(larg, linha_idx)
    if modo == "grade":
        return _linha_fundo_grade(larg, linha_idx)
    return _linha_fundo_nu(larg)


def _modo_fundo_atual():
    try:
        from ..config_usuario import obter_fundo
        return obter_fundo()
    except Exception:
        return "nu"


# =========================================================================
# Relógio em tempo real (hh:mm:ss) na barra de status inferior
# =========================================================================

_HORA_LINHA = None       # número da linha da barra de status inferior
_HORA_COLUNA = None      # coluna onde a hora é desenhada


def _tecla_pendente():
    """Verifica (sem bloquear) se há tecla digitada aguardando leitura."""
    try:
        if os.name == "nt":
            import msvcrt
            return msvcrt.kbhit()
        fd = sys.stdin.fileno()
        if not sys.stdin.readable():
            return False
        return bool(select.select([fd], [], [], 0)[0])
    except Exception:
        return False


def esperar_com_relogio(segundos, larg=None, alt=None):
    """Espera ``segundos`` repintando o relógio hh:mm:ss a cada segundo.

    Usado por telas de abertura (logo/splash) para manter a barra de
    status inferior em tempo real enquanto aguardam uma ação do usuário.
    Interrompe a espera se houver tecla pendente.
    """
    fim = time.monotonic() + max(0.0, float(segundos))
    while time.monotonic() < fim:
        restante = fim - time.monotonic()
        time.sleep(min(0.2, max(0.0, restante)))
        if _HORA_LINHA is not None:
            redesenhar_relogio()
        if _tecla_pendente():
            break


# =========================================================================
# Desktop base
# =========================================================================

def desenhar_desktop_base(larg, alt,
                          msg_rodape="Use ↑/↓ e ENTER.  X/Alt+F4 = Sair.",
                          mostrar_menu=True):
    agora = datetime.datetime.now()
    dia_sem = DIAS_SEMANA[agora.weekday()]
    data_str = f" {dia_sem}, {agora.strftime('%d/%m/%Y')} "
    hora_str = f" {agora.strftime('%H:%M:%S')} "

    # --- Cabeçalho linha 1: data (esq) │ título (centro) │ módulo (dir) ---
    centro_topo = "TORRE FÁCIL ERP v10.0"
    dir_topo = f" {INFO.modulo_atual[:24]} "
    espaco_centro = max(4, larg - len(data_str) - len(dir_topo) - 2)
    texto_centro = ajustar_texto_puro(centro_topo, espaco_centro, "centro")
    linha_1 = (
        f"{C.BARRA_STATUS_TOPO}"
        f"{data_str}│{texto_centro}│{dir_topo}"
        f"{' ' * max(0, larg - len(data_str) - len(texto_centro) - len(dir_topo) - 2)}"
        f"{C.RESET}"
    )

    # --- Linha 2: menu superior (ocupa toda a largura da janela) ---
    if mostrar_menu and barra_visivel():
        linha_2 = renderizar_menu_superior_fixo(larg, INFO.modulo_atual)
    else:
        linha_2 = f"{C.FUNDO_DESKTOP}{' ' * larg}{C.RESET}"

    # --- Linha 3: sub-barra com dados da base ---
    esq_sub = f" Base: {INFO.data_atualizacao} ({INFO.origem[:32]}) "
    if INFO.erbs > 0:
        dir_sub = (f" {INFO.erbs:,} ERBs │ {INFO.municipios:,} Mun. │ "
                   f"{INFO.ufs} UFs ").replace(",", ".")
    else:
        dir_sub = " Inicializando sistema "
    esp_meio_sub = max(0, larg - len(esq_sub) - len(dir_sub))
    linha_3 = (
        f"{C.BARRA_SUB_TOPO}{esq_sub[:larg]}{C.RESET}"
        f"{C.FUNDO_DESKTOP}{' ' * esp_meio_sub}{C.RESET}"
        f"{C.BARRA_SUB_TOPO}{dir_sub[:max(0, larg - len(esq_sub))]}{C.RESET}"
    )

    # --- Rodapé (hora em tempo real hh:mm:ss à direita) ---
    larg_msg = max(10, larg - len(hora_str) - 1)
    msg_ajustada = ajustar_texto_puro(f" {msg_rodape}", larg_msg, "esq")
    linha_rodape = f"{C.BARRA_STATUS_TOPO}{msg_ajustada}│{hora_str}{C.RESET}"

    comandos = [
        f"\033[1;1H{linha_1}",
        f"\033[2;1H{linha_2}",
        f"\033[3;1H{linha_3}",
    ]

    # --- Fundo ---
    modo_fundo = _modo_fundo_atual()
    for r in range(4, alt):
        linha_idx = r - 4
        padrao = _linha_fundo(larg, linha_idx, modo_fundo)
        comandos.append(
            f"\033[{r};1H{C.FUNDO_DESKTOP}{padrao}{C.RESET}"
        )
    comandos.append(f"\033[{alt};1H{linha_rodape}")

    # Registra a posição do relógio para atualização em tempo real
    global _HORA_LINHA, _HORA_COLUNA
    _HORA_LINHA = alt
    _HORA_COLUNA = max(1, larg - len(hora_str) + 1)
    return comandos


def redesenhar_relogio():
    """Repinta o relógio hh:mm:ss na barra de status inferior.

    Deve ser chamada após ``renderizar_quadro_completo`` para manter a
    hora em tempo real sem redesenhar a tela inteira. Não faz nada se o
    desktop base ainda não foi desenhado nesta sessão.
    """
    if _HORA_LINHA is None or _HORA_COLUNA is None:
        return False
    agora = datetime.datetime.now().strftime("%H:%M:%S")
    texto = f" {agora} "
    col = max(1, _HORA_COLUNA)
    sys.stdout.write(
        f"\033[{_HORA_LINHA};{col}H{C.BARRA_STATUS_TOPO}{texto}{C.RESET}"
    )
    sys.stdout.flush()
    return True


# ✅ CORREÇÃO: Limpar área da janela antes de desenhar
def sobrepor_janela_no_canvas(comandos, larg_term, alt_term, linhas_janela,
                              larg_janela, sombra=True, pos_y=None, pos_x=None):
    alt_janela = len(linhas_janela)
    area_util = max(4, alt_term - 3)
    linha_ini = pos_y if pos_y is not None else max(4, 4 + (area_util - alt_janela) // 2)
    col_ini = pos_x if pos_x is not None else max(2, (larg_term - larg_janela) // 2 + 1)
    
    # ✅ CORREÇÃO: Limpar toda a área da janela com fundo sólido ANTES de desenhar
    for i in range(alt_janela):
        r = linha_ini + i
        if r >= alt_term:
            break
        # Preenche a linha inteira da janela com fundo sólido
        comandos.append(
            f"\033[{r};{col_ini}H{C.FUNDO_DESKTOP}{' ' * larg_janela}{C.RESET}"
        )
    
    # ✅ CORREÇÃO: Agora desenha as linhas da janela por cima
    for i, ln in enumerate(linhas_janela):
        r = linha_ini + i
        if r >= alt_term:
            break
        comandos.append(f"\033[{r};{col_ini}H{ln}{C.RESET}")
        if sombra and i >= 1 and (col_ini + larg_janela + 1) <= larg_term:
            comandos.append(
                f"\033[{r};{col_ini + larg_janela}H{C.SOMBRA_3D}  {C.RESET}"
            )
    r_sombra = linha_ini + alt_janela
    if sombra and r_sombra < alt_term:
        larg_sombra = min(larg_janela + 2, larg_term - col_ini - 1)
        if larg_sombra > 0:
            comandos.append(
                f"\033[{r_sombra};{col_ini + 2}H"
                f"{C.SOMBRA_3D}{' ' * larg_sombra}{C.RESET}"
            )


def renderizar_quadro_completo(comandos, lembrar=True):
    if lembrar:
        _ULTIMO_QUADRO["dim"] = obter_dimensoes_terminal()
        _ULTIMO_QUADRO["cmds"] = list(comandos)
    sys.stdout.write("".join(comandos))
    sys.stdout.flush()


def obter_ultimo_quadro():
    return _ULTIMO_QUADRO