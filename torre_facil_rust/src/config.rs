//! Constantes globais, caminhos e configuração do Torre Fácil.
//!
//! Porta 1:1 de `torre_facil/config.py`.

use std::path::PathBuf;

pub const VERSAO: &str = "10.0.0";
pub const AUTOR: &str = "Seu Nome <seu.email@exemplo.com>";
pub const LICENCA: &str = "MIT";

/// URL do arquivo ZIP com dados de estações SMP da Anatel.
pub const URL_ANATEL: &str = "https://www.anatel.gov.br/dadosabertos/paineis_de_dados/outorga_e_licenciamento/estacoes_smp.zip";

pub const DIAS_EXPIRACAO_CACHE: i64 = 7;
/// Versão do esquema do cache binário.
pub const VERSAO_CACHE: i64 = 5;

pub const NOME_ARQ_ZIP: &str = "estacoes_smp.zip";
pub const NOME_ARQ_CSV_EXTRAIDO: &str = "estacoes_smp_extraido.csv";
pub const NOME_ARQ_CACHE: &str = "torre_facil_cache.pkl";
pub const NOME_ARQ_DICIONARIOS: &str = "torre_facil_dicionarios.json";
pub const NOME_ARQ_CACHE_BAIRROS: &str = "torre_facil_bairros_unificados.json";
pub const NOME_ARQ_SNAPSHOT: &str = "torre_facil_snapshot.json";
pub const NOME_ARQ_SNAPSHOT_ANTERIOR: &str = "torre_facil_snapshot_anterior.json";
pub const NOME_ARQ_CONFIG_USUARIO: &str = "torre_facil_config.json";

/// Ordem de exibição das tecnologias (para ordenação em listas e rankings).
pub fn ordem_tec(tec: &str) -> i32 {
    match tec {
        "E" => 1, // GSM (2G)
        "H" => 2, // HSPA/HSPA+ (3G)
        "L" => 3, // LTE (4G)
        "5" => 4, // 5G NR
        _ => 9,
    }
}

/// Dias da semana em português (abreviados), para exibição na TUI.
pub const DIAS_SEMANA: [&str; 7] = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"];

/// Diretório onde arquivos de dados são armazenados (cache, snapshots, etc.).
/// Usa TORRE_FACIL_DADOS_DIR se disponível, senão ~/.local/share/torre_facil.
pub fn dados_dir() -> PathBuf {
    let base = match std::env::var("TORRE_FACIL_DADOS_DIR") {
        Ok(v) if !v.is_empty() => PathBuf::from(v),
        _ => {
            let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
            PathBuf::from(home).join(".local").join("share").join("torre_facil")
        }
    };
    let _ = std::fs::create_dir_all(&base);
    base
}

pub fn arquivo_zip() -> PathBuf { dados_dir().join(NOME_ARQ_ZIP) }
pub fn arquivo_csv_extraido() -> PathBuf { dados_dir().join(NOME_ARQ_CSV_EXTRAIDO) }
pub fn arquivo_cache() -> PathBuf { dados_dir().join(NOME_ARQ_CACHE) }
pub fn arquivo_dicionarios() -> PathBuf { dados_dir().join(NOME_ARQ_DICIONARIOS) }
pub fn arquivo_cache_bairros() -> PathBuf { dados_dir().join(NOME_ARQ_CACHE_BAIRROS) }
pub fn arquivo_snapshot() -> PathBuf { dados_dir().join(NOME_ARQ_SNAPSHOT) }
pub fn arquivo_snapshot_anterior() -> PathBuf { dados_dir().join(NOME_ARQ_SNAPSHOT_ANTERIOR) }
pub fn arquivo_config_usuario() -> PathBuf { dados_dir().join(NOME_ARQ_CONFIG_USUARIO) }

/// Delay entre quadros da animação de splash (em segundos).
/// Permite acelerar a splash em testes/CI definindo TORRE_FACIL_SPLASH_DELAY=0.
pub fn splash_delay() -> f64 {
    match std::env::var("TORRE_FACIL_SPLASH_DELAY") {
        Ok(v) => match v.parse::<f64>() {
            Ok(valor) => {
                if valor < 0.0 {
                    log_warn(&format!("TORRE_FACIL_SPLASH_DELAY negativo ({valor}); usando 0.0"));
                    return 0.0;
                }
                valor
            }
            Err(_) => {
                log_warn("TORRE_FACIL_SPLASH_DELAY inválido; usando padrão 0.08");
                0.08
            }
        },
        Err(_) => 0.08,
    }
}

fn log_warn(msg: &str) {
    eprintln!("[WARN] config: {msg}");
}
