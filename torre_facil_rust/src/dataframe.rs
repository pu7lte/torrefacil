//! Mini-DataFrame — substituto enxuto do `pandas.DataFrame` usado pelo projeto.
//!
//! O Torre Fácil (Python) usa pandas apenas para: carregar CSV, colunas
//! calculadas, filtragem booleana, contagens distintas, agrupamentos simples
//! e ordenação. Este módulo reproduz exatamente essas operações com semântica
//! 1:1 (colunas como `Vec<Value>` onde `Value::Null` == NaN de pandas).

use std::cmp::Ordering;

use serde_json::{Map, Value};

pub type Cell = Value;

/// Equivalente a um DataFrame do pandas: colunas nomeadas + número de linhas.
#[derive(Debug, Clone)]
pub struct DataFrame {
    pub colunas: Vec<String>,
    /// Dados em coluna: `dados[i]` é a coluna `colunas[i]`.
    pub dados: Vec<Vec<Cell>>,
}

/// Comparação de células com semântica numérica quando ambas são números
/// (ex.: `1` == `1.0`), caso contrário igualdade estrutural de JSON.
pub fn eq_num(a: &Cell, b: &Cell) -> bool {
    match (a.as_f64(), b.as_f64()) {
        (Some(x), Some(y)) => x == y,
        _ => a == b,
    }
}

impl DataFrame {
    /// DataFrame vazio (`pd.DataFrame()`).
    pub fn new() -> Self {
        Self { colunas: Vec::new(), dados: Vec::new() }
    }

    /// `df.empty`
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// `len(df)`
    pub fn len(&self) -> usize {
        if self.colunas.is_empty() {
            0
        } else {
            self.dados[0].len()
        }
    }

    /// Índice da coluna ou erro amigável (KeyError do pandas).
    pub fn idx(&self, nome: &str) -> Result<usize, String> {
        self.colunas
            .iter()
            .position(|c| c == nome)
            .ok_or_else(|| format!("Coluna inexistente: {nome}"))
    }

    /// `df[col]` — clone da coluna inteira.
    pub fn coluna(&self, nome: &str) -> Vec<Cell> {
        match self.idx(nome) {
            Ok(i) => self.dados[i].clone(),
            Err(_) => Vec::new(),
        }
    }

    /// Referência à coluna (sem copiar).
    pub fn coluna_ref(&self, nome: &str) -> Option<&Vec<Cell>> {
        self.idx(nome).ok().map(|i| &self.dados[i])
    }

    /// `df.loc[i, col]` — célula (linha, coluna). Null se faltante.
    pub fn celula(&self, linha: usize, col: &str) -> Cell {
        match self.idx(col) {
            Ok(i) => self.dados[i].get(linha).cloned().unwrap_or(Cell::Null),
            Err(_) => Cell::Null,
        }
    }

    /// Linha i como objeto JSON (registro).
    pub fn linha(&self, i: usize) -> Map<String, Cell> {
        let mut m = Map::new();
        for (j, c) in self.colunas.iter().enumerate() {
            m.insert(c.clone(), self.dados[j].get(i).cloned().unwrap_or(Cell::Null));
        }
        m
    }

    /// Adiciona/substitui uma coluna inteira (`df[col] = serie`).
    pub fn set_coluna(&mut self, nome: &str, valores: Vec<Cell>) {
        assert_eq!(
            valores.len(),
            self.len(),
            "set_coluna({nome}): {} valores para {} linhas",
            valores.len(),
            self.len()
        );
        if let Some(i) = self.idx(nome).ok() {
            self.dados[i] = valores;
        } else {
            self.colunas.push(nome.to_string());
            self.dados.push(valores);
        }
    }

    /// `df.drop(columns=[nome])` — remove a coluna se existir.
    pub fn remover_coluna(mut self, nome: &str) -> DataFrame {
        if let Some(i) = self.idx(nome).ok() {
            self.colunas.remove(i);
            self.dados.remove(i);
        }
        self
    }

    /// Cria DataFrame a partir de registros (lista de mapas), preservando ordem
    /// de inserção das chaves (equivalente a `pd.DataFrame(list_of_dicts)`).
    pub fn from_registros(regs: Vec<Map<String, Cell>>) -> Self {
        let mut colunas: Vec<String> = Vec::new();
        for r in &regs {
            for k in r.keys() {
                if !colunas.contains(k) {
                    colunas.push(k.clone());
                }
            }
        }
        let mut df = Self { colunas: colunas.clone(), dados: vec![Vec::new(); colunas.len()] };
        for r in &regs {
            for (j, c) in df.colunas.iter().enumerate() {
                df.dados[j].push(r.get(c).cloned().unwrap_or(Cell::Null));
            }
        }
        df
    }

    // ------------------------------------------------------------------
    // Seleção / filtragem
    // ------------------------------------------------------------------

    /// `df[mask]` — máscara booleana por índice.
    pub fn filtrar_mask(&self, mask: &[bool]) -> DataFrame {
        let keep: Vec<usize> = (0..mask.len()).filter(|&i| mask[i]).collect();
        self.selecionar_linhas(&keep)
    }

    /// `df.iloc[indices]`
    pub fn selecionar_linhas(&self, indices: &[usize]) -> DataFrame {
        DataFrame {
            colunas: self.colunas.clone(),
            dados: self
                .dados
                .iter()
                .map(|col| indices.iter().map(|&i| col.get(i).cloned().unwrap_or(Cell::Null)).collect())
                .collect(),
        }
    }

    /// `df[cols]` — reordena/restringe colunas.
    pub fn selecionar_colunas(&self, cols: &[&str]) -> DataFrame {
        let mut out = DataFrame::new();
        for c in cols {
            if let Ok(i) = self.idx(c) {
                out.colunas.push((*c).to_string());
                out.dados.push(self.dados[i].clone());
            }
        }
        out
    }

    /// Concatenação vertical (`pd.concat([a, b])`).
    pub fn concat(frames: &[&DataFrame]) -> DataFrame {
        // União de colunas na ordem de aparecimento
        let mut colunas: Vec<String> = Vec::new();
        for f in frames {
            for c in &f.colunas {
                if !colunas.contains(c) {
                    colunas.push(c.clone());
                }
            }
        }
        let mut out = DataFrame { colunas: colunas.clone(), dados: vec![Vec::new(); colunas.len()] };
        for f in frames {
            let n = f.len();
            for (j, c) in colunas.iter().enumerate() {
                match f.idx(c) {
                    Ok(i) => out.dados[j].extend(f.dados[i].iter().take(n).cloned()),
                    Err(_) => out.dados[j].extend(std::iter::repeat(Cell::Null).take(n)),
                }
            }
        }
        out
    }

    // ------------------------------------------------------------------
    // Estatísticas
    // ------------------------------------------------------------------

    /// Chave de deduplicação (NaN-aware, como pandas drop_duplicates).
    fn chave_linha(&self, cols: &[usize], i: usize) -> String {
        cols.iter()
            .map(|&j| match &self.dados[j][i] {
                Cell::Number(n) => n.to_string(),
                Cell::String(s) => s.clone(),
                Cell::Bool(b) => b.to_string(),
                _ => "\u{0}nan".to_string(),
            })
            .collect::<Vec<_>>()
            .join("\u{1}")
    }

    /// `df[col].nunique()`
    pub fn n_unique(&self, col: &str) -> usize {
        match self.idx(col) {
            Ok(i) => {
                let mut s = std::collections::HashSet::new();
                for v in &self.dados[i] {
                    if !v.is_null() {
                        s.insert(chave_celula(v));
                    }
                }
                s.len()
            }
            Err(_) => 0,
        }
    }

    /// `len(df.drop_duplicates(subset=cols))`
    pub fn n_unique_multi(&self, cols: &[&str]) -> usize {
        let idxs: Vec<usize> = cols.iter().filter_map(|c| self.idx(c).ok()).collect();
        if idxs.is_empty() {
            return 0;
        }
        let mut s = std::collections::HashSet::new();
        for i in 0..self.len() {
            s.insert(self.chave_linha(&idxs, i));
        }
        s.len()
    }

    /// `df.dropna(subset=[col])`
    pub fn dropna(&self, col: &str) -> DataFrame {
        match self.idx(col) {
            Ok(i) => {
                let mask: Vec<bool> = self.dados[i].iter().map(|v| !v.is_null()).collect();
                self.filtrar_mask(&mask)
            }
            Err(_) => self.clone(),
        }
    }

    /// `df.sort_values(by=col)` estável, ascendente. Nulls por último (como pandas).
    pub fn sort_values(&self, col: &str) -> DataFrame {
        let mut idx: Vec<usize> = (0..self.len()).collect();
        let j = match self.idx(col) {
            Ok(j) => j,
            Err(_) => return self.clone(),
        };
        idx.sort_by(|&a, &b| cmp_celula(&self.dados[j][a], &self.dados[j][b]));
        self.selecionar_linhas(&idx)
    }

    /// `df.value_counts()` — contagem de ocorrências, ordem decrescente.
    pub fn value_counts(&self, col: &str) -> Vec<(Cell, usize)> {
        let j = match self.idx(col) {
            Ok(j) => j,
            Err(_) => return Vec::new(),
        };
        let mut cont: std::collections::HashMap<String, (Cell, usize)> = Default::default();
        for v in &self.dados[j] {
            if v.is_null() {
                continue;
            }
            let k = chave_celula(v);
            let e = cont.entry(k).or_insert((v.clone(), 0));
            e.1 += 1;
        }
        let mut out: Vec<(Cell, usize)> = cont.into_values().collect();
        out.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| cmp_celula(&a.0, &b.0)));
        out
    }

    /// `df.groupby(col)` — retorna grupos (chave, índices de linha), estáveis
    /// na ordem de primeira aparição.
    pub fn groupby(&self, col: &str) -> Vec<(Cell, Vec<usize>)> {
        let j = match self.idx(col) {
            Ok(j) => j,
            Err(_) => return Vec::new(),
        };
        let mut mapa: Vec<(String, Cell, Vec<usize>)> = Vec::new();
        for (i, v) in self.dados[j].iter().enumerate() {
            let k = chave_celula(v);
            match mapa.iter_mut().find(|(kk, _, _)| *kk == k) {
                Some((_, _, ids)) => ids.push(i),
                None => mapa.push((k, v.clone(), vec![i])),
            }
        }
        mapa.into_iter().map(|(_, chave, ids)| (chave, ids)).collect()
    }

    /// Subconjunto de linhas pelos índices (para reconstruir grupos).
    pub fn grupo(&self, ids: &[usize]) -> DataFrame {
        self.selecionar_linhas(ids)
    }
}

impl Default for DataFrame {
    fn default() -> Self {
        Self::new()
    }
}

fn chave_celula(v: &Cell) -> String {
    match v {
        Cell::Number(n) => n.to_string(),
        Cell::String(s) => s.clone(),
        Cell::Bool(b) => b.to_string(),
        _ => "\u{0}nan".to_string(),
    }
}

/// Comparação com semântica pandas: null sempre por último; números antes/depois
/// de strings por tipo (estável — desempate por igualdade de tipos).
pub fn cmp_celula(a: &Cell, b: &Cell) -> Ordering {
    match (a.is_null(), b.is_null()) {
        (true, true) => Ordering::Equal,
        (true, false) => Ordering::Greater,
        (false, true) => Ordering::Less,
        _ => match (a.as_f64(), b.as_f64()) {
            (Some(x), Some(y)) => x.partial_cmp(&y).unwrap_or(Ordering::Equal),
            (Some(_), None) => Ordering::Less, // numéricos antes de strings
            (None, Some(_)) => Ordering::Greater,
            (None, None) => a.to_string().cmp(&b.to_string()),
        },
    }
}

// ---------------------------------------------------------------------------
// CSV (substitui pd.read_csv nas partes usadas)
// ---------------------------------------------------------------------------

/// Parseia uma linha CSV com suporte a aspas (RFC-4180 simplificado).
pub fn parse_csv_line(linha: &str) -> Vec<String> {
    let mut campos = Vec::new();
    let mut atual = String::new();
    let mut dentro_aspas = false;
    let mut chars = linha.chars().peekable();
    while let Some(c) = chars.next() {
        match c {
            '"' => {
                if dentro_aspas && chars.peek() == Some(&'"') {
                    atual.push('"');
                    chars.next();
                } else {
                    dentro_aspas = !dentro_aspas;
                }
            }
            ',' if !dentro_aspas => {
                campos.push(std::mem::take(&mut atual));
            }
            _ => atual.push(c),
        }
    }
    campos.push(atual);
    campos
}

/// Converte campo CSV em célula: tenta número, senão string; vazio → Null (NaN).
pub fn cell_from_csv(campo: &str) -> Cell {
    let t = campo.trim();
    if t.is_empty() {
        return Cell::Null;
    }
    if let Ok(n) = t.parse::<f64>() {
        if n.fract() == 0.0 && n.abs() < 1e15 {
            return Value::from(n as i64);
        }
        return Cell::from(n);
    }
    Cell::String(campo.to_string())
}

impl DataFrame {
    /// `pd.read_csv(path)` — heurística de separador: se a 1ª linha tiver mais
    /// ';' que ',', usa ponto-e-vírgula (comportamento observado nos CSVs Anatel).
    pub fn read_csv(path: &std::path::Path) -> Result<DataFrame, String> {
        let conteudo = std::fs::read_to_string(path)
            .map_err(|e| format!("Falha ao ler {}: {e}", path.display()))?;
        Self::from_csv_str(&conteudo)
    }

    pub fn from_csv_str(conteudo: &str) -> Result<DataFrame, String> {
        let mut linhas = conteudo.lines().filter(|l| !l.trim().is_empty());
        let cabecalho = linhas.next().ok_or("CSV vazio")?;
        let sep = if cabecalho.matches(';').count() > cabecalho.matches(',').count() {
            ';'
        } else {
            ','
        };
        let head = cabecalho.replace(sep, "\u{0}");
        let _ = head;
        let split_sep = |l: &str| -> Vec<String> {
            if sep == ';' {
                l.split(';').map(|s| s.trim_matches('"').to_string()).collect()
            } else {
                parse_csv_line(l)
            }
        };
        let colunas: Vec<String> = split_sep(cabecalho)
            .into_iter()
            .map(|c| c.trim().replace('\u{feff}', ""))
            .collect();
        let n = colunas.len();
        let mut dados: Vec<Vec<Cell>> = vec![Vec::new(); n];
        for l in linhas {
            let campos = split_sep(l);
            for j in 0..n {
                dados[j].push(match campos.get(j) {
                    Some(c) => cell_from_csv(c),
                    None => Cell::Null,
                });
            }
        }
        Ok(DataFrame { colunas, dados })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn df_exemplo() -> DataFrame {
        DataFrame::from_csv_str("A;B\n1;x\n2;y\n1;z").unwrap()
    }

    #[test]
    fn basics() {
        let df = df_exemplo();
        assert_eq!(df.len(), 3);
        assert!(!df.is_empty());
        assert_eq!(df.celula(1, "B"), Cell::String("y".into()));
        assert_eq!(df.n_unique("A"), 2);
    }

    #[test]
    fn filtro_e_ordem() {
        let df = df_exemplo();
        let mask = vec![true, false, true];
        let f = df.filtrar_mask(&mask);
        assert_eq!(f.len(), 2);
        let s = df.sort_values("B");
        assert_eq!(s.celula(0, "B"), Cell::String("x".into()));
    }

    #[test]
    fn value_counts_groupby() {
        let df = df_exemplo();
        let vc = df.value_counts("A");
        assert_eq!(vc[0].0, Value::from(1i64));
        assert_eq!(vc[0].1, 2);
        let g = df.groupby("A");
        assert_eq!(g.len(), 2);
        assert_eq!(g[0].1.len(), 2);
    }
}
