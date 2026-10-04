package ui

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
)

// CampoForm replica os campos do formulario_tui legado: texto livre ou droplist.
type CampoForm struct {
	Nome    string
	Rotulo  string
	Droplist bool
	Opcoes  []Opcao // pares rotulo/valor
	Fecha   bool    // true = não abre lista ao digitar, só ←/→/Espaço
}

// Opcao é um par (valor, rótulo) como no Python.
type Opcao struct {
	Valor, Rotulo string
}

// FormModel é a tela de formulário com ↑/↓ entre campos e ←/→ nas droplists.
type FormModel struct {
	Titulo     string
	Instrucoes string
	Campos     []CampoForm
	vals       []int      // índice da opção selecionada (droplist)
	textos     []textinput.Model
	campoAtual int
	listaAberta bool
	F12Ativo   bool
}

func NovoForm(titulo string, campos []CampoForm) *FormModel {
	f := &FormModel{Titulo: titulo, Campos: campos, vals: make([]int, len(campos)),
		textos: make([]textinput.Model, len(campos))}
	for i := range campos {
		ti := textinput.New()
		ti.Prompt = ""
		ti.CharLimit = 40
		f.textos[i] = ti
	}
	return f
}

func (f *FormModel) Valor(i int) string {
	c := f.Campos[i]
	if c.Droplist {
		v := f.vals[i]
		if v >= 0 && v < len(c.Opcoes) {
			return c.Opcoes[v].Valor
		}
		return ""
	}
	return strings.TrimSpace(f.textos[i].Value())
}

func (f *FormModel) focar(i int) {
	for j := range f.textos {
		if j == i && !f.Campos[j].Droplist {
			f.textos[j].Focus()
		} else {
			f.textos[j].Blur()
		}
	}
	f.campoAtual = i
	f.listaAberta = false
}

func (f *FormModel) Update(k tea.KeyMsg) (done bool, cancel bool, cmd tea.Cmd) {
	i := f.campoAtual
	c := f.Campos[i]
	if k.Type == tea.KeyF12 {
		f.F12Ativo = !f.F12Ativo
		return false, false, nil
	}
	switch k.Type {
	case tea.KeyEscape:
		if f.listaAberta {
			f.listaAberta = false
			return false, false, nil
		}
		return true, true, nil
	case tea.KeyEnter, tea.KeyTab:
		if i+1 < len(f.Campos) {
			f.focar(i + 1)
		} else {
			return true, false, nil
		}
	case tea.KeyShiftTab:
		if i > 0 {
			f.focar(i - 1)
		}
	case tea.KeyUp:
		if i > 0 {
			f.focar(i - 1)
		}
	case tea.KeyDown:
		if i+1 < len(f.Campos) {
			f.focar(i + 1)
		}
	case tea.KeyLeft:
		if c.Droplist && f.vals[i] > 0 {
			f.vals[i]--
		}
	case tea.KeyRight:
		if c.Droplist && f.vals[i] < len(c.Opcoes)-1 {
			f.vals[i]++
		}
	case tea.KeySpace:
		if c.Droplist {
			f.listaAberta = !f.listaAberta
		} else {
			var cc tea.Cmd
			f.textos[i], cc = f.textos[i].Update(k)
			cmd = cc
		}
	default:
		if c.Droplist {
			// digitação seleciona opção que comece com o texto
			prefixo := strings.ToUpper(k.String())
			for j, o := range c.Opcoes {
				if strings.HasPrefix(strings.ToUpper(o.Rotulo), prefixo) {
					f.vals[i] = j
					break
				}
			}
		} else {
			var cc tea.Cmd
			f.textos[i], cc = f.textos[i].Update(k)
			cmd = cc
		}
	}
	return false, false, cmd
}

func (f *FormModel) View(width int) string {
	var ls []string
	ls = append(ls, CaixaTitulo.Render(pad(trunc(" "+f.Titulo+" ", width), width)))
	if f.Instrucoes != "" {
		ls = append(ls, CaixaTexto.Render(trunc(" "+f.Instrucoes, width)))
	}
	for i, c := range f.Campos {
		marca := "  "
		st := CaixaTexto
		if i == f.campoAtual {
			marca = "> "
			st = CaixaSelecao
		}
		valor := "?"
		if c.Droplist {
			v := f.vals[i]
			if v >= 0 && v < len(c.Opcoes) {
				valor = c.Opcoes[v].Rotulo
			} else {
				valor = "(nenhum)"
			}
		} else {
			valor = f.textos[i].View()
		}
		ls = append(ls, st.Render(pad(fmt.Sprintf(" %s%-34s %s", marca, c.Rotulo, valor), width)))
		if c.Droplist && f.listaAberta && i == f.campoAtual {
			for j, o := range c.Opcoes {
				sel := "   "
				stl := CaixaTexto
				if j == f.vals[i] {
					sel = " > "
					stl = CaixaSelecao
				}
				ls = append(ls, stl.Render(trunc(sel+o.Rotulo, width)))
			}
		}
	}
	ls = append(ls, CaixaCiano.Render(trunc(" ↑/↓ campo | ←/→ ou Espaço: lista | Enter: confirmar | Esc: cancelar", width)))
	return strings.Join(ls, "\n")
}
