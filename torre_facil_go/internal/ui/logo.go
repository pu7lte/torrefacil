package ui

// Tela de logo (abertura) — portada 1:1 de torre_facil/tui/janelas.py::tela_logo.
// Arte em blocos sólidos (5 linhas) com degradê LOGO_AZUL -> LOGO_CIANO -> LOGO_VERDE,
// caixa com bordas ─│╭╮╰╯├┤ e subtítulos cinza, exatamente como o legado Python.

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/mattn/go-runewidth"
)

// logoArt é a arte ASCII do cabeçalho (mesma matriz de _LOGO_ART em janelas.py).
var logoArt = []string{
	"██████  █████  ██████  ██████  ██████     ██████  █████  ██████ ██ ██",
	"  ██   ██   ██ ██   ██ ██   ██ ██         ██     ██   ██ ██     ██ ██",
	"  ██   ██   ██ ██████  ██████  █████      █████  ███████ ██     ██ ██",
	"  ██   ██   ██ ██   ██ ██   ██ ██         ██     ██   ██ ██     ██ ██",
	"  ██    █████  ██   ██ ██   ██ ██████     ██     ██   ██ ██████ ██████",
}

// centralizar replica ajustar_texto_puro(txt, miolo, 'centro') do legado:
// preenche com espaços até a largura visual exata; trunca se não couber.
func centralizar(s string, w int) string {
	l := runewidth.StringWidth(s)
	if l > w {
		if w <= 1 {
			return ""
		}
		return runewidth.Truncate(s, w, "")
	}
	esq := (w - l) / 2
	return strings.Repeat(" ", esq) + s + strings.Repeat(" ", w-l-esq)
}

// linhaBorda desenha uma linha horizontal da caixa: ╭───╮ ├───┤ ╰───╯.
func linhaBorda(esq, dir string, n int) string {
	return CaixaBorda.Render(esq + strings.Repeat("─", n) + dir)
}

// bordaL/bordaR desenham os tubos laterais com a cor da borda do legado.
func bordaL() string { return CaixaBorda.Render("│ ") }
func bordaR() string { return CaixaBorda.Render(" │") }

// linhaVazia é o respiro interno "│ <espaços> │".
func linhaVazia(miolo int) string {
	return CaixaBorda.Render("│")+FundoDesktop.Render(strings.Repeat(" ", miolo))+CaixaBorda.Render("│")
}

// celulaBorda renderiza um trecho de conteúdo já com largura visual == w,
// mantendo os tubos da caixa na cor de borda e o miolo no estilo dado
// (equivalente ao f"{C.CAIXA_BORDA}│ {cor}{texto}{C.CAIXA_BORDA} │" do legado).
func celulaBorda(estilo lipgloss.Style, texto string, w int) string {
	return CaixaBorda.Render("│ ")+estilo.Render(texto)+CaixaBorda.Render(" │")
}

// viewLogo renderiza a tela de abertura persistente (sem menu superior),
// espelhando a composição de linhas de janelas.tela_logo.
func (m Model) viewLogo() string {
	largBox := m.width - 6
	if largBox > 74 {
		largBox = 74
	}
	if largBox < 30 {
		largBox = 30
	}
	miolo := largBox - 4 // conteúdo entre "│ " e " │"

	linhas := []string{
		linhaBorda("╭", "╮", largBox-2),
		// faixa superior: SISTEMA NACIONAL DE TELECOMUNICAÇÕES (fundo claro, como o topo legado)
		CaixaBorda.Render("│")+
			BarraStatusTopo.Width(largBox-2).Render(centralizar(" SISTEMA NACIONAL DE TELECOMUNICAÇÕES ", largBox-2))+
			CaixaBorda.Render("│"),
		linhaBorda("├", "┤", largBox-2),
		linhaVazia(miolo),
	}

	// 5 linhas da arte com degradê: 2 azuis, 2 ciano, 1 verde
	for i, arte := range logoArt {
		cor := LogoAzul
		if i >= 4 {
			cor = LogoVerde
		} else if i >= 2 {
			cor = LogoCiano
		}
		linhas = append(linhas, celulaBorda(cor, centralizar(arte, miolo), miolo))
	}

	linhas = append(linhas, linhaVazia(miolo))

	// subtítulos cinza
	linhas = append(linhas,
		celulaBorda(LogoCinza, centralizar("ENGENHARIA DE REDES MÓVEIS & ERBs ANATEL", miolo), miolo),
		celulaBorda(LogoCinza, centralizar("vibecoded by @vivohans  ::  Classic ERP Edition", miolo), miolo),
		linhaVazia(miolo),
		linhaBorda("├", "┤", largBox-2),
		// teclas de navegação
		celulaBorda(CaixaCiano, centralizar("[ENTER] Abrir o menu principal    [ESC] Ficar no logo    [X] Sair", miolo), miolo),
		linhaVazia(miolo),
	)

	// rodapé com dados da base (equivalente às duas últimas INFO lines do legado)
	base := fmt.Sprintf("Base: %s   |   snapshot Go (legado: ANATEL)", m.Snap.DataBase)
	ufs := len(m.Snap.PorUF)
	municipios := m.Snap.MunicipiosUnicos()
	stats := fmt.Sprintf("%s ERBs  |  %s municípios  |  %d UFs",
		milhar(m.Snap.TotalErbs), milhar(municipios), ufs)
	linhas = append(linhas,
		celulaBorda(CaixaTexto, centralizar(trunc(base, miolo), miolo), miolo),
		celulaBorda(CaixaTexto, centralizar(stats, miolo), miolo),
		linhaVazia(miolo),
		linhaBorda("╰", "╯", largBox-2),
	)

	// centraliza a caixa no terminal
	padLeft := (m.width - largBox) / 2
	if padLeft < 0 {
		padLeft = 0
	}

	out := make([]string, 0, len(linhas))
	for _, l := range linhas {
		right := m.width - padLeft - largBox
		if right < 0 {
			right = 0
		}
		out = append(out, FundoDesktop.Render(strings.Repeat(" ", padLeft))+l+FundoDesktop.Render(strings.Repeat(" ", right)))
	}
	return strings.Join(out, "\n")
}

// milhar formata número com separador "." como no legado pt-BR (1.234.567).
func milhar(n int) string {
	s := fmt.Sprintf("%d", n)
	var partes []string
	for len(s) > 3 {
		partes = append([]string{s[len(s)-3:]}, partes...)
		s = s[:len(s)-3]
	}
	partes = append([]string{s}, partes...)
	return strings.Join(partes, ".")
}

// RenderTelaParaTeste força dimensões e devolve o View() completo,
// permitindo inspeção do layout em testes sem terminal interativo.
func RenderTelaParaTeste(m Model, w, h int) string {
m.width, m.height = w, h
return m.View()
}
