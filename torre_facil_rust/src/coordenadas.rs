//! Conversões de coordenadas e padronizações da base Anatel.
//!
//! Porta 1:1 de `torre_facil/coordenadas.py`.

use std::collections::HashMap;
use std::sync::OnceLock;

use regex::Regex;

use crate::dicionarios;

const VALORES_VAZIOS: [&str; 6] = ["", "NAN", "NONE", "NULL", "-", "S/N"];
const LIMIAR_HEURISTICA_SUL: f64 = 15.0;

fn re_gms_sufixo() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| {
        Regex::new(r"^(\d{2})(\d{2})(\d{2}(?:[.,]\d+)?)\s*([NS])$", ).unwrap()
    })
}
fn re_gms_prefixo() -> &'static Regex {
    static R: OnceLock<Regex> = OnceLock::new();
    R.get_or_init(|| Regex::new(r"^([EW])\s*(\d{2})(\d{2})(\d{2}(?:[.,]\d+)?)$").unwrap())
}

/// Converte GMS (Graus Minutos Segundos) para graus decimais.
///
/// # Exemplos (equivalentes ao doctest Python)
/// * `graus_minutos_segundos_para_decimal(23, 59, 7.0, -1)` → `-23.985278`
pub fn graus_minutos_segundos_para_decimal(graus: f64, minutos: f64, segundos: f64, hemisferio_pos: i32) -> Option<f64> {
    if !(0.0..=180.0).contains(&graus) || !(0.0..=60.0).contains(&minutos) || !(0.0..=60.0).contains(&segundos) {
        return None;
    }
    let decimal = graus + minutos / 60.0 + segundos / 3600.0;
    let com_sinal = if hemisferio_pos < 0 { -decimal } else { decimal };
    Some(arredondar6(com_sinal))
}

/// Arredonda a 6 casas decimais (comportamento `round(x, 6)` de Python).
fn arredondar6(v: f64) -> f64 {
    (v * 1e6).round() / 1e6
}

/// Processa os grupos capturados de uma regex GMS.
fn processar_match_gms(groups: &[&str], hemisferio_pos: i32) -> Option<f64> {
    // groups na ordem: [hem(?, se prefixo), g, m, s]
    let (g, m, s) = if hemisferio_pos >= 0 && groups.len() == 4 {
        // prefixo: [E/W, grau, min, seg] — validação extra de hemisphere já feita no caller
        (groups[1], groups[2], groups[3])
    } else {
        (groups[0], groups[1], groups[2])
    };

    let graus: f64 = g.parse().ok()?;
    let minutos: f64 = m.parse().ok()?;
    let seg_raw = s.replace(',', ".");
    let segundos: f64 = seg_raw.parse().ok()?;

    if minutos > 60.0 || segundos > 60.0 {
        return None;
    }

    let decimal = graus + minutos / 60.0 + segundos / 3600.0;
    let com_sinal = if hemisferio_pos < 0 { -decimal } else { decimal };
    Some(arredondar6(com_sinal))
}

/// Converte coordenada da Anatel para graus decimais.
///
/// Aceita formatos:
///   - Decimal puro: "-23.985278" ou "23.985278"
///   - GMS sem separador com hemisfério no final: "235907S"
///   - GMS com hemisfério no início: "W0451230"
///
/// Heurística: valores positivos > 15 são invertidos para negativo (Brasil
/// está entre latitudes -33 e +5). Isso corrige dados que vieram sem sinal.
///
/// # Exemplos (equivalentes ao doctest Python)
/// * `converter_coord_anatel("235907S")` → `Some(-23.985278)`
/// * `converter_coord_anatel("-23.985278")` → `Some(-23.985278)`
/// * `converter_coord_anatel("")` → `None` (Python: `None` p/ entrada vazia)
/// * `converter_coord_anatel("invalido")` → `None`
pub fn converter_coord_anatel(valor: &str) -> Option<f64> {
    let v: String = valor.trim().to_uppercase().replace(',', ".");
    if v.is_empty() || VALORES_VAZIOS.contains(&v.as_str()) {
        return None;
    }

    // 1) Tenta decimal puro
    if let Ok(num) = v.parse::<f64>() {
        if (-180.0..=180.0).contains(&num) && num != 0.0 {
            // Heurística: Brasil é hemisfério sul, então valores > 15
            // provavelmente são negativos (dados vieram sem sinal)
            let mut n = num;
            if n > LIMIAR_HEURISTICA_SUL {
                n = -n;
            }
            return Some(arredondar6(n));
        }
    }

    // 2) Tenta GMS com hemisfério no final
    if let Some(caps) = re_gms_sufixo().captures(&v) {
        let g = [&caps[1], &caps[2], &caps[3]];
        return processar_match_gms(&g, -1);
    }

    // 3) Tenta GMS com hemisfério no início
    if let Some(caps) = re_gms_prefixo().captures(&v) {
        let hem = &caps[1];
        let pos = if hem == "E" { 1 } else { -1 };
        let g = [&caps[1], &caps[2], &caps[3], &caps[4]];
        return processar_match_gms(&g, pos);
    }

    None
}

thread_local! {
    static CACHE_OPERADORA: std::sync::LazyLock<std::cell::RefCell<HashMap<String, String>>> = std::sync::LazyLock::new(|| std::cell::RefCell::new(HashMap::new()));
}

/// Mapeia o nome bruto da operadora para a sigla canônica.
///
/// Lê `dicionarios::DICIONARIOS` de forma dinâmica, para funcionar
/// mesmo se o dicionário for carregado depois deste módulo.
///
/// # Exemplos (equivalentes ao doctest Python)
/// * `padronizar_operadora("VIVO S.A.")` → `"VIVO"`
/// * `padronizar_operadora("Claro")` → `"CLARO"`
pub fn padronizar_operadora(nome: &str) -> String {
    CACHE_OPERADORA.with(|cache| {
        if let Some(v) = cache.borrow().get(nome) {
            return v.clone();
        }
        let nome_up = nome.to_uppercase();
        let operadoras = dicionarios::operadoras_padrao();
        let mut resultado = nome_up.clone();
        for (op_padrao, termos) in &operadoras {
            if termos.iter().any(|t| nome_up.contains(t)) {
                resultado = op_padrao.clone();
                break;
            }
        }
        cache.borrow_mut().insert(nome.to_string(), resultado.clone());
        resultado
    })
}

/// Pares (lista de palavras-chave, sigla correspondente) para mapeamento de tecnologia.
fn mapa_tecnologias() -> &'static [(Vec<&'static str>, &'static str)] {
    static M: OnceLock<Vec<(Vec<&'static str>, &'static str)>> = OnceLock::new();
    M.get_or_init(|| {
        vec![
            (vec!["5G", "NR"], "5"),
            (vec!["LTE", "4G"], "L"),
            (vec!["HSPA", "3G", "WCDMA", "EVDO", "TD-SCDMA"], "H"),
            (vec!["GSM", "2G", "EDGE"], "E"),
        ]
    })
}

/// Converte descrição de tecnologia em sigla (E/H/L/5).
///
/// # Exemplos (equivalentes ao doctest Python)
/// * `mapear_sigla_tecnologia("4G LTE")` → `"L"`
/// * `mapear_sigla_tecnologia("5G NR")` → `"5"`
/// * `mapear_sigla_tecnologia("desconhecido")` → `""`
pub fn mapear_sigla_tecnologia(texto: &str) -> &'static str {
    let t = texto.to_uppercase();
    for (palavras, sigla) in mapa_tecnologias() {
        if palavras.iter().any(|p| t.contains(p)) {
            return sigla;
        }
    }
    ""
}

#[cfg(test)]
mod testes {
    use super::*;

    #[test]
    fn test_converter_coord() {
        assert_eq!(converter_coord_anatel("235907S"), Some(-23.985278));
        assert_eq!(converter_coord_anatel("-23.985278"), Some(-23.985278));
        assert_eq!(converter_coord_anatel(""), None);
        assert_eq!(converter_coord_anatel("invalido"), None);
    }

    #[test]
    fn test_gms_decimal() {
        assert_eq!(graus_minutos_segundos_para_decimal(23.0, 59.0, 7.0, -1), Some(-23.985278));
    }

    #[test]
    fn test_operadora() {
        dicionarios::carregar_globais();
        assert_eq!(padronizar_operadora("VIVO S.A."), "VIVO");
        assert_eq!(padronizar_operadora("Claro"), "CLARO");
    }

    #[test]
    fn test_tecnologia() {
        assert_eq!(mapear_sigla_tecnologia("4G LTE"), "L");
        assert_eq!(mapear_sigla_tecnologia("5G NR"), "5");
        assert_eq!(mapear_sigla_tecnologia("desconhecido"), "");
    }
}
