package ui

import (
	"fmt"
	"strings"
	"time"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/mattn/go-runewidth"

	"github.com/torrefacil/torre-facil-go/internal/data"
)

// Tela identifica a tela ativa.
type Tela int

const (
	TelaLogo Tela = iota // tela de abertura persistente (espelho janelas.tela_logo)
	TelaMenu
	TelaRaioXUf
	TelaRaioXMun
	TelaFaixaUf
	TelaFaixaResultado
	TelaSobre
	TelaBusca
	TelaForm
	TelaPainel
	TelaListaErbs
	TelaComparador
	TelaChips
	TelaRodovias
	TelaFAQ
	TelaManutencao
	TelaRanking
)

// Modo replica os modos loja/analista do Python.
type Modo string

const (
	ModoAnalista Modo = "analista"
	ModoLoja     Modo = "loja"
)

// ItemMenu é um item selecionável das listas centrais.
type ItemMenu struct {
	Rotulo string
	Codigo string // ação: "1","2","A","0","V","X"...
	Divisor bool
}

// MenuBarraDef replica montar_menus() de tui/menu_barra.py.
type MenuBarraDef struct {
	Nome  string
	Hot   string
	Itens []ItemMenu
}

func menusPadrao() []MenuBarraDef {
	return []MenuBarraDef{
		{"Arquivo", "A", []ItemMenu{
			{Rotulo: "Voltar / Fechar         Esc", Codigo: "BACK"},
			{Rotulo: "Recarregar tela", Codigo: "REDRAW"},
		}},
		{"Editar", "E", []ItemMenu{
			{Rotulo: "Limpar filtro", Codigo: "CLEAR"},
			{Rotulo: "Limpar seleção", Codigo: "CLEAR_SEL"},
		}},
		{"Exibir", "X", []ItemMenu{
			{Rotulo: "Primeiro registro    Home", Codigo: "FIRST"},
			{Rotulo: "Último registro       End", Codigo: "LAST"},
		}},
		{"Pesquisa", "P", []ItemMenu{
			{Rotulo: "Pesquisa global          /", Codigo: "GLOBAL_SEARCH"},
		}},
		{"Navegação", "N", []ItemMenu{
			{Rotulo: "Página anterior        PgUp", Codigo: "PAGE_UP"},
			{Rotulo: "Próxima página         PgDn", Codigo: "PAGE_DOWN"},
		}},
		{"Ajuda", "J", []ItemMenu{
			{Rotulo: "Atalhos da tela", Codigo: "HELP"},
			{Rotulo: "Sobre o Sistema", Codigo: "ABOUT"},
		}},
	}
}

// Model é o estado central do programa Bubble Tea.
type Model struct {
	Snap *data.Snapshot

	tela      Tela
	modo      Modo
	resumo    string
	width     int
	height    int
	err       error
	agora     time.Time
	msgRodape string

	// menu principal
	itensMenu  []ItemMenu
	menuIdx    int
	ufs        []string
	ufIdx      int
	municipios []string
	munIdx     int
	ufSel      string
	munSel     string
	faixaIdx   int

	// barra de menu (F10) — visibilidade alternada; nunca duplica
	barraVisivel bool
	barraAberta  int // -1 fechado
	barraItem    int

	// busca
	busca      textinput.Model
	buscaRes   []data.Erb
	buscaIdx   int

	// formulário (formulario_tui legado)
	form     *FormModel
	formAcao string

	// lista de ERBs (navegador_tui legado)
	listaTit    string
	listaRegs   []data.Erb
	listaIdx    int
	listaScroll int
	listaVoltar Tela
	favIdx      int // seleção na tela de favoritos (modo loja)

	// painel interativo por município
	painelNome     string
	painelUF       string
	painelRegs     []data.Erb
	painelVisao    int
	painelIdx      int
	painelScroll   int
	painelFiltro   string
	painelExpandido bool
	painelVoltar   Tela

	// comparador de operadoras
	compCidades [][2]string
	rankIdx     int

	// indicador de chips
	chipsEscopo string
	chipsRegs   []data.Erb

	// rodovias / FAQ / manutenção
	rodoUF   string
	rodoIdx  int
	faqIdx   int
	manutIdx int
}

// NewModel cria o modelo inicial.
func NewModel(snap *data.Snapshot, modo Modo) Model {
	ti := textinput.New()
	ti.Placeholder = "município, UF, operadora ou ID..."
	ti.CharLimit = 48
	m := Model{
		Snap: snap, modo: modo,
		tela: TelaLogo, ufIdx: 0, faixaIdx: 0,
		barraAberta: -1, agora: time.Now(),
		resumo:    snap.ResumoStatus(),
		busca:     ti,
		msgRodape: "X = Sair  │  ESC = Ficar no logo  │  ENTER = Abrir o menu",
	}
	m.atualizarItensMenu()
	return m
}

func (m Model) Init() tea.Cmd {
	return tick()
}

func tick() tea.Cmd {
	return tea.Tick(time.Second, func(t time.Time) tea.Msg {
		return tickMsg(t)
	})
}

type tickMsg time.Time

// ---------- construção dos itens por modo (espelho main.py) ----------

func (m *Model) atualizarItensMenu() {
	var itens []ItemMenu
	if m.modo == ModoLoja {
		itens = []ItemMenu{
			{Rotulo: "1. Consulta rápida por CEP / endereço", Codigo: "1"},
			{Rotulo: "2. Comparar duas operadoras", Codigo: "2"},
			{Rotulo: "3. Favoritos", Codigo: "3"},
			{Rotulo: "4. Perguntas frequentes", Codigo: "4"},
			{Divisor: true},
			{Rotulo: "R. Raio-X de cidade e bairros", Codigo: "R"},
			{Rotulo: "I. Indicador de chip", Codigo: "I"},
			{Rotulo: "S. Sobre o Sistema / Estatísticas", Codigo: "S"},
			{Divisor: true},
			{Rotulo: "0. Manutenção do sistema / Cache", Codigo: "0"},
			{Rotulo: "V. Voltar à tela de logo", Codigo: "V"},
			{Rotulo: "X. Fim de Operação", Codigo: "X"},
		}
	} else {
		itens = []ItemMenu{
			{Rotulo: "1. Raio-X de cidade e bairros", Codigo: "1"},
			{Rotulo: "2. Ranking / Raio-X por estado", Codigo: "2"},
			{Rotulo: "3. Explorador guiado por operadora", Codigo: "3"},
			{Rotulo: "4. Comparador lado a lado cidades", Codigo: "4"},
			{Rotulo: "5. Consultor / Indicador de chip", Codigo: "5"},
			{Rotulo: "6. Consulta BRs e estradas locais", Codigo: "6"},
			{Divisor: true},
			{Rotulo: "7. Pesquisa avançada (multi-filtros)", Codigo: "7"},
			{Rotulo: "8. Exportar mapa Google Earth (.kml)", Codigo: "8"},
			{Rotulo: "A. Análise por faixa de frequência", Codigo: "A"},
			{Rotulo: "9. Sobre o Sistema / Estatísticas", Codigo: "9"},
			{Divisor: true},
			{Rotulo: "0. Manutenção do sistema / Cache", Codigo: "0"},
			{Rotulo: "V. Voltar à tela de logo", Codigo: "V"},
			{Rotulo: "X. Fim de Operação", Codigo: "X"},
		}
	}
	m.itensMenu = itens
	if m.menuIdx >= len(itens) {
		m.menuIdx = 0
	}
}

func primeiroSelecionavel(itens []ItemMenu, idx int) int {
	for i := idx; i < len(itens); i++ {
		if !itens[i].Divisor {
			return i
		}
	}
	for i := 0; i <= idx && i < len(itens); i++ {
		if !itens[i].Divisor {
			return i
		}
	}
	return idx
}

func (m *Model) moverMenu(passo int) {
	n := len(m.itensMenu)
	i := m.menuIdx
	for k := 0; k < n; k++ {
		i = (i + passo + n) % n
		if !m.itensMenu[i].Divisor {
			break
		}
	}
	m.menuIdx = i
}

// ---------- Update ----------

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tickMsg:
		m.agora = time.Time(msg)
		return m, tick()

	case rodapeMsg:
		m.msgRodape = string(msg)
		return m, nil

	case tea.WindowSizeMsg:
		m.width, m.height = msg.Width, msg.Height
		return m, nil

	case tea.KeyMsg:
		return m.tratarTecla(msg)
	}

	// texto da busca
	if m.tela == TelaBusca {
		var cmd tea.Cmd
		m.busca, cmd = m.busca.Update(msg)
		m.atualizarBusca()
		return m, cmd
	}
	_ = imprimivelVazio
	return m, nil
}

func (m Model) tratarTecla(k tea.KeyMsg) (tea.Model, tea.Cmd) {
	// F10: alterna VISIBILIDADE da barra — uma única vez, sem duplicar
	// (lição do bug legado: F10 não redesenha nem reabre nada).
	if k.Type == tea.KeyF10 {
		if m.barraAberta >= 0 {
			m.barraAberta = -1 // legado: F10/ESC fecha o dropdown
			return m, nil
		}
		if m.barraVisivel {
			m.abrirDropdown(0) // legado: barra visível + F10 abre o 1º menu
		} else {
			m.barraVisivel = true
			m.msgRodape = "Barra de menu ativada — F10 abre o menu."
		}
		return m, nil
	}

	// ALT+letra abre/alterna o menu correspondente (legado: indice_menu_por_tecla)
	if k.Alt && len(k.String()) == 1 && m.tela != TelaBusca && m.tela != TelaForm {
		novo := indiceMenuPorTecla(k.String(), m.moduloAtual(), string(m.modo))
		if novo >= 0 {
			m.abrirDropdown(novo)
			return m, nil
		}
	}

	// dropdown aberto? consome as teclas antes de tudo
	if m.barraAberta >= 0 {
		if nm, cmd, handled := m.teclaBarra(k); handled {
			return nm, cmd
		}
		m.barraAberta = -1
	}

	switch m.tela {
	case TelaLogo:
		switch k.Type {
		case tea.KeyCtrlC:
			return m, tea.Quit
		case tea.KeyEsc:
			// legado: ESC fica no logo
			return m, nil
		case tea.KeyEnter, tea.KeySpace:
			m.tela = TelaMenu
			m.menuIdx = primeiroSelecionavel(m.itensMenu, 0)
			m.msgRodape = "TORRE FÁCIL — menu principal (setas + Enter)."
		default:
			up := strings.ToUpper(k.String())
			if up == "X" || k.Type == tea.KeyCtrlD {
				return m, tea.Quit
			}
		}
		return m, nil
	case TelaMenu:
		return m.teclaMenu(k)
	case TelaRaioXUf, TelaFaixaUf:
		return m.teclaListaUF(k)
	case TelaRaioXMun:
		return m.teclaListaMun(k)
	case TelaFaixaResultado:
		if k.Type == tea.KeyEscape || k.Type == tea.KeyEnter {
			m.tela = TelaFaixaUf
		}
		return m, nil
	case TelaSobre:
		if k.Type == tea.KeyEscape || k.Type == tea.KeyEnter {
			m.tela = TelaMenu
		}
		return m, nil
	case TelaForm:
		return m.teclaForm(k)
	case TelaPainel:
		return m.teclaPainel(k)
	case TelaListaErbs:
		return m.teclaListaErbs(k)
	case TelaRodovias:
		return m.teclaRodovias(k)
	case TelaFAQ:
		return m.teclaFAQ(k)
	case TelaManutencao:
		return m.teclaManutencao(k)
	case TelaComparador, TelaChips:
		if k.Type == tea.KeyEscape || k.Type == tea.KeyEnter {
			m.tela = TelaMenu
		}
		return m, nil
	case TelaRanking:
		pares := m.ufsOrdenadasPorQtd()
		switch k.Type {
		case tea.KeyEscape:
			m.tela = TelaMenu
		case tea.KeyUp:
			m.rankIdx = (m.rankIdx - 1 + len(pares)) % maxInt(1, len(pares))
		case tea.KeyDown:
			m.rankIdx = (m.rankIdx + 1) % maxInt(1, len(pares))
		case tea.KeyEnter:
			if len(pares) > 0 && m.rankIdx < len(pares) {
				uf := pares[m.rankIdx]
				m.ufSel = uf
				m.municipios = m.Snap.MunicipiosPorUF(uf)
				if len(m.municipios) == 0 {
					m.msgRodape = "Nenhum município na base para esta UF."
					return m, nil
				}
				m.munIdx = 0
				m.tela = TelaRaioXMun
			}
		}
		return m, nil
	case TelaBusca:
		switch k.Type {
		case tea.KeyEscape:
			m.tela = TelaMenu
			m.busca.SetValue("")
			m.buscaRes = nil
		case tea.KeyEnter:
			if len(m.buscaRes) > 0 {
				e := m.buscaRes[m.buscaIdx]
				m.msgRodape = fmt.Sprintf("ERB: %s | %s (%s/%s) | %s%s",
					e.ID, e.Bairro, e.Municipio, e.UF,
					data.FormatarListaTec(e.Tecs), sa5gTag(e.SA5G))
			}
		default:
			var cmd tea.Cmd
			m.busca, cmd = m.busca.Update(k)
			m.atualizarBusca()
			return m, cmd
		}
		return m, nil
	}
	return m, nil
}

func (m Model) teclaMenu(k tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch k.Type {
	case tea.KeyCtrlC:
		return m, tea.Quit
	case tea.KeyEsc:
		if m.modo == ModoLoja {
			return m, tea.Quit // modo loja encerra como "X. Fim de Operação"
		}
		m.tela = TelaLogo // legado: ESC/V volta à tela de logo
		m.msgRodape = "X = Sair  │  ESC = Ficar no logo  │  ENTER = Abrir o menu"
		return m, nil
	case tea.KeyUp:
		m.moverMenu(-1)
	case tea.KeyDown:
		m.moverMenu(+1)
	case tea.KeyEnter:
		return m.executar(m.itensMenu[m.menuIdx].Codigo)
	default:
		// atalho por letra/número
		up := strings.ToUpper(k.String())
		for _, it := range m.itensMenu {
			if it.Codigo != "" && strings.EqualFold(it.Codigo, up) {
				return m.executar(it.Codigo)
			}
		}
	}
	return m, nil
}

// executar replica exatamente _despachar_analista / _despachar_loja de main.py.
func (m Model) executar(codigo string) (tea.Model, tea.Cmd) {
	if m.modo == ModoLoja {
		return m.executarLoja(codigo)
	}
	return m.executarAnalista(codigo)
}

// executarAnalista — espelho 1:1 de _despachar_analista (main.py).
func (m Model) executarAnalista(codigo string) (tea.Model, tea.Cmd) {
	switch codigo {
	case "X":
		return m, tea.Quit
	case "V":
		m.menuIdx = 0
		m.tela = TelaLogo
		m.msgRodape = "X = Sair  │  ESC = Ficar no logo  │  ENTER = Abrir o menu"

	case "1": // raio_x.raio_x_cidade
		m.abrirFormRaioX()
	case "2": // raio_x.raio_x_estado → ranking/pódio por UF
		if len(m.ufs) == 0 {
			m.ufs = m.Snap.UFs()
		}
		m.ufIdx = 0
		m.tela = TelaRanking
	case "3": // explorador.pesquisa_guiada_operadora
		m.abrirFormExplorador()
	case "4": // comparador.comparador_cidades
		m.abrirComparadorManual()
	case "5": // chips.indicador_de_chips
		m.abrirFormChips()
	case "6": // rodovias.consultar_estradas
		m.abrirRodovias()
	case "7": // avancada.pesquisa_avancada
		m.abrirFormAvancada()
	case "8": // kml.exportar_kml
		m.abrirFormKML()
	case "A": // faixas.analise_por_faixa: Brasil inteiro + 27 estados
		m.ufs = append([]string{"Brasil Inteiro (Consolidado)"}, m.Snap.UFs()...)
		m.faixaIdx = 0
		m.tela = TelaFaixaUf
	case "9": // sobre.sobre_sistema_tui
		m.tela = TelaSobre
	case "0": // menu_gerenciar_cache
		m.abrirManutencao()
	default:
		m.msgRodape = "Opção indisponível."
	}
	return m, nil
}

// executarLoja — espelho 1:1 de _despachar_loja (main.py).
func (m Model) executarLoja(codigo string) (tea.Model, tea.Cmd) {
	switch codigo {
	case "X":
		return m, tea.Quit
	case "V":
		m.menuIdx = 0
		m.tela = TelaLogo
		m.msgRodape = "X = Sair  │  ESC = Ficar no logo  │  ENTER = Abrir o menu"
	case "1": // consulta_rapida.consulta_rapida
		m.abrirFormConsulta(codigo)
	case "2": // comparador_loja.comparador_loja
		m.abrirFormComparadorLoja(codigo)
	case "3": // favoritos.favoritos
		m.abrirFavoritos()
	case "4": // faq.faq
		m.abrirFAQ()
	case "R": // raio_x.raio_x_cidade
		m.abrirFormRaioX()
	case "I": // chips.indicador_de_chips
		m.abrirFormChips()
	case "S": // sobre.sobre_sistema_tui
		m.tela = TelaSobre
	case "0": // menu_gerenciar_cache
		m.abrirManutencao()
	default:
		m.msgRodape = "Opção indisponível."
	}
	return m, nil
}

func (m Model) teclaListaUF(k tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch k.Type {
	case tea.KeyEscape:
		m.tela = TelaMenu
		return m, nil
	case tea.KeyUp:
		m.ufIdx = (m.ufIdx - 1 + len(m.ufs)) % len(m.ufs)
	case tea.KeyDown:
		m.ufIdx = (m.ufIdx + 1) % len(m.ufs)
	case tea.KeyEnter:
		escolhido := m.ufs[m.ufIdx]
		uf := escolhido
		if strings.HasPrefix(escolhido, "(") || strings.HasPrefix(escolhido, "Brasil") {
			uf = ""
		}
		if m.tela == TelaFaixaUf {
			m.ufSel = escolhido
			m.munSel = uf // "" = Brasil inteiro (consolidado)
			m.msgRodape = "Faixas calculadas para " + escolhido
			m.tela = TelaFaixaResultado
			return m, nil
		}
		m.ufSel = uf
		m.municipios = m.Snap.MunicipiosPorUF(uf)
		if len(m.municipios) == 0 {
			m.msgRodape = "Nenhum município na base para esta UF."
			m.tela = TelaMenu
			return m, nil
		}
		m.munIdx = primeiroSelecionavel(nil, 0)
		m.tela = TelaRaioXMun
	}
	return m, nil
}

func (m Model) teclaListaMun(k tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch k.Type {
	case tea.KeyEscape:
		m.tela = TelaRaioXUf
		return m, nil
	case tea.KeyUp:
		m.munIdx = (m.munIdx - 1 + len(m.municipios)) % len(m.municipios)
	case tea.KeyDown:
		m.munIdx = (m.munIdx + 1) % len(m.municipios)
	case tea.KeyEnter:
		mun := m.municipios[m.munIdx]
		cont := m.Snap.ContagemPorMunicipio(m.ufSel)
		k := mun + "|" + m.ufSel
		qtd := cont[k]
		if qtd == 0 {
			qtd = cont[mun+"|"+procuraUF(m.Snap, mun)]
		}
		m.msgRodape = fmt.Sprintf("RAIO-X %s/%s: %d ERBs no município.", mun, m.ufSel, qtd)
		m.tela = TelaBusca
		m.busca.SetValue(data.NormalizarTexto(mun))
		m.atualizarBusca()
	}
	return m, nil
}

func procuraUF(s *data.Snapshot, mun string) string {
	for _, r := range s.Registros {
		if r.Municipio == mun {
			return r.UF
		}
	}
	return ""
}

func (m Model) teclaDropdown(k tea.KeyMsg) (tea.Model, tea.Cmd) {
	menus := menusPadrao()
	itens := menus[m.barraAberta].Itens
	switch k.Type {
	case tea.KeyEscape:
		m.barraAberta = -1
	case tea.KeyLeft:
		m.barraAberta = (m.barraAberta - 1 + len(menus)) % len(menus)
		m.barraItem = 0
	case tea.KeyRight:
		m.barraAberta = (m.barraAberta + 1) % len(menus)
		m.barraItem = 0
	case tea.KeyUp:
		m.barraItem = (m.barraItem - 1 + len(itens)) % len(itens)
	case tea.KeyDown:
		m.barraItem = (m.barraItem + 1) % len(itens)
	case tea.KeyEnter:
		acao := itens[m.barraItem].Codigo
		m.barraAberta = -1
		switch acao {
		case "GLOBAL_SEARCH":
			m.tela = TelaBusca
			m.busca.Focus()
		case "BACK":
			m.tela = TelaMenu
		case "ABOUT":
			m.tela = TelaSobre
		}
	}
	return m, nil
}

func (m *Model) atualizarBusca() {
	q := data.NormalizarTexto(m.busca.Value())
	res := make([]data.Erb, 0, 256)
	if q == "" {
		m.buscaRes = res
		m.buscaIdx = 0
		return
	}
	for _, r := range m.Snap.Registros {
		hay := data.NormalizarTexto(r.Municipio + " " + r.UF + " " + r.Operadora + " " + r.Estacao + " " + r.Bairro)
		if strings.Contains(hay, q) {
			res = append(res, r)
			if len(res) >= 300 {
				break
			}
		}
	}
	m.buscaRes = res
	if m.buscaIdx >= len(res) {
		m.buscaIdx = 0
	}
}

func sa5gTag(b bool) string {
	if b {
		return " [5G SA]"
	}
	return ""
}

// ---------- View ----------

func trunc(s string, w int) string {
	if runewidth.StringWidth(s) <= w {
		return s
	}
	if w <= 1 {
		return ""
	}
	return runewidth.Truncate(s, w-1, "") + "…"
}

func pad(s string, w int) string {
	d := w - runewidth.StringWidth(s)
	if d < 0 {
		d = 0
	}
	return s + strings.Repeat(" ", d)
}

func (m Model) View() string {
	if m.width == 0 {
		return "Carregando terminal..."
	}
	var b strings.Builder

	// linha 1: título/status topo
	top := BarraStatusTopo.Width(m.width).Render(trunc(" TORRE FÁCIL (Go) — "+string(m.modo)+" ", m.width))
	b.WriteString(top + "\n")
	// linha 2: resumo da base
	sub := BarraSubTopo.Width(m.width).Render(trunc(" "+m.resumo, m.width))
	b.WriteString(sub + "\n")

	// linha 3: barra de menu (F10) — renderizada UMA única vez, largura total
	if m.barraVisivel {
		b.WriteString(m.viewBarraPortada() + "\n")
		if m.barraAberta >= 0 {
			b.WriteString(m.viewDropdownAncorado() + "\n")
		}
	}

	conteudo := m.viewTela()
	b.WriteString(conteudo)

	// rodapé duplo: mensagem + status com relógio hh:mm:ss em tempo real
	rod := CaixaCiano.Width(m.width).Render(trunc(" "+m.msgRodape, m.width))
	b.WriteString("\n" + rod + "\n")
	relogio := m.agora.Format("15:04:05")
	status := fmt.Sprintf(" F10 menu | / busca | Esc voltar | X sair                    %s ", relogio)
	b.WriteString(BarraStatusTopo.Width(m.width).Render(trunc(status, m.width)))
	return b.String()
}

func (m Model) viewBarraMenu() string {
	menus := menusPadrao()
	parts := make([]string, 0, len(menus))
	for i, mn := range menus {
		base := fmt.Sprintf(" %s(&%s) ", mn.Nome, mn.Hot)
		if i == m.barraAberta {
			parts = append(parts, MenuBarraAtivo.Render(base))
		} else {
			parts = append(parts, MenuBarraHot.Render(base))
		}
	}
	fundo := MenuBarra.Render(strings.Join(parts, ""))
	// preenche até a largura total (ajuste à janela)
	livre := m.width - runewidth.StringWidth(strings.Join(func() []string {
		out := make([]string, len(menus))
		for i, mn := range menus {
			out[i] = fmt.Sprintf(" %s(&%s) ", mn.Nome, mn.Hot)
		}
		return out
	}(), ""))
	if livre > 0 {
		fundo += MenuBarra.Render(strings.Repeat(" ", livre))
	}
	return fundo
}

func (m Model) viewDropdown() string {
	menus := menusPadrao()
	mn := menus[m.barraAberta]
	w := 0
	for _, it := range mn.Itens {
		if lw := runewidth.StringWidth(it.Rotulo) + 4; lw > w {
			w = lw
		}
	}
	var linhas []string
	linhas = append(linhas, MenuItem.Render(pad("─"+strings.Repeat("─", w), w+2)))
	for i, it := range mn.Itens {
		txt := " " + it.Rotulo
		if i == m.barraItem {
			linhas = append(linhas, MenuItemSel.Render(pad(txt, w+2)))
		} else {
			linhas = append(linhas, MenuItem.Render(pad(txt, w+2)))
		}
	}
	return strings.Join(linhas, "\n")
}

func (m Model) viewTela() string {
	switch m.tela {
	case TelaLogo:
		return m.viewLogo()
	case TelaForm:
		return m.viewForm()
	case TelaPainel:
		return m.viewPainel()
	case TelaListaErbs:
		return m.viewListaErbs()
	case TelaComparador:
		return m.viewComparador()
	case TelaChips:
		return m.viewChips()
	case TelaRodovias:
		return m.viewRodovias()
	case TelaFAQ:
		return m.viewFAQ()
	case TelaManutencao:
		return m.viewManutencao()
	case TelaRanking:
		return m.viewRanking()
	case TelaMenu:
		var ls []string
		ls = append(ls, CaixaTitulo.Render(pad(" MENU PRINCIPAL ", m.width)))
		for i, it := range m.itensMenu {
			if it.Divisor {
				ls = append(ls, CaixaTexto.Render(pad(strings.Repeat("─", 40), m.width)))
				continue
			}
			marca := "  "
			if i == m.menuIdx {
				marca = "> "
			}
			if i == m.menuIdx {
				ls = append(ls, CaixaSelecao.Render(pad(" "+marca+it.Rotulo, m.width)))
			} else {
				ls = append(ls, CaixaTexto.Render(pad(" "+marca+it.Rotulo, m.width)))
			}
		}
		return strings.Join(ls, "\n")

	case TelaRaioXUf, TelaFaixaUf:
		tit := " SELECIONE A UF "
		if m.tela == TelaFaixaUf {
			tit = " ANÁLISE POR FAIXA — SELECIONE O ESTADO (Brasil + 27 UFs) "
		}
		var ls []string
		ls = append(ls, CaixaTitulo.Render(pad(tit, m.width)))
		for i, u := range m.ufs {
			marca := "  "
			if i == m.ufIdx {
				marca = "> "
			}
			qtd := ""
			if m.tela == TelaFaixaUf || true {
				if c, ok := m.Snap.PorUF[u]; ok {
					qtd = fmt.Sprintf(" (%d ERBs)", c)
				}
			}
			if i == m.ufIdx {
				ls = append(ls, CaixaSelecao.Render(pad(" "+marca+u+qtd, m.width)))
			} else {
				ls = append(ls, CaixaTexto.Render(pad(" "+marca+u+qtd, m.width)))
			}
		}
		return strings.Join(ls, "\n")

	case TelaRaioXMun:
		var ls []string
		ls = append(ls, CaixaTitulo.Render(pad(fmt.Sprintf(" MUNICÍPIOS DA UF %s (%d) ", m.ufSel, len(m.municipios)), m.width)))
		ini := 0
		if m.munIdx >= 15 {
			ini = m.munIdx - 14
		}
		fim := ini + 15
		if fim > len(m.municipios) {
			fim = len(m.municipios)
		}
		cont := m.Snap.ContagemPorMunicipio(m.ufSel)
		for i := ini; i < fim; i++ {
			mun := m.municipios[i]
			qtd := cont[mun+"|"+m.ufSel]
			marca := "  "
			if i == m.munIdx {
				marca = "> "
			}
			line := pad(" "+marca+mun, m.width-12) + fmt.Sprintf("%5d", qtd)
			if i == m.munIdx {
				ls = append(ls, CaixaSelecao.Render(line))
			} else {
				ls = append(ls, CaixaTexto.Render(line))
			}
		}
		return strings.Join(ls, "\n")

	case TelaFaixaResultado:
		var ls []string
		ls = append(ls, CaixaTitulo.Render(pad(fmt.Sprintf(" ANÁLISE POR FAIXA — %s ", m.ufSel), m.width)))
		reg := m.Snap.FiltrarUF(m.munSel)
		ids := map[string]bool{}
		tem5g, temL, temH, temE := map[string]bool{}, map[string]bool{}, map[string]bool{}, map[string]bool{}
		for _, r := range reg {
			id := r.Operadora + "_" + r.Estacao
			ids[id] = true
			for _, t := range strings.Split(r.Tecs, ",") {
				switch strings.TrimSpace(t) {
				case "5":
					tem5g[id] = true
				case "L":
					temL[id] = true
				case "H":
					temH[id] = true
				case "E":
					temE[id] = true
				}
			}
		}
		total := len(ids)
		cont5, contL, contH, contE := len(tem5g), len(temL), len(temH), len(temE)
		ls = append(ls, CaixaTexto.Render(fmt.Sprintf(" ERBs distintas no escopo: %d", total)))
		barras := []struct {
			rot string
			v   int
		}{
			{"5G", cont5}, {"4G/LTE", contL}, {"3G/HSPA", contH}, {"2G/EDGE", contE},
		}
		for _, b := range barras {
			larg := 0
			if total > 0 {
				larg = b.v * 30 / total
			}
			if larg == 0 && b.v > 0 {
				larg = 1
			}
			barra := strings.Repeat("▰", larg)
			pct := float64(b.v) * 100 / float64(maxInt(1, total))
			ls = append(ls, CaixaVerde.Render(trunc(fmt.Sprintf("   %-8s ▰%-29s %8d (%4.1f%%)", b.rot, barra, b.v, pct), m.width)))
		}
		ls = append(ls, CaixaTexto.Render(" [Esc] voltar à lista de estados"))
		return strings.Join(ls, "\n")

	case TelaSobre:
		var ls []string
		ls = append(ls, CaixaTitulo.Render(pad(" SOBRE O SISTEMA / ESTATÍSTICAS ", m.width)))
		ls = append(ls, CaixaTexto.Render(fmt.Sprintf(" Data-base: %s | Gerado em: %s", m.Snap.DataBase, m.Snap.GeradoEm)))
		ls = append(ls, CaixaTexto.Render(fmt.Sprintf(" Total de ERBs: %d | Setores: %d", m.Snap.TotalErbs, m.Snap.TotalSetores)))
		ls = append(ls, CaixaAmarelo.Render(" Por tecnologia:"))
		for _, t := range data.ORDEMTEC {
			if c, ok := m.Snap.PorTecnologia[t]; ok {
				ls = append(ls, CaixaTexto.Render(fmt.Sprintf("   %-4s %-4s %8d ERBs", t, data.TECLabels[t], c)))
			}
		}
		ls = append(ls, CaixaVerde.Render(" Top operadoras:"))
		type kv struct {
			k string
			v int
		}
		var pares []kv
		for k, v := range m.Snap.PorOperadora {
			pares = append(pares, kv{k, v})
		}
		for i := 0; i < len(pares); i++ {
			for j := i + 1; j < len(pares); j++ {
				if pares[j].v > pares[i].v {
					pares[i], pares[j] = pares[j], pares[i]
				}
			}
		}
		estilos := []lipgloss.Style{CorOuro, CorPrata, CorBronze}
		for i := 0; i < 3 && i < len(pares); i++ {
			ls = append(ls, estilos[i].Render(fmt.Sprintf("   %dº %s — %d ERBs", i+1, pares[i].k, pares[i].v)))
		}
		ls = append(ls, CaixaTexto.Render(" [Esc] voltar"))
		return strings.Join(ls, "\n")

	case TelaBusca:
		var ls []string
		ls = append(ls, CaixaTitulo.Render(pad(" BUSCA GLOBAL (/) ", m.width)))
		ls = append(ls, CaixaTexto.Render(" Filtro: "+m.busca.View()))
		ls = append(ls, CaixaTexto.Render(fmt.Sprintf(" %d resultados (Enter detalha, Esc volta)", len(m.buscaRes))))
		ini := 0
		maxLinhas := m.height - 12
		if maxLinhas < 5 {
			maxLinhas = 5
		}
		if m.buscaIdx >= maxLinhas-1 {
			ini = m.buscaIdx - (maxLinhas - 2)
		}
		fim := ini + maxLinhas
		if fim > len(m.buscaRes) {
			fim = len(m.buscaRes)
		}
		for i := ini; i < fim; i++ {
			e := m.buscaRes[i]
			sinal := barraSinal(len(e.Tecs))
			line := pad(fmt.Sprintf("  %s/%s", e.UF, trunc(e.Municipio, 22)), 30) +
				pad(trunc(e.Operadora, 14), 16) +
				pad(data.FormatarListaTec(e.Tecs), 14) + sinal
			if i == m.buscaIdx {
				ls = append(ls, CaixaSelecao.Render(trunc(line, m.width)))
			} else {
				ls = append(ls, CaixaTexto.Render(trunc(line, m.width)))
			}
		}
		return strings.Join(ls, "\n")
	}
	return ""
}

func barraSinal(n int) string {
	if n >= 4 {
		return CaixaVerde.Render("▰▰▰▰")
	}
	if n == 3 {
		return CaixaVerde.Render("▰▰▰▱")
	}
	if n == 2 {
		return CaixaAmarelo.Render("▰▰▱▱")
	}
	return BarraErro.Render("▰▱▱▱")
}

func maxInt(a, b int) int {
	if a > b {
		return a
	}
	return b
}
