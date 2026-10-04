package ui

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Favorito replica a estrutura de config_usuario.py (enderecos/apelidos).
type Favorito struct {
	Endereco string `json:"endereco"`
	Apelido  string `json:"apelido"`
}

// caminhoConfig espelha dados/torre_facil_config.json do Python.
func caminhoConfig() string {
	if p := os.Getenv("TF_CONFIG"); p != "" {
		return p
	}
	cands := []string{
		filepath.Join("dados", "torre_facil_config.json"),
		filepath.Join("..", "torre_facil", "dados", "torre_facil_config.json"),
	}
	for _, c := range cands {
		if _, err := os.Stat(c); err == nil {
			return c
		}
	}
	return cands[0]
}

// CarregarFavoritos lê a lista de favoritos do mesmo JSON usado pelo Python.
func CarregarFavoritos() []Favorito {
	b, err := os.ReadFile(caminhoConfig())
	if err != nil {
		return nil
	}
	// parse simples: procura bloco "favoritos": [ {...}, ... ]
	txt := string(b)
	i := strings.Index(txt, `"favoritos"`)
	if i < 0 {
		return nil
	}
	j := strings.Index(txt[i:], "[")
	if j < 0 {
		return nil
	}
	k := strings.Index(txt[i+j:], "]")
	if k < 0 {
		return nil
	}
	bloco := txt[i+j : i+j+k]
	var out []Favorito
	for _, pedaco := range strings.Split(bloco, "}") {
		end := campo(pedaco, "endereco")
		if end == "" {
			continue
		}
		out = append(out, Favorito{Endereco: end, Apelido: campo(pedaco, "apelido")})
	}
	return out
}

func campo(s, nome string) string {
	m := `"` + nome + `": "`
	i := strings.Index(s, m)
	if i < 0 {
		return ""
	}
	s = s[i+len(m):]
	j := strings.Index(s, `"`)
	if j < 0 {
		return ""
	}
	return s[:j]
}

// LinhaFavorito formata "# | APELIDO | ENDEREÇO" como no legado.
func LinhaFavorito(i int, f Favorito) string {
	return fmt.Sprintf("%2d. %-24s %s", i+1, trunc(f.Apelido, 24), f.Endereco)
}
