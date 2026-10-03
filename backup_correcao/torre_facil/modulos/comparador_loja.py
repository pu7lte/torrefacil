"""Comparador A vs B (modo loja).

Dado um endereço, o vendedor escolhe 2 operadoras e vê lado a lado:
    - Nota de cobertura
    - Nº de torres próximas
    - Tecnologias e tipo de 5G
    - Faixas de frequência
    - Melhor uso sugerido (streaming, ligações, etc.)

Easter egg F12: aceita abrir o menu do outro modo por cima desta tela,
mantendo o estado atual da consulta.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from ..estado import AbrirMenuOutroModo
from ..tui.cores import CAIXA_TEXTO, CAIXA_TITULO
from ..tui.janelas import (
    criar_item_tui,
    formulario_tui,
    alerta_tui,
)
from ..tui.navegador import navegador_tui
from . import _geo
from .consulta_rapida import _interpretar_consulta

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Raio padrão de busca
_RAIO_PADRAO_KM = 3.0

# Largura das colunas na tabela comparativa
_LARGURA_OPERADORA = 28
_LARGURA_CAMPO = 20

# Opções de raio de busca
_OPCOES_RAIO: list[tuple[str, str]] = [
    ("1.0", "1 km"),
    ("3.0", "3 km"),
    ("5.0", "5 km"),
    ("10.0", "10 km"),
]


# ---------------------------------------------------------------------------
# Sugestão de uso
# ---------------------------------------------------------------------------

def _sugerir_uso(row: dict[str, Any] | None) -> str:
    """Sugere o melhor uso com base nas tecnologias e distância.

    Args:
        row: Dicionário com dados da operadora (pode ser None).

    Returns:
        String com sugestão de uso.

    Examples:
        >>> _sugerir_uso({"TEM_5G": True, "TEC5G_TIPO": "SA-NSA"})
        'streaming, jogos'
        >>> _sugerir_uso(None)
        '—'
    """
    if not row:
        return "—"

    partes: list[str] = []

    if row.get("TEM_5G") and row.get("TEC5G_TIPO") == "SA-NSA":
        partes.append("streaming, jogos")
    elif row.get("TEM_5G"):
        partes.append("streaming")

    if row.get("TEM_4G"):
        partes.append("internet geral")

    if row.get("TEM_3G") or row.get("TEM_2G"):
        partes.append("ligações, emergência")

    if not partes:
        return "cobertura limitada"

    return ", ".join(partes)


def _nota(row: dict[str, Any] | None) -> tuple[str, str]:
    """Retorna (texto, chave_cor) da nota de cobertura.

    Args:
        row: Dicionário com dados da operadora (pode ser None).

    Returns:
        Tupla com texto da nota e chave de cor.

    Examples:
        >>> _nota(None)
        ('SEM COBERTURA', 'sem')
    """
    if not row:
        return "SEM COBERTURA", "sem"
    return _geo.nota_cobertura(row)


# ---------------------------------------------------------------------------
# Montagem do comparativo
# ---------------------------------------------------------------------------

def _formatar_linha_comparativa(
    campo: str,
    valor_a: Any,
    valor_b: Any,
    largura_campo: int = _LARGURA_CAMPO,
    largura_valor: int = _LARGURA_OPERADORA,
) -> str:
    """Formata linha de tabela comparativa.

    Args:
        campo: Nome do campo (ex: "Nota", "Torres próximas").
        valor_a: Valor da operadora A.
        valor_b: Valor da operadora B.
        largura_campo: Largura da coluna de campo.
        largura_valor: Largura das colunas de valor.

    Returns:
        Linha formatada alinhada.

    Examples:
        >>> _formatar_linha_comparativa("Nota", "ÓTIMO", "BOM")
        'Nota                 │ ÓTIMO                          │ BOM                          '
    """
    sa = str(valor_a) if valor_a is not None else "—"
    sb = str(valor_b) if valor_b is not None else "—"
    return f"{campo:<{largura_campo}} │ {sa:<{largura_valor}} │ {sb:<{largura_valor}}"


def _montar_comparativo(
    df_resumo: pd.DataFrame,
    op_a: str,
    op_b: str,
) -> list[str]:
    """Monta as linhas de comparação lado a lado.

    Args:
        df_resumo: DataFrame com resumo por operadora.
        op_a: Nome da operadora A.
        op_b: Nome da operadora B.

    Returns:
        Lista de linhas formatadas para exibição.
    """
    linhas: list[str] = []

    # Cabeçalho
    linhas.append(_formatar_linha_comparativa("", op_a, op_b))
    linhas.append("─" * 84)

    # Busca dados das operadoras
    a = _buscar_operadora(df_resumo, op_a)
    b = _buscar_operadora(df_resumo, op_b)

    # Trata casos de cobertura ausente
    if a is None:
        linhas.append(_formatar_linha_comparativa("Cobertura", "SEM COBERTURA", None))
    if b is None:
        linhas.append(_formatar_linha_comparativa("Cobertura", None, "SEM COBERTURA"))

    # Dados comparativos
    if a or b:
        _adicionar_dados_comparativos(linhas, a, b)

    linhas.append("─" * 84)

    # Sugestão de uso
    linhas.append(_formatar_linha_comparativa(
        "Melhor uso",
        _sugerir_uso(a),
        _sugerir_uso(b),
    ))

    return linhas


def _buscar_operadora(
    df_resumo: pd.DataFrame,
    operadora: str,
) -> dict[str, Any] | None:
    """Busca dados de uma operadora no DataFrame de resumo.

    Args:
        df_resumo: DataFrame com resumo por operadora.
        operadora: Nome da operadora.

    Returns:
        Dicionário com dados da operadora, ou None se não encontrada.
    """
    sub = df_resumo[df_resumo["OPERADORA"] == operadora]
    if sub.empty:
        return None
    return sub.iloc[0].to_dict()


def _adicionar_dados_comparativos(
    linhas: list[str],
    a: dict[str, Any] | None,
    b: dict[str, Any] | None,
) -> None:
    """Adiciona dados comparativos às linhas.

    Args:
        linhas: Lista de linhas (modificada in-place).
        a: Dados da operadora A (pode ser None).
        b: Dados da operadora B (pode ser None).
    """
    nota_a = _nota(a) if a else ("SEM COBERTURA", "sem")
    nota_b = _nota(b) if b else ("SEM COBERTURA", "sem")

    linhas.append(_formatar_linha_comparativa("Nota", nota_a[0], nota_b[0]))

    linhas.append(_formatar_linha_comparativa(
        "Torres próximas",
        a.get("ERBS", 0) if a else 0,
        b.get("ERBS", 0) if b else 0,
    ))

    linhas.append(_formatar_linha_comparativa(
        "Distância mínima",
        f"{a['DIST_MIN']:.2f} km" if a else "—",
        f"{b['DIST_MIN']:.2f} km" if b else "—",
    ))

    linhas.append(_formatar_linha_comparativa(
        "Tecnologias",
        a.get("TECNOLOGIAS", "") if a else "—",
        b.get("TECNOLOGIAS", "") if b else "—",
    ))

    linhas.append(_formatar_linha_comparativa(
        "5G",
        a.get("TEC5G_TIPO", "-") if a else "-",
        b.get("TEC5G_TIPO", "-") if b else "-",
    ))

    linhas.append(_formatar_linha_comparativa(
        "Faixas",
        a.get("FAIXAS", "") if a else "—",
        b.get("FAIXAS", "") if b else "—",
    ))


# ---------------------------------------------------------------------------
# Tratamento de F12
# ---------------------------------------------------------------------------

def _tratar_f12(df_erbs: pd.DataFrame) -> None:
    """Trata o Easter egg F12 (abrir menu do outro modo).

    Args:
        df_erbs: DataFrame completo de ERBs.
    """
    from ..main import _abrir_menu_do_outro_modo
    _abrir_menu_do_outro_modo(df_erbs, "cache", modo_atual="loja")


# ---------------------------------------------------------------------------
# Tela principal
# ---------------------------------------------------------------------------

def comparador_loja(df_erbs: pd.DataFrame, endereco_inicial: str = "") -> None:
    """Ponto de entrada do comparador A vs B.

    F12 → abre o menu do outro modo por cima, sem perder o estado atual.

    Args:
        df_erbs: DataFrame completo de ERBs.
        endereco_inicial: Endereço pré-preenchido (opcional).

    Raises:
        AbrirMenuOutroModo: Se usuário pressionar F12.
    """
    # 1) Lista de operadoras disponíveis na base
    operadoras = sorted(df_erbs["OPERADORA"].dropna().unique().tolist())
    if len(operadoras) < 2:
        alerta_tui(
            "COMPARADOR",
            "OPERADORAS INSUFICIENTES",
            ["A base tem menos de 2 operadoras. Comparação impossível."],
        )
        return

    opcoes = [(o, o) for o in operadoras]

    # 2) Formulário
    try:
        res = formulario_tui(
            modulo="COMPARADOR LOJA",
            titulo_janela="COMPARADOR A vs B — DUAS OPERADORAS NO MESMO ENDEREÇO",
            campos=[
                {
                    "nome": "endereco",
                    "rotulo": "Endereço / CEP",
                    "tipo": "texto",
                    "largura": 40,
                    "padrao": endereco_inicial,
                    "max_chars": 90,
                    "maiusculo": False,
                    "dica": "CEP ou endereço livre",
                },
                {
                    "nome": "operadora_a",
                    "rotulo": "Operadora A",
                    "tipo": "droplist",
                    "largura": 24,
                    "padrao": operadoras[0],
                    "opcoes": opcoes,
                },
                {
                    "nome": "operadora_b",
                    "rotulo": "Operadora B",
                    "tipo": "droplist",
                    "largura": 24,
                    "padrao": operadoras[1] if len(operadoras) > 1 else operadoras[0],
                    "opcoes": opcoes,
                },
                {
                    "nome": "raio",
                    "rotulo": "Raio de busca",
                    "tipo": "droplist",
                    "largura": 20,
                    "padrao": str(_RAIO_PADRAO_KM),
                    "opcoes": _OPCOES_RAIO,
                },
            ],
            instrucoes_topo=[
                "Informe o endereço do cliente e escolha 2 operadoras para comparar.",
            ],
        )
    except AbrirMenuOutroModo:
        _tratar_f12(df_erbs)
        return

    if not res or not res.get("endereco"):
        return

    endereco = res["endereco"]
    op_a = res.get("operadora_a", "")
    op_b = res.get("operadora_b", "")

    if op_a == op_b:
        alerta_tui(
            "COMPARADOR",
            "ESCOLHA DUAS DIFERENTES",
            ["Você escolheu a mesma operadora nos dois lados."],
        )
        return

    try:
        raio_km = float(res.get("raio", str(_RAIO_PADRAO_KM)))
    except ValueError:
        raio_km = _RAIO_PADRAO_KM

    # 3) Interpreta endereço
    df_res, modo, lat, lon, resumo = _interpretar_consulta(df_erbs, endereco)

    if lat is None or df_res.empty:
        alerta_tui(
            "COMPARADOR",
            "ENDEREÇO NÃO LOCALIZADO",
            [f"'{endereco}' não foi encontrado na base."],
        )
        return

    # 4) ERBs próximas
    df_prox = _geo.erbs_proximas(df_erbs, lat, lon, raio_km=raio_km)

    if df_prox.empty:
        alerta_tui(
            "COMPARADOR",
            "SEM TORRES NO RAIO",
            [f"Nenhuma ERB num raio de {raio_km:.0f} km."],
        )
        return

    # 5) Resumo por operadora
    df_resumo = _geo.resumo_por_operadora(df_prox)

    # 6) Comparativo lado a lado
    linhas = _montar_comparativo(df_resumo, op_a, op_b)

    itens = [
        criar_item_tui(linha, CAIXA_TEXTO, "esq")
        for linha in linhas
    ]

    try:
        navegador_tui(
            modulo="COMPARADOR LOJA",
            titulo_janela=f"COMPARATIVO — {resumo}",
            itens_conteudo=itens,
            comandos_rodape=[
                "[ESC] Voltar   |   [F] Adicionar endereço aos favoritos",
            ],
            teclas_rapidas={"F"},
            dica_teclas="↑/↓=Rolar | F=Favoritar | ESC=Voltar",
        )
    except AbrirMenuOutroModo:
        _tratar_f12(df_erbs)