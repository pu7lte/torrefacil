// torre_facil_go — TUI em Go do Torre Fácil.
//
// Equivalente de `python -m torre_facil`:
//
//	./torre-facil [-modo loja|analista] [-snapshot caminho.json]
//
// A TUI Python permanece como legado; ambos compartilham o mesmo
// torre_facil_snapshot.json gerado pelo pipeline Python (dados/ANATEL).
package main

import (
	"flag"
	"fmt"
	"os"

	tea "github.com/charmbracelet/bubbletea"

	"github.com/torrefacil/torre-facil-go/internal/data"
	"github.com/torrefacil/torre-facil-go/internal/ui"
)

func main() {
	modo := flag.String("modo", "analista", "modo de operação: analista | loja")
	caminho := flag.String("snapshot", "", "caminho do torre_facil_snapshot.json (padrão: auto-detectar)")
	flag.Parse()

	p := *caminho
	if p == "" {
		if env := os.Getenv("TF_SNAPSHOT"); env != "" {
			p = env
		} else {
			var err error
			p, err = data.LocalizarSnapshot()
			if err != nil {
				fmt.Fprintln(os.Stderr, "ERRO:", err)
				os.Exit(2)
			}
		}
	}

	snap, err := data.CarregarSnapshot(p)
	if err != nil {
		fmt.Fprintln(os.Stderr, "ERRO ao carregar snapshot:", err)
		os.Exit(1)
	}

	m := ui.NewModel(snap, ui.Modo(*modo))
	if _, err := tea.NewProgram(m, tea.WithAltScreen()).Run(); err != nil {
		fmt.Fprintln(os.Stderr, "ERRO na TUI:", err)
		os.Exit(1)
	}
}
