"""Script completo de testes para o projeto Torre Fácil ERP.

Verifica:
1. Sintaxe de todos os arquivos .py (compilação)
2. Importação de cada módulo
3. Existência de funções/classes principais
4. Funcionalidades básicas (paleta, texto, etc.)
5. Gera relatório detalhado com cores ANSI

Uso:
    python testar_tudo.py
"""
import sys
import os
import importlib
import traceback
from pathlib import Path
from typing import List, Tuple, Dict

# Cores ANSI para relatório
VERDE = "\033[92m"
VERMELHO = "\033[91m"
AMARELO = "\033[93m"
CIANO = "\033[96m"
NEGRITO = "\033[1m"
RESET = "\033[0m"

PROJETO = Path("torre_facil")

# Resultados
resultados = {
    "sintaxe": [],
    "import": [],
    "funcoes": [],
    "funcional": [],
}


def log_ok(msg: str) -> None:
    print(f"  {VERDE}✓{RESET} {msg}")


def log_erro(msg: str) -> None:
    print(f"  {VERMELHO}✗{RESET} {msg}")


def log_warn(msg: str) -> None:
    print(f"  {AMARELO}⚠{RESET} {msg}")


def log_info(msg: str) -> None:
    print(f"  {CIANO}ℹ{RESET} {msg}")


# =========================================================================
# TESTE 1: Sintaxe (compilação)
# =========================================================================

def testar_sintaxe() -> None:
    """Testa se todos os arquivos .py compilam sem erro de sintaxe."""
    print(f"\n{NEGRITO}{'=' * 70}")
    print(f"TESTE 1: SINTAXE (compilação de todos os .py)")
    print(f"{'=' * 70}{RESET}\n")

    arquivos = sorted(PROJETO.rglob("*.py"))
    erros = 0

    for arquivo in arquivos:
        try:
            with open(arquivo, "r", encoding="utf-8") as f:
                codigo = f.read()
            compile(codigo, str(arquivo), "exec")
            log_ok(f"{arquivo.relative_to(PROJETO.parent)}")
            resultados["sintaxe"].append((str(arquivo), True, None))
        except SyntaxError as e:
            log_erro(f"{arquivo.relative_to(PROJETO.parent)}: {e}")
            resultados["sintaxe"].append((str(arquivo), False, str(e)))
            erros += 1
        except Exception as e:
            log_erro(f"{arquivo.relative_to(PROJETO.parent)}: {type(e).__name__}: {e}")
            resultados["sintaxe"].append((str(arquivo), False, str(e)))
            erros += 1

    print(f"\n  Total: {len(arquivos)} arquivos | {VERDE}{len(arquivos) - erros} OK{RESET} | "
          f"{VERMELHO}{erros} ERROS{RESET}")


# =========================================================================
# TESTE 2: Importação de módulos
# =========================================================================

def testar_imports() -> None:
    """Testa a importação de cada módulo do projeto."""
    print(f"\n{NEGRITO}{'=' * 70}")
    print(f"TESTE 2: IMPORTAÇÃO DE MÓDULOS")
    print(f"{'=' * 70}{RESET}\n")

    # Adiciona o diretório pai ao sys.path
    sys.path.insert(0, str(PROJETO.parent))

    modulos = [
        "torre_facil",
        "torre_facil.estado",
        "torre_facil.config",
        "torre_facil.texto",
        "torre_facil.dicionarios",
        "torre_facil.config_usuario",
        "torre_facil.tui",
        "torre_facil.tui.cores",
        "torre_facil.tui.motor",
        "torre_facil.tui.teclado",
        "torre_facil.tui.janelas",
        "torre_facil.tui.menus",
        "torre_facil.tui.menu_barra",
        "torre_facil.tui.navegador",
        "torre_facil.painel",
        "torre_facil.pesquisa_global",
        "torre_facil.main",
    ]

    erros = 0
    for modulo in modulos:
        try:
            mod = importlib.import_module(modulo)
            log_ok(f"{modulo}")
            resultados["import"].append((modulo, True, None))
        except Exception as e:
            log_erro(f"{modulo}: {type(e).__name__}: {e}")
            resultados["import"].append((modulo, False, f"{type(e).__name__}: {e}"))
            erros += 1

    print(f"\n  Total: {len(modulos)} módulos | {VERDE}{len(modulos) - erros} OK{RESET} | "
          f"{VERMELHO}{erros} ERROS{RESET}")


# =========================================================================
# TESTE 3: Funções e classes principais
# =========================================================================

def testar_funcoes() -> None:
    """Verifica se as funções/classes principais existem."""
    print(f"\n{NEGRITO}{'=' * 70}")
    print(f"TESTE 3: FUNÇÕES E CLASSES PRINCIPAIS")
    print(f"{'=' * 70}{RESET}\n")

    verificacoes = [
        # (módulo, nome, tipo)
        ("torre_facil.estado", "INFO", "variavel"),
        ("torre_facil.estado", "EstadoSistema", "classe"),
        ("torre_facil.estado", "definir_base_global", "funcao"),
        ("torre_facil.estado", "obter_base_global", "funcao"),
        ("torre_facil.estado", "AbrirMenuOutroModo", "classe"),
        ("torre_facil.config", "VERSAO_CACHE", "variavel"),
        ("torre_facil.config", "DIAS_SEMANA", "variavel"),
        ("torre_facil.config", "URL_ANATEL", "variavel"),
        ("torre_facil.texto", "normalizar_texto", "funcao"),
        ("torre_facil.texto", "formatar_lista_tec", "funcao"),
        ("torre_facil.texto", "RE_NAO_ALFANUM", "variavel"),
        ("torre_facil.tui.cores", "PALETAS", "variavel"),
        ("torre_facil.tui.cores", "ORDEM_PALETAS", "variavel"),
        ("torre_facil.tui.cores", "aplicar_paleta", "funcao"),
        ("torre_facil.tui.cores", "RESET", "variavel"),
        ("torre_facil.tui.cores", "CIANO", "variavel"),
        ("torre_facil.tui.cores", "NEGRITO", "variavel"),
        ("torre_facil.tui.motor", "ajustar_texto_puro", "funcao"),
        ("torre_facil.tui.motor", "desenhar_desktop_base", "funcao"),
        ("torre_facil.tui.motor", "sobrepor_janela_no_canvas", "funcao"),
        ("torre_facil.tui.motor", "RE_ANSI", "variavel"),
        ("torre_facil.tui.teclado", "ler_tecla", "funcao"),
        ("torre_facil.tui.teclado", "decodificar_sequencia_escape", "funcao"),
        ("torre_facil.tui.janelas", "criar_item_tui", "funcao"),
        ("torre_facil.tui.janelas", "formulario_tui", "funcao"),
        ("torre_facil.tui.janelas", "caixa_notificacao_tui", "funcao"),
        ("torre_facil.tui.janelas", "alerta_tui", "funcao"),
        ("torre_facil.tui.janelas", "tela_logo", "funcao"),
        ("torre_facil.tui.menus", "menu_dropdown_ancorado_tui", "funcao"),
        ("torre_facil.tui.menus", "executar_acao_menu_comum", "funcao"),
        ("torre_facil.tui.menu_barra", "montar_menus", "funcao"),
        ("torre_facil.tui.menu_barra", "renderizar_menu_superior_fixo", "funcao"),
        ("torre_facil.tui.menu_barra", "ACOES_MENU_PARA_TECLA", "variavel"),
        ("torre_facil.tui.menu_barra", "ACOES_MENU_BASICAS", "variavel"),
        ("torre_facil.tui.navegador", "navegador_tui", "funcao"),
        ("torre_facil.tui.navegador", "mostrar_podio_completo_tui", "funcao"),
        ("torre_facil.tui.navegador", "gerar_barra_sinal", "funcao"),
        ("torre_facil.painel", "painel_interativo_municipio", "funcao"),
        ("torre_facil.painel", "filtrar_municipios_exatos", "funcao"),
        ("torre_facil.painel", "dataframe_para_itens_tui", "funcao"),
        ("torre_facil.painel", "salvar_csv_tui", "funcao"),
        ("torre_facil.painel", "calcular_metricas_operadoras", "funcao"),
        ("torre_facil.pesquisa_global", "pesquisa_global_tui", "funcao"),
        ("torre_facil.pesquisa_global", "invalidar_cache_pesquisa", "funcao"),
        ("torre_facil.main", "menu_principal", "funcao"),
    ]

    erros = 0
    for modulo, nome, tipo in verificacoes:
        try:
            mod = importlib.import_module(modulo)
            obj = getattr(mod, nome, None)
            if obj is None:
                log_erro(f"{modulo}.{nome} ({tipo}) → NÃO EXISTE")
                resultados["funcoes"].append((f"{modulo}.{nome}", False, "Não existe"))
                erros += 1
            else:
                log_ok(f"{modulo}.{nome} ({tipo})")
                resultados["funcoes"].append((f"{modulo}.{nome}", True, None))
        except Exception as e:
            log_erro(f"{modulo}.{nome}: {type(e).__name__}: {e}")
            resultados["funcoes"].append((f"{modulo}.{nome}", False, str(e)))
            erros += 1

    print(f"\n  Total: {len(verificacoes)} verificações | "
          f"{VERDE}{len(verificacoes) - erros} OK{RESET} | "
          f"{VERMELHO}{erros} ERROS{RESET}")


# =========================================================================
# TESTE 4: Funcionalidades básicas
# =========================================================================

def testar_funcional() -> None:
    """Testa funcionalidades básicas sem precisar de base de dados."""
    print(f"\n{NEGRITO}{'=' * 70}")
    print(f"TESTE 4: FUNCIONALIDADES BÁSICAS")
    print(f"{'=' * 70}{RESET}\n")

    testes = []

    # 4.1. normalizar_texto
    try:
        from torre_facil.texto import normalizar_texto
        assert normalizar_texto("  São  Paulo  ") == "SAO PAULO"
        assert normalizar_texto("\ufeff  Rio de Janeiro  ") == "RIO DE JANEIRO"
        assert normalizar_texto("") == ""
        log_ok("normalizar_texto() funciona corretamente")
        testes.append(("normalizar_texto", True, None))
    except Exception as e:
        log_erro(f"normalizar_texto(): {e}")
        testes.append(("normalizar_texto", False, str(e)))

    # 4.2. formatar_lista_tec
    try:
        from torre_facil.texto import formatar_lista_tec
        assert formatar_lista_tec(["E", "H", "L", "5"]) == "2G/3G/4G/5G"
        assert formatar_lista_tec(["L", "5"]) == "4G/5G"
        assert formatar_lista_tec([]) == ""
        log_ok("formatar_lista_tec() funciona corretamente")
        testes.append(("formatar_lista_tec", True, None))
    except Exception as e:
        log_erro(f"formatar_lista_tec(): {e}")
        testes.append(("formatar_lista_tec", False, str(e)))

    # 4.3. Paleta classic
    try:
        from torre_facil.tui.cores import PALETAS, ORDEM_PALETAS, aplicar_paleta
        assert "classic" in PALETAS, "Paleta 'classic' não existe"
        assert "classic" in ORDEM_PALETAS, "'classic' não está em ORDEM_PALETAS"
        assert aplicar_paleta("classic") == True
        # Verifica se as variáveis de cor foram criadas
        from torre_facil.tui.cores import BARRA_STATUS_TOPO, CAIXA_TEXTO
        assert BARRA_STATUS_TOPO is not None
        assert CAIXA_TEXTO is not None
        log_ok("Paleta 'classic' carrega corretamente")
        testes.append(("paleta_classic", True, None))
    except Exception as e:
        log_erro(f"Paleta classic: {e}")
        testes.append(("paleta_classic", False, str(e)))

    # 4.4. Todas as paletas aplicam
    try:
        from torre_facil.tui.cores import PALETAS, ORDEM_PALETAS, aplicar_paleta
        for nome in ORDEM_PALETAS:
            assert nome in PALETAS, f"Paleta '{nome}' não existe em PALETAS"
            assert aplicar_paleta(nome), f"Falha ao aplicar paleta '{nome}'"
        aplicar_paleta("classic")  # Restaura
        log_ok(f"Todas as {len(ORDEM_PALETAS)} paletas aplicam sem erro")
        testes.append(("todas_paletas", True, None))
    except Exception as e:
        log_erro(f"Paletas: {e}")
        testes.append(("todas_paletas", False, str(e)))

    # 4.5. ajustar_texto_puro
    try:
        from torre_facil.tui.motor import ajustar_texto_puro, RE_ANSI
        # Testa regex ANSI
        assert RE_ANSI.sub("", "\033[31mOlá\033[0m") == "Olá"
        # Testa alinhamentos
        assert ajustar_texto_puro("Olá", 10, "esq") == "Olá       "
        assert ajustar_texto_puro("Olá", 10, "centro") == "   Olá    "
        assert ajustar_texto_puro("Olá", 10, "dir") == "       Olá"
        # Testa truncamento
        assert ajustar_texto_puro("Olá Mundo Grande", 10, "esq") == "Olá Mund..."
        log_ok("ajustar_texto_puro() funciona corretamente")
        testes.append(("ajustar_texto_puro", True, None))
    except Exception as e:
        log_erro(f"ajustar_texto_puro(): {e}")
        testes.append(("ajustar_texto_puro", False, str(e)))

    # 4.6. criar_item_tui
    try:
        from torre_facil.tui.janelas import criar_item_tui
        item = criar_item_tui("Teste", alinhamento="esq")
        assert item["texto"] == "Teste"
        assert item["alinhamento"] == "esq"
        assert item["selecionavel"] == False
        item2 = criar_item_tui("Sel", selecionavel=True, dados={"id": 1})
        assert item2["dados"] == {"id": 1}
        log_ok("criar_item_tui() funciona corretamente")
        testes.append(("criar_item_tui", True, None))
    except Exception as e:
        log_erro(f"criar_item_tui(): {e}")
        testes.append(("criar_item_tui", False, str(e)))

    # 4.7. gerar_barra_sinal
    try:
        from torre_facil.tui.navegador import gerar_barra_sinal
        barra = gerar_barra_sinal(8.5)
        assert "8.5" in barra
        assert "SINAL FORTE" in barra
        assert "█" in barra
        log_ok("gerar_barra_sinal() funciona corretamente")
        testes.append(("gerar_barra_sinal", True, None))
    except Exception as e:
        log_erro(f"gerar_barra_sinal(): {e}")
        testes.append(("gerar_barra_sinal", False, str(e)))

    # 4.8. obter_estilo_posicao
    try:
        from torre_facil.tui.navegador import obter_estilo_posicao
        cor, icone, rotulo = obter_estilo_posicao(1)
        assert "OURO" in icone
        cor, icone, rotulo = obter_estilo_posicao(2)
        assert "PRATA" in icone
        cor, icone, rotulo = obter_estilo_posicao(3)
        assert "BRONZE" in icone
        cor, icone, rotulo = obter_estilo_posicao(4)
        assert "COLOC" in icone
        log_ok("obter_estilo_posicao() funciona corretamente")
        testes.append(("obter_estilo_posicao", True, None))
    except Exception as e:
        log_erro(f"obter_estilo_posicao(): {e}")
        testes.append(("obter_estilo_posicao", False, str(e)))

    # 4.9. montar_menus
    try:
        from torre_facil.tui.menu_barra import montar_menus
        menus_loja = montar_menus("COMPARADOR")
        assert len(menus_loja) > 0
        assert menus_loja[0]["nome"] == "Arquivo"
        menus_analista = montar_menus("RAIO-X")
        assert len(menus_analista) > 0
        menus_default = montar_menus("")
        assert len(menus_default) > 0
        log_ok("montar_menus() funciona corretamente")
        testes.append(("montar_menus", True, None))
    except Exception as e:
        log_erro(f"montar_menus(): {e}")
        testes.append(("montar_menus", False, str(e)))

    # 4.10. indice_menu_por_tecla
    try:
        from torre_facil.tui.menu_barra import indice_menu_por_tecla
        assert indice_menu_por_tecla("F10") == 0
        assert indice_menu_por_tecla("ALT_A") == 0  # Arquivo
        assert indice_menu_por_tecla("ALT_X") is not None  # Exibir
        log_ok("indice_menu_por_tecla() funciona corretamente")
        testes.append(("indice_menu_por_tecla", True, None))
    except Exception as e:
        log_erro(f"indice_menu_por_tecla(): {e}")
        testes.append(("indice_menu_por_tecla", False, str(e)))

    # 4.11. ACOES_MENU sem espaços
    try:
        from torre_facil.tui.menu_barra import ACOES_MENU_PARA_TECLA, ACOES_MENU_BASICAS
        assert "BACK" in ACOES_MENU_PARA_TECLA
        assert ACOES_MENU_PARA_TECLA["BACK"] == "ESC"
        assert "GLOBAL_SEARCH" in ACOES_MENU_BASICAS
        assert "HELP" in ACOES_MENU_BASICAS
        # Verifica que não há chaves com espaços
        for chave in ACOES_MENU_PARA_TECLA:
            assert chave == chave.strip(), f"Chave '{chave}' tem espaços!"
        log_ok("Constantes de menu sem espaços")
        testes.append(("acoes_menu", True, None))
    except Exception as e:
        log_erro(f"Constantes de menu: {e}")
        testes.append(("acoes_menu", False, str(e)))

    # 4.12. decodificar_sequencia_escape
    try:
        from torre_facil.tui.teclado import decodificar_sequencia_escape
        assert decodificar_sequencia_escape("\x1b[A") == "UP"
        assert decodificar_sequencia_escape("\x1b[B") == "DOWN"
        assert decodificar_sequencia_escape("\x1b[C") == "RIGHT"
        assert decodificar_sequencia_escape("\x1b[D") == "LEFT"
        assert decodificar_sequencia_escape("\x1bOP") == "F1"
        assert decodificar_sequencia_escape("\x1b") == "ESC"
        log_ok("decodificar_sequencia_escape() funciona corretamente")
        testes.append(("decodificar_sequencia_escape", True, None))
    except Exception as e:
        log_erro(f"decodificar_sequencia_escape(): {e}")
        testes.append(("decodificar_sequencia_escape", False, str(e)))

    # 4.13. EstadoSistema
    try:
        from torre_facil.estado import INFO, EstadoSistema
        assert isinstance(INFO, EstadoSistema)
        assert INFO.modulo_atual == "INICIALIZAÇÃO"
        assert hasattr(INFO, "ultimo_erro")
        assert hasattr(INFO, "base")  # Campo adicionado para pesquisa global
        log_ok("EstadoSistema e INFO corretos")
        testes.append(("estado_sistema", True, None))
    except Exception as e:
        log_erro(f"EstadoSistema: {e}")
        testes.append(("estado_sistema", False, str(e)))

    # 4.14. definir/obter_base_global
    try:
        from torre_facil.estado import definir_base_global, obter_base_global, INFO
        import pandas as pd
        df_teste = pd.DataFrame({"a": [1, 2, 3]})
        definir_base_global(df_teste)
        obtido = obter_base_global()
        assert obtido is not None
        assert len(obtido) == 3
        assert INFO.base is not None  # Backup
        # Limpa
        definir_base_global(None)
        log_ok("definir/obter_base_global() funciona corretamente")
        testes.append(("base_global", True, None))
    except Exception as e:
        log_erro(f"base_global: {e}")
        testes.append(("base_global", False, str(e)))

    # 4.15. config
    try:
        from torre_facil.config import VERSAO_CACHE, DIAS_SEMANA, SPLASH_DELAY
        assert VERSAO_CACHE == 5
        assert len(DIAS_SEMANA) == 7
        assert isinstance(SPLASH_DELAY, float)
        log_ok("config.py carrega corretamente")
        testes.append(("config", True, None))
    except Exception as e:
        log_erro(f"config: {e}")
        testes.append(("config", False, str(e)))

    resultados["funcional"] = testes
    print(f"\n  Total: {len(testes)} testes | "
          f"{VERDE}{sum(1 for t in testes if t[1])} OK{RESET} | "
          f"{VERMELHO}{sum(1 for t in testes if not t[1])} ERROS{RESET}")


# =========================================================================
# TESTE 5: Verificação de bugs comuns
# =========================================================================

def testar_bugs_comuns() -> None:
    """Verifica bugs comuns de strings corrompidas."""
    print(f"\n{NEGRITO}{'=' * 70}")
    print(f"TESTE 5: VERIFICAÇÃO DE BUGS COMUNS (strings corrompidas)")
    print(f"{'=' * 70}{RESET}\n")

    bugs_encontrados = 0

    # 5.1. Verifica "from future" sem underscores
    for arquivo in PROJETO.rglob("*.py"):
        with open(arquivo, "r", encoding="utf-8") as f:
            conteudo = f.read()
        if "from future import annotations" in conteudo:
            log_erro(f"{arquivo.relative_to(PROJETO.parent)}: 'from future' sem underscores")
            bugs_encontrados += 1

    if bugs_encontrados == 0:
        log_ok("Nenhum 'from future' sem underscores encontrado")

    # 5.2. Verifica strings com espaços no final em dicionários críticos
    arquivos_criticos = [
        "torre_facil/tui/cores.py",
        "torre_facil/tui/teclado.py",
        "torre_facil/tui/menu_barra.py",
        "torre_facil/main.py",
    ]
    for arquivo_rel in arquivos_criticos:
        arquivo = PROJETO.parent / arquivo_rel
        if not arquivo.exists():
            continue
        with open(arquivo, "r", encoding="utf-8") as f:
            conteudo = f.read()
        # Procura padrões como "X " em chaves de dict
        import re
        # Padrão: "chave ": (chave com espaço antes de :)
        matches = re.findall(r'"[A-Z_]+ "\s*:', conteudo)
        if matches:
            log_erro(f"{arquivo_rel}: {len(matches)} chaves com espaços extras")
            bugs_encontrados += len(matches)

    # 5.3. Verifica regex ANSI no motor.py
    motor_path = PROJETO / "tui" / "motor.py"
    if motor_path.exists():
        with open(motor_path, "r", encoding="utf-8") as f:
            conteudo = f.read()
        if r'\x1b[[0-9;]' in conteudo:
            log_erro("motor.py: regex ANSI com colchetes duplos (quebrada)")
            bugs_encontrados += 1
        else:
            log_ok("motor.py: regex ANSI correta")

    # 5.4. Verifica padding duplo no motor.py
    if motor_path.exists():
        with open(motor_path, "r", encoding="utf-8") as f:
            conteudo = f.read()
        if '("  " * esq)' in conteudo or '("  " * faltam)' in conteudo:
            log_erro("motor.py: padding com dois espaços (quebrado)")
            bugs_encontrados += 1
        else:
            log_ok("motor.py: padding com um espaço (correto)")

    # 5.5. Verifica __name__ == "__main__"
    main_path = PROJETO / "__main__.py"
    if main_path.exists():
        with open(main_path, "r", encoding="utf-8") as f:
            conteudo = f.read()
        if 'if name == "main":' in conteudo:
            log_erro("__main__.py: 'if name' sem underscores")
            bugs_encontrados += 1
        elif 'if __name__ == "__main__":' in conteudo:
            log_ok("__main__.py: '__name__' correto")

    print(f"\n  Total de bugs comuns verificados: {bugs_encontrados}")


# =========================================================================
# RELATÓRIO FINAL
# =========================================================================

def gerar_relatorio() -> None:
    """Gera relatório final com resumo."""
    print(f"\n{NEGRITO}{'=' * 70}")
    print(f"RELATÓRIO FINAL")
    print(f"{'=' * 70}{RESET}\n")

    total_sintaxe = len(resultados["sintaxe"])
    ok_sintaxe = sum(1 for r in resultados["sintaxe"] if r[1])

    total_import = len(resultados["import"])
    ok_import = sum(1 for r in resultados["import"] if r[1])

    total_funcoes = len(resultados["funcoes"])
    ok_funcoes = sum(1 for r in resultados["funcoes"] if r[1])

    total_funcional = len(resultados["funcional"])
    ok_funcional = sum(1 for t in resultados["funcional"] if t[1])

    print(f"  {NEGRITO}Sintaxe:{RESET}       {VERDE}{ok_sintaxe}/{total_sintaxe} OK{RESET}")
    print(f"  {NEGRITO}Importação:{RESET}    {VERDE}{ok_import}/{total_import} OK{RESET}")
    print(f"  {NEGRITO}Funções:{RESET}       {VERDE}{ok_funcoes}/{total_funcoes} OK{RESET}")
    print(f"  {NEGRITO}Funcional:{RESET}     {VERDE}{ok_funcional}/{total_funcional} OK{RESET}")

    total_geral = total_sintaxe + total_import + total_funcoes + total_funcional
    ok_geral = ok_sintaxe + ok_import + ok_funcoes + ok_funcional

    print(f"\n  {NEGRITO}TOTAL GERAL:{RESET}  {VERDE}{ok_geral}/{total_geral} OK{RESET}")

    if ok_geral == total_geral:
        print(f"\n  {VERDE}{NEGRITO}🎉 TODOS OS TESTES PASSARAM! O projeto está saudável.{RESET}")
    else:
        falhas = total_geral - ok_geral
        print(f"\n  {VERMELHO}{NEGRITO}⚠ {falhas} teste(s) falharam. Verifique os erros acima.{RESET}")

    # Lista erros detalhados
    erros_detalhados = []
    for r in resultados["sintaxe"] + resultados["import"] + resultados["funcoes"]:
        if not r[1]:
            erros_detalhados.append((r[0], r[2]))
    for t in resultados["funcional"]:
        if not t[1]:
            erros_detalhados.append((t[0], t[2]))

    if erros_detalhados:
        print(f"\n  {NEGRITO}Erros detalhados:{RESET}")
        for nome, erro in erros_detalhados:
            print(f"    {VERMELHO}- {nome}{RESET}: {erro}")


# =========================================================================
# MAIN
# =========================================================================

def main() -> None:
    print(f"\n{NEGRITO}{CIANO}")
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║       TORRE FÁCIL ERP — SUITE DE TESTES COMPLETA          ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print(f"{RESET}")

    testar_sintaxe()
    testar_imports()
    testar_funcoes()
    testar_funcional()
    testar_bugs_comuns()
    gerar_relatorio()

    print(f"\n{NEGRITO}{'=' * 70}")
    print(f"Testes concluídos em {os.getcwd()}")
    print(f"{'=' * 70}{RESET}\n")


if __name__ == "__main__":
    main()