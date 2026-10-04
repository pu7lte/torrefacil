package main

import (
"fmt"
"os"

tea "github.com/charmbracelet/bubbletea"

"github.com/torrefacil/torre-facil-go/internal/data"
"github.com/torrefacil/torre-facil-go/internal/ui"
)

func main() {
snap, err := data.CarregarSnapshot("../torre_facil_snapshot.json")
if err != nil { panic(err) }
fmt.Println("UFs:", len(snap.UFs()), "| registros:", len(snap.Registros))
m := ui.NewModel(snap, ui.ModoAnalista)
p := tea.NewProgram(m)
go func() {
// injeta eventos como um usuário: resize, F10, navegação, Enter, busca, Esc, X
p.Send(tea.WindowSizeMsg{Width: 100, Height: 30})
p.Send(tea.KeyMsg{Type: tea.KeyEnter})          // logo -> menu principal
p.Send(tea.KeyMsg{Type: tea.KeyEscape})         // menu -> volta ao logo (legado)
p.Send(tea.KeyMsg{Type: tea.KeyEnter})          // logo -> menu de novo
p.Send(tea.KeyMsg{Type: tea.KeyF10})            // mostra barra
p.Send(tea.KeyMsg{Type: tea.KeyF10})            // esconde (sem duplicar)
p.Send(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("A")}) // atalho analista -> lista UF
p.Send(tea.KeyMsg{Type: tea.KeyDown})
p.Send(tea.KeyMsg{Type: tea.KeyEnter})          // escolhe UF
p.Send(tea.KeyMsg{Type: tea.KeyEnter})          // escolhe municipio -> busca
p.Send(tea.KeyMsg{Type: tea.KeyEscape})         // volta menu
p.Send(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("A")}) // faixas
p.Send(tea.KeyMsg{Type: tea.KeyEnter})          // Brasil Inteiro consolidado
p.Send(tea.KeyMsg{Type: tea.KeyEscape})         // volta
p.Send(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("9")}) // sobre
p.Send(tea.KeyMsg{Type: tea.KeyEscape})
p.Send(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune("X")}) // sair
}()
final, err := p.Run()
if err != nil { panic(err) }
fm := final.(ui.Model)
v := fm.View()
fmt.Println("VIEW OK, linhas:", len(fmt.Sprintln(v)))
fmt.Println("snapshot carregado e fluxo de telas executado sem panics")
os.Exit(0)
}
