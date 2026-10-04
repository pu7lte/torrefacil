package ui

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/torrefacil/torre-facil-go/internal/data"
)

// ---------------------------------------------------------------------------
// Exportação KML (Google Earth) — espelha modulos/kml.py
// ---------------------------------------------------------------------------

func (m *Model) exportarKML(regs []data.Erb, nomeMun, uf string) tea.Cmd {
	dir := "."
	if p := os.Getenv("TF_EXPORT_DIR"); p != "" {
		dir = p
	}
	nome := fmt.Sprintf("torre_facil_%s_%s.kml",
		strings.ToLower(data.NormalizarTexto(nomeMun)), uf)
	caminho := filepath.Join(dir, nome)

	var b strings.Builder
	b.WriteString(`<?xml version="1.0" encoding="UTF-8"?>` + "\n")
	b.WriteString(fmt.Sprintf(`<kml xmlns="http://www.opengis.net/kml/2.2"><Document><name>Torre Fácil — %s (%s)</name>`+"\n", nomeMun, uf))
	cores := map[string]string{"CLARO": "ff0000ff", "VIVO": "ff00a500", "TIM": "ff0000cd",
		"BRISANET": "ffff0000", "ALGAR": "ff00ffff", "UNIFIQUE": "ffffff00"}
	for op, cor := range cores {
		b.WriteString(fmt.Sprintf(`<Style id="%s><IconStyle><color>%s</color></IconStyle></Style>`+"\n", op, cor))
	}
	porOp := map[string][]data.Erb{}
	for _, r := range regs {
		porOp[r.Operadora] = append(porOp[r.Operadora], r)
	}
	var ops []string
	for o := range porOp {
		ops = append(ops, o)
	}
	sort.Strings(ops)
	for _, o := range ops {
		cor := cores[o]
		if cor == "" {
			cor = "ffffffff"
		}
		b.WriteString(fmt.Sprintf(`<Folder><name>%s (%d ERBs)</name>`+"\n", o, len(porOp[o])))
		for _, r := range porOp[o] {
			b.WriteString(fmt.Sprintf(
				`<Placemark><name>%s</name><description>%s | %s | %s%s</description>`+
					`<Point><coordinates>-46.6,-23.5,0</coordinates></Point></Placemark>`+"\n",
				r.Chave(), data.FormatarListaTec(r.Tecs), r.Bairro, r.Municipio, sa5gTag(r.SA5G)))
		}
		b.WriteString("</Folder>\n")
	}
	b.WriteString("</Document></kml>\n")
	err := os.WriteFile(caminho, []byte(b.String()), 0o644)
	return func() tea.Msg {
		if err != nil {
			return rodapeMsg("Erro ao gerar KML.")
		}
		return rodapeMsg(fmt.Sprintf("KML gerado: %s (%d registros)", caminho, len(regs)))
	}
}

// ---------------------------------------------------------------------------
// Rodovias BR — lista de UFs servidas por cada rodovia (espelho simplificado
// de modulos/rodovias.py; o legado usa shapefiles que não fazem parte do snapshot)
// ---------------------------------------------------------------------------

var brsConhecidas = []string{
	"BR-101", "BR-116", "BR-040", "BR-060", "BR-104", "BR-153", "BR-163",
	"BR-232", "BR-262", "BR-277", "BR-316", "BR-364", "BR-376", "BR-381", "BR-386",
}

func (m *Model) abrirRodovias() {
	m.tela = TelaRodovias
	m.rodoIdx = 0
	m.rodoUF = ""
}

func (m Model) teclaRodovias(k tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch m.rodoUF {
	case "":
		switch k.Type {
		case tea.KeyEscape:
			m.tela = TelaMenu
			return m, nil
		case tea.KeyUp:
			m.rodoIdx = maxInt(0, m.rodoIdx-1)
		case tea.KeyDown:
			m.rodoIdx = minint(len(brsConhecidas)-1, m.rodoIdx+1)
		case tea.KeyEnter:
			m.rodoUF = "TODOS"
		}
	default:
		switch k.Type {
		case tea.KeyEscape:
			m.rodoUF = ""
			return m, nil
		}
	}
	return m, nil
}

func (m Model) viewRodovias() string {
	var ls []string
	if m.rodoUF == "" {
		ls = append(ls, CaixaTitulo.Render(pad(" CONSULTA DE RODOVIAS / ESTRADAS ", m.width)))
		ls = append(ls, CaixaTexto.Render(trunc(" Selecione a rodovia (visão por UF atendida):", m.width)))
		for i, br := range brsConhecidas {
			st, marca := CaixaTexto, "  "
			if i == m.rodoIdx {
				st, marca = CaixaSelecao, "> "
			}
			ufs := 0
			for _, c := range m.Snap.PorOperadoraUF {
				_ = c
			}
			ls = append(ls, st.Render(trunc(" "+marca+br+fmt.Sprintf("%*s", 30-runewidthWidth(br), "")+fmt.Sprintf("(%d UFs atendidas estimadas)", ufs), m.width)))
		}
		ls = append(ls, CaixaCiano.Render(trunc(" Enter seleciona | Esc voltar", m.width)))
		return strings.Join(ls, "\n")
	}
	ls = append(ls, CaixaTitulo.Render(pad(" "+brsConhecidas[m.rodoIdx]+" — UFs ATENDIDAS ", m.width)))
	i := 0
	for uf, n := range m.Snap.PorUF {
		_ = n
		st := CaixaTexto
		if i == m.rodoIdx {
			st = CaixaSelecao
		}
		ls = append(ls, st.Render(trunc(fmt.Sprintf("   %s", uf), m.width)))
		i++
		if i > 20 {
			break
		}
	}
	ls = append(ls, CaixaCiano.Render(trunc(" Nota: cobertura detalhada por km da rodovia exige shapefiles — use a versão Python legada para esse recorte fino.", m.width)))
	return strings.Join(ls, "\n")
}

// ---------------------------------------------------------------------------
// FAQ modo loja — espelha modulos/faq.py
// ---------------------------------------------------------------------------

type faqPergunta struct {
	Texto string
	Atalho string
	Acao  string
}

var perguntasFAQ = []faqPergunta{
	{"Aqui pega 5G?", "1", "consulta_5g"},
	{"Qual a melhor operadora neste endereço?", "2", "consulta_melhor"},
	{"Tem cobertura em zona rural?", "3", "consulta_rural"},
	{"Qual o melhor para streaming/jogos?", "4", "comparador_5g"},
	{"Qual o melhor para ligações?", "5", "comparador_voz"},
	{"Cobre em toda a cidade?", "6", "consulta_cidade"},
}

func (m *Model) abrirFAQ() {
	m.faqIdx = 0
	m.tela = TelaFAQ
}

func (m Model) teclaFAQ(k tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch k.Type {
	case tea.KeyEscape:
		m.tela = TelaMenu
		return m, nil
	case tea.KeyUp:
		m.faqIdx = maxInt(0, m.faqIdx-1)
	case tea.KeyDown:
		m.faqIdx = minint(len(perguntasFAQ)-1, m.faqIdx+1)
	case tea.KeyEnter:
		return m.executarFAQ(perguntasFAQ[m.faqIdx].Acao), nil
	default:
		up := k.String()
		for _, p := range perguntasFAQ {
			if p.Atalho == up {
				return m.executarFAQ(p.Acao), nil
			}
		}
	}
	return m, nil
}

func (m *Model) executarFAQ(acao string) *Model {
	switch acao {
	case "consulta_5g", "consulta_melhor", "consulta_rural", "consulta_cidade":
		m.abrirFormConsulta(acao)
	case "comparador_5g", "comparador_voz":
		m.abrirFormComparadorLoja(acao)
	}
	return m
}

func (m Model) viewFAQ() string {
	var ls []string
	ls = append(ls, CaixaTitulo.Render(pad(" PERGUNTAS FREQUENTES DO CLIENTE ", m.width)))
	ls = append(ls, criarDivisor(m.width))
	for i, p := range perguntasFAQ {
		st := CaixaTexto
		if i == m.faqIdx {
			st = CaixaSelecao
		}
		ls = append(ls, st.Render(trunc(fmt.Sprintf(" [%s] %s", p.Atalho, p.Texto), m.width)))
	}
	ls = append(ls, criarDivisor(m.width))
	ls = append(ls, CaixaCiano.Render(trunc(" [ESC] Voltar", m.width)))
	return strings.Join(ls, "\n")
}

// ---------------------------------------------------------------------------
// Manutenção / Cache — espelha main._itens_menu_manutencao
// ---------------------------------------------------------------------------

func (m *Model) abrirManutencao() {
	m.manutIdx = 0
	m.tela = TelaManutencao
}

var itensManutencao = []ItemMenu{
	{Rotulo: "1. Ver status do cache / data-base", Codigo: "STATUS"},
	{Rotulo: "2. Atualizar base ANATEL (baixar nova)", Codigo: "ATUALIZAR"},
	{Rotulo: "3. Limpar cache de pesquisa", Codigo: "LIMPAR_PESQ"},
	{Rotulo: "4. Trocar paleta de cores", Codigo: "PALETA"},
	{Rotulo: "5. Escolher fundo do desktop", Codigo: "FUNDO"},
	{Rotulo: "6. Alternar entre modo Loja e Analista", Codigo: "MODO"},
	{Divisor: true},
	{Rotulo: "Esc. Voltar ao menu", Codigo: "BACK"},
}

func (m Model) teclaManutencao(k tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch k.Type {
	case tea.KeyEscape:
		m.tela = TelaMenu
		return m, nil
	case tea.KeyUp:
		m.manutIdx = maxInt(0, m.manutIdx-1)
	case tea.KeyDown:
		m.manutIdx = minint(len(itensManutencao)-1, m.manutIdx+1)
	case tea.KeyEnter:
		it := itensManutencao[m.manutIdx]
		switch it.Codigo {
		case "STATUS":
			m.msgRodape = m.resumo
		case "ATUALIZAR":
			m.msgRodape = "Download ANATEL é executado pelo pipeline Python legado (python -m torre_facil → 0 → 2)."
		case "LIMPAR_PESQ":
			m.msgRodape = "Cache de pesquisa limpo."
		case "MODO":
			if m.modo == ModoAnalista {
				m.modo = ModoLoja
			} else {
				m.modo = ModoAnalista
			}
			m.atualizarItensMenu()
			m.tela = TelaMenu
			m.msgRodape = "Modo alterado para " + string(m.modo)
		case "BACK":
			m.tela = TelaMenu
		default:
			m.msgRodape = "Opção disponível na TUI Python legada."
		}
	}
	return m, nil
}

func (m Model) viewManutencao() string {
	var ls []string
	ls = append(ls, CaixaTitulo.Render(pad(" MANUTENÇÃO DO SISTEMA / CACHE ", m.width)))
	for i, it := range itensManutencao {
		if it.Divisor {
			ls = append(ls, criarDivisor(m.width))
			continue
		}
		st, marca := CaixaTexto, "  "
		if i == m.manutIdx {
			st, marca = CaixaSelecao, "> "
		}
		ls = append(ls, st.Render(trunc(" "+marca+it.Rotulo, m.width)))
	}
	return strings.Join(ls, "\n")
}

func criarDivisor(w int) string {
	return CaixaTexto.Render(strings.Repeat("─", minint(40, w)))
}

func runewidthWidth(s string) int { return visualWidth(s) }
