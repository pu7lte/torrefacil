"""Sobre o Sistema + Estatísticas da base/cache/consumo."""
from __future__ import annotations

import datetime
import os
import sys

from ..config import ARQUIVO_CACHE, ARQUIVO_ZIP, ARQUIVO_CSV_EXTRAIDO
from ..estado import INFO
from ..tui.cores import BARRA_STATUS_TOPO
from ..tui.janelas import caixa_notificacao_tui


# =========================================================================
# Métricas de consumo (sem dependências externas)
# =========================================================================

def _formatar_bytes(valor) -> str:
    """Formata bytes sem depender de bibliotecas externas."""
    try:
        valor = float(valor)
    except Exception:
        return "N/D"
    unidades = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while valor >= 1024 and i < len(unidades) - 1:
        valor /= 1024.0
        i += 1
    return f"{valor:.1f} {unidades[i]}"


def _memoria_processo_atual():
    """Pico de RSS do processo, só com recursos nativos do SO."""
    try:
        import resource
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return int(rss)
        return int(rss) * 1024
    except Exception:
        pass
    try:
        if os.name == "nt":
            import ctypes
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(counters)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(
                handle, ctypes.byref(counters), counters.cb
            ):
                return int(counters.WorkingSetSize)
    except Exception:
        pass
    return None


def _estatisticas_base(df_erbs) -> dict:
    """Calcula estatísticas úteis da sessão sem alterar o DataFrame."""
    stats = {}
    try:
        stats["linhas"] = len(df_erbs)
        stats["erbs"] = (df_erbs["ID_ERB"].nunique()
                         if "ID_ERB" in df_erbs else len(df_erbs))
        stats["estacoes"] = (df_erbs["NUM_ESTACAO"].nunique()
                             if "NUM_ESTACAO" in df_erbs else 0)
        stats["setores"] = int(INFO.setores)
        stats["ufs"] = df_erbs["UF"].nunique() if "UF" in df_erbs else 0
        stats["municipios"] = (
            df_erbs[["UF", "MUNICIPIO_NORM"]].drop_duplicates().shape[0]
            if {"UF", "MUNICIPIO_NORM"}.issubset(df_erbs.columns) else 0
        )
        stats["bairros"] = (
            df_erbs[["UF", "MUNICIPIO_NORM", "BAIRRO"]]
            .drop_duplicates().shape[0]
            if {"UF", "MUNICIPIO_NORM", "BAIRRO"}.issubset(df_erbs.columns) else 0
        )
        stats["operadoras"] = (df_erbs["OPERADORA"].nunique()
                               if "OPERADORA" in df_erbs else 0)
        stats["tecnologias"] = (df_erbs["TECNOLOGIA"].nunique()
                                if "TECNOLOGIA" in df_erbs else 0)
        if "TECNOLOGIA" in df_erbs:
            tec = df_erbs["TECNOLOGIA"].astype(str).str.upper()
            stats["5g"] = int(tec.str.contains("5G", na=False).sum())
            stats["4g"] = int(tec.str.contains("4G", na=False).sum())
            stats["3g"] = int(tec.str.contains("3G", na=False).sum())
        else:
            stats["5g"] = stats["4g"] = stats["3g"] = 0
        if "LAT_NUM" in df_erbs and "LON_NUM" in df_erbs:
            ok = df_erbs["LAT_NUM"].notna() & df_erbs["LON_NUM"].notna()
            stats["gps"] = int(ok.sum())
            stats["gps_pct"] = (stats["gps"] / max(1, len(df_erbs))) * 100.0
        else:
            stats["gps"] = 0
            stats["gps_pct"] = 0.0
        stats["ram_df"] = int(df_erbs.memory_usage(deep=True).sum())
    except Exception as e:
        # ✅ CORREÇÃO: usa getattr para evitar erro se ultimo_erro não existir
        ultimo = getattr(INFO, 'ultimo_erro', '')
        if ultimo:
            pass  # apenas ignora
        stats.setdefault("linhas", len(df_erbs))
    return stats


# =========================================================================
# Janelas
# =========================================================================

def estatisticas_base_tui(df_erbs) -> None:
    """Caixa com estatísticas da base, cache e consumo da sessão."""
    INFO.modulo_atual = "ESTATÍSTICAS DA BASE"
    s = _estatisticas_base(df_erbs)
    cache_bytes = os.path.getsize(ARQUIVO_CACHE) if os.path.exists(ARQUIVO_CACHE) else 0
    zip_bytes = os.path.getsize(ARQUIVO_ZIP) if os.path.exists(ARQUIVO_ZIP) else 0
    csv_bytes = (os.path.getsize(ARQUIVO_CSV_EXTRAIDO)
                 if os.path.exists(ARQUIVO_CSV_EXTRAIDO) else 0)
    cache_data = "N/D"
    cache_dias = "N/D"
    if os.path.exists(ARQUIVO_CACHE):
        try:
            dt = datetime.datetime.fromtimestamp(os.path.getmtime(ARQUIVO_CACHE))
            cache_data = dt.strftime("%d/%m/%Y %H:%M")
            cache_dias = str((datetime.datetime.now() - dt).days)
        except Exception:
            pass
    ram_proc = _memoria_processo_atual()
    ram_proc_txt = _formatar_bytes(ram_proc) if ram_proc is not None else "N/D"
    linhas = [
        f"BASE: {s.get('linhas', 0):,} linhas | {s.get('erbs', 0):,} ERBs | "
        f"{s.get('estacoes', 0):,} estações".replace(",", "."),
        f"MALHA: {s.get('setores', 0):,} setores | {s.get('ufs', 0)} UFs | "
        f"{s.get('municipios', 0):,} municípios".replace(",", "."),
        f"BAIRROS: {s.get('bairros', 0):,} distintos | "
        f"{INFO.bairros_unificados:,} regras/cache".replace(",", "."),
        f"OPERADORAS: {s.get('operadoras', 0)} | "
        f"TECNOLOGIAS: {s.get('tecnologias', 0)} | "
        f"5G/4G/3G: {s.get('5g', 0):,}/{s.get('4g', 0):,}/"
        f"{s.get('3g', 0):,}".replace(",", "."),
        f"GPS: {s.get('gps', 0):,} registros válidos "
        f"({s.get('gps_pct', 0):.1f}%)".replace(",", "."),
        f"DATA: {INFO.data_atualizacao} | ORIGEM: {INFO.origem}",
        f"CACHE: {_formatar_bytes(cache_bytes)} | idade: {cache_dias} dia(s) | "
        f"{cache_data}",
        f"ZIP ANATEL: {_formatar_bytes(zip_bytes)} | "
        f"CSV extraído: {_formatar_bytes(csv_bytes)}",
        f"MEMÓRIA DATAFRAME: {_formatar_bytes(s.get('ram_df', 0))} | "
        f"RSS/pico processo: {ram_proc_txt}",
    ]
    # ✅ CORREÇÃO: usa getattr para evitar erro se ultimo_erro não existir
    ultimo_erro = getattr(INFO, 'ultimo_erro', '')
    if ultimo_erro:
        linhas.append(f"ÚLTIMO ERRO: {ultimo_erro[:80]}")
    caixa_notificacao_tui(
        modulo="ESTATÍSTICAS DA BASE",
        titulo="ESTATÍSTICAS DA BASE / CACHE / CONSUMO",
        linhas_mensagem=linhas,
        botoes=[("ENTER", "Fechar", "OK")],
        cor_cabecalho=BARRA_STATUS_TOPO,
    )


def sobre_sistema_tui(df_erbs) -> None:
    """Tela 'Sobre o Sistema' com acesso à caixa de estatísticas."""
    while True:
        escolha = caixa_notificacao_tui(
            modulo="SOBRE O SISTEMA",
            titulo="SOBRE O TORRE FÁCIL ERP",
            linhas_mensagem=[
                "Torre Fácil ERP v10.0 — Engenharia SMP / ANATEL",
                "TUI Python puro: ANSI + Alternate Screen Buffer + teclado atômico.",
                "Base: Estações SMP da Anatel, com processamento, indexação e cache local.",
                "Projeto em estilo Classic ERP / Clipper / vDos, sem curses.",
                "Cache binário: torre_facil_cache.pkl | Dicionários em JSON.",
                "A sessão atual mantém telemetria da base, cache, DataFrame e consumo.",
            ],
            botoes=[
                ("E", "Estatísticas da Base", "ESTAT"),
                ("ENTER", "Fechar", "OK"),
            ],
            cor_cabecalho=BARRA_STATUS_TOPO,
        )
        if escolha == "ESTAT":
            estatisticas_base_tui(df_erbs)
        else:
            return