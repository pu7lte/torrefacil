package ui

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
)

// Lista é uma tela genérica de lista navegável (↑/↓, PgUp/PgDn, Home/End,
// Enter seleciona, Esc volta). Replica o comportamento do navegador_tui legado.
type Lista struct {
	Titulo    string
	Itens     []string       // rótulos exibidos
	Dados     []string       // valores retornados no Enter (mesmo índice)
	Idx       int
	Scroll    int
	Pagina    func(m *Model) string // conteúdo dinâmico por item (opcional)
	AoSelecionar func(m *Model, dado string, idx int) (tea.Model, tea.Cmd)
	Voltar    func(m *Model) (tea.Model, tea.Cmd)
	Rodape    string
}

const linhasVisiveis = 15

func (l *Lista) mover(m *Model, passo int) {
	n := len(l.Itens)
	if n == 0 {
		return
	}
	l.Idx = (l.Idx + passo + n) % n
	l.ajustarScroll()
}

func (l *Lista) ajustarScroll() {
	if l.Idx < l.Scroll {
		l.Scroll = l.Idx
	}
	if l.Idx >= l.Scroll+linhasVisiveis {
		l.Scroll = l.Idx - linhasVisiveis + 1
	}
}

func (l *Lista) Update(m *Model, k tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch k.Type {
	case tea.KeyEscape:
		if l.Voltar != nil {
			return l.Voltar(m)
		}
		m.tela = TelaMenu
		return m, nil
	case tea.KeyUp:
		l.mover(m, -1)
	case tea.KeyDown:
		l.mover(m, +1)
	case tea.KeyPgUp:
		l.mover(m, -linhasVisiveis)
	case tea.KeyPgDown:
		l.mover(m, +linhasVisiveis)
	case tea.KeyHome:
		l.Idx, l.Scroll = 0, 0
	case tea.KeyEnd:
		l.Idx = len(l.Itens) - 1
		l.ajustarScroll()
	case tea.KeyEnter:
		if l.AoSelecionar != nil && len(l.Dados) > l.Idx {
			return l.AoSelecionar(m, l.Dados[l.Idx], l.Idx)
		}
	}
	return m, nil
}

func (l *Lista) View(m *Model) string {
	var ls []string
	tit := l.Titulo
	if n := len(l.Itens); n > 0 {
		tit = fmt.Sprintf(" %s (%d) ", tit, n)
	} else {
		tit = " " + tit + " "
	}
	ls = append(ls, CaixaTitulo.Render(pad(trunc(tit, m.width), m.width)))
	fim := l.Scroll + linhasVisiveis
	if fim > len(l.Itens) {
		fim = len(l.Itens)
	}
	for i := l.Scroll; i < fim; i++ {
		marca := "  "
		if i == l.Idx {
			marca = "> "
		}
		line := pad(" "+marca+l.Itens[i], m.width)
		if i == l.Idx {
			ls = append(ls, CaixaSelecao.Render(trunc(line, m.width)))
		} else {
			ls = append(ls, CaixaTexto.Render(trunc(line, m.width)))
		}
	}
	if l.Rodape != "" {
		ls = append(ls, CaixaTexto.Render(trunc(" "+l.Rodape, m.width)))
	}
	return strings.Join(ls, "\n")
}
