package data

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Erb replica um registro de torre_facil_snapshot.json -> erbs_ids.
type Erb struct {
	ID        string // ex: "CLARO_1000628059"
	Operadora string
	Estacao   string
	UF        string
	Municipio string
	Bairro    string
	Tecs      string // "H,L" etc.
	SA5G      bool
}

// Snapshot é a estrutura completa do snapshot ANATEL compartilhado com o Python.
type Snapshot struct {
	VersaoSnapshot  int               `json:"versao_snapshot"`
	GeradoEm        string            `json:"gerado_em"`
	DataBase        string            `json:"data_base"`
	TotalErbs       int               `json:"total_erbs"`
	TotalSetores    int               `json:"total_setores"`
	PorUF           map[string]int    `json:"por_uf"`
	PorOperadora    map[string]int    `json:"por_operadora"`
	PorOperadoraUF  map[string]int    `json:"por_operadora_uf"`
	PorTecnologia   map[string]int    `json:"por_tecnologia"`
	PorOperadora5G  map[string]int    `json:"por_operadora_5g"`
	PorOperadora5GSa map[string]int   `json:"por_operadora_5g_sa"`
	PorMunicipio5G  map[string]int    `json:"por_municipio_5g"`
	ErbsIDs         map[string]struct {
		UF     string `json:"uf"`
	Mun    string `json:"mun"`
	Bairro string `json:"bairro"`
	Tecs   string `json:"tecs"`
	SA5G   bool   `json:"5g_sa"`
	Op     string `json:"op"`
	Estacao string `json:"estacao"`
} `json:"erbs_ids"`

	Registros []Erb // achatado para busca/filtro
}

// NomeArquivoSnapshot é o mesmo arquivo usado pelo Torre Fácil Python.
const NomeArquivoSnapshot = "torre_facil_snapshot.json"

// LocalizarSnapshot procura o JSON em locais-padrão e devolve o caminho.
func LocalizarSnapshot() (string, error) {
	candidatos := []string{
		NomeArquivoSnapshot,                       // cwd
		filepath.Join("..", NomeArquivoSnapshot),  // torre_facil_go/ -> repo raiz
	}
	if home, err := os.UserHomeDir(); err == nil {
		candidatos = append(candidatos, filepath.Join(home, NomeArquivoSnapshot))
	}
	for _, c := range candidatos {
		if st, err := os.Stat(c); err == nil && !st.IsDir() {
			return c, nil
		}
	}
	return "", fmt.Errorf("snapshot não encontrado (%s). Rode o Torre Fácil Python para gerá-lo ou aponte TF_SNAPSHOT", NomeArquivoSnapshot)
}

// CarregarSnapshot lê e monta o Snapshot a partir do JSON.
func CarregarSnapshot(caminho string) (*Snapshot, error) {
	b, err := os.ReadFile(caminho)
	if err != nil {
		return nil, err
	}
	var s Snapshot
	if err := json.Unmarshal(b, &s); err != nil {
		return nil, fmt.Errorf("snapshot inválido: %w", err)
	}
	s.Registros = make([]Erb, 0, len(s.ErbsIDs))
	for id, v := range s.ErbsIDs {
		op, est := v.Op, v.Estacao
		if op == "" || est == "" {
			// chave no formato "OPERADORA_IDERB" (legado) — separa pela última "_"
			if i := strings.LastIndex(id, "_"); i > 0 {
				op, est = id[:i], id[i+1:]
			} else {
				op, est = id, ""
			}
		}
		s.Registros = append(s.Registros, Erb{
			ID: id, Operadora: op, Estacao: est,
			UF: v.UF, Municipio: v.Mun, Bairro: v.Bairro,
			Tecs: v.Tecs, SA5G: v.SA5G,
		})
	}
	return &s, nil
}

// TEC_LABELS converte siglas ANATEL em nomes comerciais (espelho de formatar_lista_tec).
var TECLabels = map[string]string{"E": "2G", "H": "3G", "L": "4G", "5": "5G"}

// ORDEMTEC é a ordem de exibição (espelho de config.ORDEM_TEC).
var ORDEMTEC = []string{"5", "L", "H", "E"}

// FormatarListaTec transforma "E,H,L,5" em "2G/3G/4G/5G".
func FormatarListaTec(tecs string) string {
	set := map[string]bool{}
	for _, t := range strings.Split(tecs, ",") {
		t = strings.TrimSpace(t)
		if t != "" {
			set[t] = true
		}
	}
	var nomes []string
	for _, t := range ORDEMTEC {
		if set[t] {
			nomes = append(nomes, TECLabels[t])
		}
	}
	if len(nomes) == 0 {
		return "—"
	}
	return strings.Join(nomes, "/")
}

// FiltrarUF retorna registros da UF (vazio = todos).
func (s *Snapshot) FiltrarUF(uf string) []Erb {
	if uf == "" {
		return s.Registros
	}
	out := make([]Erb, 0, 64)
	for _, r := range s.Registros {
		if r.UF == uf {
			out = append(out, r)
		}
	}
	return out
}

// MunicipiosPorUF retorna municípios únicos (ordenados) da UF informada.
func (s *Snapshot) MunicipiosPorUF(uf string) []string {
	seen := map[string]bool{}
	var out []string
	for _, r := range s.FiltrarUF(uf) {
		if r.Municipio != "" && !seen[r.Municipio] {
			seen[r.Municipio] = true
			out = append(out, r.Municipio)
		}
	}
	sortStrings(out)
	return out
}

// ContagemPorMunicipio agrupa por municipio|uf -> nº de ERBs distintos.
func (s *Snapshot) ContagemPorMunicipio(uf string) map[string]int {
	cont := map[string]int{}
	chave := map[string]map[string]bool{}
	for _, r := range s.FiltrarUF(uf) {
		k := r.Municipio + "|" + r.UF
		if chave[k] == nil {
			chave[k] = map[string]bool{}
		}
		id := r.Operadora + "_" + r.Estacao
		if !chave[k][id] {
			chave[k][id] = true
			cont[k]++
		}
	}
	return cont
}

// UFs ordenadas presentes na base.
func (s *Snapshot) UFs() []string { return ChavesOrdenadasInt(s.PorUF) }

// Operadoras ordenadas presentes na base.
func (s *Snapshot) Operadoras() []string { return ChavesOrdenadasInt(s.PorOperadora) }

// ResumoStatus gera texto de status da base (barra superior).
func (s *Snapshot) ResumoStatus() string {
	return fmt.Sprintf("Base ANATEL %s | %d ERBs | %d setores",
		s.DataBase, s.TotalErbs, s.TotalSetores)
}

func sortStrings(v []string) {
	for i := 1; i < len(v); i++ {
		for j := i; j > 0 && v[j] < v[j-1]; j-- {
			v[j], v[j-1] = v[j-1], v[j]
		}
	}
}
