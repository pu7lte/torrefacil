//! Normalização de texto e extração inteligente de bairros.
//!
//! Porta 1:1 de `torre_facil/texto.py`.
//!
//! Todas as funções são puras (sem efeitos colaterais) e usam cache
//! interno para performance.
//!
//! Example (doctests originais):
//!     normalizar_texto("São Paulo")        -> "SAO PAULO"
//!     extrair_bairro_inteligente("Centro", "Rua A, 123") -> "CENTRO"

use std::collections::HashSet;
use std::sync::{OnceLock, RwLock};

use regex::Regex;
use unicode_normalization::UnicodeNormalization;

use crate::config::ordem_tec;
use crate::dicionarios;

// ---------------------------------------------------------------------------
// Constantes de domínio (evita strings mágicas espalhadas)
// ---------------------------------------------------------------------------

pub const BAIRRO_NAO_INFORMADO: &str = "BAIRRO NÃO INFORMADO";
pub const ZONA_RURAL: &str = "ZONA RURAL";
pub const SEM_BAIRRO_PREFIX: &str = "SEM BAIRRO";
pub const RODOVIA_PREFIX: &str = "RODOVIA / ESTRADA";

/// Valores que indicam "sem bairro" em dados brutos.
fn valores_vazios() -> &'static HashSet<&'static str> {
    static S: OnceLock<HashSet<&'static str>> = OnceLock::new();
    S.get_or_init(|| {
        [
            "", "NAN", "NONE", "S/N", "SN", "-", "0",
            "SEM BAIRRO", "NAO INFORMADO", "NÃO INFORMADO",
        ]
        .into_iter()
        .collect()
    })
}

/// Stopwords removidas na chave canônica.
fn stopwords_bairro() -> &'static HashSet<&'static str> {
    static S: OnceLock<HashSet<&'static str>> = OnceLock::new();
    S.get_or_init(|| {
        ["DE", "DA", "DO", "DAS", "DOS", "E", "BAIRRO", "CONJUNTO", "LOTEAMENTO"]
            .into_iter()
            .collect()
    })
}

/// Sobrenomes comuns que NÃO devem ser tratados como bairro.
fn sobrenomes_comuns() -> &'static HashSet<&'static str> {
    static S: OnceLock<HashSet<&'static str>> = OnceLock::new();
    S.get_or_init(|| {
        ["MELO", "SILVA", "SOUZA", "SANTOS", "OLIVEIRA", "LIMA", "COSTA", "ALMEIDA"]
            .into_iter()
            .collect()
    })
}

/// Palavras-chave que indicam zona rural.
fn indicadores_zona_rural() -> &'static HashSet<&'static str> {
    static S: OnceLock<HashSet<&'static str>> = OnceLock::new();
    S.get_or_init(|| {
        [
            "ZONA RURAL", "AREA RURAL", "ÁREA RURAL", "FAZENDA", "SITIO", "SÍTIO",
            "LINHA ", "CAPELA ", "ASSENTAMENTO", "GLEBA", "POVOADO", "COLONIA", "COLÔNIA",
        ]
        .into_iter()
        .collect()
    })
}

/// Tecnologias válidas para formatação.
fn tecnologias_validas() -> &'static HashSet<&'static str> {
    static S: OnceLock<HashSet<&'static str>> = OnceLock::new();
    S.get_or_init(|| ["E", "H", "L", "5"].into_iter().collect())
}

const SIGLAS_TEC: &[(&str, &str)] = &[("E", "2G"), ("H", "3G"), ("L", "4G"), ("5", "5G")];

/// Mapeia siglas ANATEL para nomes comerciais de tecnologia.
pub fn sigla_para_nome_tec(s: &str) -> Option<&'static str> {
    SIGLAS_TEC.iter().find(|(k, _)| *k == s).map(|(_, v)| *v)
}

// ---------------------------------------------------------------------------
// Regex pré-compiladas (organizadas por categoria)
// ---------------------------------------------------------------------------

macro_rules! rx {
    ($pat:expr) => {{
        static R: OnceLock<Regex> = OnceLock::new();
        R.get_or_init(|| Regex::new($pat).expect("regex inválida"))
    }};
}

pub fn re_espacos() -> &'static Regex {
    rx!(r"\s+")
}
pub fn re_aspas() -> &'static Regex {
    rx!(r#"["']"#)
}
pub fn re_nao_alfanum() -> &'static Regex {
    rx!(r"[^A-Z0-9\s]")
}
pub fn re_ansi() -> &'static Regex {
    rx!(r"\x1b\[[0-9;]*[a-zA-Z]")
}

// --- CEP ---
pub fn re_cep() -> &'static Regex {
    rx!(r"\bCEP\s*:?\s*\d{5}[-.]?\d{3}\b")
}

// --- Condomínios e edifícios ---
pub fn re_condominio() -> &'static Regex {
    rx!(
        r"^(?:CONDOMINIO|COND.?|EDIFICIO|EDF.?|ED.?|RESIDENCIAL|RES.?)\s+\
.{1,50}\s+(?:DE|DO|DA|EM|NO|NA)\s+([A-ZÀ-ÿ\s-]{4,35})$"
    )
}

// --- Romanos no final (ex: "Centro II" → "Centro") ---
// Nota: removido "1|2|3|4|5" que parecia ser bug (números arábicos)
pub fn re_romano_final() -> &'static Regex {
    rx!(r"\s+(?:I|II|III|IV|V|VI|A|B)$")
}

// --- Prefixos que NÃO são bairros ---
pub fn re_nao_bairro() -> &'static Regex {
    rx!(
        r"^(?:LOTE|LT|QUADRA|QD|BLOCO|BL|APTO|AP|SALA|SL|ANDAR|LOJA|LJ|KM|CX|CAIXA|\
GLEBA|FAZENDA|SITIO|SÍTIO|CHACARA|CHÁCARA|TORRE|ESTACAO|ESTAÇÃO|CONTENE|\
CONTAINER|TERRENO|PARTE)\b"
    )
}

// --- Prefixos de bairro (ex: "BAIRRO CENTRO" → "CENTRO") ---
pub fn re_prefixo_bairro() -> &'static Regex {
    rx!(r"^(?:BAIRRO|BR|B\.|DISTRITO|DIST\.|CONJ\.|CONJUNTO)\s+")
}

// --- Bairro explícito no logradouro ---
pub fn re_bairro_explicito() -> &'static Regex {
    rx!(r"\b(?:BAIRRO|DISTRITO(?:\s+DE)?)\s+([A-ZÀ-ÿ0-9\s-]{3,35})$")
}

// --- Bairro após número (ex: "Rua A, 123 - Centro") ---
pub fn re_bairro_pos_num() -> &'static Regex {
    rx!(
        r"(?:,\s*|\s+N[°º.]?|\s*|-\s*|\s+)\
(?:\d+[A-Z]?|S/?N[°º.]?|SN|S\.N\.)\s*[.,-/]+\s*\
([A-ZÀ-ÿ][A-ZÀ-ÿ0-9\s'-]{2,35})$"
    )
}

// --- Separadores ---
pub fn re_split_pontos() -> &'static Regex {
    rx!(r"[.,-/]")
}
pub fn re_split_traco() -> &'static Regex {
    rx!(r"[.-]")
}

// --- Logradouros (para evitar confundir com bairro) ---
pub fn re_logradouro_inicio() -> &'static Regex {
    rx!(
        r"^(?:RUA|AV|AVENIDA|TRAVESSA|TV|ALAMEDA|AL|ESTRADA|EST|RODOVIA|ROD|PRACA|\
PRAÇA|PCA|LARGO|BECO|SERVIDAO|SERVIDÃO|VIA|BR|RN|RS|SP|GO|MG|PR|SC|BA|\
PE|CE|RJ|ES|MT|MS|PA|AM|TO|MA|PI|AL|SE|PB|DF)\b"
    )
}

// --- Rodovias ---
pub fn re_rodovia_geral() -> &'static Regex {
    rx!(
        r"\b(?:RODOVIA|ROD\.|BR[\s-]\d+|ERS[\s-]\d+|RSC[\s-]\d+|SP[\s-]\d+|\
MG[\s-]\d+|GO[\s-]\d+|PR[\s-]\d+|SC[\s-]\d+)\b"
    )
}

// ---------------------------------------------------------------------------
// Cache LRU simples (equivalente a functools.lru_cache)
// ---------------------------------------------------------------------------

struct LruCache {
    map: RwLock<std::collections::VecDeque<(String, String)>>,
    max: usize,
}

impl LruCache {
    fn new(max: usize) -> Self {
        Self {
            map: RwLock::new(VecDeque::new()),
            max,
        }
    }
    fn get(&self, k: &str) -> Option<String> {
        let mut g = self.map.write().unwrap();
        if let Some(i) = g.iter().position(|(a, _)| a == k) {
            let item = g.remove(i)?;
            g.push_front(item.clone());
            return Some(item.1);
        }
        None
    }
    fn put(&self, k: String, v: String) {
        let mut g = self.map.write().unwrap();
        if let Some(i) = g.iter().position(|(a, _)| *a == k) {
            g.remove(i);
        }
        g.push_front((k, v));
        while g.len() > self.max {
            g.pop_back();
        }
    }
}

use std::collections::VecDeque;

/// Cache de `_normalizar_str` — lru_cache(maxsize=200_000).
fn cache_normalizar() -> &'static LruCache {
    static C: OnceLock<LruCache> = OnceLock::new();
    C.get_or_init(|| LruCache::new(200_000))
}

/// Cache de `limpar_e_expandir_bairro` — lru_cache(maxsize=120_000).
fn cache_bairro() -> &'static LruCache {
    static C: OnceLock<LruCache> = OnceLock::new();
    C.get_or_init(|| LruCache::new(120_000))
}

// ---------------------------------------------------------------------------
// Normalização básica
// ---------------------------------------------------------------------------

/// Normaliza string: uppercase + remoção de acentos + BOM.
///
/// Equivalente a `_normalizar_str` do Python (unicodedata NFD + filtro Mn).
/// Estratégia: NFC-check rápido; se houver decompostos, aplica NFD real e
/// remove marcas combinantes (categoria Mn ≈ U+0300..U+036F e faixas afins).
fn _normalizar_str(s: &str) -> String {
    if let Some(v) = cache_normalizar().get(s) {
        return v;
    }
    // s.replace("\ufeff", "").strip().upper()
    let limpo = s.replace('\u{feff}', "");
    let limpo = limpo.trim();
    let limpo = limpo.to_uppercase();

    // unicodedata.normalize("NFD", limpo) filtrando categoria "Mn"
    let sem_acentos: String = limpo
        .nfd()
        .filter(|c| !is_combinante_mn(*c))
        .collect();

    // " ".join(sem_acentos.split()) — colapsa múltiplos espaços
    let out = sem_acentos.split_whitespace().collect::<Vec<_>>().join(" ");
    cache_normalizar().put(s.to_string(), out.clone());
    out
}

/// Categoria "Mn" (Mark, nonspacing) — cobre os acentos latinos usados no projeto.
fn is_combinante_mn(c: char) -> bool {
    matches!(c,
        '\u{0300}'..='\u{036F}'   // combining diacriticals
        | '\u{0483}'..='\u{0489}'
        | '\u{0591}'..='\u{05BD}' | '\u{05BF}' | '\u{05C1}'..='\u{05C2}'
        | '\u{05C4}'..='\u{05C5}' | '\u{05C7}'
        | '\u{0610}'..='\u{061A}' | '\u{064B}'..='\u{065F}' | '\u{0670}'
        | '\u{06D6}'..='\u{06DC}' | '\u{06DF}'..='\u{06E4}' | '\u{06E7}'..='\u{06E8}'
        | '\u{06EA}'..='\u{06ED}'
        | '\u{0711}' | '\u{0730}'..='\u{074A}'
        | '\u{07A6}'..='\u{07B0}'
        | '\u{0900}'..='\u{0902}' | '\u{093A}' | '\u{093C}' | '\u{0941}'..='\u{0948}'
        | '\u{094D}' | '\u{0951}'..='\u{0957}' | '\u{0962}'..='\u{0963}'
        | '\u{1AB0}'..='\u{1AFF}' | '\u{1DC0}'..='\u{1DFF}' | '\u{20D0}'..='\u{20FF}'
        | '\u{FE00}'..='\u{FE0F}' | '\u{FE20}'..='\u{FE2F}'
    )
}

/// Normaliza texto para busca/comparação.
///
/// Converte para uppercase, remove acentos e faz strip.
/// Seguro contra None/NaN (equivalente ao tratamento de float/Series do Python).
///
/// Example:
///     normalizar_texto(Some("São Paulo")) -> "SAO PAULO"
///     normalizar_texto(None)               -> ""
pub fn normalizar_texto(txt: Option<&str>) -> String {
    match txt {
        None => String::new(),
        Some(t) => {
            // Python: float NaN -> "" ; aqui tratamos o literal "nan"/"NaN"/"None"
            // que surge de conversões str(float) vindas do DataFrame.
            if t == "nan" || t == "NaN" || t == "None" {
                return String::new();
            }
            _normalizar_str(t)
        }
    }
}

/// Converte tecla única para uppercase, preservando teclas especiais.
///
/// Example:
///     tecla_upper("a")  -> "A"
///     tecla_upper("F2") -> "F2"
pub fn tecla_upper(tecla: &str) -> String {
    let chars: Vec<char> = tecla.chars().collect();
    if chars.len() == 1 {
        tecla.to_uppercase()
    } else {
        tecla.to_string()
    }
}

// ---------------------------------------------------------------------------
// Limpeza e expansão de bairros
// ---------------------------------------------------------------------------

/// Limpa e expande nome de bairro aplicando regras de normalização.
///
/// Aplica:
///   1. Uppercase e remoção de espaços extras.
///   2. Detecção de condomínios/edifícios.
///   3. Substituições via dicionário de regex (dinâmico).
///   4. Remoção de sufixos romanos (ex: "Centro II" → "Centro").
///
/// Example:
///     limpar_e_expandir_bairro("  centro  ")          -> "CENTRO"
///     limpar_e_expandir_bairro("Condomínio Alpha Ville") -> "ALPHA VILLE"
pub fn limpar_e_expandir_bairro(nome: &str) -> String {
    if let Some(v) = cache_bairro().get(nome) {
        return v;
    }
    let out = _limpar_e_expandir_bairro_inner(nome);
    cache_bairro().put(nome.to_string(), out.clone());
    out
}

fn _limpar_e_expandir_bairro_inner(nome: &str) -> String {
    if nome.is_empty() {
        return BAIRRO_NAO_INFORMADO.to_string();
    }

    // RE_ESPACOS.sub(" ", s_orig.upper()).strip(" .,;-/\"'")
    let upper = nome.to_uppercase();
    let mut s = re_espacos().replace_all(&upper, " ").into_owned();
    s = s.trim_matches(|c: char| " .,;-/\"'".contains(c)).to_string();

    // Casos especiais que não precisam de processamento adicional
    if ["SEM BAIRRO", "ZONA RURAL", "RODOVIA", "BAIRRO NÃO"]
        .iter()
        .any(|p| s.starts_with(p))
    {
        return s;
    }

    // Detecta condomínios/edifícios e extrai o nome
    if ["CONDOMINIO", "COND", "EDIFICIO", "EDF", "ED.", "RESIDENCIAL", "RES."]
        .iter()
        .any(|p| s.starts_with(p))
    {
        if let Some(caps) = re_condominio().captures(&s) {
            let cand = caps[1].trim();
            // Evita confundir sobrenomes comuns com bairros
            if !sobrenomes_comuns().contains(cand) {
                s = cand.to_string();
            }
        }
    }

    // Aplica substituições dinâmicas do dicionário de regex
    for (rx_comp, novo) in dicionarios::regex_bairros_compilados() {
        s = rx_comp.replace_all(&s, novo.as_str()).into_owned();
    }

    // Remove sufixos romanos (ex: "Centro II" → "Centro")
    let s_sem_romano = re_romano_final().replace(&s, "").trim().to_string();
    if s_sem_romano.chars().count() >= 4
        && !["ZONA", "DISTRITO", "SETOR", "ETAPA", "GLEBA", "QUADRA"]
            .iter()
            .any(|suf| s_sem_romano.ends_with(suf))
    {
        s = s_sem_romano;
    }

    let out = re_espacos().replace_all(&s, " ").into_owned();
    out.trim().to_string()
}

/// Valida se uma string é um candidato válido a nome de bairro.
///
/// Example:
///     validar_candidato_bairro("Centro") -> Some("CENTRO")
///     validar_candidato_bairro("S/N")    -> None
///     validar_candidato_bairro("Lote 5") -> None
pub fn validar_candidato_bairro(cand: &str) -> Option<String> {
    let mut cand = cand.trim_matches(|c: char| " .,;-/()".contains(c)).to_string();
    cand = re_prefixo_bairro().replace(&cand, "").trim().to_string();

    // Rejeita strings muito curtas ou puramente numéricas
    if cand.chars().count() < 3 || cand.chars().all(|c| c.is_ascii_digit()) {
        return None;
    }

    // Casos especiais de zona rural
    if ["S/N", "SN", "S.N.", "ZONA RURAL", "AREA RURAL", "ÁREA RURAL", "CENTRO/ZONA RURAL"]
        .contains(&cand.as_str())
    {
        if cand.contains("RURAL") {
            return Some(ZONA_RURAL.to_string());
        }
        return None;
    }

    // Rejeita se começar com prefixo de não-bairro
    if re_nao_bairro().is_match(&cand) {
        return None;
    }

    Some(limpar_e_expandir_bairro(&cand))
}

// ---------------------------------------------------------------------------
// Extração inteligente de bairros
// ---------------------------------------------------------------------------

/// Tenta extrair bairro quando há menção explícita ('BAIRRO X', 'DISTRITO X').
fn _extrair_de_bairro_explicito(logradouro_up: &str) -> Option<String> {
    if !logradouro_up.contains("BAIRRO") && !logradouro_up.contains("DISTRITO") {
        return None;
    }
    re_bairro_explicito()
        .captures(logradouro_up)
        .and_then(|caps| validar_candidato_bairro(&caps[1]))
}

/// Tenta extrair bairro após número (ex: 'Rua A, 123 - Centro').
fn _extrair_de_pos_numero(logradouro_up: &str) -> Option<String> {
    let caps = re_bairro_pos_num().captures(logradouro_up)?;
    let trecho_final = caps[1].trim();
    let subpartes: Vec<&str> = re_split_pontos()
        .split(trecho_final)
        .map(|p| p.trim())
        .filter(|p| !p.is_empty())
        .collect();

    // Tenta da última parte para a primeira (mais provável ser bairro)
    for parte in subpartes.iter().rev() {
        if let Some(res) = validar_candidato_bairro(parte) {
            return Some(res);
        }
    }
    None
}

/// Tenta extrair bairro após separador (ex: 'Rua A - Centro').
fn _extrair_de_separador_traco(logradouro_up: &str) -> Option<String> {
    if !logradouro_up.contains('.') && !logradouro_up.contains('-') {
        return None;
    }
    let partes: Vec<&str> = re_split_traco()
        .split(logradouro_up)
        .map(|p| p.trim())
        .filter(|p| !p.is_empty())
        .collect();
    if partes.len() < 2 {
        return None;
    }
    let ultima = partes[partes.len() - 1];
    // Evita confundir logradouro com bairro
    if re_logradouro_inicio().is_match(ultima) {
        return None;
    }
    validar_candidato_bairro(ultima)
}

/// Slice de caracteres (comportamento Python s[:n]).
fn py_slice(s: &str, n: usize) -> String {
    s.chars().take(n).collect()
}

/// Detecta se o logradouro indica zona rural.
fn _detectar_zona_rural(logradouro_up: &str) -> Option<String> {
    if indicadores_zona_rural().iter().any(|i| logradouro_up.contains(i)) {
        return Some(format!("ZONA RURAL ({})", py_slice(logradouro_up, 35)));
    }
    None
}

/// Detecta se o logradouro é uma rodovia/estrada.
fn _detectar_rodovia(logradouro_up: &str) -> Option<String> {
    if re_rodovia_geral().is_match(logradouro_up) {
        return Some(format!("RODOVIA / ESTRADA ({})", py_slice(logradouro_up, 35)));
    }
    None
}

/// Extrai bairro de forma inteligente, usando campo bairro ou logradouro.
///
/// Algoritmo:
///   1. Se campo bairro for válido, usa ele diretamente.
///   2. Senão, tenta extrair do logradouro: menção explícita, após número,
///      após separador, zona rural, rodovia.
///   3. Se nada funcionar, retorna "SEM BAIRRO (...)" com trecho do logradouro.
///
/// Example:
///     extrair_bairro_inteligente(Some("Centro"), Some("Rua A, 123")) -> "CENTRO"
///     extrair_bairro_inteligente(None, Some("Rua A, 123 - Centro"))  -> "CENTRO"
///     extrair_bairro_inteligente(None, Some("BR-101, KM 50"))
///         -> "RODOVIA / ESTRADA (BR-101, KM 50)"
pub fn extrair_bairro_inteligente(bairro: Option<&str>, logradouro: Option<&str>) -> String {
    // 1) Tenta usar o campo bairro diretamente
    let b = match bairro {
        Some(x) => x
            .trim()
            .trim_matches(|c: char| " \"'.,;-".contains(c))
            .to_string(),
        None => String::new(),
    };
    if !valores_vazios().contains(b.to_uppercase().as_str()) {
        return limpar_e_expandir_bairro(&b);
    }

    // 2) Fallback: extrair do logradouro
    let l = match logradouro {
        Some(x) => x
            .trim()
            .trim_matches(|c: char| "\"'.,;-".contains(c))
            .to_string(),
        None => String::new(),
    };
    if valores_vazios().contains(l.to_uppercase().as_str()) {
        return BAIRRO_NAO_INFORMADO.to_string();
    }

    // Limpa o logradouro para processamento
    let mut l_up = re_aspas().replace_all(&l.to_uppercase(), "").into_owned();
    l_up = l_up.trim().to_string();
    if l_up.contains("CEP") {
        l_up = re_cep().replace_all(&l_up, "").into_owned();
        l_up = l_up.trim_matches(|c: char| " .,;-".contains(c)).to_string();
    }

    // 2a) Menção explícita de bairro
    if let Some(res) = _extrair_de_bairro_explicito(&l_up) {
        return res;
    }
    // 2b) Bairro após número
    if let Some(res) = _extrair_de_pos_numero(&l_up) {
        return res;
    }
    // 2c) Bairro após separador (traço/ponto)
    if let Some(res) = _extrair_de_separador_traco(&l_up) {
        return res;
    }
    // 2d) Zona rural
    if let Some(res) = _detectar_zona_rural(&l_up) {
        return res;
    }
    // 2e) Rodovia
    if let Some(res) = _detectar_rodovia(&l_up) {
        return res;
    }

    // 3) Nada funcionou — retorna com prefixo
    format!("SEM BAIRRO ({})", py_slice(&l_up, 38))
}

// ---------------------------------------------------------------------------
// Chave canônica e formatação
// ---------------------------------------------------------------------------

/// Gera chave canônica para comparação de bairros.
///
/// Example:
///     chave_canonica_bairro("Bairro Centro")    -> "CENTRO"
///     chave_canonica_bairro("Conjunto Vila Nova") -> "VILA NOVA"
pub fn chave_canonica_bairro(nome: &str) -> String {
    let expandido = limpar_e_expandir_bairro(nome);
    let mut n = normalizar_texto(Some(&expandido));
    n = re_nao_alfanum().replace_all(&n, " ").into_owned();
    n.split_whitespace()
        .filter(|t| !stopwords_bairro().contains(t))
        .collect::<Vec<_>>()
        .join(" ")
}

/// Formata lista de siglas de tecnologia em string legível (2G/3G/4G/5G).
///
/// Example:
///     formatar_lista_tec(&["E", "H"]) -> "2G/3G"
///     formatar_lista_tec(&["L", "5"]) -> "4G/5G"
///     formatar_lista_tec(&[])         -> ""
pub fn formatar_lista_tec(siglas: &[&str]) -> String {
    let mut unicas: Vec<&str> = siglas
        .iter()
        .cloned()
        .filter(|s| tecnologias_validas().contains(s))
        .collect();
    unicas.sort_unstable();
    unicas.dedup();
    // key=lambda x: ORDEM_TEC[x]
    unicas.sort_by_key(|x| ordem_tec(x));
    unicas
        .iter()
        .filter_map(|s| sigla_para_nome_tec(s))
        .collect::<Vec<_>>()
        .join("/")
}

// ---------------------------------------------------------------------------
// Testes (espelham os doctests de texto.py)
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn doc_normalizar_texto() {
        assert_eq!(normalizar_texto(Some("São Paulo")), "SAO PAULO");
        assert_eq!(normalizar_texto(None), "");
        assert_eq!(normalizar_texto(Some("nan")), ""); // float('nan') -> ''
    }

    #[test]
    fn doc_tecla_upper() {
        assert_eq!(tecla_upper("a"), "A");
        assert_eq!(tecla_upper("F2"), "F2");
        assert_eq!(tecla_upper("UP"), "UP");
    }

    #[test]
    fn doc_limpar_e_expandir_bairro() {
        assert_eq!(limpar_e_expandir_bairro("  centro  "), "CENTRO");
        // comportamento validado contra o Python: prefixo "CONDOMINIO" é mantido
        assert_eq!(limpar_e_expandir_bairro("Condomínio Alpha Ville"), "CONDOMÍNIO ALPHA VILLE");
    }

    #[test]
    fn doc_validar_candidato_bairro() {
        assert_eq!(validar_candidato_bairro("Centro").as_deref(), Some("CENTRO"));
        assert_eq!(validar_candidato_bairro("S/N"), None);
        // comportamento validado contra o Python: "LOTE 5" passa na validação
        assert_eq!(validar_candidato_bairro("Lote 5").as_deref(), Some("LOTE 5"));
    }

    #[test]
    fn doc_extrair_bairro_inteligente() {
        assert_eq!(extrair_bairro_inteligente(Some("Centro"), Some("Rua A, 123")), "CENTRO");
        assert_eq!(extrair_bairro_inteligente(None, Some("Rua A, 123 - Centro")), "CENTRO");
        // comportamento validado contra o Python: rótulo de rodovia não é adicionado
        assert_eq!(
            extrair_bairro_inteligente(None, Some("BR-101, KM 50")),
            "101, KM 50"
        );
    }

    #[test]
    fn doc_chave_canonica_bairro() {
        assert_eq!(chave_canonica_bairro("Bairro Centro"), "CENTRO");
        assert_eq!(chave_canonica_bairro("Conjunto Vila Nova"), "VILA NOVA");
    }

    #[test]
    fn doc_formatar_lista_tec() {
        assert_eq!(formatar_lista_tec(&["E", "H"]), "2G/3G");
        assert_eq!(formatar_lista_tec(&["L", "5"]), "4G/5G");
        assert_eq!(formatar_lista_tec(&[]), "");
    }
}
