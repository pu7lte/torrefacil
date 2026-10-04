// Package ui contém a TUI em Go (Bubble Tea), equivalente ao torre_facil/tui.
package ui

import (
	"fmt"

	"github.com/charmbracelet/lipgloss"
)

// c256 converte um índice ANSI-256 para lipgloss.Color.
func c256(i int) lipgloss.TerminalColor {
	return lipgloss.Color(fmt.Sprintf("%d", i))
}

// Paleta "classic" (Classic ERP) — portada 1:1 de torre_facil/tui/cores.py.
var (
	// Topo / barras
	BarraStatusTopo = lipgloss.NewStyle().Foreground(c256(232)).Background(c256(250))
	BarraSubTopo    = lipgloss.NewStyle().Bold(true).Foreground(c256(231)).Background(c256(24))
	FundoDesktop    = lipgloss.NewStyle().Foreground(c256(252)).Background(c256(17))

	// Caixas/janelas
	CaixaBorda   = lipgloss.NewStyle().Bold(true).Foreground(c256(252)).Background(c256(17))
	CaixaTitulo  = lipgloss.NewStyle().Bold(true).Foreground(c256(231)).Background(c256(17))
	CaixaTexto   = lipgloss.NewStyle().Foreground(c256(253)).Background(c256(17))
	CaixaCiano   = lipgloss.NewStyle().Bold(true).Foreground(c256(159)).Background(c256(17))
	CaixaVerde   = lipgloss.NewStyle().Bold(true).Foreground(c256(120)).Background(c256(17))
	CaixaAmarelo = lipgloss.NewStyle().Bold(true).Foreground(c256(227)).Background(c256(17))
	CaixaSelecao = lipgloss.NewStyle().Bold(true).Foreground(c256(232)).Background(c256(250))

	// Logo (degradê da tela de abertura — portado de cores.py: LOGO_AZUL/CIANO/VERDE/CINZA)
	LogoAzul  = lipgloss.NewStyle().Bold(true).Foreground(c256(117)).Background(c256(17))
	LogoCiano = lipgloss.NewStyle().Bold(true).Foreground(c256(159)).Background(c256(17))
	LogoVerde = lipgloss.NewStyle().Bold(true).Foreground(c256(120)).Background(c256(17))
	LogoCinza = lipgloss.NewStyle().Foreground(c256(246)).Background(c256(17))

	// Alertas
	BarraAlerta = lipgloss.NewStyle().Bold(true).Foreground(c256(232)).Background(c256(222))
	BarraVerde  = lipgloss.NewStyle().Bold(true).Foreground(c256(232)).Background(c256(120))
	BarraErro   = lipgloss.NewStyle().Bold(true).Foreground(c256(231)).Background(c256(124))

	// Pódio
	CorOuro   = lipgloss.NewStyle().Bold(true).Foreground(c256(220)).Background(c256(17))
	CorPrata  = lipgloss.NewStyle().Bold(true).Foreground(c256(253)).Background(c256(17))
	CorBronze = lipgloss.NewStyle().Bold(true).Foreground(c256(215)).Background(c256(17))
	CorDemais = lipgloss.NewStyle().Foreground(c256(250)).Background(c256(17))

	// Barra de menu
	MenuBarra      = lipgloss.NewStyle().Inline(true).Foreground(c256(232)).Background(c256(250))
	MenuBarraHot   = lipgloss.NewStyle().Bold(true).Underline(true).Foreground(c256(24)).Background(c256(250))
	MenuBarraAtivo = lipgloss.NewStyle().Bold(true).Foreground(c256(231)).Background(c256(232))
	MenuItem       = lipgloss.NewStyle().Inline(true).Foreground(c256(232)).Background(c256(250))
	MenuItemSel    = lipgloss.NewStyle().Inline(true).Bold(true).Foreground(c256(231)).Background(c256(24))
)
