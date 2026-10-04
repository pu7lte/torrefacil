package ui

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/charmbracelet/lipgloss"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/torrefacil/torre-facil-go/internal/data"
)

// ---------------------------------------------------------------------------
// Painel do município (4 visões, como painel_interativo_municipio no Python)
// ---------------------------------------------------------------------------

func (m *Model) abrirPainel(regs []data.Erb, nome, uf, filtro string) {
	m.painelRegs = regs
	m.painelNome = nome
	m.painelUF = uf
	m.painelFiltro = filtro
	m.painelVisao = 1
	m.painelIdx = 0
	m.painelScroll = 0
	m.painelExpandido = false
	m.tela = TelaPainel
}

func (m Model) teclaPainel(k tea.KeyMsg) (tea.Model, tea.Cmd) {
	switch k.Type {
	case tea.KeyEscape:
		m.tela = m.painelVoltar
		return m, nil
	case tea.KeyEnter:
		up := strings.ToUpper(k.String())
		switch up {
		case "1", "2", "3", "4":
			m.painelVisao = int(up[0] - '0')
			m.painelIdx, m.painelScroll = 0, 0
				m.painelExpandido = false
			return m, nil
		case "E":
			return m, m.exportarPainel()
		}
		if k.Type == tea.KeyEnter && m.painelVisao == 3 {
			// Enter num bairro abre a lista de ERBs daquele bairro
			itens := m.itensPainel()
			if m.painelIdx < len(itens) {
				bairro := itens[m.painelIdx].dados
				var regs []data.Erb
				for _, r := range m.painelRegs {
					if r.Bairro == bairro {
						regs = append(regs, r)
					}
				}
				m.abrirListaERBs("BAIRRO "+bairro+" — "+m.painelNome, regs, TelaPainel)
				return m, nil
			}
		}
	}
	// navegação comum
	n := len(m.itensPainel())
	switch k.Type {
	case tea.KeyUp:
		m.painelIdx = maxInt(0, m.painelIdx-1)
	case tea.KeyDown:
		m.painelIdx = minint(n-1, m.painelIdx+1)
	case tea.KeyPgUp:
		m.painelIdx = maxInt(0, m.painelIdx-linhasVisiveis)
	case tea.KeyPgDown:
		m.painelIdx = minint(n-1, m.painelIdx+linhasVisiveis)
	case tea.KeyHome:
		m.painelIdx = 0
	case tea.KeyEnd:
		m.painelIdx = n - 1
	}
	if m.painelIdx < m.painelScroll {
		m.painelScroll = m.painelIdx
	}
	if m.painelIdx >= m.painelScroll+linhasVisiveis {
		m.painelScroll = m.painelIdx - linhasVisiveis + 1
	}
	return m, nil
}

type itemPainel struct {
	texto string
	dados string
}

func (m *Model) itensPainel() []itemPainel {
	switch m.painelVisao {
	case 1:
		var out []itemPainel
		for _, a := range data.PorOperadora(m.painelRegs) {
			tecs := []string{}
			for sigla, nome := range map[string]string{"5": "5G", "L": "4G", "H": "3G", "E": "2G"} {
				_ = sigla
				switch nome {
				case "5G":
					if a.Tem5G {
						tecs = append(tecs, "5G")
					}
				case "4G":
					if a.Tem4G {
						tecs = append(tecs, "4G")
					}
				case "3G":
					if a.Tem3G {
						tecs = append(tecs, "3G")
					}
				case "2G":
					if a.Tem2G {
						tecs = append(tecs, "2G")
					}
				}
			}
			sort.SliceStable(tecs, func(i, j int) bool { return tecs[i] > tecs[j] })
			out = append(out, itemPainel{
				fmt.Sprintf("%-16s %4d ERB(s)  %3d setor(es)  %3d local(is)  [%s]",
					a.Nome, a.Erbs, a.Setores, a.Bairros, strings.Join(tecs, "/")),
				a.Nome})
		}
		return out
	case 2:
		var out []itemPainel
		for _, a := range data.PorTecnologia(m.painelRegs) {
			out = append(out, itemPainel{
				fmt.Sprintf("%-12s %4d ERB(s)  %3d setor(es)", a.Nome, a.Erbs, a.Setores),
				a.Nome})
		}
		return out
	case 3:
		var out []itemPainel
		for i, a := range data.PorBairro(m.painelRegs) {
			out = append(out, itemPainel{
				fmt.Sprintf("%2dº %-30s %4d ERB(s)  %2d operadora(s)", i+1, trunc(a.Nome, 30), a.Erbs, a.Bairros),
				a.Nome})
		}
		return out
	default: // 4 — lista de ERBs
		var out []itemPainel
		seen := map[string]bool{}
		for _, r := range m.painelRegs {
			k := r.Chave()
			if seen[k] {
				continue
			}
			seen[k] = true
			out = append(out, itemPainel{
				fmt.Sprintf("%-14s %-12s %-26s %s%s", r.Operadora, r.Estacao, trunc(r.Bairro, 26),
					data.FormatarListaTec(r.Tecs), sa5gTag(r.SA5G)),
				k})
		}
		return out
	}
}

func (m *Model) exportarPainel() tea.Cmd {
	dir := "."
	if p := os.Getenv("TF_EXPORT_DIR"); p != "" {
		dir = p
	}
	nome := fmt.Sprintf("painel_%s_%s.csv",
		strings.ToLower(data.NormalizarTexto(m.painelNome)), m.painelUF)
	caminho := filepath.Join(dir, nome)
	var b strings.Builder
	b.WriteString("OPERADORA;ESTACAO;UF;MUNICIPIO;BAIRRO;TECS;5G_SA\n")
	seen := map[string]bool{}
	for _, r := range m.painelRegs {
		if seen[r.Chave()] {
			continue
		}
		seen[r.Chave()] = true
		b.WriteString(fmt.Sprintf("%s;%s;%s;%s;%s;%s;%v\n",
			r.Operadora, r.Estacao, r.UF, r.Municipio, r.Bairro, r.Tecs, r.SA5G))
	}
	err := os.WriteFile(caminho, []byte(b.String()), 0o644)
	return func() tea.Msg {
		if err != nil {
			return rodapeMsg("Erro ao exportar CSV.")
		}
		return rodapeMsg("Exportado: " + caminho)
	}
}

func (m Model) viewPainel() string {
	totalErbs := data.ErbsDistintos(m.painelRegs)
	totalBairros := map[string]bool{}
	for _, r := range m.painelRegs {
		totalBairros[r.Bairro] = true
	}
	sufixo := ""
	if m.painelFiltro != "" {
		sufixo = " │ FILTRO: " + m.painelFiltro
	}
	titulos := map[int]string{
		1: "VISÃO [1]: POR OPERADORA",
		2: "VISÃO [2]: POR TECNOLOGIA",
		3: "VISÃO [3]: RANKING POR BAIRROS (ENTER abre o bairro)",
		4: "VISÃO [4]: LISTA DE ERBs",
	}
	var ls []string
	ls = append(ls, CaixaTitulo.Render(trunc(fmt.Sprintf(" MUNICÍPIO: %s (%s) │ TOTAL: %d ERB(s) │ BAIRROS: %d%s",
		m.painelNome, m.painelUF, totalErbs, len(totalBairros), sufixo), m.width)))
	ls = append(ls, CaixaAmarelo.Render(trunc(" "+titulos[m.painelVisao]+"   [1-4 trocar visão | E exportar CSV | Esc voltar]", m.width)))
	itens := m.itensPainel()
	fim := m.painelScroll + linhasVisiveis
	if fim > len(itens) {
		fim = len(itens)
	}
	for i := m.painelScroll; i < fim; i++ {
		marca := "  "
		st := CaixaTexto
		if i == m.painelIdx {
			marca, st = "> ", CaixaSelecao
		}
		ls = append(ls, st.Render(trunc(" "+marca+itens[i].texto, m.width)))
	}
	return strings.Join(ls, "\n")
}

// ---------------------------------------------------------------------------
// Lista simples de ERBs (usada por bairro/faixa/pesquisa guiada)
// ---------------------------------------------------------------------------

func (m *Model) abrirListaERBs(titulo string, regs []data.Erb, voltar Tela) {
	m.listaTit = titulo
	m.listaRegs = regs
	m.listaVoltar = voltar
	m.listaIdx, m.listaScroll = 0, 0
	m.tela = TelaListaErbs
}

func (m Model) teclaListaErbs(k tea.KeyMsg) (tea.Model, tea.Cmd) {
	// favoritos (modo loja): lista própria, sem registros de ERB
	if m.listaTit == "FAVORITOS" {
		return m.teclaFavoritos(k)
	}
	n := len(m.listaRegs)
	switch k.Type {
	case tea.KeyEscape:
		m.tela = m.listaVoltar
		return m, nil
	case tea.KeyUp:
		m.listaIdx = maxInt(0, m.listaIdx-1)
	case tea.KeyDown:
		m.listaIdx = minint(n-1, m.listaIdx+1)
	case tea.KeyPgUp:
		m.listaIdx = maxInt(0, m.listaIdx-linhasVisiveis)
	case tea.KeyPgDown:
		m.listaIdx = minint(n-1, m.listaIdx+linhasVisiveis)
	}
	if m.listaIdx < m.listaScroll {
		m.listaScroll = m.listaIdx
	}
	if m.listaIdx >= m.listaScroll+linhasVisiveis {
		m.listaScroll = m.listaIdx - linhasVisiveis + 1
	}
	return m, nil
}

func (m Model) viewListaErbs() string {
	// tela de favoritos (modo loja): linhas "N. APELIDO  ENDEREÇO"
	if m.listaTit == "FAVORITOS" {
		favs := CarregarFavoritos()
		var ls []string
		ls = append(ls, CaixaTitulo.Render(trunc(" FAVORITOS ("+fmt.Sprint(len(favs))+") ", m.width)))
		if len(favs) == 0 {
			ls = append(ls, CaixaTexto.Render("  Nenhum favorito salvo. Use a TUI Python para cadastrar endereços."))
		}
		for i, f := range favs {
			st, marca := CaixaTexto, "  "
			if i == m.favIdx {
				st, marca = CaixaSelecao, "> "
			}
			ls = append(ls, st.Render(trunc(marca+LinhaFavorito(i, f), m.width)))
		}
		return strings.Join(ls, "\n")
	}
	var ls []string
	ls = append(ls, CaixaTitulo.Render(trunc(" "+m.listaTit+" ("+fmt.Sprint(len(m.listaRegs))+") ", m.width)))
	fim := m.listaScroll + linhasVisiveis
	if fim > len(m.listaRegs) {
		fim = len(m.listaRegs)
	}
	for i := m.listaScroll; i < fim; i++ {
		e := m.listaRegs[i]
		st, marca := CaixaTexto, "  "
		if i == m.listaIdx {
			st, marca = CaixaSelecao, "> "
		}
		line := fmt.Sprintf("%s%-14s %-10s %-24s %-8s %s%s", marca, e.Operadora, e.Estacao,
			trunc(e.Municipio, 24), e.UF, data.FormatarListaTec(e.Tecs), sa5gTag(e.SA5G))
		ls = append(ls, st.Render(trunc(line, m.width)))
	}
	return strings.Join(ls, "\n")
}

// ---------------------------------------------------------------------------
// Ranking por estado (podium ouro/prata/bronze por UF)
// ---------------------------------------------------------------------------

func (m Model) viewRanking() string {
	type kv struct {
		K string
		V int
	}
	var pares []kv
	for k, v := range m.Snap.PorUF {
		pares = append(pares, kv{k, v})
	}
	sort.Slice(pares, func(i, j int) bool { return pares[i].V > pares[j].V })
	var ls []string
	ls = append(ls, CaixaTitulo.Render(pad(" RANKING / RAIO-X POR ESTADO ", m.width)))
	medalhas := []lipgloss.Style{CorOuro, CorPrata, CorBronze}
	for i, p := range pares {
		st := CaixaTexto
		linha := fmt.Sprintf(" %2dº  %-4s %8d ERBs", i+1, p.K, p.V)
		if i < 3 {
			st = medalhas[i]
		} else if i == m.rankIdx {
			st = CaixaSelecao
		}
		if i == m.rankIdx && i >= 3 {
			linha = ">" + linha
		} else if i == m.rankIdx {
			linha = "> " + strings.TrimSpace(linha)
		}
		ls = append(ls, st.Render(trunc(linha, m.width)))
	}
	ls = append(ls, CaixaCiano.Render(trunc(" ↑/↓ navegar | ENTER ver municípios da UF | Esc voltar", m.width)))
	return strings.Join(ls, "\n")
}

// ufsOrdenadasPorQtd retorna as UFs na mesma ordem do ranking (desc por ERBs),
// garantindo consistência entre teclas e renderização.
func (m Model) ufsOrdenadasPorQtd() []string {
	type kv struct {
		K string
		V int
	}
	var pares []kv
	for k, v := range m.Snap.PorUF {
		pares = append(pares, kv{k, v})
	}
	sort.Slice(pares, func(i, j int) bool {
		if pares[i].V != pares[j].V {
			return pares[i].V > pares[j].V
		}
		return pares[i].K < pares[j].K
	})
	out := make([]string, len(pares))
	for i, p := range pares {
		out[i] = p.K
	}
	return out
}

// ---------------------------------------------------------------------------
// Comparador lado a lado (duas cidades)
// ---------------------------------------------------------------------------

func (m *Model) abrirComparador(cidades [][2]string) {
	m.compCidades = cidades
	m.tela = TelaComparador
}

func (m Model) viewComparador() string {
	var ls []string
	ls = append(ls, CaixaTitulo.Render(pad(" COMPARADOR LADO A LADO ", m.width)))
	if len(m.compCidades) != 2 {
		ls = append(ls, CaixaTexto.Render(" Selecione exatamente 2 cidades."))
		return strings.Join(ls, "\n")
	}
	header := fmt.Sprintf(" %-18s │ %-22s │ %-22s", "MÉTRICA", m.compCidades[0][0], m.compCidades[1][0])
	ls = append(ls, CaixaAmarelo.Render(trunc(header, m.width)))
	var a, b []data.Erb
	for _, r := range m.Snap.Registros {
		if r.Municipio == m.compCidades[0][0] && r.UF == m.compCidades[0][1] {
			a = append(a, r)
		}
		if r.Municipio == m.compCidades[1][0] && r.UF == m.compCidades[1][1] {
			b = append(b, r)
		}
	}
	metrica := func(nome string, fa, fb func([]data.Erb) int) {
		va, vb := fa(a), fb(b)
		marcaA, marcaB := " ", " "
		if va > vb {
			marcaA = "*"
		} else if vb > va {
			marcaB = "*"
		}
		ls = append(ls, CaixaTexto.Render(trunc(fmt.Sprintf(" %-18s │%6d %-15s │%6d %-15s",
			nome, va, marcaA, vb, marcaB), m.width)))
	}
	metrica("ERBs distintos", data.ErbsDistintos, data.ErbsDistintos)
	comTec := func(sig string) func([]data.Erb) int {
		return func(rs []data.Erb) int {
			set := map[string]bool{}
			for _, r := range rs {
				if r.TemTec(sig) {
					set[r.Chave()] = true
				}
			}
			return len(set)
		}
	}
	metrica("com 5G", comTec("5"), comTec("5"))
	metrica("com 4G", comTec("L"), comTec("L"))
	metrica("com 3G", comTec("H"), comTec("H"))
	metrica("com 2G", comTec("E"), comTec("E"))
	opsDistintas := func(rs []data.Erb) int {
		s := map[string]bool{}
		for _, r := range rs {
			s[r.Operadora] = true
		}
		return len(s)
	}
	metrica("operadoras", opsDistintas, opsDistintas)
	ls = append(ls, CaixaCiano.Render(trunc(" * = melhor na métrica | Esc voltar", m.width)))
	return strings.Join(ls, "\n")
}

// ---------------------------------------------------------------------------
// Indicador de chip (pódio de operadoras) — espelha chips.py
// ---------------------------------------------------------------------------

func (m *Model) abrirChips(regs []data.Erb, escopo string) {
	m.chipsEscopo = escopo
	m.chipsRegs = regs
	m.tela = TelaChips
}

func (m Model) viewChips() string {
	var ls []string
	ls = append(ls, CaixaTitulo.Render(pad(" CONSULTOR / INDICADOR DE CHIP — "+m.chipsEscopo+" ", m.width)))
	aggs := data.PorOperadora(m.chipsRegs)
	max5, max4 := 0, 0
	cont5 := map[string]int{}
	cont4 := map[string]int{}
	for _, r := range m.chipsRegs {
		k := r.Chave()
		if r.TemTec("5") {
			cont5[r.Operadora+"|"+k] = 1
		}
		if r.TemTec("L") {
			cont4[r.Operadora+"|"+k] = 1
		}
	}
	countUniq := func(mm map[string]int, op string) int {
		n := 0
		for k := range mm {
			if strings.HasPrefix(k, op+"|") {
				n++
			}
		}
		return n
	}
	for _, a := range aggs {
		v5, v4 := countUniq(cont5, a.Nome), countUniq(cont4, a.Nome)
		if v5 > max5 {
			max5 = v5
		}
		if v4 > max4 {
			max4 = v4
		}
	}
	medalhas := []lipgloss.Style{CorOuro, CorPrata, CorBronze}
	for i, a := range aggs {
		v5, v4 := countUniq(cont5, a.Nome), countUniq(cont4, a.Nome)
		var pontos []string
		switch {
		case v5 > 0 && v5 == max5:
			pontos = append(pontos, fmt.Sprintf("Líder 5G (%d ERBs)", v5))
		case v5 > 0:
			pontos = append(pontos, fmt.Sprintf("%d ERB(s) 5G", v5))
		default:
			pontos = append(pontos, "Sem 5G")
		}
		if v4 > 0 && v4 == max4 {
			pontos = append(pontos, fmt.Sprintf("Líder 4G (%d ERBs)", v4))
		} else if v4 > 0 {
			pontos = append(pontos, fmt.Sprintf("%d ERB(s) 4G", v4))
		}
		pontos = append(pontos, fmt.Sprintf("%d local(is)", a.Bairros))
		st := CaixaTexto
		pos := fmt.Sprintf("%2dº", i+1)
		if i < 3 {
			st = medalhas[i]
			pos = []string{"🥇", "🥈", "🥉"}[i]
		}
		ls = append(ls, st.Render(trunc(fmt.Sprintf(" %s %-14s %s", pos, a.Nome, strings.Join(pontos, " · ")), m.width)))
	}
	ls = append(ls, CaixaCiano.Render(trunc(" Esc voltar", m.width)))
	return strings.Join(ls, "\n")
}

// ---------------------------------------------------------------------------
// Rodapé-mensagem (usado por comandos assíncronos)
// ---------------------------------------------------------------------------

type rodapeMsg string

func agoraStamp() string { return time.Now().Format("15:04:05") }
