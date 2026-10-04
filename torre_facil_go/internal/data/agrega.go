package data

import (
	"sort"
	"strings"
)

// Chave do registro composto (uma linha por setor no Python; aqui por ERB).
func (e Erb) Chave() string { return e.Operadora + "_" + e.Estacao }

// TemTec informa se o registro possui a sigla de tecnologia ("5","L","H","E").
func (e Erb) TemTec(sig string) bool {
	for _, t := range strings.Split(e.Tecs, ",") {
		if strings.TrimSpace(t) == sig {
			return true
		}
	}
	return false
}

// Agregado é uma métrica por grupo (operadora, bairro ou tecnologia).
type Agregado struct {
	Nome   string
	Erbs   int     // ERBs distintos
	Setores int    // setores (linhas) — no snapshot 1 linha = 1 registro base
	Bairros int    // bairros distintos
	Tem5G, Tem4G, Tem3G, Tem2G bool
	Maior5GSA bool
}

func novoAgregado(nome string) *Agregado { return &Agregado{Nome: nome} }

// PorOperadora agrupa registros por operadora (ordenado por nº de ERBs desc).
func PorOperadora(regs []Erb) []Agregado {
	m := map[string]*Agregado{}
	bairros := map[string]map[string]bool{}
	chaves := map[string]map[string]bool{}
	for _, r := range regs {
		a := m[r.Operadora]
		if a == nil {
			a = novoAgregado(r.Operadora)
			m[r.Operadora] = a
			bairros[r.Operadora] = map[string]bool{}
			chaves[r.Operadora] = map[string]bool{}
		}
		a.Setores++
		k := r.Chave()
		if !chaves[r.Operadora][k] {
			chaves[r.Operadora][k] = true
			a.Erbs++
		}
		if r.Bairro != "" && !bairros[r.Operadora][r.Bairro] {
			bairros[r.Operadora][r.Bairro] = true
			a.Bairros++
		}
		if r.TemTec("5") {
			a.Tem5G = true
		}
		if r.TemTec("L") {
			a.Tem4G = true
		}
		if r.TemTec("H") {
			a.Tem3G = true
		}
		if r.TemTec("E") {
			a.Tem2G = true
		}
		if r.SA5G {
			a.Maior5GSA = true
		}
	}
	out := valoresAgreg(m)
	sort.Slice(out, func(i, j int) bool {
		if out[i].Erbs != out[j].Erbs {
			return out[i].Erbs > out[j].Erbs
		}
		return out[i].Nome < out[j].Nome
	})
	return out
}

// PorTecnologia agrupa por tecnologia presente (um registro conta em várias).
func PorTecnologia(regs []Erb) []Agregado {
	nomes := map[string]string{"5": "5G", "L": "4G/LTE", "H": "3G/HSPA", "E": "2G/GSM"}
	m := map[string]*Agregado{}
	chaves := map[string]map[string]bool{}
	for _, s := range ORDEMTEC {
		m[s] = novoAgregado(nomes[s])
		chaves[s] = map[string]bool{}
	}
	for _, r := range regs {
		for _, t := range strings.Split(r.Tecs, ",") {
			t = strings.TrimSpace(t)
			a := m[t]
			if a == nil {
				continue
			}
			a.Setores++
			k := r.Chave()
			if !chaves[t][k] {
				chaves[t][k] = true
				a.Erbs++
			}
		}
	}
	var out []Agregado
	for _, s := range ORDEMTEC {
		if m[s].Erbs > 0 {
			out = append(out, *m[s])
		}
	}
	return out
}

// PorBairro agrupa por bairro (ranking por nº de ERBs distintos).
func PorBairro(regs []Erb) []Agregado {
	m := map[string]*Agregado{}
	ops := map[string]map[string]bool{}
	chaves := map[string]map[string]bool{}
	for _, r := range regs {
		b := r.Bairro
		if b == "" {
			b = "(sem bairro)"
		}
		a := m[b]
		if a == nil {
			a = novoAgregado(b)
			m[b] = a
			ops[b] = map[string]bool{}
			chaves[b] = map[string]bool{}
		}
		a.Setores++
		ops[b][r.Operadora] = true
		k := r.Chave()
		if !chaves[b][k] {
			chaves[b][k] = true
			a.Erbs++
		}
		if r.TemTec("5") {
			a.Tem5G = true
		}
		if r.TemTec("L") {
			a.Tem4G = true
		}
		if r.TemTec("H") {
			a.Tem3G = true
		}
		if r.TemTec("E") {
			a.Tem2G = true
		}
	}
	out := valoresAgreg(m)
	sort.Slice(out, func(i, j int) bool {
		if out[i].Erbs != out[j].Erbs {
			return out[i].Erbs > out[j].Erbs
		}
		return out[i].Nome < out[j].Nome
	})
	// anota nº de operadoras no campo Bairros (reuso simples p/ ranking)
	for i := range out {
		out[i].Bairros = len(ops[out[i].Nome])
	}
	return out
}

func valoresAgreg(m map[string]*Agregado) []Agregado {
	var out []Agregado
	for _, a := range m {
		out = append(out, *a)
	}
	return out
}

// FiltrarRegistros aplica UF / município exato / operadora / tecnologia.
func FiltrarRegistros(regs []Erb, uf, mun, op, tecSig string) []Erb {
	var out []Erb
	for _, r := range regs {
		if uf != "" && r.UF != uf {
			continue
		}
		if mun != "" && NormalizarTexto(r.Municipio) != NormalizarTexto(mun) {
			continue
		}
		if op != "" && !strings.Contains(strings.ToUpper(r.Operadora), strings.ToUpper(op)) {
			continue
		}
		if tecSig != "" && !r.TemTec(tecSig) {
			continue
		}
		out = append(out, r)
	}
	return out
}

// ErbsDistintos conta chaves OPERADORA_ESTACAO únicas.
func ErbsDistintos(regs []Erb) int {
	set := map[string]bool{}
	for _, r := range regs {
		set[r.Chave()] = true
	}
	return len(set)
}

// MunicipiosComTec retorna municípios (ordenados) que possuem a tecnologia.
func (s *Snapshot) MunicipiosComTec(uf, tec string) []string {
	seen := map[string]bool{}
	var out []string
	for _, r := range s.FiltrarUF(uf) {
		if r.TemTec(tec) && !seen[r.Municipio+"|"+r.UF] {
			seen[r.Municipio+"|"+r.UF] = true
			out = append(out, r.Municipio)
		}
	}
	sortStrings(out)
	return out
}
