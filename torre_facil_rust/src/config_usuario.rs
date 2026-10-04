//! Configurações do usuário persistidas em JSON.
//!
//! Porta 1:1 de `torre_facil/config_usuario.py`.
//!
//! Configurações disponíveis:
//!   - paleta: Paleta de cores da TUI (ex: "classic", "green", "amber").
//!   - modo: Modo de operação padrão ("loja" ou "analista"), ou None.
//!   - favoritos: Lista de endereços favoritos (modo loja).
//!   - fundo: Padrão de fundo do desktop ("nu", "xadrez", "grade").

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::config::arquivo_config_usuario;

pub const FUNDOS_VALIDOS: [&str; 3] = ["nu", "xadrez", "grade"];
pub const MODOS_VALIDOS: [&str; 2] = ["loja", "analista"];

/// Estrutura de um endereço favorito.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Favorito {
    pub endereco: String,
    pub apelido: String,
}

/// Schema das configurações do usuário.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ConfigUsuario {
    #[serde(default = "default_paleta")]
    pub paleta: String,
    #[serde(default)]
    pub modo: Option<String>,
    #[serde(default)]
    pub favoritos: Vec<Favorito>,
    #[serde(default = "default_fundo")]
    pub fundo: String,
}

fn default_paleta() -> String {
    "classic".into()
}
fn default_fundo() -> String {
    "nu".into()
}

impl Default for ConfigUsuario {
    fn default() -> Self {
        Self {
            paleta: default_paleta(),
            modo: None,
            favoritos: Vec::new(),
            fundo: default_fundo(),
        }
    }
}

fn log_debug(msg: &str) {
    eprintln!("[DEBUG] config_usuario: {msg}");
}
fn log_warn(msg: &str) {
    eprintln!("[WARN] config_usuario: {msg}");
}

/// Valida e normaliza a lista de favoritos (equivalente a `_validar_favoritos`).
fn validar_favoritos(brutos: &Value) -> Vec<Favorito> {
    let Some(arr) = brutos.as_array() else {
        return Vec::new();
    };
    let mut validos = Vec::new();
    for item in arr {
        let Some(obj) = item.as_object() else { continue };
        let endereco = obj
            .get("endereco")
            .map(|v| v.as_str().unwrap_or("").to_string())
            .unwrap_or_default();
        let endereco = endereco.trim().to_string();
        if endereco.is_empty() {
            continue;
        }
        let apelido_raw = obj
            .get("apelido")
            .and_then(|v| v.as_str())
            .unwrap_or(&endereco)
            .to_string();
        let mut apelido = apelido_raw.trim().to_string();
        if apelido.is_empty() {
            apelido = endereco.clone();
        }
        validos.push(Favorito { endereco, apelido });
    }
    validos
}

/// Carrega configurações do arquivo JSON (defaults se ausente/corrompido).
pub fn carregar_config() -> ConfigUsuario {
    let path = arquivo_config_usuario();
    if !path.exists() {
        log_debug("Arquivo de configuração não encontrado; usando defaults.");
        return ConfigUsuario::default();
    }
    match std::fs::read_to_string(&path)
        .map_err(|e| e.to_string())
        .and_then(|s| serde_json::from_str::<Value>(&s).map_err(|e| e.to_string()))
    {
        Ok(dados) => {
            // Normalização idêntica ao Python: valores fora do domínio viram default/None.
            let paleta = dados
                .get("paleta")
                .and_then(|v| v.as_str())
                .unwrap_or("classic")
                .to_string();
            let modo = dados
                .get("modo")
                .and_then(|v| v.as_str())
                .filter(|m| MODOS_VALIDOS.contains(m))
                .map(|m| m.to_string());
            let fav_padrao = Value::Array(Vec::new());
            let favoritos = validar_favoritos(dados.get("favoritos").unwrap_or(&fav_padrao));
            let fundo = dados
                .get("fundo")
                .and_then(|v| v.as_str())
                .filter(|f| FUNDOS_VALIDOS.contains(f))
                .unwrap_or("nu")
                .to_string();
            log_debug(&format!("Configuração carregada: paleta={paleta}, modo={modo:?}"));
            ConfigUsuario { paleta, modo, favoritos, fundo }
        }
        Err(e) => {
            log_warn(&format!("Arquivo de configuração corrompido ({e}); usando defaults."));
            ConfigUsuario::default()
        }
    }
}

/// Salva configurações no arquivo JSON.
pub fn salvar_config(config: &ConfigUsuario) -> bool {
    let path = arquivo_config_usuario();
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    // Ordem das chaves como no dict Python: paleta, modo, favoritos, fundo.
    let dados = serde_json::json!({
        "paleta": config.paleta,
        "modo": config.modo,
        "favoritos": config.favoritos,
        "fundo": config.fundo,
    });
    match serde_json::to_string_pretty(&dados) {
        Ok(s) => match std::fs::write(&path, s) {
            Ok(_) => {
                log_debug("Configuração salva com sucesso.");
                true
            }
            Err(e) => {
                eprintln!("[ERROR] Falha ao salvar configuração em {}: {e}", path.display());
                false
            }
        },
        Err(_) => false,
    }
}

// ---------------------------------------------------------------------------
// Paleta de cores
// ---------------------------------------------------------------------------

/// Retorna o nome da paleta de cores atual.
pub fn obter_paleta() -> String {
    carregar_config().paleta
}

/// Define a paleta de cores.
pub fn definir_paleta(nome: &str) -> bool {
    let mut config = carregar_config();
    config.paleta = nome.to_string();
    salvar_config(&config)
}

// ---------------------------------------------------------------------------
// Modo de uso
// ---------------------------------------------------------------------------

/// Retorna o modo de operação salvo ("loja", "analista", ou None).
pub fn obter_modo() -> Option<String> {
    carregar_config().modo
}

/// Define o modo de operação padrão. False se inválido ou falhar.
pub fn definir_modo(nome: &str) -> bool {
    if !MODOS_VALIDOS.contains(&nome) {
        log_warn(&format!("Modo inválido: '{nome}'. Use {MODOS_VALIDOS:?}."));
        return false;
    }
    let mut config = carregar_config();
    config.modo = Some(nome.to_string());
    salvar_config(&config)
}

/// Remove o modo salvo (voltará a perguntar na próxima execução).
pub fn esquecer_modo() -> bool {
    let mut config = carregar_config();
    config.modo = None;
    salvar_config(&config)
}

// ---------------------------------------------------------------------------
// Padrão de fundo
// ---------------------------------------------------------------------------

/// Retorna o padrão de fundo do desktop.
pub fn obter_fundo() -> String {
    carregar_config().fundo
}

/// Define o padrão de fundo do desktop. False se inválido ou falhar.
pub fn definir_fundo(nome: &str) -> bool {
    if !FUNDOS_VALIDOS.contains(&nome) {
        log_warn(&format!("Fundo inválido: '{nome}'. Use {FUNDOS_VALIDOS:?}."));
        return false;
    }
    let mut config = carregar_config();
    config.fundo = nome.to_string();
    salvar_config(&config)
}

// ---------------------------------------------------------------------------
// Favoritos
// ---------------------------------------------------------------------------

/// Retorna a lista de endereços favoritos.
pub fn listar_favoritos() -> Vec<Favorito> {
    carregar_config().favoritos
}

/// Adiciona ou atualiza um endereço favorito (case-insensitive por endereço).
pub fn adicionar_favorito(endereco: &str, apelido: &str) -> bool {
    let endereco = endereco.trim().to_string();
    if endereco.is_empty() {
        log_warn("Endereço vazio; favorito não adicionado.");
        return false;
    }

    let mut config = carregar_config();

    // Verifica se já existe (case-insensitive)
    if let Some(fav) = config
        .favoritos
        .iter_mut()
        .find(|f| f.endereco.to_uppercase() == endereco.to_uppercase())
    {
        if !apelido.is_empty() {
            let a = apelido.trim();
            fav.apelido = if a.is_empty() { endereco.clone() } else { a.to_string() };
        }
        log_debug(&format!("Favorito atualizado: {endereco}"));
        return salvar_config(&config);
    }

    let apelido_final = {
        let a = apelido.trim();
        if a.is_empty() { endereco.clone() } else { a.to_string() }
    };
    config.favoritos.push(Favorito { endereco: endereco.clone(), apelido: apelido_final });
    log_debug(&format!("Favorito adicionado: {endereco}"));
    salvar_config(&config)
}

/// Remove um endereço favorito. False se não encontrado ou falhar.
pub fn remover_favorito(endereco: &str) -> bool {
    let mut config = carregar_config();
    let endereco_upper = endereco.trim().to_uppercase();

    let antes = config.favoritos.len();
    config
        .favoritos
        .retain(|fav| fav.endereco.to_uppercase() != endereco_upper);

    if config.favoritos.len() == antes {
        log_debug(&format!("Favorito não encontrado: {endereco}"));
        return false;
    }
    log_debug(&format!("Favorito removido: {endereco}"));
    salvar_config(&config)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Isola o arquivo de config por teste via TORRE_FACIL_DADOS_DIR.
    /// Os testes rodam serializados (SERIAL_LOCK) porque a variável de ambiente
    /// é global ao processo — equivalente ao `monkeypatch.setenv` do pytest.
    static SERIAL_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

    fn dir_tempo(nome: &str) -> (tempfile::TempDir, std::sync::MutexGuard<'static, ()>) {
        let guard = SERIAL_LOCK.lock().unwrap_or_else(|e| e.into_inner());
        let t = tempfile::tempdir().unwrap();
        std::env::set_var("TORRE_FACIL_DADOS_DIR", t.path().join(nome));
        (t, guard)
    }

    #[test]
    fn doc_exemplo_obter_definir_modo() {
        let (_t, _g) = dir_tempo("modo");
        assert_eq!(obter_modo(), None); // sem arquivo -> default None
        assert!(definir_modo("loja"));
        assert_eq!(obter_modo().as_deref(), Some("loja"));
        assert!(!definir_modo("invalido"));
        assert!(esquecer_modo());
        assert_eq!(obter_modo(), None);
    }

    #[test]
    fn favoritos_fluxo() {
        let (_t, _g) = dir_tempo("fav");
        assert!(adicionar_favorito("Rua A, 100", ""));
        assert_eq!(listar_favoritos().len(), 1);
        assert_eq!(listar_favoritos()[0].apelido, "Rua A, 100");
        assert!(adicionar_favorito("rua a, 100", "Casa")); // atualiza (case-insensitive)
        assert_eq!(listar_favoritos().len(), 1);
        assert_eq!(listar_favoritos()[0].apelido, "Casa");
        assert!(remover_favorito("RUA A, 100"));
        assert!(!remover_favorito("RUA A, 100"));
        assert!(listar_favoritos().is_empty());
        assert!(!adicionar_favorito("   ", ""));
    }

    #[test]
    fn paleta_e_fundo() {
        let (_t, _g) = dir_tempo("paleta");
        assert_eq!(obter_paleta(), "classic");
        assert!(definir_paleta("green"));
        assert_eq!(obter_paleta(), "green");
        assert_eq!(obter_fundo(), "nu");
        assert!(!definir_fundo("bolhas"));
        assert!(definir_fundo("grade"));
        assert_eq!(obter_fundo(), "grade");
    }

    #[test]
    fn corrompido_usa_defaults() {
        let (_t, _g) = dir_tempo("corrompido");
        let path = arquivo_config_usuario();
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(&path, "{isso não é json}").unwrap();
        let c = carregar_config();
        assert_eq!(c, ConfigUsuario::default());
    }
}
