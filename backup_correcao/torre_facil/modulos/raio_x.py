"""Raio-X de cidade e de estado.
Easter egg F12: aceita abrir o menu do outro modo por cima destas telas.
"""
from __future__ import annotations

import re

import pandas as pd

from ..dicionarios import obter_opcoes_uf
from ..estado import AbrirMenuOutroModo
from ..painel import (
    filtrar_municipios_exatos,
    painel_interativo_municipio,
    diagnosticar_melhor_cobertura,
)
from ..texto import formatar_lista_tec
from ..tui.cores import CAIXA_TEXTO
from ..tui.janelas import (
    criar_item_tui,
    formulario_tui,
    alerta_tui,
    caixa_notificacao_tui,
)
from ..tui.navegador import (
    navegador_tui,
    mostrar_podio_completo_tui,
    obter_estilo_posicao,
)


# =========================================================================
# 1. Raio-X de cidade
# =========================================================================

def raio_x_cidade(df_erbs) -> None:
    """Raio-X por cidade. Aceita F12 para abrir o menu do outro modo."""

    # ✅ CORREÇÃO: Gera lista de UFs diretamente do DataFrame
    def obter_ufs():
        ufs = sorted(df_erbs["UF"].dropna().unique())
        return [("", "QUALQUER UF (BRASIL)")] + [(uf, uf) for uf in ufs]

    def sugerir_cidades(vals):
        uf = vals.get("uf", "")
        if uf and uf != "QUALQUER UF (BRASIL)":
            sub = df_erbs[df_erbs["UF"] == uf]
        else:
            sub = df_erbs
        return [(c, c) for c in sorted(sub["MUNICIPIO_LIMPO"].unique())]

    try:
        res = formulario_tui(
            modulo="PESQUISA DE CIDADE",
            titulo_janela="1. RAIO-X DE CIDADE E BAIRROS",
            campos=[
                {
                    "nome": "uf", "rotulo": "Estado / UF", "tipo": "droplist",
                    "largura": 28, "padrao": "",
                    "opcoes": obter_ufs(),  # ✅ CORREÇÃO: usa função local
                    "dica": "Use ←/→ ou ESPAÇO/F2 para abrir a Droplist de UFs",
                },
                {
                    "nome": "municipio", "rotulo": "Nome do Município",
                    "tipo": "combobox", "largura": 34,
                    "opcoes": sugerir_cidades,
                    "dica": "Digite o nome OU tecle [F2] p/ abrir a Droplist de Cidades",
                },
            ],
            instrucoes_topo=[
                "Selecione a UF e informe/escolha o Município na Droplist [F2]:"
            ],
        )
    except AbrirMenuOutroModo:
        from ..main import _abrir_menu_do_outro_modo
        _abrir_menu_do_outro_modo(df_erbs, "cache", modo_atual="analista")
        return

    if not res or not res["municipio"]:
        return

    df_base = (df_erbs[df_erbs["UF"] == res["uf"]].copy()
               if res["uf"] else df_erbs)

    df_cid = filtrar_municipios_exatos(df_base, res["municipio"])
    if df_cid.empty:
        return

    ufs = sorted(df_cid["UF"].unique())
    if len(ufs) > 1:
        botoes = [
            (str(i + 1),
             f"{u} ({df_cid[df_cid['UF'] == u]['ID_ERB'].nunique()} ERBs)",
             u)
            for i, u in enumerate(ufs)
        ]
        try:
            uf_esc = caixa_notificacao_tui(
                modulo="MUNICÍPIO HOMÔNIMO",
                titulo=f"MÚLTIPLOS ESTADOS PARA '{res['municipio'][:22]}'",
                linhas_mensagem=[
                    f"O município '{res['municipio']}' existe em mais de um estado.",
                    "Selecione abaixo qual UF deseja inspecionar:",
                ],
                botoes=botoes,
            )
        except AbrirMenuOutroModo:
            from ..main import _abrir_menu_do_outro_modo
            _abrir_menu_do_outro_modo(df_erbs, "cache", modo_atual="analista")
            return
        if uf_esc in ufs:
            df_cid = df_cid[df_cid["UF"] == uf_esc]
        else:
            return

    for (uf, mun), grp_cid in df_cid.groupby(["UF", "MUNICIPIO"]):
        nome_limpo = re.sub(r"\s*-\s*[A-Za-z]{2}$", "", mun).upper()
        try:
            painel_interativo_municipio(grp_cid, nome_limpo, uf)
        except AbrirMenuOutroModo:
            from ..main import _abrir_menu_do_outro_modo
            _abrir_menu_do_outro_modo(df_erbs, "cache", modo_atual="analista")
            return


# =========================================================================
# 2. Raio-X de estado
# =========================================================================

def raio_x_estado(df_erbs) -> None:
    """Raio-X por UF. Aceita F12."""

    # ✅ CORREÇÃO: Gera lista de UFs diretamente do DataFrame
    def obter_ufs_estado():
        ufs = sorted(df_erbs["UF"].dropna().unique())
        return [("", "BRASIL INTEIRO (CONSOLIDADO)")] + [(uf, uf) for uf in ufs]

    try:
        res = formulario_tui(
            modulo="RAIO-X POR ESTADO",
            titulo_janela="2. RANKING / RAIO-X DE OPERADORAS POR ESTADO",
            campos=[
                {
                    "nome": "uf", "rotulo": "Unidade Federativa (UF)",
                    "tipo": "droplist", "largura": 30, "padrao": "",
                    "opcoes": obter_ufs_estado(),  # ✅ CORREÇÃO: usa função local
                    "dica": "Use ←/→ ou ESPAÇO/F2 para escolher a UF",
                }
            ],
            instrucoes_topo=[
                "Selecione o Estado na Droplist ou mantenha Brasil Inteiro:"
            ],
        )
    except AbrirMenuOutroModo:
        from ..main import _abrir_menu_do_outro_modo
        _abrir_menu_do_outro_modo(df_erbs, "cache", modo_atual="analista")
        return

    if res is None:
        return

    uf_input = res["uf"]
    df_f = (df_erbs[df_erbs["UF"] == uf_input].copy()
            if uf_input else df_erbs.copy())

    if df_f.empty:
        alerta_tui(
            "ESTADO NÃO ENCONTRADO",
            "UF INVÁLIDA OU SEM REGISTROS",
            [f"Nenhum dado localizado para a UF '{uf_input}'."],
        )
        return

    escopo = f"ESTADO: {uf_input}" if uf_input else "BRASIL (CONSOLIDADO NACIONAL)"
    total_mun = df_f[["UF", "MUNICIPIO_NORM"]].drop_duplicates().shape[0]
    total_erbs = df_f["ID_ERB"].nunique()

    linhas = []
    for op, grp in df_f.groupby("OPERADORA"):
        erbs_op = grp["NUM_ESTACAO"].nunique()
        mun_op = grp[["UF", "MUNICIPIO_NORM"]].drop_duplicates().shape[0]
        perc_mun = (mun_op / total_mun * 100) if total_mun > 0 else 0
        erbs_5g = grp[grp["TECS_RAW"].str.contains("5", na=False)]["NUM_ESTACAO"].nunique()
        erbs_4g = grp[grp["TECS_RAW"].str.contains("L", na=False)]["NUM_ESTACAO"].nunique()
        erbs_3g = grp[grp["TECS_RAW"].str.contains("H", na=False)]["NUM_ESTACAO"].nunique()
        tecs_op = formatar_lista_tec(",".join(grp["TECS_RAW"]).split(","))
        linhas.append({
            "OPERADORA": op,
            "TOTAL ERBS": erbs_op,
            "SHARE ERBS": f"{(erbs_op / total_erbs * 100):.1f}%",
            "MUNICÍPIOS": f"{mun_op}/{total_mun} ({perc_mun:.1f}%)",
            "5G (5)": erbs_5g,
            "4G (L)": erbs_4g,
            "3G (H)": erbs_3g,
            "TECS ATIVAS": tecs_op,
        })

    df_rank = (pd.DataFrame(linhas)
               .sort_values(by="TOTAL ERBS", ascending=False)
               .reset_index(drop=True))

    cab = (f"   {'POSIÇÃO':<12} {'OPERADORA':<12} {'TOTAL ERBS':^12} "
           f"{'SHARE':^9} {'MUNICÍPIOS':^18} {'5G':^6} {'4G':^6} "
           f"{'3G':^6} {'TECS'}")

    itens = []
    for idx, row in df_rank.iterrows():
        pos = idx + 1
        cor, icone, _ = obter_estilo_posicao(pos)
        linha = (
            f"{icone:<12} {row['OPERADORA']:<12} {row['TOTAL ERBS']:^12} "
            f"{row['SHARE ERBS']:^9} {row['MUNICÍPIOS']:^18} "
            f"{row['5G (5)']:^6} {row['4G (L)']:^6} "
            f"{row['3G (H)']:^6} {row['TECS ATIVAS']}"
        )
        itens.append(criar_item_tui(
            linha, cor, "esq", selecionavel=True, dados=row["OPERADORA"],
        ))

    _, linhas_diag = diagnosticar_melhor_cobertura(df_f)

    while True:
        try:
            acao, dados, _, _ = navegador_tui(
                modulo=f"RAIO-X ({escopo})",
                titulo_janela=(
                    f"RAIO-X DE INFRAESTRUTURA — {escopo} "
                    f"({total_erbs:,} ERBs)".replace(",", ".")
                ),
                itens_conteudo=itens,
                subcabecalho_fixo=linhas_diag,
                colunas_fixas_tabela=cab,
                comandos_rodape=[
                    "[P] Pódio completo   |   [ESC/0] Voltar",
                ],
                teclas_rapidas={"P"},
                dica_teclas=("↑/↓=Navegar | PgUp/PgDn=Página | "
                             "P=Pódio | ESC/0/ENTER=Voltar"),
            )
        except AbrirMenuOutroModo:
            from ..main import _abrir_menu_do_outro_modo
            _abrir_menu_do_outro_modo(df_erbs, "cache", modo_atual="analista")
            continue

        if acao == "KEY" and dados == "P":
            mostrar_podio_completo_tui()
            continue

        break