//! Motor de unificação de bairros por município.
//!
//! Porta 1:1 de `torre_facil/dados/bairros.py`.
//!
//! Complementa [`crate::texto`] (que faz limpeza/expansão por linha) com a
//! consolidação por cidade, usando:
//!     - Chave canônica (tokens ordenados sem stopwords)
//!     - ``SequenceMatcher`` para grafias próximas (porta de difflib)
//!     - Regras de "opostos" (NORTE/SUL, NOVO/VELHO, etc.)
//!     - Cache em JSON por ``UF|MUNICIPIO``

use std::collections::{HashMap, HashSet};

use crate::config::arquivo_cache_bairros;
use crate::dataframe::DataFrame;
use crate::estado;
use crate::texto;

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------

/// Prefixos que NÃO participam da unificação (`_IGNORES`)
pub const IGNORES: [&str; 4] = ["SEM BAIRRO", "ZONA RURAL", "RODOVIA", "BAIRRO NÃO"];

/// Palavras que, quando divergem entre dois candidatos, IMPEDEM a fusão (`_OPOSTOS`)
pub const OPOSTOS: [&str; 15] = [
    "NORTE", "SUL", "LESTE", "OESTE", "ALTO", "BAIXO", "NOVA", "VELHA", "NOVO", "VELHO",
    "CENTRO", "PRAIA", "PARQUE", "JARDIM", "VILA",
];

/// Limiares do algoritmo de fusão
const LIMITE_BUSCA_RAPIDA: usize = 200;
const LIMITE_CANDIDATOS_CONSOLIDADAS: usize = 220;
const SIMILARIDADE_MINIMA: f64 = 0.84;
const PROPORCAO_MINIMA_PREFIXO: f64 = 0.40;
const TAMANHO_MINIMO_PREFIXO: usize = 6;
const TAMANHO_MINIMO_SEQUENCE: usize = 5;
const DIFERENCA_MAXIMA_TAMANHO: i64 = 2;

fn opostos_set() -> HashSet<&'static str> {
    OPOSTOS.iter().copied().collect()
}

fn eh_ignorado(nome: &str) -> bool {
    IGNORES.iter().any(|p| nome.starts_with(p))
}

// ---------------------------------------------------------------------------
// SequenceMatcher (porta mínima de difflib.SequenceMatcher.ratio)
// ---------------------------------------------------------------------------

/// Tamanho máximo do matching bloco a bloco (equivalente ao algoritmo
/// `find_longest_match` recursivo do difflib, versão "quick_ratio=False").
fn maior_bloco_comum(a: &[char], b: &[char]) -> usize {
    let n = a.len();
    let m = b.len();
    if n == 0 || m == 0 {
        return 0;
    }
    // DP clássico de substring comum mais longo
    let mut melhor = 0usize;
    let mut prev = vec![0usize; m + 1];
    for i in 1..=n {
        let mut cur = vec![0usize; m + 1];
        for j in 1..=m {
            if a[i - 1] == b[j - 1] {
                cur[j] = prev[j - 1] + 1;
                if cur[j] > melhor {
                    melhor = cur[j];
                }
            }
        }
        prev = cur;
    }
    melhor
}

/// Similaridade total (difflib: soma dos blocos do matching recursivo / tamanho médio).
/// Implementação fiel: particiona recursivamente pelo maior bloco comum.
pub fn sequence_matcher_ratio(a: &str, b: &str) -> f64 {
    let av: Vec<char> = a.chars().collect();
    let bv: Vec<char> = b.chars().collect();
    let mut matches = 0usize;
    sm_rec(&av, &bv, &mut matches);
    let total = av.len() + bv.len();
    if total == 0 {
        return 1.0;
    }
    (2 * matches) as f64 / total as f64
}

fn sm_rec(a: &[char], b: &[char], matches: &mut usize) {
    if a.is_empty() || b.is_empty() {
        return;
    }
    let (i, j, k) = find_longest_match(a, b);
    if k == 0 {
        return;
    }
    *matches += k;
    sm_rec(&a[..i], &b[..j], matches);
    sm_rec(&a[i + k..], &b[j + k..], matches);
}

/// Equivalente a `SequenceMatcher.find_longest_match` do difflib:
/// retorna (i, j, size) do maior bloco comum, preferindo o mais à esquerda
/// em `a` e, entre iguais, o mais à esquerda em `b`.
fn find_longest_match(a: &[char], b: &[char]) -> (usize, usize, usize) {
    let n = a.len();
    let m = b.len();
    let mut melhor = (0usize, 0usize, 0usize);
    if n == 0 || m == 0 {
        return melhor;
    }
    // best[j] = tamanho do sufixo comum terminando em a[i-1]/b[j-1]
    let mut prev = vec![0usize; m + 1];
    for i in 1..=n {
        let mut cur = vec![0usize; m + 1];
        for j in 1..=m {
            if a[i - 1] == b[j - 1] {
                cur[j] = prev[j - 1] + 1;
            }
            let size = cur[j];
            if size > melhor.2 {
                melhor = (i - size, j - size, size);
            }
        }
        prev = cur;
    }
    melhor
}

#[allow(dead_code)]
fn _usa_maior_bloco(a: &str, b: &str) -> usize {
    maior_bloco_comum(&a.chars().collect::<Vec<char>>(), &b.chars().collect::<Vec<char>>())
}

// ---------------------------------------------------------------------------
// Cache de bairros em disco (JSON por cidade)
// ---------------------------------------------------------------------------

/// Carrega cache de bairros unificados do disco.
pub fn carregar_cache_bairros_disco() -> HashMap<String, HashMap<String, String>> {
    let caminho = arquivo_cache_bairros();
    if !caminho.exists() {
        return HashMap::new();
    }
    match std::fs::read_to_string(&caminho) {
        Ok(txt) => serde_json::from_str(&txt).unwrap_or_default(),
        Err(_) => {
            estado::info_set_ultimo_erro("Falha ao carregar cache de bairros");
            HashMap::new()
        }
    }
}

/// Salva cache de bairros unificados no disco.
pub fn salvar_cache_bairros_disco(mapa_cidades: &HashMap<String, HashMap<String, String>>) {
    let caminho = arquivo_cache_bairros();
    match serde_json::to_string_pretty(mapa_cidades) {
        Ok(json) => {
            if std::fs::write(&caminho, json).is_err() {
                estado::info_set_ultimo_erro("Falha ao salvar cache de bairros");
            }
        }
        Err(_) => estado::info_set_ultimo_erro("Falha ao salvar cache de bairros"),
    }
}

// ---------------------------------------------------------------------------
// Helpers internos
// ---------------------------------------------------------------------------

/// Remove sufixo de UF do nome do município e converte para maiúsculas.
pub fn reduzir_municipio(mun: &str) -> String {
    static RE: std::sync::OnceLock<regex::Regex> = std::sync::OnceLock::new();
    let re = RE.get_or_init(|| regex::Regex::new(r"(?i)\s*-\s*[A-Za-z]{2}$").unwrap());
    re.replace(mun, "").to_uppercase()
}

/// Conta ocorrências de cada bairro por município → {"UF|MUN": {"BAIRRO": cont}}.
fn contar_bairros_por_cidade(
    ufs: &[String],
    muns: &[String],
    bairros: &[String],
) -> HashMap<String, Vec<(String, i64)>> {
    // Vec mantém ordem de inserção (como dict do Python)
    let mut contagem: HashMap<String, Vec<(String, i64)>> = HashMap::new();
    for (u, m, b) in ufs.iter().zip(muns.iter()).zip(bairros.iter()).map(|((u, m), b)| (u, m, b)) {
        let chave_cid = format!("{u}|{m}");
        let d_cid = contagem.entry(chave_cid).or_default();
        match d_cid.iter_mut().find(|(nome, _)| nome == b) {
            Some(e) => e.1 += 1,
            None => d_cid.push((b.clone(), 1)),
        }
    }
    contagem
}

/// Seleciona cidades que precisam de recompilação.
fn selecionar_cidades_pendentes(
    contagem_por_cidade: &HashMap<String, Vec<(String, i64)>>,
    cache_bairros_cidades: &HashMap<String, HashMap<String, String>>,
    forcar_recompilacao: bool,
    ordem: &[String],
) -> Vec<(String, Vec<(String, i64)>)> {
    if forcar_recompilacao {
        return ordem
            .iter()
            .filter_map(|k| contagem_por_cidade.get(k).map(|v| (k.clone(), v.clone())))
            .collect();
    }
    let mut pendentes: Vec<(String, Vec<(String, i64)>)> = Vec::new();
    for chave_cid in ordem {
        let cont = match contagem_por_cidade.get(chave_cid) {
            Some(c) => c,
            None => continue,
        };
        if cont.len() <= 1 {
            continue;
        }
        let cache_cid = cache_bairros_cidades.get(chave_cid);
        match cache_cid {
            None => pendentes.push((chave_cid.clone(), cont.clone())),
            Some(cid) => {
                // Se algum bairro novo apareceu, recompila
                let faltando = cont
                    .iter()
                    .any(|(b, _)| !cid.contains_key(b) && !eh_ignorado(b));
                if faltando {
                    pendentes.push((chave_cid.clone(), cont.clone()));
                }
            }
        }
    }
    pendentes
}

/// Aplica mapeamento de unificação nas listas de bairros.
fn aplicar_mapeamento(
    ufs: &[String],
    muns: &[String],
    bairros: &[String],
    cache_bairros_cidades: &HashMap<String, HashMap<String, String>>,
) -> Vec<String> {
    let mut resultado: Vec<String> = Vec::with_capacity(bairros.len());
    for (u, m, b) in ufs.iter().zip(muns.iter()).zip(bairros.iter()).map(|((u, m), b)| (u, m, b)) {
        let chave = format!("{u}|{m}");
        match cache_bairros_cidades.get(&chave).and_then(|mc| mc.get(b)) {
            Some(novo) => resultado.push(novo.clone()),
            None => resultado.push(b.clone()),
        }
    }
    resultado
}

// ---------------------------------------------------------------------------
// Unificação por município (função principal)
// ---------------------------------------------------------------------------

/// Coluna como lista de strings (fillna("") + tolist() do pandas).
fn coluna_strings(df: &DataFrame, nome: &str) -> Vec<String> {
    df.coluna_ref(nome)
        .map(|col| {
            col.iter()
                .map(|v| match v {
                    serde_json::Value::Null => String::new(),
                    serde_json::Value::String(s) => s.clone(),
                    other => other.to_string(),
                })
                .collect()
        })
        .unwrap_or_else(|| vec![String::new(); df.len()])
}

/// Unifica bairros por município usando cache e heurísticas.
pub fn unificar_bairros_por_municipio(
    df_erbs: &DataFrame,
    forcar_recompilacao: bool,
) -> Vec<String> {
    let ufs_col = coluna_strings(df_erbs, "UF");
    let muns_col = coluna_strings(df_erbs, "MUNICIPIO");
    let bairros_col = coluna_strings(df_erbs, "BAIRRO");

    let mut cache_bairros_cidades = if forcar_recompilacao {
        HashMap::new()
    } else {
        carregar_cache_bairros_disco()
    };

    // Ordem de primeira aparição das chaves de cidade (dict Python é ordenado)
    let contagem_por_cidade = contar_bairros_por_cidade(&ufs_col, &muns_col, &bairros_col);
    let mut ordem_chaves: Vec<String> = Vec::new();
    for chave in contagem_por_cidade.keys() {
        ordem_chaves.push(chave.clone());
    }
    // preserva ordem original de inserção rederiving:
    ordem_chaves.clear();
    for (u, m) in ufs_col.iter().zip(muns_col.iter()) {
        let k = format!("{u}|{m}");
        if !ordem_chaves.contains(&k) {
            ordem_chaves.push(k);
        }
    }

    // 2) Seleciona cidades pendentes
    let pendentes = selecionar_cidades_pendentes(
        &contagem_por_cidade,
        &cache_bairros_cidades,
        forcar_recompilacao,
        &ordem_chaves,
    );

    // 3) Processa pendentes com barra de progresso
    if !pendentes.is_empty() {
        processar_pendentes(&pendentes, &mut cache_bairros_cidades);
        salvar_cache_bairros_disco(&cache_bairros_cidades);
    }

    // 4) Estatística global
    let total_unif: i64 = cache_bairros_cidades.values().map(|m| m.len() as i64).sum();
    estado::info_set_bairros_unificados(total_unif);

    // 5) Aplica mapeamento
    aplicar_mapeamento(&ufs_col, &muns_col, &bairros_col, &cache_bairros_cidades)
}

/// Callback de progresso (injetável; padrão: no-op fora da TUI).
pub fn desenhar_progresso(perc: f64, titulo: &str, frase: &str, detalhe_extra: &str) {
    // Em modo não-TUI (testes/CLI) apenas registra em stderr quando verbose.
    if std::env::var("TORRE_FACIL_VERBOSE").is_ok() {
        eprintln!("[{perc:>3.0}%] {titulo} — {frase} {detalhe_extra}");
    }
}

/// Processa cidades pendentes de unificação.
fn processar_pendentes(
    pendentes: &[(String, Vec<(String, i64)>)],
    cache_bairros_cidades: &mut HashMap<String, HashMap<String, String>>,
) {
    let total_pend = pendentes.len();
    let passo_barra = (total_pend / 50).max(1);

    for (idx_c, (chave_cid, contagem)) in pendentes.iter().enumerate() {
        let idx_c = idx_c + 1;
        let (uf, mun) = match chave_cid.split_once('|') {
            Some(p) => p,
            None => continue,
        };
        let mun_limpo = reduzir_municipio(mun);
        let mun_norm = texto::normalizar_texto(Some(&mun_limpo));

        // Atualiza barra de progresso
        if contagem.len() > 40 || idx_c % passo_barra == 0 || idx_c == total_pend {
            let perc = 75.0 + (idx_c as f64 / total_pend as f64) * 14.0;
            let detalhe = format!(
                "Município {idx_c}/{total_pend}: {}/{} ({} locais)",
                truncate_chars(&mun_limpo, 22),
                uf,
                contagem.len()
            );
            desenhar_progresso(
                perc,
                "COMPILANDO DICIONÁRIO NACIONAL DE BAIRROS",
                "Padronizando abreviações, acentos e grafias próximas...",
                &detalhe,
            );
        }

        let mapa_cid = unificar_uma_cidade(contagem, &mun_norm);
        cache_bairros_cidades.insert(chave_cid.clone(), mapa_cid);
    }
}

fn truncate_chars(s: &str, n: usize) -> String {
    s.chars().take(n).collect()
}

// ---------------------------------------------------------------------------
// Unificação de uma cidade
// ---------------------------------------------------------------------------

/// Unifica os bairros de UMA cidade. Retorna mapa `{nome_orig: nome_final}`.
pub fn unificar_uma_cidade(
    contagem: &[(String, i64)],
    mun_norm: &str,
) -> HashMap<String, String> {
    // 1) Agrupa por chave canônica
    let (grupos, mapa_nome_chave) = agrupar_por_chave_canonica(contagem);
    if grupos.is_empty() {
        return HashMap::new();
    }

    // 2) Escolhe representante de cada grupo
    let (mut rep_por_chave, freq_por_chave) = escolher_representantes(&grupos, contagem);

    // 3) Mescla chaves próximas
    let (redir, consolidadas) = mesclar_chaves_proximas(&mut rep_por_chave, &freq_por_chave, mun_norm);

    // 4) Atalho para "SEM BAIRRO (...)"
    let busca_rapida = construir_busca_rapida(&consolidadas, &rep_por_chave, mun_norm);

    // 5) Monta mapa final
    montar_mapa_final(contagem, &mapa_nome_chave, &redir, &rep_por_chave, &busca_rapida)
}

type Grupos = Vec<(String, Vec<String>)>;

/// Agrupa bairros por chave canônica → (grupos, mapa_nome_chave).
fn agrupar_por_chave_canonica(contagem: &[(String, i64)]) -> (Grupos, HashMap<String, String>) {
    let mut grupos: Grupos = Vec::new();
    let mut mapa_nome_chave: HashMap<String, String> = HashMap::new();

    for (nome, _) in contagem {
        if eh_ignorado(nome) {
            continue;
        }
        let ch = texto::chave_canonica_bairro(nome);
        if ch.is_empty() {
            continue;
        }
        mapa_nome_chave.insert(nome.clone(), ch.clone());
        match grupos.iter_mut().find(|(k, _)| *k == ch) {
            Some((_, nomes)) => nomes.push(nome.clone()),
            None => grupos.push((ch, vec![nome.clone()])),
        }
    }
    (grupos, mapa_nome_chave)
}

/// Escolhe representante de cada grupo (mais frequente, com acento, mais longo).
fn escolher_representantes(
    grupos: &Grupos,
    contagem: &[(String, i64)],
) -> (HashMap<String, String>, HashMap<String, i64>) {
    let mut rep_por_chave: HashMap<String, String> = HashMap::new();
    let mut freq_por_chave: HashMap<String, i64> = HashMap::new();

    for (ch, lista) in grupos {
        let melhor = lista
            .iter()
            .max_by_key(|x| {
                let cnt = contagem.iter().find(|(n, _)| n == *x).map(|(_, c)| *c).unwrap_or(0);
                let tem_acento = x.chars().any(|c| (c as u32) > 127);
                let len = x.chars().count();
                (cnt, tem_acento, len)
            })
            .cloned()
            .unwrap_or_default();
        let freq: i64 = lista
            .iter()
            .map(|n| contagem.iter().find(|(x, _)| x == n).map(|(_, c)| *c).unwrap_or(0))
            .sum();
        rep_por_chave.insert(ch.clone(), melhor);
        freq_por_chave.insert(ch.clone(), freq);
    }
    (rep_por_chave, freq_por_chave)
}

/// Mescla chaves canônicas próximas → (redir, consolidadas).
fn mesclar_chaves_proximas(
    rep_por_chave: &mut HashMap<String, String>,
    freq_por_chave: &HashMap<String, i64>,
    mun_norm: &str,
) -> (HashMap<String, String>, Vec<String>) {
    let mut chaves_ord: Vec<String> = rep_por_chave.keys().cloned().collect();
    chaves_ord.sort_by(|a, b| {
        let ka = (freq_por_chave[a], a.chars().count());
        let kb = (freq_por_chave[b], b.chars().count());
        kb.cmp(&ka) // reverse=True
    });

    let mut redir: HashMap<String, String> = HashMap::new();
    let mut consolidadas: Vec<String> = Vec::new();

    for ch in chaves_ord {
        if let Some(alvo) = buscar_alvo_proximo(&ch, &consolidadas, mun_norm) {
            redir.insert(ch.clone(), alvo.clone());
            // Promove representante se o novo for mais frequente/longo
            let len_ch = rep_por_chave[&ch].chars().count();
            let len_alvo = rep_por_chave[&alvo].chars().count();
            if len_ch > len_alvo && freq_por_chave[&ch] >= freq_por_chave[&alvo] {
                let rep = rep_por_chave[&ch].clone();
                rep_por_chave.insert(alvo.clone(), rep);
            }
        } else {
            consolidadas.push(ch.clone());
            redir.insert(ch.clone(), ch.clone());
        }
    }
    (redir, consolidadas)
}

/// Constrói lista de busca rápida para "SEM BAIRRO (...)".
fn construir_busca_rapida(
    consolidadas: &[String],
    rep_por_chave: &HashMap<String, String>,
    mun_norm: &str,
) -> Vec<(String, String)> {
    let mut busca_rapida: Vec<(String, String)> = consolidadas
        .iter()
        .take(LIMITE_BUSCA_RAPIDA)
        .filter(|c| c.chars().count() >= 5 && *c != mun_norm)
        .map(|c| (format!(" {c} "), rep_por_chave[c].clone()))
        .collect();
    busca_rapida.sort_by(|a, b| b.0.chars().count().cmp(&a.0.chars().count())); // key=len, reverse
    busca_rapida
}

/// Monta mapa final `{nome_orig: nome_final}`.
fn montar_mapa_final(
    contagem: &[(String, i64)],
    mapa_nome_chave: &HashMap<String, String>,
    redir: &HashMap<String, String>,
    rep_por_chave: &HashMap<String, String>,
    busca_rapida: &[(String, String)],
) -> HashMap<String, String> {
    let mut mapa_cid: HashMap<String, String> = HashMap::new();

    for (nome, _) in contagem {
        if !eh_ignorado(nome) && mapa_nome_chave.contains_key(nome) {
            let ch_orig = &mapa_nome_chave[nome];
            let ch_dest = redir.get(ch_orig).unwrap_or(ch_orig);
            let novo = &rep_por_chave[ch_dest];
            if novo != nome {
                mapa_cid.insert(nome.clone(), novo.clone());
            }
        } else if nome.starts_with("SEM BAIRRO") && !busca_rapida.is_empty() {
            let norm = texto::normalizar_texto(Some(nome));
            let sem = texto::re_nao_alfanum().replace_all(&norm, " ");
            let texto_limpo = texto::re_espacos().replace_all(&sem, " ").into_owned();
            let texto_limpo = format!(" {texto_limpo} ");
            for (padrao_b, rep_b) in busca_rapida {
                if texto_limpo.contains(padrao_b.as_str()) {
                    mapa_cid.insert(nome.clone(), rep_b.clone());
                    break;
                }
            }
        }
    }
    mapa_cid
}

// ---------------------------------------------------------------------------
// Busca de alvo próximo (SequenceMatcher)
// ---------------------------------------------------------------------------

/// Encontra uma chave já consolidada próxima o suficiente para mesclar.
fn buscar_alvo_proximo(ch: &str, consolidadas: &[String], mun_norm: &str) -> Option<String> {
    let ch_sem_esp: String = ch.chars().filter(|c| *c != ' ').collect();
    let tokens_ch: HashSet<&str> = ch.split_whitespace().collect();

    for cand in consolidadas.iter().take(LIMITE_CANDIDATOS_CONSOLIDADAS) {
        if let Some(alvo) = tentar_match_com_candidato(ch, &ch_sem_esp, &tokens_ch, cand, mun_norm) {
            return Some(alvo);
        }
    }
    None
}

/// Tenta encontrar match entre chave e candidato.
fn tentar_match_com_candidato(
    ch: &str,
    ch_sem_esp: &str,
    tokens_ch: &HashSet<&str>,
    cand: &str,
    mun_norm: &str,
) -> Option<String> {
    let cand_sem_esp: String = cand.chars().filter(|c| *c != ' ').collect();

    // 1) Idênticos após remover espaços
    if ch_sem_esp == cand_sem_esp {
        return Some(cand.to_string());
    }

    let (menor, maior) = if ch.chars().count() <= cand.chars().count() { (ch, cand) } else { (cand, ch) };
    let tam_menor = menor.chars().count();
    let proporcao = tam_menor as f64 / maior.chars().count().max(1) as f64;
    let opostos = opostos_set();

    // 2) Prefixo/sufixo comum
    if tam_menor >= TAMANHO_MINIMO_PREFIXO && proporcao >= PROPORCAO_MINIMA_PREFIXO {
        if maior.starts_with(menor) || maior.ends_with(menor) {
            let resto = maior.replace(menor, "");
            let resto = resto.trim();
            if menor != mun_norm && !opostos.contains(resto) {
                return Some(cand.to_string());
            }
        }

        // 3) Tokens em comum
        let tokens_cand: HashSet<&str> = cand.split_whitespace().collect();
        let ch_sub_cand = tokens_ch.is_subset(&tokens_cand);
        let cand_sub_ch = tokens_cand.is_subset(tokens_ch);
        if ch_sub_cand || cand_sub_ch {
            let dif: HashSet<&str> = symmetric_difference(tokens_ch, &tokens_cand);
            if menor != mun_norm && dif.intersection(&opostos).next().is_none() {
                return Some(cand.to_string());
            }
        }
    }

    // 4) SequenceMatcher (passo caro)
    let l1 = ch_sem_esp.chars().count();
    let l2 = cand_sem_esp.chars().count();
    if l1 >= TAMANHO_MINIMO_SEQUENCE && (l1 as i64 - l2 as i64).abs() <= DIFERENCA_MAXIMA_TAMANHO {
        let c1: Vec<char> = ch_sem_esp.chars().collect();
        let c2: Vec<char> = cand_sem_esp.chars().collect();
        if c1.first() == c2.first() && c1.last() == c2.last() {
            let sim = sequence_matcher_ratio(ch_sem_esp, &cand_sem_esp);
            if sim >= SIMILARIDADE_MINIMA {
                let tokens_cand: HashSet<&str> = cand.split_whitespace().collect();
                let dif: HashSet<&str> = symmetric_difference(tokens_ch, &tokens_cand);
                if dif.intersection(&opostos).next().is_none() {
                    return Some(cand.to_string());
                }
            }
        }
    }

    None
}

fn symmetric_difference<'a>(a: &HashSet<&'a str>, b: &HashSet<&'a str>) -> HashSet<&'a str> {
    let mut out = HashSet::new();
    for x in a {
        if !b.contains(x) {
            out.insert(*x);
        }
    }
    for x in b {
        if !a.contains(x) {
            out.insert(*x);
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reduzir_municipio_doc() {
        assert_eq!(reduzir_municipio("NATAL - RN"), "NATAL");
        assert_eq!(reduzir_municipio("SAO PAULO-SP"), "SAO PAULO");
    }

    #[test]
    fn sequence_matcher_ratio_basico() {
        // Valores idênticos aos do difflib python (verificados com python3 -c)
        assert_eq!(sequence_matcher_ratio("abcde", "abcde"), 1.0);
        assert_eq!(sequence_matcher_ratio("", ""), 1.0);
        assert!(
            (sequence_matcher_ratio("ab cd", "abcd") - 0.8888888888888888).abs() < 1e-12
        );
        assert!(
            (sequence_matcher_ratio("JARDIM POMPEIA", "JAR DIM POMPEI") - 0.9285714285714286)
                .abs()
                < 1e-12
        );
    }

    #[test]
    fn unificacao_simples() {
        let contagem = vec![
            ("CENTRO".to_string(), 10i64),
            ("Centro".to_string(), 1i64),
            ("CIDADE ALTA".to_string(), 3i64),
            ("CIDADE BAIXA".to_string(), 3i64),
        ];
        let mapa = unificar_uma_cidade(&contagem, "TESTE");
        // "Centro" deve apontar para "CENTRO" (mesma chave canônica)
        assert_eq!(mapa.get("Centro").map(String::as_str), Some("CENTRO"));
        // OPOSTOS impedem fusão de CIDADE ALTA / CIDADE BAIXA
        assert!(!mapa.contains_key("CIDADE BAIXA") || mapa["CIDADE BAIXA"] == "CIDADE BAIXA");
    }

    #[test]
    fn ignora_sem_bairro() {
        let contagem = vec![("SEM BAIRRO (AREA RURAL)".to_string(), 5i64)];
        let mapa = unificar_uma_cidade(&contagem, "TESTE");
        assert!(mapa.is_empty());
    }
}
