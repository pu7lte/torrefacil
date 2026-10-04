package ui

// Port 1:1 de torre_facil/tui/menu_barra.py e tui/menus.py.
//
// A barra de menu replica exatamente o comportamento legado:
//   - montar_menus() escolhe os menus conforme o MODO/MÓDULO atual;
//   - renderizar_menu_superior_fixo() desenha a barra com hotkey destacada,
//     preenchendo a largura total da janela;
//   - o dropdown é um POPUP ANCORADO abaixo do nome do menu, com bordas
//     ╭─╮ │ ╰─╯, separadores ─┼─, atalhos à direita e rodapé com a dica;
//   - ←/→ troca de menu, ↑/↓ pula entre itens habilitados, Home/PgUp =
//     primeiro, End/PgDn = último, ENTER executa, ESC/F10 fecha,
//     ALT+letra alterna, tecla quente executa direto.

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	runewidth "github.com/mattn/go-runewidth"

	"github.com/torrefacil/torre-facil-go/internal/data"
)

func normalizarTexto(s string) string { return data.NormalizarTexto(s) }

// ---------------------------------------------------------------------------
// Tipos legados (_mi / menus)
// ---------------------------------------------------------------------------

type MiItem struct {
	Rotulo string
	Tecla  string
	Acao   string
	Atalho string
	Dica   string
	Sep    bool
}

type MiMenu struct {
	Nome  string
	Tecla string
	Itens []MiItem
}

func mi(rotulo, tecla, acao, atalho, dica string) MiItem {
	return MiItem{Rotulo: rotulo, Tecla: tecla, Acao: acao, Atalho: atalho, Dica: dica}
}

var sepItem = MiItem{Sep: true}

// ---------------------------------------------------------------------------
// montar_menus(): idêntico ao Python, adaptado aos modos loja/analista
// ---------------------------------------------------------------------------

func montarMenus(modo string, modulo string) []MiMenu {
	mArquivo := MiMenu{"Arquivo", "A", []MiItem{
		mi("Voltar / Fechar", "V", "BACK", "Esc", "Volta à tela anterior."),
		mi("Recarregar tela", "R", "REDRAW", "", "Redesenha a tela atual."),
	}}
	mEditar := MiMenu{"Editar", "E", []MiItem{
		mi("Limpar filtro", "L", "CLEAR", "", "Remove o filtro ao vivo."),
		mi("Limpar seleção", "S", "CLEAR_SELECTION", "", "Limpa seleções."),
	}}
	mCesta := MiMenu{"Cesta", "C", []MiItem{
		mi("Adicionar município", "A", "ADD", "F2", "Abre a lista."),
		mi("Top 5 da UF", "T", "TOP5", "T", "Cinco municípios com mais ERBs."),
		mi("Gerar comparação", "G", "GENERATE", "G", "Gera o comparativo."),
		sepItem,
		mi("Remover município", "R", "REMOVE", "R", "Remove o destacado."),
	}}
	mFiltro := MiMenu{"Filtro", "F", []MiItem{
		mi("Filtro ao vivo", "F", "FILTER", "", "Filtra conforme digita."),
		mi("Limpar filtro", "L", "CLEAR", "", "Remove o filtro atual."),
	}}
	mExibir := MiMenu{"Exibir", "X", []MiItem{
		mi("Primeiro registro", "P", "FIRST", "Home", "Vai ao primeiro."),
		mi("Último registro", "U", "LAST", "End", "Vai ao último."),
		sepItem,
		mi("Pódio completo", "D", "PODIO", "P", "Classificação completa."),
	}}
	mPesquisa := MiMenu{"Pesquisa", "P", []MiItem{
		mi("Pesquisa global", "P", "GLOBAL_SEARCH", "/", "Busca na base."),
	}}
	mNav := MiMenu{"Navegação", "N", []MiItem{
		mi("Primeiro registro", "P", "FIRST", "Home", "Vai ao primeiro."),
		mi("Último registro", "U", "LAST", "End", "Vai ao último."),
		sepItem,
		mi("Página anterior", "A", "PAGE_UP", "PgUp", "Rola acima."),
		mi("Próxima página", "X", "PAGE_DOWN", "PgDn", "Rola abaixo."),
	}}
	mAjuda := MiMenu{"Ajuda", "J", []MiItem{
		mi("Atalhos da tela", "A", "HELP", "", "Atalhos de teclado."),
		mi("Sobre o Sistema", "S", "ABOUT", "", "Info e estatísticas."),
	}}
	mFuncoes := MiMenu{"Funções", "U", []MiItem{}}
	if modo == "loja" {
		mFuncoes.Itens = []MiItem{
			mi("Consulta rápida", "C", "1", "", "Consulta por município."),
			mi("Comparador loja", "O", "2", "", "Compara cidades."),
			mi("Favoritos", "F", "3", "", "Municípios favoritos."),
			mi("FAQ", "Q", "4", "", "Perguntas frequentes."),
		}
	} else {
		mFuncoes.Itens = []MiItem{
			mi("Raio-X cidade", "R", "1", "", "Painel do município."),
			mi("Raio-X estado", "E", "2", "", "Ranking por UF."),
			mi("Exploradora", "P", "3", "", "Guia por operadora."),
			mi("Comparador", "M", "4", "", "Cidades lado a lado."),
			sepItem,
			mi("Faixas de frequência", "X", "A", "", "Brasil + 27 estados."),
			mi("Análise avançada", "V", "7", "", "Filtros combinados."),
			mi("Exportar KML", "K", "8", "", "Arquivo Google Earth."),
		}
	}

	mod := strings.ToUpper(normalizarTexto(modulo))
	switch {
	case strings.Contains(mod, "COMPARADOR"):
		return []MiMenu{mArquivo, mCesta, mExibir, mPesquisa, mNav, mAjuda}
	case strings.Contains(mod, "RAIO-X") || strings.Contains(mod, "OPERADORA"):
		return []MiMenu{mArquivo, mFiltro, mExibir, mPesquisa, mNav, mAjuda}
	default:
		return []MiMenu{mArquivo, mEditar, mFuncoes, mExibir, mPesquisa, mNav, mAjuda}
	}
}

func indiceMenuPorTecla(letra, modulo, modo string) int {
	l := strings.ToUpper(normalizarTexto(letra))
	for i, m := range montarMenus(modo, modulo) {
		if m.Tecla == l {
			return i
		}
	}
	return -1
}

func posicoesBarra(menus []MiMenu) [][2]int {
	pos := make([][2]int, 0, len(menus))
	x := 2
	for _, m := range menus {
		larg := runewidth.StringWidth(m.Nome) + 2
		pos = append(pos, [2]int{x, larg})
		x += larg + 1
	}
	return pos
}

// ---------------------------------------------------------------------------
// Barra superior (renderizar_menu_superior_fixo)
// ---------------------------------------------------------------------------

const resetANSI = "\x1b[0m"

const (
	ansiMenuBarra      = "\x1b[38;5;232;48;5;250m"
	ansiMenuBarraHot   = "\x1b[1;4;38;5;24;48;5;250m"
	ansiMenuBarraAtivo = "\x1b[1;38;5;231;48;5;232m"
	ansiItemAtivoHot   = "\x1b[1;4;38;5;231;48;5;232m"
)

func rotuloHotkey(texto, letra, corNormal, corHot string) string {
	if letra == "" {
		return corNormal + texto
	}
	pos := strings.Index(strings.ToUpper(texto), strings.ToUpper(letra))
	if pos < 0 {
		return corNormal + texto
	}
	return corNormal + texto[:pos] + corHot + texto[pos:pos+1] + corNormal + texto[pos+1:]
}

func renderizarBarraSuperior(larg int, modo, modulo string, categoriaAtiva int) string {
	menus := montarMenus(modo, modulo)
	var partes []string
	usado := 1
	for i, m := range menus {
		cor, hot := ansiMenuBarra, ansiMenuBarraHot
		if i == categoriaAtiva {
			cor, hot = ansiMenuBarraAtivo, ansiItemAtivoHot
		}
		partes = append(partes, fmt.Sprintf("%s %s%s ", cor,
			rotuloHotkey(m.Nome, m.Tecla, cor, hot), cor))
		usado += runewidth.StringWidth(m.Nome) + 3
	}
	dica := "X=Sair  F10=Menu  "
	sobra := larg - usado
	if sobra < 0 {
		sobra = 0
	}
	if sobra > runewidth.StringWidth(dica)+1 {
		partes = append(partes, strings.Repeat(" ", sobra-runewidth.StringWidth(dica))+ansiMenuBarra+dica)
	} else if sobra > 0 {
		partes = append(partes, strings.Repeat(" ", sobra))
	}
	return strings.Join(partes, "") + resetANSI
}

// ---------------------------------------------------------------------------
// Popup dropdown ancorado (menu_dropdown_ancorado_tui)
// ---------------------------------------------------------------------------

const (
	ansiMenuBorda   = "\x1b[1;38;5;252;48;5;17m"
	ansiMenuItem    = "\x1b[38;5;232;48;5;250m"
	ansiMenuItemHot = "\x1b[1;4;38;5;24;48;5;250m"
	ansiItemSel     = "\x1b[1;38;5;231;48;5;232m"
	ansiItemOff     = "\x1b[38;5;245;48;5;250m"
)

func linhaItemMenu(it MiItem, iw int, selecionado, habilitado bool) string {
	cor, hot := ansiMenuItem, ansiMenuItemHot
	switch {
	case selecionado:
		cor, hot = ansiItemSel, ansiItemSel
	case !habilitado:
		cor, hot = ansiItemOff, ansiItemOff
	}
	rot := it.Rotulo
	espaco := iw - 2 - runewidth.StringWidth(rot) - runewidth.StringWidth(it.Atalho)
	if espaco < 1 {
		espaco = 1
	}
	rotPintado := cor + rot
	if it.Tecla != "" {
		pos := strings.Index(strings.ToUpper(normalizarTexto(rot)), strings.ToUpper(it.Tecla))
		if pos >= 0 && pos < len(rot) {
			rotPintado = cor + rot[:pos] + hot + rot[pos:pos+1] + cor + rot[pos+1:]
		}
	}
	return ansiMenuBorda + "│" + cor + " " + rotPintado + cor +
		strings.Repeat(" ", espaco) + it.Atalho + " " + ansiMenuBorda + "│" + resetANSI
}

func montarLinhasDropdown(itens []MiItem, iw, idx int, habilitadas map[string]bool) []string {
	linhas := []string{ansiMenuBorda + "╭" + strings.Repeat("─", iw) + "╮" + resetANSI}
	for i, it := range itens {
		if it.Sep {
			linhas = append(linhas, ansiMenuBorda+"├"+strings.Repeat("─", iw)+"┤"+resetANSI)
			continue
		}
		linhas = append(linhas, linhaItemMenu(it, iw, i == idx, itemHabilitado(it, habilitadas)))
	}
	linhas = append(linhas, ansiMenuBorda+"╰"+strings.Repeat("─", iw)+"╯"+resetANSI)
	return linhas
}

func itemHabilitado(it MiItem, habilitadas map[string]bool) bool {
	if it.Sep {
		return false
	}
	if habilitadas == nil {
		return true
	}
	return habilitadas[it.Acao]
}

func primeiroHabilitado(itens []MiItem, hab map[string]bool) int {
	for i, it := range itens {
		if itemHabilitado(it, hab) {
			return i
		}
	}
	return -1
}

func ultimoHabilitado(itens []MiItem, hab map[string]bool) int {
	for i := len(itens) - 1; i >= 0; i-- {
		if itemHabilitado(itens[i], hab) {
			return i
		}
	}
	return -1
}

func vizinhoHabilitado(itens []MiItem, hab map[string]bool, atual, passo int) int {
	i := atual
	for range itens {
		i = (i + passo + len(itens)) % len(itens)
		if itemHabilitado(itens[i], hab) {
			return i
		}
	}
	return atual
}

// ---------------------------------------------------------------------------
// Integração com o Model
// ---------------------------------------------------------------------------

func (m *Model) abrirDropdown(cat int) {
	menus := montarMenus(string(m.modo), m.moduloAtual())
	if len(menus) == 0 {
		return
	}
	if cat < 0 {
		cat = 0
	}
	if cat >= len(menus) {
		cat = len(menus) - 1
	}
	m.barraVisivel = true
	m.barraAberta = cat
	m.barraItem = primeiroHabilitado(menus[cat].Itens, m.acoesHabilitadas())
}

func (m Model) moduloAtual() string {
	switch m.tela {
	case TelaComparador:
		return "COMPARADOR"
	case TelaPainel, TelaListaErbs, TelaBusca, TelaRaioXUf, TelaRaioXMun:
		return "RAIO-X"
	default:
		return ""
	}
}

func (m Model) acoesHabilitadas() map[string]bool {
	basicas := map[string]bool{
		"GLOBAL_SEARCH": true, "HELP": true, "ABOUT": true, "CLOSE": true,
		"REDRAW": true, "FIRST": true, "LAST": true,
		"BACK": true, "PAGE_UP": true, "PAGE_DOWN": true,
		"CLEAR": true, "CLEAR_SELECTION": true, "FILTER": true, "PODIO": true,
		"ADD": true, "TOP5": true, "GENERATE": true, "REMOVE": true,
	}
	for _, a := range []string{"1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "A", "R", "I", "S"} {
		basicas[a] = true
	}
	return basicas
}

// teclaBarra replica _tratar_tecla_menu(); handled=true quando consumida.
func (m Model) teclaBarra(k tea.KeyMsg) (tea.Model, tea.Cmd, bool) {
	menus := montarMenus(string(m.modo), m.moduloAtual())
	hab := m.acoesHabilitadas()
	cat, idx := m.barraAberta, m.barraItem
	if cat >= len(menus) {
		m.barraAberta = 0
		return m, nil, true
	}
	itens := menus[cat].Itens

	fechar := func() (tea.Model, tea.Cmd, bool) {
		m.barraAberta = -1
		m.msgRodape = "Menu fechado."
		return m, nil, true
	}

	switch k.Type {
	case tea.KeyEscape, tea.KeyF10:
		return fechar()
	case tea.KeyLeft:
		nova := (cat - 1 + len(menus)) % len(menus)
		m.barraAberta = nova
		m.barraItem = primeiroHabilitado(menus[nova].Itens, hab)
		return m, nil, true
	case tea.KeyRight:
		nova := (cat + 1) % len(menus)
		m.barraAberta = nova
		m.barraItem = primeiroHabilitado(menus[nova].Itens, hab)
		return m, nil, true
	case tea.KeyUp:
		m.barraItem = vizinhoHabilitado(itens, hab, idx, -1)
		return m, nil, true
	case tea.KeyDown:
		m.barraItem = vizinhoHabilitado(itens, hab, idx, +1)
		return m, nil, true
	case tea.KeyHome, tea.KeyPgUp:
		m.barraItem = primeiroHabilitado(itens, hab)
		return m, nil, true
	case tea.KeyEnd, tea.KeyPgDown:
		m.barraItem = ultimoHabilitado(itens, hab)
		return m, nil, true
	case tea.KeyEnter:
		if idx >= 0 && itemHabilitado(itens[idx], hab) {
			acao := itens[idx].Acao
			m.barraAberta = -1
			nm, cmd := m.executar(acao)
			return nm, cmd, true
		}
		return m, nil, true
	}

	if k.Alt && len(k.String()) == 1 {
		novo := indiceMenuPorTecla(k.String(), m.moduloAtual(), string(m.modo))
		if novo >= 0 {
			if novo == cat {
				return fechar()
			}
			m.barraAberta = novo
			m.barraItem = primeiroHabilitado(menus[novo].Itens, hab)
			return m, nil, true
		}
	}

	if len(k.String()) == 1 && k.Type != tea.KeyRunes || len(k.String()) == 1 && k.Type == tea.KeyRunes {
		letra := strings.ToUpper(normalizarTexto(k.String()))
		for _, it := range itens {
			if itemHabilitado(it, hab) && strings.EqualFold(it.Tecla, letra) {
				m.barraAberta = -1
				nm, cmd := m.executar(it.Acao)
				return nm, cmd, true
			}
		}
	}
	return m, nil, false
}

// ---------------------------------------------------------------------------
// Renderização
// ---------------------------------------------------------------------------

func (m Model) viewBarraPortada() string {
	return renderizarBarraSuperior(m.width, string(m.modo), m.moduloAtual(), m.barraAberta)
}

func (m Model) viewDropdownAncorado() string {
	if m.barraAberta < 0 {
		return ""
	}
	menus := montarMenus(string(m.modo), m.moduloAtual())
	if m.barraAberta >= len(menus) {
		return ""
	}
	itens := menus[m.barraAberta].Itens

	iw := 22
	for _, it := range itens {
		if it.Sep {
			continue
		}
		l := runewidth.StringWidth(it.Rotulo)
		if it.Atalho != "" {
			l += runewidth.StringWidth(it.Atalho) + 3
		}
		if l+2 > iw {
			iw = l + 2
		}
	}
	linhas := montarLinhasDropdown(itens, iw, m.barraItem, m.acoesHabilitadas())
	largBox := iw + 2

	posX := posicoesBarra(menus)[m.barraAberta][0]
	if posX > m.width-largBox-2 {
		posX = m.width - largBox - 2
	}
	if posX < 1 {
		posX = 1
	}

	padEsq := strings.Repeat(" ", posX-1)
	var b strings.Builder
	for i, ln := range linhas {
		if i == 0 {
			b.WriteString(padEsq + ln)
		} else {
			b.WriteString("\n" + padEsq + ln)
		}
	}
	idx := m.barraItem
	dica := ""
	if idx >= 0 && idx < len(itens) {
		dica = itens[idx].Dica
	}
	if dica == "" {
		dica = "←/→ Menu   ↑/↓ Item   ENTER Executa   ESC Fecha"
	}
	rodape := fmt.Sprintf("%s %s%s", ansiMenuBarra, trunc(" "+dica, m.width-2), resetANSI)
	b.WriteString("\n" + rodape)
	return b.String()
}
