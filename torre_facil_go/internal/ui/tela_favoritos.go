package ui

import (
	"fmt"

	tea "github.com/charmbracelet/bubbletea"
)

// abrirFavoritos — espelho 1:1 de modulos/favoritos.py (lista de endereços
// salvos em dados/torre_facil_config.json, compartilhado com o Python).
func (m *Model) abrirFavoritos() {
	m.listaTit = "FAVORITOS"
	m.listaRegs = nil // favoritos não são ERBs; exibidos como linhas próprias
	m.favIdx = 0
	m.tela = TelaListaErbs
	m.msgRodape = "ENTER abre busca do favorito · ESC volta ao menu."
}

// teclaFavoritos trata navegação quando a lista exibida é de favoritos.
func (m Model) teclaFavoritos(k tea.KeyMsg) (tea.Model, tea.Cmd) {
	favs := CarregarFavoritos()
	n := len(favs)
	if n == 0 {
		if k.Type == tea.KeyEscape {
			m.tela = TelaMenu
		}
		return m, nil
	}
	switch k.Type {
	case tea.KeyEscape:
		m.tela = TelaMenu
	case tea.KeyUp:
		m.favIdx = (m.favIdx - 1 + n) % n
	case tea.KeyDown:
		m.favIdx = (m.favIdx + 1) % n
	case tea.KeyEnter:
		f := favs[m.favIdx]
		m.tela = TelaBusca
		m.busca.SetValue(NormalizarParaBusca(f.Endereco))
		m.atualizarBusca()
		m.msgRodape = fmt.Sprintf("Busca do favorito: %s", f.Apelido)
	}
	return m, nil
}

// NormalizarParaBusca prepara o texto digitável do endereço.
func NormalizarParaBusca(s string) string {
	return s
}

var _ = key.IsPressed
