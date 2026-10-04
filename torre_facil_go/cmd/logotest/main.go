package main

import (
"fmt"

"github.com/torrefacil/torre-facil-go/internal/data"
"github.com/torrefacil/torre-facil-go/internal/ui"
)

// logotest renderiza a tela de logo fora do programa interativo.
func main() {
snap, err := data.CarregarSnapshot("../torre_facil_snapshot.json")
if err != nil { panic(err) }
m := ui.NewModel(snap, ui.ModoAnalista)
fmt.Println(ui.RenderTelaParaTeste(m, 100, 30))
}
