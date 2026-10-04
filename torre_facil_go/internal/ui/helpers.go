package ui

import (
"sort"
"strings"

tea "github.com/charmbracelet/bubbletea"
)

func minint(a, b int) int {
if a < b {
return a
}
return b
}

// imprimivelVazio detecta KeyMsg que não deve ser enviado ao textinput.
func imprimivelVazio(k tea.KeyMsg) bool {
switch k.Type {
case tea.KeyRunes, tea.KeySpace, tea.KeyBackspace, tea.KeyDelete,
tea.KeyLeft, tea.KeyRight, tea.KeyUp, tea.KeyDown:
return false
}
return true
}

// abrirComparadorManual abre o comparador com as duas maiores cidades da base.
func (m *Model) abrirComparadorManual() {
cont := m.Snap.ContagemPorMunicipio("")
type kv struct {
chave string
qtd   int
}
var pares []kv
for k, v := range cont {
pares = append(pares, kv{k, v})
}
sort.Slice(pares, func(i, j int) bool {
if pares[i].qtd != pares[j].qtd {
return pares[i].qtd > pares[j].qtd
}
return pares[i].chave < pares[j].chave
})
var cidades [][2]string
for i := 0; i < len(pares) && i < 2; i++ {
partes := strings.SplitN(pares[i].chave, "|", 2)
if len(partes) == 2 {
cidades = append(cidades, [2]string{partes[0], partes[1]})
}
}
if len(cidades) < 2 {
m.msgRodape = "Base pequena demais para comparar duas cidades."
return
}
m.abrirComparador(cidades)
}
