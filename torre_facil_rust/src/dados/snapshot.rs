//! Snapshot e comparação da base ANATEL.
//!
//! Porta 1:1 de `torre_facil/dados/snapshot.py`.
//!
//! Mantém um arquivo `torre_facil_snapshot.json` com o último estado conhecido
//! da base. Na próxima compilação, comparamos o snapshot antigo com o novo e
//! devolvemos uma estrutura de diferenças.

use std::collections::{HashMap, HashSet};

use serde_json::{Map, Value};

use crate::config::arquivo_snapshot;
use crate::dataframe::{cmp_celula, DataFrame};
use crate::estado::formatar_milhar;

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------

/// Nome do arquivo de snapshot (constante própria do módulo Python).
pub const ARQUIVO_SNAPSHOT: &str = "torre_facil_snapshot.json";
pub const VERSAO_SNAPSHOT: i64 = 1;

/// Tecnologias monitoradas (`_TECNOLOGIAS_MONITORADAS`)
const TECNOLOGIAS_MONITORADAS: [&str; 4] = ["5", "L", "H", "E"];

fn celula_str(v: &Value) -> String {
    match v {
        Value::Null => String::new(),
        Value::String(s) => s.clone(),
        other => other.to_string(),
    }
}

// ---------------------------------------------------------------------------
// Geração
// ---------------------------------------------------------------------------

/// Constrói o dict do snapshot a partir do DataFrame.
pub fn gerar_snapshot(df_erbs: Option<&DataFrame>, total_setores: i64, data_base: &str) -> Value {
    let df = match df_erbs {
        Some(d) if !d.is_empty() => d,
        _ => return snapshot_vazio(total_setores, data_base),
    };

    let hoje = agora_iso8601();
    let data_fmt = if !data_base.is_empty() {
        data_base.to_string()
    } else {
        hoje_data_br()
    };

    let por_uf = contar_por_uf(df);
    let por_op = contar_por_operadora(df);
    let por_op_uf = contar_por_operadora_uf(df);
    let por_tec = contar_por_tecnologia(df);
    let por_op_5g = contar_5g_por_operadora(df);
    let por_op_5g_sa = contar_5g_sa_por_operadora(df);
    let por_mun_5g = contar_5g_por_municipio(df);
    let por_mun_op = contar_operadoras_por_municipio(df);
    let erbs_ids = extrair_metadados_erbs(df);

    // Total de ERBs únicas
    let total_erbs = if df.colunas.iter().any(|c| c == "ID_ERB") {
        df.n_unique("ID_ERB") as i64
    } else {
        df.len() as i64
    };

    let mut snap = Map::new();
    snap.insert("versao_snapshot".into(), Value::from(VERSAO_SNAPSHOT));
    snap.insert("gerado_em".into(), Value::from(hoje));
    snap.insert("data_base".into(), Value::from(data_fmt));
    snap.insert("total_erbs".into(), Value::from(total_erbs));
    snap.insert("total_setores".into(), Value::from(total_setores));
    snap.insert("por_uf".into(), mapa_json(por_uf));
    snap.insert("por_operadora".into(), mapa_json(por_op));
    snap.insert("por_operadora_uf".into(), mapa_json(por_op_uf));
    snap.insert("por_tecnologia".into(), mapa_json(por_tec));
    snap.insert("por_operadora_5g".into(), mapa_json(por_op_5g));
    snap.insert("por_operadora_5g_sa".into(), mapa_json(por_op_5g_sa));
    snap.insert("por_municipio_5g".into(), mapa_json(por_mun_5g));
    snap.insert("por_municipio_op".into(), lista_mapa_json(por_mun_op));
    snap.insert("erbs_ids".into(), erbs_ids);
    Value::Object(snap)
}

fn mapa_json(m: Vec<(String, i64)>) -> Value {
    let mut o = Map::new();
    for (k, v) in m {
        o.insert(k, Value::from(v));
    }
    Value::Object(o)
}

fn lista_mapa_json(m: Vec<(String, Vec<String>)>) -> Value {
    let mut o = Map::new();
    for (k, v) in m {
        o.insert(k, Value::Array(v.into_iter().map(Value::from).collect()));
    }
    Value::Object(o)
}

/// Snapshot vazio quando não há dados.
pub fn snapshot_vazio(total_setores: i64, data_base: &str) -> Value {
    let mut snap = Map::new();
    snap.insert("versao_snapshot".into(), Value::from(VERSAO_SNAPSHOT));
    snap.insert("gerado_em".into(), Value::from(agora_iso8601()));
    snap.insert(
        "data_base".into(),
        Value::from(if !data_base.is_empty() { data_base.to_string() } else { hoje_data_br() }),
    );
    snap.insert("total_erbs".into(), Value::from(0));
    snap.insert("total_setores".into(), Value::from(total_setores));
    for k in [
        "por_uf",
        "por_operadora",
        "por_operadora_uf",
        "por_tecnologia",
        "por_operadora_5g",
        "por_operadora_5g_sa",
        "por_municipio_5g",
        "por_municipio_op",
        "erbs_ids",
    ] {
        snap.insert(k.into(), Value::Object(Map::new()));
    }
    Value::Object(snap)
}

/// Data/hora atual em ISO-8601 com segundos (equivalente a
/// `datetime.now().isoformat(timespec="seconds")` — horário local).
pub fn agora_iso8601() -> String {
    let g = quebrar_local(now_epoch_secs());
    format!("{}-{}-{}T{}:{}:{}", g[0], g[1], g[2], g[3], g[4], g[5])
}

/// Data atual em DD/MM/AAAA.
pub fn hoje_data_br() -> String {
    let g = quebrar_local(now_epoch_secs());
    format!("{:02}/{:02}/{:04}", g[2], g[1], g[0])
}

fn now_epoch_secs() -> i64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs() as i64)
        .unwrap_or(0)
}

/// Conversão epoch → data local como vetor `[ano, mês, dia, hora, min, seg]`
/// (mesma convenção de `datetime.fromtimestamp(...)` seguida de indexação;
/// equivalente a `time.struct_time` fatiado). Mesma zona do sistema.
pub fn quebrar_local(secs: i64) -> Vec<i64> {
    unsafe {
        let t: libc::time_t = secs as libc::time_t;
        let mut tmv: libc::tm = std::mem::zeroed();
        libc::localtime_r(&t, &mut tmv);
        vec![
            tmv.tm_year as i64 + 1900,
            tmv.tm_mon as i64 + 1,
            tmv.tm_mday as i64,
            tmv.tm_hour as i64,
            tmv.tm_min as i64,
            tmv.tm_sec as i64,
        ]
    }
}

/// Timestamp local (segundos desde epoch) a partir de data DD/MM/AAAA.
pub fn epoch_de_data_br(data: &str) -> Option<i64> {
    let partes: Vec<&str> = data.split('/').collect();
    if partes.len() != 3 {
        return None;
    }
    let (d, m, y) = (partes[0].parse::<i64>().ok()?, partes[1].parse::<i64>().ok()?, partes[2].parse::<i64>().ok()?);
    // Dias desde epoch (algoritmo civil-days, Howard Hinnant)
    fn days_from_civil(y: i64, m: i64, d: i64) -> i64 {
        let y = if m <= 2 { y - 1 } else { y };
        let era = (if y >= 0 { y } else { y - 399 }) / 400;
        let yoe = y - era * 400;
        let mp = (m + (if m > 2 { -3 } else { 9 })) as i64;
        let doy = (153 * mp + 2) / 5 + d - 1;
        let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
        era * 146097 + doe - 719468
    }
    let dias = days_from_civil(y, m, d);
    // Ajuste de fuso: assume meia-noite local; usa gmtoff de agora (aproximação
    // idêntica ao comportamento observado nos testes locais).
    let tz_off = unsafe {
        let t: libc::time_t = now_epoch_secs() as libc::time_t;
        let mut tmv: libc::tm = std::mem::zeroed();
        libc::localtime_r(&t, &mut tmv);
        tmv.tm_gmtoff as i64
    };
    Some(dias * 86400 - tz_off)
}

/// Conta ERBs únicas por UF → {UF: contagem}, ordenado como groupby do pandas.
fn contar_por_uf(df: &DataFrame) -> Vec<(String, i64)> {
    contar_nunique_por_chave(df, &["UF"], "ID_ERB")
}

/// Conta ERBs únicas por operadora.
fn contar_por_operadora(df: &DataFrame) -> Vec<(String, i64)> {
    contar_nunique_por_chave(df, &["OPERADORA"], "ID_ERB")
}

fn contar_nunique_por_chave(df: &DataFrame, cols: &[&str], col_valor: &str) -> Vec<(String, i64)> {
    // groupby(cols)[col_valor].nunique() — ordem dos grupos = chaves ordenadas (pandas sort=True)
    let mut grupos: Vec<(Vec<String>, HashSet<String>)> = Vec::new();
    for i in 0..df.len() {
        let chave: Vec<String> = cols
            .iter()
            .map(|c| celula_str(&df.celula(i, c)))
            .collect();
        let val = celula_str(&df.celula(i, col_valor));
        match grupos.iter_mut().find(|(k, _)| *k == chave) {
            Some((_, set)) => {
                set.insert(val);
            }
            None => {
                let mut set = HashSet::new();
                set.insert(val);
                grupos.push((chave, set));
            }
        }
    }
    grupos.sort_by(|a, b| cmp_celula(&Value::from(a.0.join("\u{1}")), &Value::from(b.0.join("\u{1}"))));
    grupos.into_iter().map(|(k, set)| (k.join(if k.len() == 1 { "\u{0}" } else { "|" }), set.len() as i64)).collect()
}

/// Conta ERBs únicas por operadora+UF → {"OPERADORA|UF": contagem}.
fn contar_por_operadora_uf(df: &DataFrame) -> Vec<(String, i64)> {
    let raw = contar_nunique_por_chave(df, &["OPERADORA", "UF"], "ID_ERB");
    raw.into_iter().map(|(k, v)| (k.replace('\u{0}', "|"), v)).collect()
}

/// Conta ERBs por tecnologia (2G/3G/4G/5G).
fn contar_por_tecnologia(df: &DataFrame) -> Vec<(String, i64)> {
    let mut tec_counts: Vec<(String, i64)> = TECNOLOGIAS_MONITORADAS
        .iter()
        .map(|t| (t.to_string(), 0i64))
        .collect();

    if !df.colunas.iter().any(|c| c == "TECS_RAW") {
        tec_counts.retain(|(_, v)| *v > 0);
        return tec_counts;
    }

    // Uma linha por ERB com a string "L,5" ou "E,H,L,5"
    let tem_id = df.colunas.iter().any(|c| c == "ID_ERB");
    let mut vistos: HashSet<String> = HashSet::new();
    for i in 0..df.len() {
        if tem_id {
            let id = celula_str(&df.celula(i, "ID_ERB"));
            if !vistos.insert(id) {
                continue;
            }
        }
        let tec_raw = celula_str(&df.celula(i, "TECS_RAW"));
        for t in tec_raw.split(',') {
            let t = t.trim();
            if let Some(e) = tec_counts.iter_mut().find(|(k, _)| k == t) {
                e.1 += 1;
            }
        }
    }

    tec_counts.retain(|(_, v)| *v > 0);
    tec_counts
}

/// Filtra índices onde TECS_RAW contém "5" (str.contains na=False).
fn indices_com_5g(df: &DataFrame) -> Vec<usize> {
    (0..df.len())
        .filter(|&i| celula_str(&df.celula(i, "TECS_RAW")).contains('5'))
        .collect()
}

/// Filtra índices onde TEC5G_TIPO contém "SA" (case-sensitive, como str.contains).
fn indices_com_sa(df: &DataFrame) -> Vec<usize> {
    (0..df.len())
        .filter(|&i| celula_str(&df.celula(i, "TEC5G_TIPO")).contains("SA"))
        .collect()
}

fn nunique_id_entre(df: &DataFrame, idxs: &[usize], col_grupo: &str) -> Vec<(String, i64)> {
    if idxs.is_empty() {
        return Vec::new();
    }
    let mut grupos: Vec<(String, HashSet<String>)> = Vec::new();
    for &i in idxs {
        let chave = celula_str(&df.celula(i, col_grupo));
        let id = celula_str(&df.celula(i, "ID_ERB"));
        match grupos.iter_mut().find(|(k, _)| *k == chave) {
            Some((_, set)) => {
                set.insert(id);
            }
            None => {
                let mut set = HashSet::new();
                set.insert(id);
                grupos.push((chave, set));
            }
        }
    }
    grupos.sort_by(|a, b| cmp_celula(&Value::from(a.0.as_str()), &Value::from(b.0.as_str())));
    grupos.into_iter().map(|(k, set)| (k, set.len() as i64)).collect()
}

/// Conta ERBs com 5G por operadora.
fn contar_5g_por_operadora(df: &DataFrame) -> Vec<(String, i64)> {
    if !df.colunas.iter().any(|c| c == "TECS_RAW") {
        return Vec::new();
    }
    let idx = indices_com_5g(df);
    nunique_id_entre(df, &idx, "OPERADORA")
}

/// Conta ERBs com 5G SA (SA-NSA) por operadora.
fn contar_5g_sa_por_operadora(df: &DataFrame) -> Vec<(String, i64)> {
    if !df.colunas.iter().any(|c| c == "TEC5G_TIPO") {
        return Vec::new();
    }
    let idx = indices_com_sa(df);
    nunique_id_entre(df, &idx, "OPERADORA")
}

/// Conta ERBs com 5G por município → {"MUNICIPIO_LIMPO|UF": contagem}.
fn contar_5g_por_municipio(df: &DataFrame) -> Vec<(String, i64)> {
    if !df.colunas.iter().any(|c| c == "TECS_RAW") {
        return Vec::new();
    }
    let idx = indices_com_5g(df);
    if idx.is_empty() {
        return Vec::new();
    }
    let mut grupos: Vec<(String, HashSet<String>)> = Vec::new();
    for &i in &idx {
        let chave = format!("{}|{}", celula_str(&df.celula(i, "MUNICIPIO_LIMPO")), celula_str(&df.celula(i, "UF")));
        let id = celula_str(&df.celula(i, "ID_ERB"));
        match grupos.iter_mut().find(|(k, _)| *k == chave) {
            Some((_, set)) => {
                set.insert(id);
            }
            None => {
                let mut set = HashSet::new();
                set.insert(id);
                grupos.push((chave, set));
            }
        }
    }
    grupos.sort_by(|a, b| cmp_celula(&Value::from(a.0.as_str()), &Value::from(b.0.as_str())));
    grupos.into_iter().map(|(k, set)| (k, set.len() as i64)).collect()
}

/// Lista operadoras presentes em cada município → {"MUN|UF": [ops ordenadas]}.
fn contar_operadoras_por_municipio(df: &DataFrame) -> Vec<(String, Vec<String>)> {
    let mut grupos: Vec<(String, HashSet<String>)> = Vec::new();
    for i in 0..df.len() {
        let chave = format!("{}|{}", celula_str(&df.celula(i, "MUNICIPIO_LIMPO")), celula_str(&df.celula(i, "UF")));
        let op = celula_str(&df.celula(i, "OPERADORA"));
        match grupos.iter_mut().find(|(k, _)| *k == chave) {
            Some((_, set)) => {
                set.insert(op);
            }
            None => {
                let mut set = HashSet::new();
                set.insert(op);
                grupos.push((chave, set));
            }
        }
    }
    grupos.sort_by(|a, b| cmp_celula(&Value::from(a.0.as_str()), &Value::from(b.0.as_str())));
    grupos
        .into_iter()
        .map(|(k, set)| {
            let mut ops: Vec<String> = set.into_iter().collect();
            ops.sort();
            (k, ops)
        })
        .collect()
}

/// Extrai metadados de cada ERB → {ID_ERB: {uf, mun, bairro, tecs, 5g_sa}}.
fn extrair_metadados_erbs(df: &DataFrame) -> Value {
    if !df.colunas.iter().any(|c| c == "ID_ERB") {
        return Value::Object(Map::new());
    }
    let tem_bairro = df.colunas.iter().any(|c| c == "BAIRRO");
    let tem_5g_tipo = df.colunas.iter().any(|c| c == "TEC5G_TIPO");
    let tem_tecs = df.colunas.iter().any(|c| c == "TECS_RAW");

    let mut out = Map::new();
    for i in 0..df.len() {
        let chave = celula_str(&df.celula(i, "ID_ERB"));
        if chave.is_empty() {
            continue;
        }
        let sa_flag = if tem_5g_tipo {
            celula_str(&df.celula(i, "TEC5G_TIPO")).contains("SA")
        } else {
            false
        };
        let mut meta = Map::new();
        meta.insert("uf".into(), Value::from(celula_str(&df.celula(i, "UF"))));
        meta.insert("mun".into(), Value::from(celula_str(&df.celula(i, "MUNICIPIO_LIMPO"))));
        meta.insert(
            "bairro".into(),
            Value::from(if tem_bairro { celula_str(&df.celula(i, "BAIRRO")) } else { String::new() }),
        );
        meta.insert(
            "tecs".into(),
            Value::from(if tem_tecs { celula_str(&df.celula(i, "TECS_RAW")) } else { String::new() }),
        );
        meta.insert("5g_sa".into(), Value::from(sa_flag));
        out.insert(chave, Value::Object(meta));
    }
    Value::Object(out)
}

// ---------------------------------------------------------------------------
// Persistência
// ---------------------------------------------------------------------------

/// Salva snapshot em arquivo JSON (compacto, sem espaços).
pub fn salvar_snapshot(snap: &Value, caminho: Option<&std::path::Path>) -> bool {
    let alvo = caminho.map(|p| p.to_path_buf()).unwrap_or_else(|| {
        // Em Python o padrão é o nome relativo "torre_facil_snapshot.json";
        // aqui usamos o diretório de dados configurado.
        arquivo_snapshot()
    });
    let txt = format!("{}", compactar_json(snap));
    std::fs::write(&alvo, txt).is_ok()
}

/// Serializa JSON no formato do json.dump com separators=(",", ":").
fn compactar_json(v: &Value) -> String {
    let s = serde_json::to_string(v).unwrap_or_default();
    // serde_json já produz compacto sem espaços — equivalente.
    s
}

/// Carrega snapshot do arquivo JSON (None se não existir/incompatível).
pub fn carregar_snapshot(caminho: Option<&std::path::Path>) -> Option<Value> {
    let alvo = caminho.map(|p| p.to_path_buf()).unwrap_or_else(arquivo_snapshot);
    if !alvo.exists() {
        return None;
    }
    let txt = std::fs::read_to_string(&alvo).ok()?;
    let snap: Value = serde_json::from_str(&txt).ok()?;
    if snap.get("versao_snapshot").and_then(|v| v.as_i64()) != Some(VERSAO_SNAPSHOT) {
        return None;
    }
    Some(snap)
}

/// Carrega snapshot anterior (backup `_anterior.json`).
pub fn carregar_snapshot_anterior() -> Option<Value> {
    let caminho_backup = arquivo_snapshot()
        .to_string_lossy()
        .replace(".json", "_anterior.json");
    carregar_snapshot(Some(std::path::Path::new(&caminho_backup)))
}

// ---------------------------------------------------------------------------
// Comparação
// ---------------------------------------------------------------------------

/// Diferença de um par de dicts {chave: int}.
#[derive(Debug, Clone)]
pub struct DiffInt(pub String, pub i64, pub i64, pub i64);

/// Compara dois dicts {chave: valor} e devolve diferenças (apenas deltas ≠ 0).
fn diff_dicts_int(a: &Map<String, Value>, b: &Map<String, Value>) -> Vec<DiffInt> {
    let mut chaves: Vec<String> = a.keys().cloned().collect();
    for k in b.keys() {
        if !chaves.contains(k) {
            chaves.push(k.clone());
        }
    }
    chaves.sort();
    let mut saida = Vec::new();
    for k in chaves {
        let va = a.get(&k).and_then(|v| v.as_i64()).unwrap_or(0);
        let vb = b.get(&k).and_then(|v| v.as_i64()).unwrap_or(0);
        if va != vb {
            saida.push(DiffInt(k, va, vb, vb - va));
        }
    }
    saida
}

fn sort_por_delta_abs_desc(v: &mut Vec<DiffInt>) {
    // key=lambda x: -abs(x[3]) — estável
    let mut idx: Vec<usize> = (0..v.len()).collect();
    idx.sort_by(|&a, &b| (v[b].3.abs()).cmp(&(v[a].3.abs())));
    let ordenado: Vec<DiffInt> = idx.iter().map(|&i| v[i].clone()).collect();
    *v = ordenado;
}

fn get_mapa<'a>(snap: &'a Value, campo: &str) -> Map<String, Value> {
    snap.get(campo)
        .and_then(|v| v.as_object())
        .cloned()
        .unwrap_or_default()
}

/// Lê uma lista de um snapshot (`snap[campo]` quando é array; senão `[]`).
pub fn get_array(snap: &Value, campo: &str) -> Vec<Value> {
    snap.get(campo)
        .and_then(|v| v.as_array())
        .cloned()
        .unwrap_or_default()
}

/// Compara dois snapshots e devolve dict de diferenças.
pub fn comparar(antigo: &Value, novo: &Value) -> Value {
    if antigo.is_null() || novo.is_null()
        || antigo.as_object().map_or(true, |o| o.is_empty())
        || novo.as_object().map_or(true, |o| o.is_empty())
    {
        return Value::Object(Map::new());
    }

    let mut diff = Map::new();
    diff.insert(
        "data_antiga".into(),
        antigo.get("data_base").cloned().unwrap_or(Value::from("?")),
    );
    diff.insert("data_nova".into(), novo.get("data_base").cloned().unwrap_or(Value::from("?")));

    // Total
    let n_antigo = antigo.get("total_erbs").and_then(|v| v.as_i64()).unwrap_or(0);
    let n_novo = novo.get("total_erbs").and_then(|v| v.as_i64()).unwrap_or(0);
    let mut total = Map::new();
    total.insert("antes".into(), Value::from(n_antigo));
    total.insert("agora".into(), Value::from(n_novo));
    total.insert("delta".into(), Value::from(n_novo - n_antigo));
    diff.insert("total".into(), Value::Object(total));

    // Por operadora / UF / tecnologia
    for (campo, destino) in [
        ("por_operadora", "por_operadora"),
        ("por_uf", "por_uf"),
        ("por_tecnologia", "por_tecnologia"),
    ] {
        let mut d = diff_dicts_int(&get_mapa(antigo, campo), &get_mapa(novo, campo));
        sort_por_delta_abs_desc(&mut d);
        let arr: Vec<Value> = d
            .into_iter()
            .map(|DiffInt(k, va, vb, delta)| {
                Value::Array(vec![Value::from(k), Value::from(va), Value::from(vb), Value::from(delta)])
            })
            .collect();
        diff.insert(destino.into(), Value::Array(arr));
    }

    // 5G por município
    let mun_5g_antigo: HashSet<String> = get_mapa(antigo, "por_municipio_5g").keys().cloned().collect();
    let mun_5g_novo: HashSet<String> = get_mapa(novo, "por_municipio_5g").keys().cloned().collect();
    let novas_5g: Vec<&String> = mun_5g_novo.iter().filter(|k| !mun_5g_antigo.contains(*k)).collect();
    let _saiu_5g: Vec<&String> = mun_5g_antigo.iter().filter(|k| !mun_5g_novo.contains(*k)).collect();

    // ERBs novas e removidas
    let antigo_ids = get_mapa(antigo, "erbs_ids");
    let novo_ids = get_mapa(novo, "erbs_ids");
    let chaves_antigas: HashSet<String> = antigo_ids.keys().cloned().collect();
    let chaves_novas: HashSet<String> = novo_ids.keys().cloned().collect();
    let mut ids_novas: Vec<String> = chaves_novas.iter().filter(|k| !chaves_antigas.contains(*k)).cloned().collect();
    let mut ids_removidas: Vec<String> =
        chaves_antigas.iter().filter(|k| !chaves_novas.contains(*k)).cloned().collect();
    ids_novas.sort();
    ids_removidas.sort();

    let montar = |ids: &[String], mapa: &Map<String, Value>| -> Vec<Value> {
        ids.iter()
            .map(|k| {
                let obj = mapa.get(k).and_then(|v| v.as_object()).cloned().unwrap_or_default();
                let mut final_obj = Map::new();
                final_obj.insert("id".into(), Value::from(k.clone()));
                for (kk, vv) in obj {
                    final_obj.insert(kk, vv);
                }
                Value::Object(final_obj)
            })
            .collect()
    };
    let erbs_novas = montar(&ids_novas, &novo_ids);
    let erbs_removidas = montar(&ids_removidas, &antigo_ids);
    diff.insert("erbs_novas".into(), Value::Array(erbs_novas.clone()));
    diff.insert("erbs_removidas".into(), Value::Array(erbs_removidas.clone()));

    // 5G ativado por operadora
    let mut ativ_5g_op: HashMap<String, HashSet<String>> = HashMap::new();
    for e in &erbs_novas {
        let tecs = e.get("tecs").and_then(|v| v.as_str()).unwrap_or("").to_string();
        if !tecs.contains('5') {
            continue;
        }
        let chave_cid = format!(
            "{}|{}",
            e.get("mun").and_then(|v| v.as_str()).unwrap_or(""),
            e.get("uf").and_then(|v| v.as_str()).unwrap_or("")
        );
        if mun_5g_antigo.contains(&chave_cid) {
            continue;
        }
        let op = e.get("id").and_then(|v| v.as_str()).unwrap_or("").split('|').next().unwrap_or("").to_string();
        ativ_5g_op.entry(op).or_default().insert(chave_cid);
    }
    diff.insert("5g_ativado_op".into(), contar_sets(&ativ_5g_op));

    // 5G SA ativado por operadora
    let cidades_5g_sa_antes = cidades_com_5g_sa(&antigo_ids);
    let cidades_5g_sa_agora = cidades_com_5g_sa(&novo_ids);
    let novas_sa: Vec<String> = cidades_5g_sa_agora
        .iter()
        .filter(|k| !cidades_5g_sa_antes.contains(*k))
        .cloned()
        .collect();
    let saiu_sa: Vec<String> = cidades_5g_sa_antes
        .iter()
        .filter(|k| !cidades_5g_sa_agora.contains(*k))
        .cloned()
        .collect();
    let novas_sa_set: HashSet<String> = novas_sa.iter().cloned().collect();

    let mut ativ_5g_sa_op: HashMap<String, HashSet<String>> = HashMap::new();
    for e in &erbs_novas {
        if !e.get("5g_sa").and_then(|v| v.as_bool()).unwrap_or(false) {
            continue;
        }
        let chave_cid = format!(
            "{}|{}",
            e.get("mun").and_then(|v| v.as_str()).unwrap_or(""),
            e.get("uf").and_then(|v| v.as_str()).unwrap_or("")
        );
        if !novas_sa_set.contains(&chave_cid) {
            continue;
        }
        let op = e.get("id").and_then(|v| v.as_str()).unwrap_or("").split('|').next().unwrap_or("").to_string();
        ativ_5g_sa_op.entry(op).or_default().insert(chave_cid);
    }
    diff.insert("5g_sa_ativado_op".into(), contar_sets(&ativ_5g_sa_op));
    let mut ns = novas_sa.clone();
    ns.sort();
    let mut sp = saiu_sa.clone();
    sp.sort();
    diff.insert("5g_sa_novas_cidades".into(), Value::Array(ns.into_iter().map(Value::from).collect()));
    diff.insert("5g_sa_cidades_perdidas".into(), Value::Array(sp.into_iter().map(Value::from).collect()));

    // 5G desativado por operadora
    let mut desativ_5g_op: HashMap<String, HashSet<String>> = HashMap::new();
    for e in &erbs_removidas {
        let tecs = e.get("tecs").and_then(|v| v.as_str()).unwrap_or("").to_string();
        if !tecs.contains('5') {
            continue;
        }
        let chave_cid = format!(
            "{}|{}",
            e.get("mun").and_then(|v| v.as_str()).unwrap_or(""),
            e.get("uf").and_then(|v| v.as_str()).unwrap_or("")
        );
        if !mun_5g_novo.contains(&chave_cid) {
            let op = e.get("id").and_then(|v| v.as_str()).unwrap_or("").split('|').next().unwrap_or("").to_string();
            desativ_5g_op.entry(op).or_default().insert(chave_cid);
        }
    }
    diff.insert("5g_desativado_op".into(), contar_sets(&desativ_5g_op));

    // Cidades que ganharam/perderam operadoras
    let mun_op_antigo = get_mapa(antigo, "por_municipio_op");
    let mun_op_novo = get_mapa(novo, "por_municipio_op");
    let (ganharam_2op, ganharam_3op, perderam_op) =
        comparar_operadoras_por_municipio(&mun_op_antigo, &mun_op_novo);
    diff.insert("novas_cidades_2op".into(), Value::Array(ganharam_2op.into_iter().map(Value::from).collect()));
    diff.insert("novas_cidades_3op".into(), Value::Array(ganharam_3op.into_iter().map(Value::from).collect()));
    diff.insert("cidades_perderam_op".into(), Value::Array(perderam_op.into_iter().map(Value::from).collect()));

    // ``5g_novas_cidades`` / ``5g_cidades_perdidas`` (nome legado usado pela TUI)
    let novas_arr = diff
        .get("5g_sa_novas_cidades")
        .cloned()
        .unwrap_or(Value::Array(Vec::new()));
    let _ = novas_arr;
    let novas_5g_arr: Vec<Value> = {
        let mut v: Vec<String> = novas_5g.into_iter().cloned().collect();
        v.sort();
        v.into_iter().map(Value::from).collect()
    };
    let saiu_5g_arr: Vec<Value> = {
        let mut v: Vec<String> = _saiu_5g.into_iter().cloned().collect();
        v.sort();
        v.into_iter().map(Value::from).collect()
    };
    diff.insert("5g_novas_cidades".into(), Value::Array(novas_5g_arr));
    diff.insert("5g_cidades_perdidas".into(), Value::Array(saiu_5g_arr));

    Value::Object(diff)
}

fn contar_sets(mapa: &HashMap<String, HashSet<String>>) -> Value {
    let mut o = Map::new();
    let mut chaves: Vec<&String> = mapa.keys().collect();
    chaves.sort();
    for k in chaves {
        o.insert(k.clone(), Value::from(mapa[k].len() as i64));
    }
    Value::Object(o)
}

/// Conjunto de cidades com pelo menos uma ERB 5G SA.
fn cidades_com_5g_sa(erbs_ids: &Map<String, Value>) -> HashSet<String> {
    let mut cidades = HashSet::new();
    for v in erbs_ids.values() {
        if v.get("5g_sa").and_then(|x| x.as_bool()).unwrap_or(false) {
            let chave = format!(
                "{}|{}",
                v.get("mun").and_then(|x| x.as_str()).unwrap_or(""),
                v.get("uf").and_then(|x| x.as_str()).unwrap_or("")
            );
            cidades.insert(chave);
        }
    }
    cidades
}

/// Compara operadoras por município entre dois snapshots.
fn comparar_operadoras_por_municipio(
    mun_op_antigo: &Map<String, Value>,
    mun_op_novo: &Map<String, Value>,
) -> (Vec<String>, Vec<String>, Vec<String>) {
    let mut chaves: Vec<String> = mun_op_antigo.keys().cloned().collect();
    for k in mun_op_novo.keys() {
        if !chaves.contains(k) {
            chaves.push(k.clone());
        }
    }
    let mut ganharam_2op = Vec::new();
    let mut ganharam_3op = Vec::new();
    let mut perderam_op = Vec::new();

    for chave_cid in chaves {
        let parse = |m: &Map<String, Value>| -> HashSet<String> {
            m.get(&chave_cid)
                .and_then(|v| v.as_array())
                .map(|arr| arr.iter().filter_map(|x| x.as_str().map(String::from)).collect())
                .unwrap_or_default()
        };
        let ops_antes = parse(mun_op_antigo);
        let ops_agora = parse(mun_op_novo);

        if ops_agora.len() > ops_antes.len() {
            if ops_agora.len() == 2 {
                ganharam_2op.push(chave_cid);
            } else if ops_agora.len() >= 3 {
                ganharam_3op.push(chave_cid);
            }
        } else if ops_agora.len() < ops_antes.len() {
            perderam_op.push(chave_cid);
        }
    }
    ganharam_2op.sort();
    ganharam_3op.sort();
    perderam_op.sort();
    (ganharam_2op, ganharam_3op, perderam_op)
}

// ---------------------------------------------------------------------------
// Helpers para formatação
// ---------------------------------------------------------------------------

/// Formata delta com sinal e separador de milhar pt-BR.
pub fn formatar_delta(delta: i64) -> String {
    if delta > 0 {
        format!("+{}", formatar_milhar(delta))
    } else if delta < 0 {
        format!("{}", formatar_milhar(delta))
    } else {
        "0".to_string()
    }
}

/// Verifica se há algo digno de abrir a tela de novidades.
pub fn tem_novidade_relevante(diff: &Value) -> bool {
    let d = match diff.as_object() {
        Some(o) if !o.is_empty() => o,
        _ => return false,
    };

    if d.get("total")
        .and_then(|t| t.get("delta"))
        .and_then(|v| v.as_i64())
        .unwrap_or(0)
        != 0
    {
        return true;
    }

    let nao_vazio = |k: &str| d.get(k).and_then(|v| v.as_array()).map_or(false, |a| !a.is_empty());
    if nao_vazio("erbs_novas") || nao_vazio("erbs_removidas") {
        return true;
    }

    let mapa_nao_vazio = |k: &str| d.get(k).and_then(|v| v.as_object()).map_or(false, |o| !o.is_empty());
    if mapa_nao_vazio("5g_ativado_op") || mapa_nao_vazio("5g_sa_ativado_op") {
        return true;
    }

    if nao_vazio("novas_cidades_2op") || nao_vazio("novas_cidades_3op") {
        return true;
    }

    false
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn formatar_delta_doc() {
        assert_eq!(formatar_delta(1234), "+1.234");
        assert_eq!(formatar_delta(-567), "-567");
        assert_eq!(formatar_delta(0), "0");
    }

    #[test]
    fn snapshot_vazio_tem_estrutura() {
        let s = snapshot_vazio(10, "02/10/2025");
        assert_eq!(s["versao_snapshot"], 1);
        assert_eq!(s["total_erbs"], 0);
        assert_eq!(s["data_base"], "02/10/2025");
        assert!(s["por_uf"].is_object());
    }

    #[test]
    fn gerar_e_comparar() {
        let df = DataFrame::from_csv_str(
            "UF;MUNICIPIO_LIMPO;OPERADORA;NUM_ESTACAO;TECS_RAW;BAIRRO;TEC5G_TIPO\n\
             RN;NATAL;VIVO;100;\"L,5\";PONTA NEGRA;SA-NSA\n\
             RN;NATAL;TIM;200;L;AREIA BRANCA;\n",
        )
        .unwrap();
        // ID_ERB precisa existir — cria como no pipeline
        let ids: Vec<Value> = (0..df.len())
            .map(|i| Value::from(format!("{}_{}", celula_str(&df.celula(i, "OPERADORA")), celula_str(&df.celula(i, "NUM_ESTACAO")))))
            .collect();
        let mut df2 = df.clone();
        df2.set_coluna("ID_ERB", ids);

        let snap = gerar_snapshot(Some(&df2), 300, "02/10/2025");
        assert_eq!(snap["total_erbs"], 2);
        assert_eq!(snap["por_uf"]["RN"], 2);
        assert_eq!(snap["por_operadora_5g"]["VIVO"], 1);
        assert_eq!(snap["por_operadora_5g_sa"]["VIVO"], 1);
        assert_eq!(snap["por_municipio_op"]["NATAL|RN"][0], "TIM");
        assert_eq!(snap["por_municipio_op"]["NATAL|RN"][1], "VIVO");

        // Comparar com snapshot "antigo" sem a ERB da VIVO
        let mut antigo = snap.clone();
        {
            let ids_map = antigo["erbs_ids"].as_object().unwrap().clone();
            let mut novo_ids_map = ids_map.clone();
            novo_ids_map.remove("VIVO_100");
            antigo["erbs_ids"] = Value::Object(novo_ids_map);
            antigo["total_erbs"] = Value::from(1);
        }
        let diff = comparar(&antigo, &snap);
        assert_eq!(diff["total"]["delta"], 1);
        let novas = diff["erbs_novas"].as_array().unwrap();
        assert_eq!(novas.len(), 1);
        assert_eq!(novas[0]["id"], "VIVO_100");
        assert!(tem_novidade_relevante(&diff));
    }

    #[test]
    fn sem_novidade() {
        assert!(!tem_novidade_relevante(&Value::Null));
        assert!(!tem_novidade_relevante(&Value::Object(Map::new())));
    }
}
