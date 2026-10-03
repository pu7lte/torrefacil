"""Consulta Rápida (modo loja).

Entrada: CEP, endereço livre, ou apenas cidade/bairro.
Saída: ERBs próximas, resumo por operadora, recomendação.

Regra de exibição do resumo:
    - CEP geral (termina em -000)        → CIDADE - UF
    - CEP específico (de rua/bairro)     → BAIRRO / CIDADE - UF
    - CEP espalhado por várias cidades   → CIDADE - UF  (+N cidade(s))
    - Endereço livre                     → BAIRRO / CIDADE - UF

Easter egg F12: aceita abrir o menu do outro modo por cima desta tela,
mantendo o estado atual da consulta.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd

from ..config_usuario import adicionar_favorito
from ..estado import AbrirMenuOutroModo
from ..texto import normalizar_texto
from ..tui.cores import (
    CAIXA_TEXTO, CAIXA_TITULO, CAIXA_CIANO,
    CAIXA_VERDE, CAIXA_AMARELO, BARRA_VERDE, BARRA_ALERTA,
)
from ..tui.janelas import (
    criar_item_tui, formulario_tui, alerta_tui, caixa_notificacao_tui,
)
from ..tui.navegador import navegador_tui
from . import _geo

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Modos de interpretação de consulta
_MODO_VAZIO = "vazio"
_MODO_CEP = "cep"
_MODO_TEXTO = "texto"

# Cores por nota de cobertura
_CORES_NOTA: dict[str, str] = {
    "otimo": CAIXA_VERDE,
    "bom": CAIXA_CIANO,
    "fraco": CAIXA_AMARELO,
    "sem": CAIXA_TEXTO,
}

# Raio padrão de busca
_RAIO_PADRAO_KM = 3.0


# ---------------------------------------------------------------------------
# Helpers de formatação
# ---------------------------------------------------------------------------

def _formatar_distancia(dist_km: float) -> str:
    """Formata distância em km ou metros.

    Args:
        dist_km: Distância em quilômetros.

    Returns:
        String formatada (ex: "1.5 km", "850 m").

    Examples:
        >>> _formatar_distancia(1.5)
        '1.5 km'
        >>> _formatar_distancia(0.5)
        '500 m'
    """
    if dist_km < 1.0:
        return f"{int(dist_km * 1000)} m"
    return f"{dist_km:.1f} km"


def _formatar_distancia_detalhe(dist_km: float) -> str:
    """Formata distância com mais precisão para tela de detalhe.

    Args:
        dist_km: Distância em quilômetros.

    Returns:
        String formatada (ex: "1.50 km", "850 m").

    Examples:
        >>> _formatar_distancia_detalhe(1.5)
        '1.50 km'
        >>> _formatar_distancia_detalhe(0.5)
        '500 m'
    """
    if dist_km < 1.0:
        return f"{int(dist_km * 1000)} m"
    return f"{dist_km:.2f} km"


# ---------------------------------------------------------------------------
# Interpretação da consulta
# ---------------------------------------------------------------------------

def _extrair_cep(texto: str) -> str | None:
    """Extrai CEP (8 dígitos) de um texto livre.

    Args:
        texto: Texto a analisar.

    Returns:
        CEP com 8 dígitos, ou None se não encontrado.

    Examples:
        >>> _extrair_cep("CEP 59020-000")
        '59020000'
        >>> _extrair_cep("Rua X, 123") is None
        True
    """
    digitos = re.sub(r"\D", "", texto)
    if len(digitos) == 8:
        return digitos
    return None


def _formatar_cep(cep: str) -> str:
    """Formata 8 dígitos como 00000-000.

    Args:
        cep: CEP com 8 dígitos.

    Returns:
        CEP formatado (ex: "59020-000").

    Examples:
        >>> _formatar_cep("59020000")
        '59020-000'
    """
    cep = re.sub(r"\D", "", cep)
    if len(cep) == 8:
        return f"{cep[:5]}-{cep[5:]}"
    return cep


def _cep_e_geral(cep: str) -> bool:
    """True quando o CEP termina em '000' — CEP do município inteiro.

    Args:
        cep: CEP com 8 dígitos.

    Returns:
        True se CEP é geral, False caso contrário.

    Examples:
        >>> _cep_e_geral("59020000")
        True
        >>> _cep_e_geral("59020123")
        False
    """
    cep = re.sub(r"\D", "", cep)
    return len(cep) == 8 and cep.endswith("000")


def _cidade_principal(df_local: pd.DataFrame) -> tuple[str, str, str, int, int]:
    """Devolve (bairro, cidade, uf, qtd_cidades, qtd_bairros).

    Args:
        df_local: DataFrame com resultados da consulta.

    Returns:
        Tupla com informações da cidade principal.
    """
    if df_local.empty:
        return "", "", "", 0, 0

    cidades = df_local["MUNICIPIO_LIMPO"].dropna().astype(str)
    cidade = cidades.value_counts().idxmax() if not cidades.empty else ""
    qtd_cidades = cidades.nunique() if not cidades.empty else 0

    ufs = df_local["UF"].dropna().astype(str)
    uf = ufs.value_counts().idxmax() if not ufs.empty else ""

    if cidade:
        sub = df_local[df_local["MUNICIPIO_LIMPO"] == cidade]
    else:
        sub = df_local

    bairros = sub["BAIRRO"].dropna().astype(str)
    bairros = bairros[bairros.str.strip() != ""]
    bairro = bairros.value_counts().idxmax() if not bairros.empty else ""
    qtd_bairros = bairros.nunique() if not bairros.empty else 0

    return bairro, cidade, uf, qtd_cidades, qtd_bairros


def _montar_resumo(
    cidade: str,
    uf: str,
    bairro: str = "",
    qtd_cidades: int = 1,
    incluir_bairro: bool = False,
    prefixo: str = "",
) -> str:
    """Monta a string de resumo.

    Args:
        cidade: Nome da cidade.
        uf: Sigla da UF.
        bairro: Nome do bairro (opcional).
        qtd_cidades: Número de cidades encontradas.
        incluir_bairro: Se True, inclui bairro no resumo.
        prefixo: Prefixo do resumo (ex: "CEP 59020-000").

    Returns:
        String de resumo formatada.

    Examples:
        >>> _montar_resumo("NATAL", "RN", prefixo="CEP 59020-000")
        'CEP 59020-000 — NATAL - RN'
    """
    partes = []
    if prefixo:
        partes.append(prefixo)

    local = []
    if incluir_bairro and bairro:
        local.append(bairro)
    if cidade:
        local.append(cidade)

    local_txt = " / ".join(local)
    if uf:
        local_txt = f"{local_txt} - {uf}" if local_txt else uf

    if local_txt:
        partes.append(local_txt)

    resumo = " — ".join(partes)

    if qtd_cidades > 1:
        resumo += f"  (+{qtd_cidades - 1} cidade(s))"

    return resumo


def _interpretar_consulta(
    df: pd.DataFrame, texto: str
) -> tuple[pd.DataFrame, str, float | None, float | None, str]:
    """Retorna (df_resultado, modo, lat, lon, resumo).

    Args:
        df: DataFrame completo de ERBs.
        texto: Texto da consulta (CEP ou endereço).

    Returns:
        Tupla com DataFrame filtrado, modo, coordenadas e resumo.
    """
    texto = (texto or "").strip()
    if not texto:
        return df.head(0), _MODO_VAZIO, None, None, "consulta vazia"

    # 1) CEP
    cep = _extrair_cep(texto)
    if cep and "CEP" in df.columns:
        df_cep = df[df["CEP"] == cep]
        if df_cep.empty:
            return (
                df.head(0), _MODO_CEP, None, None,
                f"CEP {_formatar_cep(cep)} não encontrado na base"
            )

        bairro, cidade, uf, qtd_cidades, _ = _cidade_principal(df_cep)
        incluir_bairro = not _cep_e_geral(cep)
        resumo = _montar_resumo(
            cidade, uf, bairro,
            qtd_cidades=qtd_cidades,
            incluir_bairro=incluir_bairro,
            prefixo=f"CEP {_formatar_cep(cep)}",
        )

        lat = df_cep["LAT_NUM"].dropna().median()
        lon = df_cep["LON_NUM"].dropna().median()

        if pd.isna(lat) or pd.isna(lon):
            return df_cep, _MODO_CEP, None, None, resumo

        return df_cep, _MODO_CEP, float(lat), float(lon), resumo

    # 2) Texto livre — sempre com bairro
    termo = normalizar_texto(texto)
    mask = df["ENDERECO_BUSCA"].str.contains(re.escape(termo), na=False)
    df_res = df[mask]

    if df_res.empty:
        return (
            df.head(0), _MODO_TEXTO, None, None,
            f"nenhum resultado para '{texto}'"
        )

    bairro, cidade, uf, qtd_cidades, _ = _cidade_principal(df_res)
    resumo = _montar_resumo(
        cidade, uf, bairro,
        qtd_cidades=qtd_cidades,
        incluir_bairro=True,
        prefixo=f"'{texto}'",
    )

    lat = df_res["LAT_NUM"].dropna().median()
    lon = df_res["LON_NUM"].dropna().median()

    if pd.isna(lat) or pd.isna(lon):
        return (
            df_res, _MODO_TEXTO, None, None,
            f"{resumo}  ({len(df_res)} ERBs, sem GPS)"
        )

    return df_res, _MODO_TEXTO, float(lat), float(lon), resumo


# ---------------------------------------------------------------------------
# Formatação do resumo por operadora
# ---------------------------------------------------------------------------

def _montar_linhas_resumo(
    df_resumo: pd.DataFrame, raio_km: float
) -> list[dict[str, Any]]:
    """Monta uma linha por operadora para exibição.

    Args:
        df_resumo: DataFrame com resumo por operadora.
        raio_km: Raio de busca em km.

    Returns:
        Lista de itens para ``navegador_tui``.
    """
    itens: list[dict[str, Any]] = []

    # Iteração vetorizada (mais rápida que iterrows)
    operadoras = df_resumo["OPERADORA"].tolist()
    dist_min = df_resumo["DIST_MIN"].tolist()
    erbs_count = df_resumo["ERBS"].tolist()
    tecnologias = df_resumo["TECNOLOGIAS"].fillna("-").tolist()
    tipo5g = df_resumo["TEC5G_TIPO"].fillna("-").tolist()
    faixas = df_resumo["FAIXAS"].fillna("-").tolist()

    # Converte cada linha para dict para passar ao _geo.nota_cobertura
    rows_dict = df_resumo.to_dict("records")

    for i, row in enumerate(rows_dict):
        nota, chave = _geo.nota_cobertura(row)
        cor = _CORES_NOTA.get(chave, CAIXA_TEXTO)

        dist_txt = _formatar_distancia(dist_min[i])
        op = operadoras[i][:10]
        erbs = erbs_count[i]
        tecs = tecnologias[i]
        tipo = tipo5g[i]
        faixa = faixas[i]

        linha = (
            f"{op:<10} {nota:<10} {erbs:>3} torre(s)  │  "
            f"mais próxima: {dist_txt:>8}  │  "
            f"tecnologias: {tecs:<10}  │  5G: {tipo:<7}  │  "
            f"faixas: {faixa}"
        )

        itens.append(criar_item_tui(
            linha, cor, "esq",
            selecionavel=True,
            dados=row,
        ))

    return itens


def _recomendar(df_resumo: pd.DataFrame) -> tuple[str | None, str]:
    """Devolve (operadora_top, texto_recomendacao).

    Args:
        df_resumo: DataFrame com resumo por operadora.

    Returns:
        Tupla com operadora recomendada e texto da recomendação.
    """
    if df_resumo.empty:
        return None, "Sem cobertura registrada neste endereço."

    top = df_resumo.iloc[0]
    op = top["OPERADORA"]
    nota, _ = _geo.nota_cobertura(top.to_dict())

    partes = [f"Recomendada: {op} ({nota})"]

    if top["TEM_5G"]:
        partes.append("tem 5G")
    if top["TEM_4G"]:
        partes.append("tem 4G")

    partes.append(f"{top['ERBS']} torre(s) em até {top['DIST_MIN']:.1f} km")

    return op, " — ".join(partes)


# ---------------------------------------------------------------------------
# Tela de torres por operadora
# ---------------------------------------------------------------------------

def _mostrar_torres_da_operadora(
    df_sub: pd.DataFrame,
    operadora: str,
    resumo: str,
    endereco: str,
) -> None:
    """Lista as torres de uma operadora específica.

    Args:
        df_sub: DataFrame com torres da operadora.
        operadora: Nome da operadora.
        resumo: Resumo do endereço consultado.
        endereco: Endereço original da consulta.

    Raises:
        AbrirMenuOutroModo: Se usuário pressionar F12.
    """
    itens: list[dict[str, Any]] = []

    # Iteração vetorizada
    dist_km = df_sub["DIST_KM"].tolist()
    bairros = df_sub["BAIRRO"].fillna("").astype(str).tolist()
    enderecos = df_sub["ENDERECO"].fillna("").astype(str).tolist()
    tecs = df_sub["TECNOLOGIA"].fillna("").tolist()
    tipo5g = df_sub["TEC5G_TIPO"].fillna("-").tolist()
    faixas = df_sub["FAIXA_NOMINAL"].fillna("-").tolist()
    rows_dict = df_sub.to_dict("records")

    for i, row in enumerate(rows_dict):
        dist = _formatar_distancia_detalhe(dist_km[i])
        bairro = bairros[i][:20]
        end = enderecos[i][:40]
        tec = tecs[i]
        tipo = tipo5g[i]
        faixa = faixas[i]

        linha = (
            f"{dist:>7}  │  {bairro:<20}  │  {tec:<10}  │  "
            f"5G: {tipo:<7}  │  {faixa:<14}  │  {end}"
        )

        itens.append(criar_item_tui(
            linha, CAIXA_TEXTO, "esq",
            selecionavel=True, dados=row,
        ))

    cab = (
        f"   {'DIST':>7}  │  {'BAIRRO':<20}  │  {'TECS':<10}  │  "
        f"{'5G':<11}  │  {'FAIXAS':<14}  │  ENDEREÇO"
    )

    try:
        navegador_tui(
            modulo="TORRES",
            titulo_janela=(
                f"TORRES DA {operadora} — {len(itens)} encontrada(s)  │  {resumo}"
            ),
            itens_conteudo=itens,
            colunas_fixas_tabela=cab,
            comandos_rodape=["[ESC] Voltar"],
            dica_teclas="↑/↓=Mover | ESC=Voltar",
        )
    except AbrirMenuOutroModo:
        from ..main import _abrir_menu_do_outro_modo
        _abrir_menu_do_outro_modo(df_sub, "cache", modo_atual="loja")


# ---------------------------------------------------------------------------
# Tela principal
# ---------------------------------------------------------------------------

def consulta_rapida(df_erbs: pd.DataFrame, endereco_inicial: str = "") -> None:
    """Ponto de entrada do módulo.

    Aceita ``endereco_inicial`` para ser pré-preenchido (pelos favoritos).
    F12 → abre o menu do outro modo por cima, sem perder o estado atual.

    Args:
        df_erbs: DataFrame completo de ERBs.
        endereco_inicial: Endereço pré-preenchido (opcional).

    Raises:
        AbrirMenuOutroModo: Se usuário pressionar F12.
    """
    res = formulario_tui(
        modulo="CONSULTA RÁPIDA",
        titulo_janela="CONSULTA RÁPIDA — COBERTURA POR ENDEREÇO",
        campos=[
            {
                "nome": "endereco",
                "rotulo": "Endereço / CEP",
                "tipo": "texto",
                "largura": 46,
                "padrao": endereco_inicial,
                "max_chars": 90,
                "maiusculo": False,
                "dica": "Ex.: 59020000  |  Rua X, 123 Natal  |  Ponta Negra, Natal-RN",
            },
            {
                "nome": "raio",
                "rotulo": "Raio de busca",
                "tipo": "droplist",
                "largura": 20,
                "padrao": str(_RAIO_PADRAO_KM),
                "opcoes": [
                    ("1.0", "1 km (vizinhança)"),
                    ("3.0", "3 km (bairro)"),
                    ("5.0", "5 km (região)"),
                    ("10.0", "10 km (cidade)"),
                ],
            },
        ],
        instrucoes_topo=[
            "Digite um CEP (8 dígitos) ou um endereço livre.",
            "O sistema busca ERBs próximas e resume a cobertura.",
        ],
    )

    if not res or not res.get("endereco"):
        return

    endereco = res["endereco"]

    try:
        raio_km = float(res.get("raio", str(_RAIO_PADRAO_KM)))
    except ValueError:
        raio_km = _RAIO_PADRAO_KM

    df_res, modo, lat, lon, resumo = _interpretar_consulta(df_erbs, endereco)

    if modo == _MODO_VAZIO or df_res.empty or lat is None:
        alerta_tui(
            "CONSULTA RÁPIDA",
            "NÃO ENCONTRADO",
            [
                "Não consegui identificar um endereço válido.",
                "",
                f"Consulta: '{endereco}'",
                "",
                "Tente:",
                "  • CEP com 8 dígitos (ex.: 59020000)",
                "  • Rua + cidade (ex.: Rua X Natal)",
                "  • Bairro + cidade (ex.: Ponta Negra Natal)",
            ],
            cor_titulo=BARRA_ALERTA,
        )
        return

    df_prox = _geo.erbs_proximas(df_erbs, lat, lon, raio_km=raio_km)

    if df_prox.empty:
        alerta_tui(
            "CONSULTA RÁPIDA",
            "SEM TORRES PRÓXIMAS",
            [
                f"O endereço foi localizado, mas não há ERBs dentro de "
                f"{raio_km:.0f} km.",
                "",
                "Tente aumentar o raio de busca na próxima consulta.",
            ],
        )
        return

    df_resumo = _geo.resumo_por_operadora(df_prox)
    op_top, texto_rec = _recomendar(df_resumo)

    while True:
        cab_resumo = (
            f"   {'OPERADORA':<10} {'NOTA':<10} {'ERBs':>4}       "
            f"{'DISTÂNCIA':<14}  {'TECNOLOGIAS':<12}  {'5G TIPO':<8}  FAIXAS"
        )

        itens = _montar_linhas_resumo(df_resumo, raio_km)

        info = [
            f"Local: {resumo}",
            f"Coordenadas: {lat:.6f}, {lon:.6f}   │   "
            f"Raio: {raio_km:.0f} km   │   "
            f"{len(df_prox)} torre(s) encontrada(s)",
            f"⭐ {texto_rec}",
        ]

        try:
            acao, dados, _, _ = navegador_tui(
                modulo="CONSULTA RÁPIDA",
                titulo_janela=f"RESULTADO DA CONSULTA — {resumo}",
                itens_conteudo=itens,
                subcabecalho_fixo=info,
                colunas_fixas_tabela=cab_resumo,
                comandos_rodape=[
                    "[ENTER] Ver torres desta operadora   |   "
                    "[F] Adicionar endereço aos favoritos   |   "
                    "[N] Nova consulta   |   [ESC] Voltar",
                ],
                teclas_rapidas={"F", "N"},
                dica_teclas=(
                    "↑/↓=Mover | ENTER=Ver torres | F=Favoritar | "
                    "N=Nova consulta | ESC=Voltar"
                ),
            )
        except AbrirMenuOutroModo:
            # F12: abre o menu do outro modo em cima, sem perder o estado
            from ..main import _abrir_menu_do_outro_modo
            _abrir_menu_do_outro_modo(df_erbs, "cache", modo_atual="loja")
            continue

        if acao == "SELECT" and isinstance(dados, dict):
            op = dados.get("OPERADORA")
            sub = df_prox[df_prox["OPERADORA"] == op]
            _mostrar_torres_da_operadora(sub, op, resumo, endereco)

        elif acao == "KEY" and dados == "F":
            ok = adicionar_favorito(endereco, apelido=resumo[:60])
            if ok:
                alerta_tui(
                    "FAVORITOS", "ENDEREÇO SALVO",
                    [
                        "O endereço foi adicionado aos favoritos.",
                        "Próxima vez, abra pelo menu 3 (Favoritos).",
                    ],
                    cor_titulo=BARRA_VERDE,
                )
            else:
                alerta_tui(
                    "FAVORITOS", "FALHA AO SALVAR",
                    ["Não foi possível salvar o favorito."],
                )

        elif acao == "KEY" and dados == "N":
            return consulta_rapida(df_erbs, endereco_inicial="")

        else:
            return