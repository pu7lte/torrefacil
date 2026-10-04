//! Dicionários externos em JSON + regex de bairros compiladas.
//!
//! Porta 1:1 de `torre_facil/dicionarios.py`.
//!
//! Estratégia de estado (IMPORTANTE):
//!   ``REGEX_BAIRROS_COMPILADOS`` e ``DICIONARIOS`` são mutados in-place
//!   (via RwLock global), nunca reatribuídos — equivalente ao comportamento
//!   do módulo Python.

use std::path::PathBuf;
use std::sync::{LazyLock, RwLock};

use regex::Regex;
use serde_json::{Map, Value};

use crate::config::arquivo_dicionarios;

pub mod dados {
    include!("dados_dicionarios.rs");
}

// ---------------------------------------------------------------------------
// Estado global — MUTADO in-place, nunca reatribuído
// ---------------------------------------------------------------------------

pub struct RegexBairro {
    pub rx: Regex,
    pub novo: String,
}

static REGEX_BAIRROS_COMPILADOS: RwLock<Vec<RegexBairro>> = RwLock::new(Vec::new());
static DICIONARIOS: LazyLock<RwLock<Value>> = LazyLock::new(|| RwLock::new(Value::Object(Map::new())));

fn log_info(msg: &str) { eprintln!("[INFO] dicionarios: {msg}"); }
fn log_warn(msg: &str) { eprintln!("[WARN] dicionarios: {msg}"); }

/// Instantânea da lista de regex compiladas (clones baratos: Arc interno do Regex).
pub fn regex_bairros_compilados() -> Vec<(Regex, String)> {
    REGEX_BAIRROS_COMPILADOS
        .read()
        .unwrap()
        .iter()
        .map(|r| (r.rx.clone(), r.novo.clone()))
        .collect()
}

pub fn dicionarios_snapshot() -> Value {
    DICIONARIOS.read().unwrap().clone()
}

/// Mapa `operadora_padrao` (nome → termos de busca).
pub fn operadoras_padrao() -> Vec<(String, Vec<String>)> {
    let d = DICIONARIOS.read().unwrap();
    let mut out = Vec::new();
    if let Some(obj) = d.get("operadoras_padrao").and_then(|v| v.as_object()) {
        for (k, v) in obj {
            if let Some(arr) = v.as_array() {
                out.push((k.clone(), arr.iter().filter_map(|x| x.as_str().map(String::from)).collect()));
            }
        }
    } else {
        // fallback: dados padrão embutidos (equivale a carregar_globais automático)
        for (k, v) in dados::operadoras_padrao_dados() {
            out.push((k.to_string(), v.iter().map(|s| s.to_string()).collect()));
        }
    }
    out
}

// ---------------------------------------------------------------------------
// Geração de dicionários padrão
// ---------------------------------------------------------------------------

/// Gera o objeto JSON padrão completo (ufs_brasil, mapa_ufs_br, etc.).
pub fn gerar_dicionarios_padrao() -> Value {
    let mut m = Map::new();

    m.insert(
        "ufs_brasil".into(),
        Value::Array(dados::UFS_BRASIL.iter().map(|u| Value::String(u.to_string())).collect()),
    );

    let mut mapa = Map::new();
    for (k, v) in dados::mapa_ufs_br_dados() {
        mapa.insert(k.to_string(), Value::Array(v.iter().map(|u| Value::String(u.to_string())).collect()));
    }
    m.insert("mapa_ufs_br".into(), Value::Object(mapa));

    m.insert(
        "substituicoes_bairros".into(),
        Value::Array(
            dados::substituicoes_bairros_dados()
                .into_iter()
                .map(|(p, n)| Value::Array(vec![Value::String(p.into()), Value::String(n.into())]))
                .collect(),
        ),
    );

    let mut ops = Map::new();
    for (k, v) in dados::operadoras_padrao_dados() {
        ops.insert(k.to_string(), Value::Array(v.iter().map(|u| Value::String(u.to_string())).collect()));
    }
    m.insert("operadoras_padrao".into(), Value::Object(ops));

    let mut cores = Map::new();
    for (k, v) in dados::cores_kml_dados() {
        cores.insert(k.to_string(), Value::String(v.to_string()));
    }
    m.insert("cores_kml".into(), Value::Object(cores));

    Value::Object(m)
}

// ---------------------------------------------------------------------------
// Compilação de regex
// ---------------------------------------------------------------------------

/// Compila `substituicoes_bairros` para dentro de REGEX_BAIRROS_COMPILADOS.
/// Retorna o número de regexes compiladas com sucesso.
pub fn compilar_regex_dicionarios(dic: &Value) -> usize {
    let substituicoes = dic.get("substituicoes_bairros").and_then(|v| v.as_array()).cloned().unwrap_or_default();
    let mut compiladas: Vec<RegexBairro> = Vec::new();
    let mut erros = 0usize;

    for item in &substituicoes {
        let (padrao, novo) = match item.as_array().filter(|a| a.len() >= 2) {
            Some(a) => (a[0].as_str().unwrap_or("").to_string(), a[1].as_str().unwrap_or("").to_string()),
            None => {
                log_warn(&format!("Item inválido em substituicoes_bairros: {item:?}"));
                erros += 1;
                continue;
            }
        };
        match Regex::new(&padrao) {
            Ok(rx) => compiladas.push(RegexBairro { rx, novo }),
            Err(e) => {
                log_warn(&format!("Regex inválida '{padrao}': {e}"));
                erros += 1;
                continue;
            }
        }
    }

    // Mutação in-place para não quebrar consumidores com import congelado
    *REGEX_BAIRROS_COMPILADOS.write().unwrap() = compiladas;

    log_info(&format!(
        "Compiladas {} regexes de bairro ({erros} erros).",
        REGEX_BAIRROS_COMPILADOS.read().unwrap().len()
    ));
    REGEX_BAIRROS_COMPILADOS.read().unwrap().len()
}

// ---------------------------------------------------------------------------
// Carga e persistência
// ---------------------------------------------------------------------------

fn salvar_json(caminho: &PathBuf, dados: &Value) -> std::io::Result<()> {
    if let Some(parent) = caminho.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let s = serde_json::to_string_pretty(dados).unwrap_or_default();
    std::fs::write(caminho, s)
}

/// Mescla dicionários antigos com o padrão (adiciona substituições faltantes).
fn mesclar_dicionarios_antigos(dados_disco: &mut Value, dados_padrao: &Value) -> Value {
    let existentes: std::collections::HashSet<String> = dados_disco
        .get("substituicoes_bairros")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter_map(|it| it.as_array().and_then(|a| a.first()).and_then(|p| p.as_str()).map(String::from))
                .collect()
        })
        .unwrap_or_default();

    let novas: Vec<Value> = dados_padrao
        .get("substituicoes_bairros")
        .and_then(|v| v.as_array())
        .map(|arr| {
            arr.iter()
                .filter(|it| {
                    it.as_array()
                        .and_then(|a| a.first())
                        .and_then(|p| p.as_str())
                        .map(|p| !existentes.contains(p))
                        .unwrap_or(false)
                })
                .cloned()
                .collect()
        })
        .unwrap_or_default();

    if !novas.is_empty() {
        let qtd = novas.len();
        if let Some(cur) = dados_disco.get_mut("substituicoes_bairros").and_then(|v| v.as_array_mut()) {
            cur.extend(novas.into_iter());
        } else {
            dados_disco["substituicoes_bairros"] = Value::Array(novas);
        }
        log_info(&format!("Mescladas {qtd} substituições faltantes."));
    }
    dados_disco.clone()
}

/// Carrega o JSON do disco (ou cria), compila regex e retorna o dict.
pub fn carregar_ou_criar_dicionarios(forcar_recriacao: bool) -> Value {
    let caminho = arquivo_dicionarios();

    // 1) Recriar do zero se solicitado ou se arquivo não existir
    if forcar_recriacao || !caminho.exists() {
        log_info(&format!("Criando arquivo de dicionários: {}", caminho.display()));
        let dados = gerar_dicionarios_padrao();
        let _ = salvar_json(&caminho, &dados);
        compilar_regex_dicionarios(&dados);
        return dados;
    }

    // 2) Tentar carregar do disco
    match std::fs::read_to_string(&caminho).ok().and_then(|s| serde_json::from_str::<Value>(&s).ok()) {
        Some(mut dados) => {
            // Mescla se o arquivo em disco for antigo (poucas substituições)
            let n_subs = dados.get("substituicoes_bairros").and_then(|v| v.as_array()).map(|a| a.len()).unwrap_or(0);
            if n_subs < 30 {
                let padrao = gerar_dicionarios_padrao();
                dados = mesclar_dicionarios_antigos(&mut dados, &padrao);
                let _ = salvar_json(&caminho, &dados);
            }
            compilar_regex_dicionarios(&dados);
            dados
        }
        None => {
            log_warn("Falha ao carregar dicionários; recriando padrão.");
            let dados = gerar_dicionarios_padrao();
            let _ = salvar_json(&caminho, &dados);
            compilar_regex_dicionarios(&dados);
            dados
        }
    }
}

/// Popula DICIONARIOS e REGEX_BAIRROS_COMPILADOS (in-place) e devolve DICIONARIOS.
pub fn carregar_globais() -> Value {
    let dados = carregar_ou_criar_dicionarios(false);
    *DICIONARIOS.write().unwrap() = dados;
    dicionarios_snapshot()
}

/// Retorna opções de UF para menus/dropdowns: lista de `(valor, rótulo)`.
pub fn obter_opcoes_uf(incluir_todas: bool, rotulo_todas: &str) -> Vec<(String, String)> {
    // auto-carrega os dicionários se necessário — evita listas vazias
    let ufs: Vec<String> = {
        let d = DICIONARIOS.read().unwrap();
        d.get("ufs_brasil")
            .and_then(|v| v.as_array())
            .map(|a| a.iter().filter_map(|x| x.as_str().map(String::from)).collect())
            .unwrap_or_default()
    };
    let ufs = if ufs.is_empty() {
        drop(DICIONARIOS.read().unwrap());
        carregar_globais();
        let d = DICIONARIOS.read().unwrap();
        d.get("ufs_brasil")
            .and_then(|v| v.as_array())
            .map(|a| a.iter().filter_map(|x| x.as_str().map(String::from)).collect())
            .unwrap_or_default()
    } else {
        ufs
    };

    let mut ufs = ufs;
    ufs.sort();
    let mut opcoes: Vec<(String, String)> = Vec::new();
    if incluir_todas {
        opcoes.push((String::new(), rotulo_todas.to_string()));
    }
    opcoes.extend(ufs.into_iter().map(|u| (u.clone(), u)));
    opcoes
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn test_carregar_globais() {
        let dados = carregar_globais();
        assert!(dados.get("operadoras_padrao").is_some());
        assert!(!regex_bairros_compilados().is_empty());
    }
}
