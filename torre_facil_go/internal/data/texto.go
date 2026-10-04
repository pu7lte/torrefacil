// Package data replica a camada de dados do Torre Fácil (Python) em Go.
// Carrega o snapshot JSON e oferece normalização de texto compatível com
// torre_facil/texto.py (uppercase + remoção de acentos).
package data

import (
	"sort"
	"strings"
	"unicode"

	"golang.org/x/text/unicode/norm"
)

// NormalizarTexto equivale a normalizar_texto() do Python:
// uppercase, remove acentos (NFD -> descarta combining), colapsa espaços.
func NormalizarTexto(txt string) string {
	if txt == "" {
		return ""
	}
	var b strings.Builder
	for _, r := range norm.NFD.String(txt) {
		if unicode.Is(unicode.Mn, r) { // marks (acentos combinantes)
			continue
		}
		b.WriteRune(r)
	}
	s := strings.ToUpper(b.String())
	parts := strings.Fields(s)
	return strings.Join(parts, " ")
}

// ChavesOrdenadas retorna as chaves de um map[string]int em ordem alfabética.
func ChavesOrdenadasInt(m map[string]int) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}
