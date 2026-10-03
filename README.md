# Torre Fácil ERP

**Torre Fácil** é um pacote modular em Python com interface de terminal (TUI) para consulta, análise e exportação de dados de estações SMP (torres de telecomunicações) da **Anatel** no Brasil.

- **Versão:** 10.0.0
- **Licença:** MIT
- **Interface:** TUI retrô baseada em terminal (ANSI colors, `termios`/`msvcrt`)
- **Dados:** Base aberta da Anatel (estações SMP), com download, cache binário e snapshot versionado

## Funcionalidades

O sistema opera em dois modos — **Loja** (atendimento a clientes) e **Analista** (análise técnica) — com troca via easter egg `F12`.

### Módulos de negócio (`torre_facil/modulos/`)

| Módulo | Descrição |
|---|---|
| `consulta_rapida` | Consulta rápida (modo loja) por CEP, endereço livre ou cidade/bairro |
| `avancada` | Pesquisa avançada parametrizada com 6 filtros |
| `raio_x` | Raio-X de cidade e de estado |
| `comparador` | Comparação lado a lado de municípios (modo analista) |
| `comparador_loja` | Comparador A vs B de operadoras por endereço (modo loja) |
| `explorador` | Explorador guiado por operadora (fluxo em 4 passos) |
| `faixas` | Análise por faixa de frequência e tipo de infraestrutura (inclui 5G) |
| `rodovias` | Localização de ERBs ao longo de BRs e rodovias estaduais |
| `chips` | Consultor/indicador de chip (melhor operadora por perfil de uso) |
| `favoritos` | Lista de endereços favoritos salvos pelo usuário |
| `faq` | Perguntas frequentes com ações pré-configuradas (modo loja) |
| `kml` | Exportação KML para Google Earth (pinos coloridos por operadora) |
| `novidades` | Tela de novidades entre duas atualizações da base Anatel |
| `paletas` | Seletor de paleta de cores retrô |
| `sobre` | Sobre o sistema + estatísticas da base/cache/consumo |

### Camadas do projeto

- `torre_facil/dados/` — acesso e cache dos dados da Anatel: download do ZIP, extração do CSV, cache binário (pickle), snapshots JSON e normalização de bairros
- `torre_facil/tui/` — camada de interface textual: motor de renderização, menus, janelas, barra de menu, teclado e cores
- Núcleo: `main.py` (hub/menu principal e manutenção de cache), `config.py` (constantes e caminhos), `estado.py`, `dicionarios.py`, `coordenadas.py`, `pesquisa_global.py`, `texto.py`, `painel.py`, `config_usuario.py`

## Requisitos

- **Python 3.10+** (usa `from __future__ import annotations`, `typing.Final`, dataclasses)
- Bibliotecas externas:
  - `pandas`
  - `numpy`
  - `requests`
- Terminal real (TTY) com suporte a sequências ANSI. Em Linux/macOS usa `termios`/`tty`/`select`; no Windows usa `msvcrt`.

## Instalação

```bash
git clone <url-do-repositorio> torre-facil
cd torre-facil
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install pandas numpy requests
```

> Observação: o `requirements.txt` incluído é um dump do ambiente (contém pacotes específicos de sistema). Para instalar apenas o necessário, prefira `pip install pandas numpy requests`.

## Uso

```bash
python -m torre_facil
```

Fluxo de inicialização:

1. Verificação do ambiente (terminal real)
2. Aplicação da paleta de cores escolhida
3. Seleção do modo de operação (loja / analista)
4. Bootstrap da base de dados Anatel (download + cache automático)
5. Exibição de novidades (se a base mudou desde a última execução)
6. Loop principal: tela de logo → menu → logo

Encerramento: `X` no menu, `Alt+F4` na janela ou `Ctrl+C` (código 130).

### Dados e cache

Os dados externos são baixados de:

```
https://www.anatel.gov.br/dadosabertos/paineis_de_dados/outorga_e_licenciamento/estacoes_smp.zip
```

Arquivos gerados (em diretório de dados do próprio pacote, caminhos absolutos independentes do CWD):

- `estacoes_smp.zip` — ZIP baixado da Anatel
- `estacoes_smp_extraido.csv` — CSV extraído (uso durante processamento)
- `torre_facil_cache.pkl` — cache binário do DataFrame processado
- Dicionários, cache de bairros e snapshots JSON (incluindo comparação entre versões da base)

A manutenção do cache (limpeza/reprocessamento) é feita pelo menu **Gerenciar cache** em `main.py`.

## Testes

O repositório inclui um script completo de verificação:

```bash
python testar_tudo.py
```

Ele checa:

1. Sintaxe de todos os arquivos `.py` (compilação)
2. Importação de cada módulo
3. Existência de funções/classes principais
4. Funcionalidades básicas (paleta, texto etc.)
5. Relatório detalhado com cores ANSI

## Estrutura do repositório

```
.
├── torre_facil/              # Pacote principal
│   ├── __main__.py           # Entrypoint (python -m torre_facil)
│   ├── main.py               # Menu principal / hub / loop de operação
│   ├── config.py             # Constantes, URLs e caminhos
│   ├── config_usuario.py     # Preferências do usuário (modo, fundo)
│   ├── estado.py              # Estado global / exceções de navegação
│   ├── dicionarios.py        # Dicionários persistentes
│   ├── coordenadas.py        # Utilidades geográficas
│   ├── pesquisa_global.py    # Busca global
│   ├── texto.py / painel.py  # Utilidades de texto e painéis
│   ├── dados/                # Acesso e cache de dados da Anatel
│   ├── modulos/              # Módulos de negócio (ver tabela acima)
│   └── tui/                  # Camada de interface textual
├── backup_correcao/          # Cópia de segurança de uma correção anterior
├── torre_facil_snapshot.json # Snapshot da base de dados
├── testar_tudo.py            # Script de testes do projeto
├── requirements.txt          # Dependências (dump do ambiente)
└── README.md
```

## Licença

Distribuído sob a licença **MIT**.
