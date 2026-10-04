package ui

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/mattn/go-runewidth"

	"github.com/torrefacil/torre-facil-go/internal/data"
)

// ---------------------------------------------------------------------------
// Formulários de fluxo (consulta rápida / comparador loja / chips / avançada /
// explorador / kml) — máquina de estados por tela, como formulario_tui legado.
// ---------------------------------------------------------------------------

func (m *Model) abrirFormConsulta(acao string) {
	campos := []CampoForm{
		{Nome: "uf", Rotulo: "Estado / UF", Droplist: true, Opcoes: opcoesUF(m.Snap, "QUALQUER UF")},
		{Nome: "municipio", Rotulo: "Município"},
	}
	f := NovoForm("CONSULTA RÁPIDA POR LOCALIDADE", campos)
	f.Instrucoes = "Selecione a UF (←/→) e digite o município:"
	m.form = f
	m.formAcao = "consulta:" + acao
	m.tela = TelaForm
}

func (m *Model) abrirFormComparadorLoja(acao string) {
	campos := []CampoForm{
		{Nome: "uf", Rotulo: "Estado / UF", Droplist: true, Opcoes: opcoesUF(m.Snap, "QUALQUER UF")},
		{Nome: "cidade_a", Rotulo: "Cidade A"},
		{Nome: "cidade_b", Rotulo: "Cidade B"},
	}
	f := NovoForm("COMPARADOR DE OPERADORAS (LOJA)", campos)
	f.Instrucoes = "Informe as duas cidades para comparar:"
	m.form = f
	m.formAcao = "comparador_loja:" + acao
	m.tela = TelaForm
}

func (m *Model) abrirFormChips() {
	campos := []CampoForm{
		{Nome: "uf", Rotulo: "Estado / UF", Droplist: true, Opcoes: opcoesUF(m.Snap, "QUALQUER UF")},
		{Nome: "municipio", Rotulo: "Município de Uso"},
		{Nome: "perfil", Rotulo: "Perfil de Uso Principal", Droplist: true, Opcoes: []Opcao{
			{"1", "1. Máxima Velocidade / 5G / Streaming"},
			{"2", "2. Uso Geral / Equilíbrio no Dia a Dia"},
			{"3", "3. Interior / Alcance / Zona Rural / Voz"},
		}},
	}
	f := NovoForm("CONSULTOR / INDICADOR DE CHIP", campos)
	f.Instrucoes = "Selecione o local e o seu Perfil de Uso:"
	m.form = f
	m.formAcao = "chips"
	m.tela = TelaForm
}

func (m *Model) abrirFormAvancada() {
	campos := []CampoForm{
		{Nome: "uf", Rotulo: "1. Estado/UF", Droplist: true, Opcoes: opcoesUF(m.Snap, "TODOS OS ESTADOS (BRASIL)")},
		{Nome: "municipio", Rotulo: "2. Município(s)"},
		{Nome: "operadora", Rotulo: "3. Filtro de Operadora", Droplist: true, Opcoes: []Opcao{
			{"", "TODAS AS OPERADORAS"}, {"1", "APENAS GRANDES (CLARO / VIVO / TIM)"},
			{"VIVO", "VIVO"}, {"CLARO", "CLARO"}, {"TIM", "TIM"},
			{"BRISANET", "BRISANET"}, {"ALGAR", "ALGAR"}, {"UNIFIQUE", "UNIFIQUE"},
		}},
		{Nome: "tecnologia", Rotulo: "4. Tecnologia Exigida", Droplist: true, Opcoes: []Opcao{
			{"", "QUALQUER TECNOLOGIA"}, {"5", "5G ATIVO (NR)"}, {"L", "4G ATIVO (LTE)"},
			{"H", "3G ATIVO (HSPA/WCDMA)"}, {"E", "2G ATIVO (GSM/EDGE)"},
		}},
		{Nome: "qtd_erbs", Rotulo: "5. Nº ERBs na Cidade", Droplist: true, Opcoes: []Opcao{
			{"", "QUALQUER QUANTIDADE"}, {"1", "EXATAMENTE 1 ERB NA CIDADE (= 1)"},
			{"<=2", "ATÉ 2 ERBs NA CIDADE (<= 2)"}, {"<=3", "ATÉ 3 ERBs NA CIDADE (<= 3)"},
			{"<=5", "ATÉ 5 ERBs NA CIDADE (<= 5)"}, {">=5", "5 OU MAIS ERBs (>= 5)"},
			{">=10", "10 OU MAIS ERBs (>= 10)"}, {">=50", "50 OU MAIS ERBs (>= 50)"},
		}},
		{Nome: "unica_op", Rotulo: "6. Operadora Única", Droplist: true, Opcoes: []Opcao{
			{"N", "NÃO (QUALQUER CIDADE)"}, {"S", "SIM (APENAS 1 OPERADORA NA CIDADE)"},
		}},
	}
	f := NovoForm("PESQUISA AVANÇADA PARAMETRIZADA", campos)
	f.Instrucoes = "Use ←/→ ou ESPAÇO nas Droplists e ↑/↓ para mudar de campo:"
	m.form = f
	m.formAcao = "avancada"
	m.tela = TelaForm
}

func (m *Model) abrirFormExplorador() {
	campos := []CampoForm{
		{Nome: "operadora", Rotulo: "1. Operadora", Droplist: true, Opcoes: opcoesOperadoras(m.Snap)},
		{Nome: "uf", Rotulo: "2. Estado/UF", Droplist: true, Opcoes: opcoesUF(m.Snap, "TODAS AS UFs")},
		{Nome: "tecnologia", Rotulo: "3. Tecnologia", Droplist: true, Opcoes: []Opcao{
			{"", "QUALQUER"}, {"5", "5G"}, {"L", "4G/LTE"}, {"H", "3G/HSPA"}, {"E", "2G/GSM"},
		}},
	}
	f := NovoForm("EXPLORADOR GUIADO POR OPERADORA", campos)
	f.Instrucoes = "Passo 1-3: escolha operadora, UF e tecnologia; depois navegue os municípios."
	m.form = f
	m.formAcao = "explorador"
	m.tela = TelaForm
}

func (m *Model) abrirFormKML() {
	campos := []CampoForm{
		{Nome: "uf", Rotulo: "Estado / UF", Droplist: true, Opcoes: opcoesUF(m.Snap, "QUALQUER UF")},
		{Nome: "municipio", Rotulo: "Município"},
	}
	f := NovoForm("EXPORTAR MAPA GOOGLE EARTH (.kml)", campos)
	f.Instrucoes = "O KML será gravado com todas as ERBs do município selecionado."
	m.form = f
	m.formAcao = "kml"
	m.tela = TelaForm
}

func (m *Model) abrirFormRaioX() {
	campos := []CampoForm{
		{Nome: "uf", Rotulo: "Estado / UF", Droplist: true, Opcoes: opcoesUF(m.Snap, "QUALQUER UF (BRASIL)")},
		{Nome: "municipio", Rotulo: "Nome do Município"},
	}
	f := NovoForm("RAIO-X DE CIDADE E BAIRROS", campos)
	f.Instrucoes = "Selecione a UF e informe/escolha o Município:"
	m.form = f
	m.formAcao = "raiox"
	m.tela = TelaForm
}

func opcoesUF(s *data.Snapshot, todosLabel string) []Opcao {
	out := []Opcao{{"", todosLabel}}
	for _, uf := range s.UFs() {
		out = append(out, Opcao{uf, fmt.Sprintf("%s (%d ERBs)", uf, s.PorUF[uf])})
	}
	return out
}

func opcoesOperadoras(s *data.Snapshot) []Opcao {
	out := []Opcao{{"", "TODAS AS OPERADORAS"}}
	for _, o := range s.Operadoras() {
		out = append(out, Opcao{o, fmt.Sprintf("%s (%d ERBs)", o, s.PorOperadora[o])})
	}
	return out
}

func visualWidth(s string) int { return runewidth.StringWidth(s) }

// pós-formulário: executa a ação conforme formAcao
func (m Model) posFormulario() (tea.Model, tea.Cmd) {
	f := m.form
	val := func(nome string) string {
		for i, c := range f.Campos {
			if c.Nome == nome {
				return f.Valor(i)
			}
		}
		return ""
	}
	uf, mun := val("uf"), data.NormalizarTexto(val("municipio"))
	switch {
	case strings.HasPrefix(m.formAcao, "raiox"), strings.HasPrefix(m.formAcao, "consulta:"):
		var regs []data.Erb
		for _, r := range m.Snap.Registros {
			if uf != "" && r.UF != uf {
				continue
			}
			if mun != "" && data.NormalizarTexto(r.Municipio) != mun {
				continue
			}
			regs = append(regs, r)
		}
		if len(regs) == 0 {
			m.msgRodape = "Nenhum resultado para o recorte informado."
			m.tela = TelaMenu
			return m, nil
		}
		nome := mun
		if nome == "" {
			nome = "UF " + uf
		}
		m.abrirPainel(regs, strings.ToUpper(nome), uf, "")
		m.painelVoltar = TelaMenu
	case strings.HasPrefix(m.formAcao, "comparador_loja:"):
		a, b := val("cidade_a"), val("cidade_b")
		if a == "" || b == "" {
			m.msgRodape = "Informe as duas cidades."
			m.tela = TelaMenu
			return m, nil
		}
		m.abrirComparador([][2]string{{strings.ToUpper(a), uf}, {strings.ToUpper(b), uf}})
	case m.formAcao == "chips":
		var regs []data.Erb
		for _, r := range m.Snap.Registros {
			if uf != "" && r.UF != uf {
				continue
			}
			if mun != "" && data.NormalizarTexto(r.Municipio) != mun {
				continue
			}
			regs = append(regs, r)
		}
		escopo := mun
		if escopo == "" {
			escopo = "ESTADO " + uf
		}
		m.abrirChips(regs, strings.ToUpper(escopo))
	case m.formAcao == "avancada":
		op := val("operadora")
		if op == "1" {
			op = "" // grandes tratado abaixo
		}
		var regs []data.Erb
		grandes := map[string]bool{"CLARO": true, "VIVO": true, "TIM": true}
		for _, r := range m.Snap.Registros {
			if uf != "" && r.UF != uf {
				continue
			}
			if mun != "" && data.NormalizarTexto(r.Municipio) != mun {
				continue
			}
			if val("operadora") == "1" && !grandes[r.Operadora] {
				continue
			}
			if op != "" && !strings.Contains(strings.ToUpper(r.Operadora), strings.ToUpper(op)) {
				continue
			}
			if t := val("tecnologia"); t != "" && !r.TemTec(t) {
				continue
			}
			regs = append(regs, r)
		}
		// filtro de quantidade por cidade
		if q := val("qtd_erbs"); q != "" {
			porCidade := map[string]int{}
			chaves := map[string]map[string]bool{}
			for _, r := range regs {
				k := r.Municipio + "|" + r.UF
				if chaves[k] == nil {
					chaves[k] = map[string]bool{}
				}
				if !chaves[k][r.Chave()] {
					chaves[k][r.Chave()] = true
					porCidade[k]++
				}
			}
			ok := func(n int) bool {
				switch q {
				case "1":
					return n == 1
				case "<=2":
					return n <= 2
				case "<=3":
					return n <= 3
				case "<=5":
					return n <= 5
				case ">=5":
					return n >= 5
				case ">=10":
					return n >= 10
				case ">=50":
					return n >= 50
				}
				return true
			}
			var out []data.Erb
			for _, r := range regs {
				if ok(porCidade[r.Municipio+"|"+r.UF]) {
					out = append(out, r)
				}
			}
			regs = out
		}
		if val("unica_op") == "S" {
			opsPorCidade := map[string]map[string]bool{}
			for _, r := range regs {
				k := r.Municipio + "|" + r.UF
				if opsPorCidade[k] == nil {
					opsPorCidade[k] = map[string]bool{}
				}
				opsPorCidade[k][r.Operadora] = true
			}
			var out []data.Erb
			for _, r := range regs {
				if len(opsPorCidade[r.Municipio+"|"+r.UF]) == 1 {
					out = append(out, r)
				}
			}
			regs = out
		}
		m.abrirListaERBs(fmt.Sprintf("PESQUISA AVANÇADA — %d registros", len(regs)), dedup(regs), TelaMenu)
	case m.formAcao == "explorador":
		op := val("operadora")
		t := val("tecnologia")
		var regs []data.Erb
		for _, r := range m.Snap.Registros {
			if op != "" && !strings.EqualFold(r.Operadora, op) {
				continue
			}
			if uf != "" && r.UF != uf {
				continue
			}
			if t != "" && !r.TemTec(t) {
				continue
			}
			regs = append(regs, r)
		}
		m.abrirListaERBs(fmt.Sprintf("EXPLORADOR %s %s — %d ERBs", op, uf, len(dedup(regs))), dedup(regs), TelaMenu)
	case m.formAcao == "kml":
		var regs []data.Erb
		for _, r := range m.Snap.Registros {
			if uf != "" && r.UF != uf {
				continue
			}
			if mun != "" && data.NormalizarTexto(r.Municipio) != mun {
				continue
			}
			regs = append(regs, r)
		}
		nome := strings.ToUpper(mun)
		if nome == "" {
			nome = "UF_" + uf
		}
		return m, m.exportarKML(dedup(regs), nome, uf)
	}
	m.form = nil
	return m, nil
}

func dedup(regs []data.Erb) []data.Erb {
	seen := map[string]bool{}
	var out []data.Erb
	for _, r := range regs {
		if seen[r.Chave()] {
			continue
		}
		seen[r.Chave()] = true
		out = append(out, r)
	}
	return out
}

func (m Model) teclaForm(k tea.KeyMsg) (tea.Model, tea.Cmd) {
	done, cancel, cmd := m.form.Update(k)
	if cancel {
		m.form = nil
		m.tela = TelaMenu
		return m, nil
	}
	if done {
		return m.posFormulario()
	}
	return m, cmd
}

func (m Model) viewForm() string {
	return m.form.View(m.width)
}
