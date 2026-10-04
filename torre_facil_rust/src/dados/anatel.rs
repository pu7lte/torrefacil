//! Porta 1:1 do módulo `torre_facil/dados/anatel.py`.
//!
//! Download, parsing e cache da base ANATEL SMP:
//! - Baixar o ZIP oficial de estações SMP (`baixar_zip_anatel`)
//! - Extrair o CSV do ZIP (`extrair_csv_do_zip`)
//! - Pipeline de processamento em etapas (`processar_base_e_salvar_cache`)
//! - Cache binário em JSON (substituto do `.pkl` do pandas) (`carregar_do_cache`)
//! - Snapshot para comparação entre versões (via [`crate::dados::snapshot`])
//! - Limpeza e bootstrap (`limpar_arquivos_cache`, `inicializar_base_com_cache`)
//!
//! Diferenças documentadas em relação ao Python:
//! - O cache `.pkl` (pickle) vira um arquivo JSON com o mesmo conteúdo lógico
//!   (`versao`, `df_erbs`, `total_setores`, `bairros_unificados`, `data_geracao`).
//! - As caixas de notificação da TUI (`caixa_notificacao_tui`) só existem na
//!   porta completa da interface; por isso as funções de bootstrap que as usam
//!   recebem a escolha do usuário como parâmetro (`escolha_*`), mantendo a
//!   mesma árvore de decisão.

use std::collections::{HashMap, HashSet};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use regex::Regex;
use serde_json::{Map, Value};

use crate::config::{
    arquivo_cache, arquivo_cache_bairros, arquivo_csv_extraido, arquivo_zip, dados_dir,
    ordem_tec, URL_ANATEL, VERSAO_CACHE,
};
use crate::coordenadas::{converter_coord_anatel, mapear_sigla_tecnologia, padronizar_operadora};
use crate::dados::bairros::unificar_bairros_por_municipio;
use crate::dados::snapshot as snap_mod;
use crate::dataframe::{cmp_celula, Cell, DataFrame};
use crate::estado;
use crate::texto::normalizar_texto;

// ---------------------------------------------------------------------------
// Constantes
// ---------------------------------------------------------------------------

/// Origens da base (usadas em `INFO.origem`).
pub const ORIGEM_CACHE_RECENTE: &str = "Cache Recém-Indexado";
pub const ORIGEM_CACHE_RAPIDO: &str = "Cache Rápido";
#[allow(dead_code)]
pub const ORIGEM_CACHE_INVALIDO: &str = "Cache Inválido";

/// Faixas nominais para agrupar frequências (MHz): (lo, hi, nome).
const FAIXAS_NOMINAIS: [(f64, f64, &str); 13] = [
    (400.0, 500.0, "450"),
    (600.0, 800.0, "700"),
    (800.0, 900.0, "850"),
    (900.0, 1000.0, "900"),
    (1700.0, 1800.0, "1700"),
    (1800.0, 1900.0, "1800"),
    (1900.0, 2000.0, "1900"),
    (2000.0, 2200.0, "2100"),
    (2300.0, 2400.0, "2300"),
    (2500.0, 2700.0, "2600"),
    (3300.0, 3600.0, "3500"), // 5G principal
    (3600.0, 4000.0, "3700"),
    (24000.0, 28000.0, "26000"), // mmWave
];

/// Colunas usadas no índice de busca global.
pub const COLUNAS_BUSCA_GLOBAL: [&str; 16] = [
    "UF", "MUNICIPIO_LIMPO", "MUNICIPIO", "BAIRRO", "ENDERECO",
    "ENDERECO_BUSCA", "LOGR_RAW", "OPERADORA", "NUM_ESTACAO",
    "TECNOLOGIA", "TECS_RAW", "GPS",
    "FAIXA_NOMINAL", "CARATER", "INFRA", "TEC5G_TIPO",
];

/// Sequência de progresso ao carregar do cache: (perc, titulo, frase).
const SEQUENCIA_PROGRESSO_CACHE: [(i64, &str, &str); 5] = [
    (25, "CONSOLIDANDO TECNOLOGIAS", "Subindo portadoras 4G e 5G..."),
    (45, "CARREGANDO BAIRROS E GPS", "Ajustando o azimute e tilt das antenas..."),
    (70, "UNIFICANDO BAIRROS", "Consultando dicionário nacional compilado..."),
    (90, "CONSOLIDANDO ERBs", "Medindo VSWR e integrando BBUs..."),
    (100, "UFA, PRONTO! SITE CONSTRUÍDO!", "Liberando tráfego nos setores..."),
];

// ---------------------------------------------------------------------------
// Callback de progresso (abstração para desacoplar da TUI)
// ---------------------------------------------------------------------------

/// Reporta progresso do pipeline (equivale a `_progresso` → `desenhar_progresso_tui`).
pub fn progresso(perc: i64, titulo: &str, frase: &str, detalhe_extra: &str) {
    if std::env::var("TORRE_FACIL_VERBOSE").is_ok() {
        eprintln!("[{perc:>3}%] {titulo} — {frase} {detalhe_extra}");
    }
}

fn agora_unix() -> i64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs() as i64).unwrap_or(0)
}

fn sleep_ms(ms: u64) {
    std::thread::sleep(Duration::from_millis(ms));
}

// ---------------------------------------------------------------------------
// Funções puras de parsing
// ---------------------------------------------------------------------------

/// Mapeia frequência em MHz para faixa nominal (`_faixa_nominal`).
///
/// ```
/// use torre_facil::dados::anatel::faixa_nominal;
/// assert_eq!(faixa_nominal(&serde_json::json!(1850)), "1800");
/// assert_eq!(faixa_nominal(&serde_json::json!(3500)), "3500");
/// assert_eq!(faixa_nominal(&Value::Null), "");
/// ```
pub fn faixa_nominal(freq_mhz: &Cell) -> String {
    let Some(f) = freq_mhz.as_f64().or_else(|| freq_mhz.as_str().and_then(|s| s.trim().replace(',', ".").parse::<f64>().ok())) else {
        return "".to_string();
    };
    for (lo, hi, nome) in FAIXAS_NOMINAIS {
        if lo <= f && f < hi {
            return nome.to_string();
        }
    }
    "outra".to_string()
}

/// Converte string com vírgula decimal em float (`_parse_float_br`).
///
/// ```
/// use torre_facil::dados::anatel::parse_float_br;
/// assert_eq!(parse_float_br(&serde_json::json!("1875,00")), Some(1875.0));
/// assert_eq!(parse_float_br(&Value::Null), None);
/// ```
pub fn parse_float_br(valor: &Cell) -> Option<f64> {
    match valor {
        Cell::Null => None,
        Cell::Number(_) => valor.as_f64(),
        Cell::String(s) => s.trim().replace(',', ".").parse::<f64>().ok(),
        _ => None,
    }
}

/// Normaliza código IBGE para string de dígitos (`_limpar_ibge`).
///
/// ```
/// use torre_facil::dados::anatel::limpar_ibge;
/// assert_eq!(limpar_ibge(&serde_json::json!(2401008.0)), "2401008");
/// assert_eq!(limpar_ibge(&Value::Null), "");
/// ```
pub fn limpar_ibge(valor: &Cell) -> String {
    match valor {
        Cell::Null => String::new(),
        Cell::Number(n) => n.as_f64().map(|f| (f.trunc() as i64).to_string()).unwrap_or_default(),
        Cell::String(s) => {
            let t = s.trim();
            if t.is_empty() {
                return String::new();
            }
            match t.parse::<f64>() {
                Ok(f) => (f.trunc() as i64).to_string(),
                Err(_) => String::new(),
            }
        }
        _ => String::new(),
    }
}

/// Normaliza CEP para string de 8 dígitos (`_limpar_cep`).
///
/// ```
/// use torre_facil::dados::anatel::limpar_cep;
/// assert_eq!(limpar_cep(&serde_json::json!("59420000")), "59420000");
/// assert_eq!(limpar_cep(&Value::Null), "");
/// ```
pub fn limpar_cep(valor: &Cell) -> String {
    let s = match valor {
        Cell::String(s) => s.clone(),
        Cell::Null => return String::new(),
        other => other.to_string(),
    };
    let digitos: String = s.chars().filter(|c| c.is_ascii_digit()).collect();
    if digitos.len() == 8 {
        digitos
    } else {
        String::new()
    }
}

// ---------------------------------------------------------------------------
// Identificação de colunas
// ---------------------------------------------------------------------------

/// Identifica coluna do CSV por termos exatos ou parciais (`_identificar_coluna`).
pub fn identificar_coluna(
    colunas: &[String],
    termos_exatos: &[&str],
    termos_parciais: Option<&[&str]>,
    ignorar: &HashSet<String>,
) -> Option<String> {
    let parcias: &[&str] = termos_parciais.unwrap_or(termos_exatos);

    // Ordem de iteração preserva a ordem do CSV (dict comprehension do Python)
    let mapa: Vec<(&String, String)> = colunas
        .iter()
        .filter(|c| !ignorar.contains(*c))
        .map(|c| (c, normalizar_texto(Some(c))))
        .collect();

    // Match exato
    for termo in termos_exatos {
        let t = normalizar_texto(Some(termo));
        for (col, col_n) in &mapa {
            if *col_n == t {
                return Some((*col).clone());
            }
        }
    }
    // Match parcial
    for termo in parcias {
        let t = normalizar_texto(Some(termo));
        for (col, col_n) in &mapa {
            if col_n.contains(&t) {
                return Some((*col).clone());
            }
        }
    }
    None
}

// ---------------------------------------------------------------------------
// Leitura de CSV bruto (sep=";", dtype=str; utf-8-sig → latin-1 fallback)
// ---------------------------------------------------------------------------

fn decode_bytes(bytes: &[u8], codificacao: &str) -> String {
    if codificacao == "latin-1" {
        bytes.iter().map(|&b| b as char).collect()
    } else {
        let sem_bom = if bytes.starts_with(&[0xEF, 0xBB, 0xBF]) { &bytes[3..] } else { bytes };
        String::from_utf8_lossy(sem_bom).into_owned()
    }
}

/// Lê o cabeçalho do CSV Anatel detectando encoding (`_etapa_inspecionar_cabecalho`).
/// Retorna (lista de colunas, codificação).
pub fn inspecionar_cabecalho(csv_path: &Path) -> Result<(Vec<String>, String), String> {
    progresso(10, "INSPECIONANDO CABEÇALHO DO ARQUIVO", "Conectando os cabos e mapeando colunas...", "");
    let bytes = std::fs::read(csv_path)
        .map_err(|e| format!("Falha ao ler {}: {e}", csv_path.display()))?;
    // utf-8-sig: falha se não for UTF-8 válido → latin-1
    let teste = bytes.strip_prefix(&[0xEF, 0xBB, 0xBF]).unwrap_or(&bytes[..]);
    let conteudo = match std::str::from_utf8(teste) {
        Ok(_) => {
            let s = String::from_utf8(bytes.to_vec()).unwrap();
            (s.replace('\u{feff}', ""), "utf-8-sig".to_string())
        }
        Err(_) => (decode_bytes(&bytes, "latin-1"), "latin-1".to_string()),
    };
    let primeira_linha = conteudo.0.lines().next().ok_or("CSV vazio")?.to_string();
    let colunas = split_semicolon_quoted(&primeira_linha)
        .into_iter()
        .map(|c| c.trim().replace('\u{feff}', ""))
        .collect();
    Ok((colunas, conteudo.1))
}

/// Divide uma linha por ';' respeitando aspas duplas RFC-4180 simplificado.
fn split_semicolon_quoted(linha: &str) -> Vec<String> {
    let mut campos = Vec::new();
    let mut atual = String::new();
    let mut dentro = false;
    let mut chars = linha.chars().peekable();
    while let Some(c) = chars.next() {
        match c {
            '"' => {
                if dentro && chars.peek() == Some(&'"') {
                    atual.push('"');
                    chars.next();
                } else {
                    dentro = !dentro;
                }
            }
            ';' if !dentro => campos.push(std::mem::take(&mut atual)),
            _ => atual.push(c),
        }
    }
    campos.push(atual);
    campos
}

/// Carrega o CSV Anatel em baixa memória, apenas colunas necessárias, tudo str
/// (`_etapa_carregar_csv`: sep=";", dtype=str, keep_default_na=False).
pub fn carregar_csv_bruto(
    csv_path: &Path,
    codificacao: &str,
    colunas_necessarias: &[String],
) -> Result<DataFrame, String> {
    progresso(15, "CARREGANDO BASE DE SETORES", "Iluminando a fibra óptica (modo de baixa memória)...", "");
    let bytes = std::fs::read(csv_path)
        .map_err(|e| format!("Falha ao ler {}: {e}", csv_path.display()))?;
    let conteudo = decode_bytes(&bytes, codificacao);
    let linhas = conteudo.lines().filter(|l| !l.trim().is_empty());
    let mut linhas = linhas;
    let cabecalho = linhas.next().ok_or("CSV vazio")?;
    let todas: Vec<String> = split_semicolon_quoted(cabecalho)
        .into_iter()
        .map(|c| c.trim().replace('\u{feff}', ""))
        .collect();
    let indices: Vec<usize> = colunas_necessarias
        .iter()
        .filter_map(|n| todas.iter().position(|c| c == n))
        .collect();
    let colunas: Vec<String> = indices.iter().map(|&i| todas[i].clone()).collect();
    let mut dados: Vec<Vec<Cell>> = vec![Vec::new(); colunas.len()];
    for l in linhas {
        let campos = split_semicolon_quoted(l);
        for (j, &orig) in indices.iter().enumerate() {
            dados[j].push(match campos.get(orig) {
                Some(c) => Cell::String(c.clone()),
                None => Cell::Null,
            });
        }
    }
    Ok(DataFrame { colunas, dados })
}

// ---------------------------------------------------------------------------
// Download e extração
// ---------------------------------------------------------------------------

/// Baixa o ZIP oficial de estações SMP do servidor da Anatel (`baixar_zip_anatel`).
///
/// Retorna true se download bem-sucedido. Remove o CSV extraído antigo para
/// forçar reextração. Em caso de erro grava `INFO.ultimo_erro` e retorna false.
pub fn baixar_zip_anatel() -> bool {
    estado::info_set_modulo_atual("DOWNLOAD ANATEL");
    let destino = arquivo_zip();
    baixar_zip_para(URL_ANATEL, &destino)
}

/// Núcleo do download (separado para permitir teste sem rede).
pub fn baixar_zip_para(url: &str, destino: &Path) -> bool {
    let config = ureq::config::Config::builder()
        .timeout_recv_body(Some(Duration::from_secs(120)))
        .timeout_connect(Some(Duration::from_secs(120)))
        .build();
    let agente = ureq::Agent::new_with_config(config);
    match agente.get(url).call() {
        Ok(resp) => {
            let total_bytes: i64 = resp
                .headers()
                .get("content-length")
                .and_then(|v| v.to_str().ok())
                .and_then(|v| v.parse().ok())
                .unwrap_or(0);
            let mut baixado: i64 = 0;
            let mut ultimo_desenho = 0.0f64;
            let t_inicio = Instant::now();
            let arq = std::fs::File::create(destino);
            let mut arq = match arq {
                Ok(a) => a,
                Err(e) => {
                    estado::info_set_ultimo_erro(&format!(
                        "Falha no download ANATEL: IO: {e}"
                    ));
                    return false;
                }
            };
            let mut corpo_reader = resp.into_body();
            let mut corpo = corpo_reader.as_reader();
            let mut buf = vec![0u8; 512 * 1024];
            loop {
                let n = match corpo.read(&mut buf) {
                    Ok(0) => break,
                    Ok(n) => n,
                    Err(e) => {
                        estado::info_set_ultimo_erro(&format!(
                            "Falha no download ANATEL: NetworkError: {e}"
                        ));
                        return false;
                    }
                };
                if arq.write_all(&buf[..n]).is_err() {
                    estado::info_set_ultimo_erro("Falha no download ANATEL: IO");
                    return false;
                }
                baixado += n as i64;
                let agora = t_inicio.elapsed().as_secs_f64();
                if agora - ultimo_desenho > 0.12 || baixado == total_bytes {
                    ultimo_desenho = agora;
                    let mb_atual = baixado as f64 / (1024.0 * 1024.0);
                    let mb_tot = if total_bytes > 0 { total_bytes as f64 / (1024.0 * 1024.0) } else { mb_atual };
                    let perc = if total_bytes > 0 { baixado as f64 / total_bytes as f64 * 100.0 } else { 50.0 };
                    let decorrido = agora.max(0.001);
                    let vel_mb_s = mb_atual / decorrido;
                    let eta_txt = if total_bytes > 0 && vel_mb_s > 0.0 {
                        let restante_s = ((mb_tot - mb_atual) / vel_mb_s).max(0.0);
                        format!("{:02}:{:02}", (restante_s as i64) / 60, (restante_s as i64) % 60)
                    } else {
                        "--:--".to_string()
                    };
                    let detalhe = format!(
                        "{mb_atual:5.1}/{mb_tot:.1} MB  •  {vel_mb_s:5.1} MB/s  •  ETA {eta_txt}"
                    );
                    progresso(
                        perc as i64,
                        "TRANSFERÊNCIA DE ARQUIVO - SERVIDOR ANATEL",
                        "Recebendo pacote oficial de estações licenciadas...",
                        &detalhe,
                    );
                }
            }
            // Remove CSV extraído antigo para forçar reextração
            let csv = arquivo_csv_extraido();
            if csv.exists() {
                let _ = std::fs::remove_file(&csv);
            }
            true
        }
        Err(e) => {
            estado::info_set_ultimo_erro(&format!("Falha no download ANATEL: RequestException: {e}"));
            false
        }
    }
}

/// Extrai o CSV de dentro do ZIP da Anatel (`extrair_csv_do_zip`).
pub fn extrair_csv_do_zip() -> Result<(), String> {
    let zip_path = arquivo_zip();
    if !zip_path.exists() {
        return Err(format!("Arquivo {} não encontrado.", zip_path.display()));
    }
    progresso(5, "DESCOMPACTANDO PACOTE ZIP", &format!("Extraindo {} em disco (operação única)...", zip_path.display()), "");
    extrair_csv_do_zip_para(&zip_path, &arquivo_csv_extraido())
}

/// Núcleo da extração (testável com caminho injetado).
pub fn extrair_csv_do_zip_para(zip_path: &Path, destino: &Path) -> Result<(), String> {
    let arq = std::fs::File::open(zip_path).map_err(|e| e.to_string())?;
    let mut zip = zip::ZipArchive::new(arq).map_err(|e| e.to_string())?;
    let nomes: Vec<String> = (0..zip.len())
        .filter_map(|i| zip.name_for_index(i).map(|s| s.to_string()))
        .collect();
    let csv_interno = nomes
        .iter()
        .find(|f| f.to_lowercase().ends_with(".csv"))
        .ok_or("Nenhum arquivo CSV encontrado dentro do ZIP.")?;
    let mut origem = zip.by_name(csv_interno).map_err(|e| e.to_string())?;
    let mut destino_arq = std::fs::File::create(destino).map_err(|e| e.to_string())?;
    let mut bloco = vec![0u8; 1024 * 1024];
    loop {
        let n = origem.read(&mut bloco).map_err(|e| e.to_string())?;
        if n == 0 {
            break;
        }
        destino_arq.write_all(&bloco[..n]).map_err(|e| e.to_string())?;
    }
    Ok(())
}

// ---------------------------------------------------------------------------
// Índice de busca global
// ---------------------------------------------------------------------------

/// Concatena colunas relevantes em `__BUSCA_GLOBAL` (`_compilar_indice_busca_global`).
pub fn compilar_indice_busca_global(df_erbs: &mut DataFrame) {
    let colunas: Vec<String> = COLUNAS_BUSCA_GLOBAL
        .iter()
        .filter(|c| df_erbs.colunas.iter().any(|cc| cc == *c))
        .cloned()
        .map(|s| s.to_string())
        .collect();
    if colunas.is_empty() {
        let n = df_erbs.len();
        df_erbs.set_coluna("__BUSCA_GLOBAL", vec![Cell::String(String::new()); n]);
        return;
    }
    let n = df_erbs.len();
    let mut combinada: Vec<String> = vec![String::new(); n];
    for (k, c) in colunas.iter().enumerate() {
        let col = df_erbs.coluna(c);
        for i in 0..n {
            let val = celula_para_str(&col[i]);
            if k == 0 {
                combinada[i] = val;
            } else {
                combinada[i].push_str(" | ");
                combinada[i].push_str(&val);
            }
        }
    }
    let valores: Vec<Cell> = combinada.iter().map(|s| Cell::String(normalizar_texto(Some(s)))).collect();
    df_erbs.set_coluna("__BUSCA_GLOBAL", valores);
}

fn celula_para_str(v: &Cell) -> String {
    match v {
        Cell::Null => String::new(),
        Cell::String(s) => s.clone(),
        other => other.to_string(),
    }
}

// ---------------------------------------------------------------------------
// Etapas do pipeline
// ---------------------------------------------------------------------------

type MapaColunas = HashMap<String, Option<String>>;

/// Etapa 2: mapeia colunas do CSV para nomes canônicos (`_etapa_mapear_colunas`).
pub fn etapa_mapear_colunas(todas_colunas: &[String]) -> Result<MapaColunas, String> {
    let mut usadas: HashSet<String> = HashSet::new();
    let mut mapa: MapaColunas = HashMap::new();

    let mut pick = |exatos: &[&str], parciais: &[&str]| -> Option<String> {
        let c = identificar_coluna(todas_colunas, exatos, Some(parciais), &usadas);
        if let Some(cc) = &c {
            usadas.insert(cc.clone());
        }
        c
    };

    // Essenciais. O Python mapeia "uf" PRIMEIRO com parciais ["SIGLA_UF",
    // "SIGLAUF", "UF"]; num CSV sem coluna UF dedicada isso captura
    // "Município-UF" (contém "UF"). Nesse caso o valor real de UF vem depois
    // da regex sobre o município — ver `etapa_processar_tecnologias`.
    mapa.insert("uf".into(), pick(&["UF", "SIGLAUF", "SIGLA_UF"], &["SIGLA_UF", "SIGLAUF", "UF"]));
    mapa.insert("mun".into(), pick(&["Município-UF", "MUNICIPIO", "NOMEMUNICIPIO"], &["MUNICIPIO", "CIDADE", "MUNICÍPIO"]));
    mapa.insert("estacao".into(), pick(&["Número Estação", "NUMESTACAO", "NUMEROESTACAO"], &["ESTACAO", "ESTAÇÃO"]));
    mapa.insert("empresa".into(), pick(&["Empresa Estação", "NOMEENTIDADE", "Entidade"], &["EMPRESA ESTAÇÃO", "ENTIDADE", "EMPRESA"]));
    mapa.insert("entidade".into(), pick(&["Entidade", "NOMEENTIDADE"], &["ENTIDADE"]));
    // Tecnologias
    mapa.insert("tec".into(), pick(&["Tecnologia", "TECNOLOGIA"], &["TECNOLOGIA"]));
    mapa.insert("ger".into(), pick(&["Geração", "GERACAO"], &["GERACAO", "GERAÇÃO"]));
    mapa.insert("tec5g".into(), pick(&["Tipo de Tecnologia 5G"], &["TIPO DE TECNOLOGIA 5G"]));
    // Endereços
    mapa.insert("bairro".into(), pick(&["EndBairro", "BAIRRO", "NOMEBAIRRO"], &["BAIRRO"]));
    mapa.insert("logr".into(), pick(&["EnderecoEstacao", "LOGRADOURO", "ENDERECO"], &["LOGRADOURO", "ENDERECO", "ENDEREÇO"]));
    mapa.insert("num".into(), pick(&["EndNumero"], &["ENDNUMERO", "NÚMERO", "NUMERO"]));
    mapa.insert("compl".into(), pick(&["EndComplemento", "COMPLEMENTO"], &["COMPLEMENTO"]));
    mapa.insert("cep".into(), pick(&["Cep", "CEP"], &["CEP"]));
    // Coordenadas
    mapa.insert("lat_dec".into(), pick(&["Latitude decimal"], &["LATITUDE DECIMAL"]));
    mapa.insert("lon_dec".into(), pick(&["Longitude decimal"], &["LONGITUDE DECIMAL"]));
    mapa.insert("lat".into(), pick(&["Latitude", "LATITUDE"], &["LATITUDE"]));
    mapa.insert("lon".into(), pick(&["Longitude", "LONGITUDE"], &["LONGITUDE"]));
    // Frequência
    mapa.insert("freq".into(), pick(&["Frequência (MHz)", "Frequência"], &["FREQUÊNCIA", "FREQUENCIA"]));
    mapa.insert("freq_tx".into(), pick(&["FreqTxMHz"], &["FREQTX"]));
    mapa.insert("freq_rx".into(), pick(&["FreqRxMHz"], &["FREQRX"]));
    mapa.insert("largura".into(), pick(&["Banda_MHZ", "Banda"], &["BANDA"]));
    // Classificações
    mapa.insert("carater".into(), pick(&["Caráter", "Carater"], &["CARÁTER", "CARATER"]));
    mapa.insert("infra".into(), pick(&["ClassInfraFisica"], &["CLASSINFRA", "INFRA"]));
    // Datas
    mapa.insert("data_lic".into(), pick(&["Data Licenciamento"], &["DATA LICENCIAMENTO"]));
    mapa.insert("data_prim".into(), pick(&["Data Primeiro Licenciamento"], &["DATA PRIMEIRO"]));
    mapa.insert("ibge".into(), pick(&["Código IBGE", "Codigo IBGE"], &["IBGE"]));

    let tem = |k: &str| mapa.get(k).and_then(|v| v.as_ref()).is_some();
    if !(tem("mun") && tem("estacao")) {
        return Err(format!("Colunas essenciais não identificadas. Disponíveis: {todas_colunas:?}"));
    }
    if !(tem("empresa") || tem("entidade")) {
        return Err("Nenhuma coluna de empresa/entidade encontrada.".into());
    }
    Ok(mapa)
}

fn get_m<'a>(mapa: &'a MapaColunas, k: &str) -> Option<&'a String> {
    mapa.get(k).and_then(|v| v.as_ref())
}

/// Helper: série da coluna com fillna("") + strip; vazia se coluna ausente.
fn serie_strip(df: &DataFrame, nome: Option<&String>) -> Vec<String> {
    match nome {
        Some(n) if df.colunas.iter().any(|c| c == n) => df
            .coluna(n)
            .iter()
            .map(|v| celula_para_str(v).trim().to_string())
            .collect(),
        _ => vec![String::new(); df.len()],
    }
}

/// Etapa 4: consolida tecnologias 2G/3G/4G/5G (`_etapa_processar_tecnologias`).
pub fn etapa_processar_tecnologias(mut df: DataFrame, mapa: &MapaColunas) -> DataFrame {
    progresso(25, "CONSOLIDANDO TECNOLOGIAS (2G/3G/4G/5G)", "Provisionando setores e subindo portadoras...", "");
    let n = df.len();
    let col_tec = get_m(mapa, "tec").cloned();
    let col_ger = get_m(mapa, "ger").cloned();

    let tec_combinada: Vec<String> = match (&col_tec, &col_ger) {
        (Some(t), Some(g)) => {
            let ct = df.coluna(t);
            let cg = df.coluna(g);
            (0..n).map(|i| format!("{} {}", celula_para_str(&ct[i]), celula_para_str(&cg[i]))).collect()
        }
        (Some(t), None) => df.coluna(t).iter().map(celula_para_str).collect(),
        (None, Some(g)) => df.coluna(g).iter().map(celula_para_str).collect(),
        (None, None) => vec![String::new(); n],
    };

    // Pré-condição (pipeline): materializa a coluna canônica "UF" ANTES do
    // primeiro filtro, replicando a ordem do pandas — que resolve `colunas` e
    // `mapa` na etapa 2 e só então roda as etapas. Assim, quando o mapa apontou
    // "uf" para a coluna de município (parcial "UF" em "Município-UF") ou não
    // achou coluna UF, o valor real vem do sufixo "-XX" via regex — igual ao
    // fallback `str.extract(r"-\s*([A-Za-z]{2})$")` da etapa 5 em Python.
    {
        let uf_col = get_m(mapa, "uf").cloned();
        let mun_col = get_m(mapa, "mun").cloned();
        let dedicada = match (&uf_col, &mun_col) {
            (Some(u), m) => m.as_deref() != Some(u.as_str()),
            (None, _) => false,
        };
        if !dedicada {
            let re_uf = Regex::new(r"-\s*([A-Za-z]{2})$").unwrap();
            let mun_raw = serie_strip(&df, mun_col.as_ref());
            let uf_vals: Vec<String> = mun_raw
                .iter()
                .map(|s| re_uf.captures(s).map(|c| c[1].to_uppercase()).unwrap_or_default())
                .collect();
            df.set_coluna("UF", uf_vals.into_iter().map(Cell::String).collect());
        }
    }

    let mut mapa_tec: HashMap<String, String> = HashMap::new();
    let siglas: Vec<String> = tec_combinada
        .iter()
        .map(|v| {
            mapa_tec
                .entry(v.clone())
                .or_insert_with(|| mapear_sigla_tecnologia(v).to_string())
                .clone()
        })
        .collect();

    let mask: Vec<bool> = siglas.iter().map(|s| !s.is_empty()).collect();
    // pandas: df["TEC_SIGLA"] = serie (alinhada por índice) e SÓ então
    // df = df[df["TEC_SIGLA"] != ""] — o filtro remove as linhas descartadas.
    let mut df2 = df;
    df2.set_coluna("TEC_SIGLA", siglas.into_iter().map(Cell::String).collect());
    df2 = df2.filtrar_mask(&mask);

    // drop colunas originais de tecnologia
    for c_drop in [col_tec, col_ger].into_iter().flatten() {
        df2 = df2.remover_coluna(&c_drop);
    }
    df2
}



/// Etapa 5: município, operadora e UF (`_etapa_processar_municipio_operadora_uf`).
pub fn etapa_processar_municipio_operadora_uf(mut df: DataFrame, mapa: &MapaColunas) -> DataFrame {
    let mun = serie_strip(&df, get_m(mapa, "mun"));
    df.set_coluna("MUNICIPIO", mun.into_iter().map(Cell::String).collect());
    let est = serie_strip(&df, get_m(mapa, "estacao"));
    df.set_coluna("NUM_ESTACAO", est.into_iter().map(Cell::String).collect());

    if let Some(emp) = get_m(mapa, "empresa") {
        let op: Vec<String> = serie_strip(&df, Some(emp)).into_iter().map(|s| s.to_uppercase()).collect();
        df.set_coluna("OPERADORA", op.into_iter().map(Cell::String).collect());
    } else if let Some(ent) = get_m(mapa, "entidade") {
        let entidade = serie_strip(&df, Some(ent));
        let mut mapa_op: HashMap<String, String> = HashMap::new();
        let op: Vec<String> = entidade
            .iter()
            .map(|v| mapa_op.entry(v.clone()).or_insert_with(|| padronizar_operadora(v)).clone())
            .collect();
        df.set_coluna("OPERADORA", op.into_iter().map(Cell::String).collect());
    }

    df
}

/// Etapa 6: remove setores duplicados por ERB+tecnologia (`_etapa_desduplicar`).
pub fn etapa_desduplicar(df: DataFrame) -> DataFrame {
    progresso(35, "DESDUPLICANDO SETORES POR ERB", "Alinhando os enlaces de micro-ondas...", "");
    let cols = ["UF", "MUNICIPIO", "OPERADORA", "NUM_ESTACAO", "TEC_SIGLA"];
    let chaves: Vec<Vec<String>> = (0..df.len())
        .map(|i| cols.iter().map(|c| celula_para_str(&df.celula(i, c))).collect())
        .collect();
    let mut vistos: HashSet<Vec<String>> = HashSet::new();
    let mask: Vec<bool> = chaves.into_iter().map(|k| vistos.insert(k)).collect();
    df.filtrar_mask(&mask)
}

/// Etapa 7: endereços e coordenadas brutas (`_etapa_preparar_enderecos_coordenadas`).
pub fn etapa_preparar_enderecos_coordenadas(mut df: DataFrame, mapa: &MapaColunas) -> DataFrame {
    progresso(45, "PREPARANDO ENDEREÇOS E COORDENADAS", "Ajustando o azimute e tilt das antenas...", "");
    let s_bairro = serie_strip(&df, get_m(mapa, "bairro"));
    let s_logr = serie_strip(&df, get_m(mapa, "logr"));
    let s_num = serie_strip(&df, get_m(mapa, "num"));
    let s_compl = serie_strip(&df, get_m(mapa, "compl"));

    let re_esp = Regex::new(r"\s+").unwrap();
    let logr_full: Vec<String> = (0..df.len())
        .map(|i| {
            let joined = format!("{} {} {}", s_logr[i], s_num[i], s_compl[i]);
            let t = joined.trim().to_string();
            re_esp.replace_all(&t, " ").to_string()
        })
        .collect();

    df.set_coluna("BAIRRO_RAW", s_bairro.into_iter().map(Cell::String).collect());
    df.set_coluna("LOGR_RAW", logr_full.into_iter().map(Cell::String).collect());

    // Coordenadas: prioriza decimal; senão GMS como fallback
    let lat_raw = escolher_coluna(&df, &[get_m(mapa, "lat_dec"), get_m(mapa, "lat")]);
    let lon_raw = escolher_coluna(&df, &[get_m(mapa, "lon_dec"), get_m(mapa, "lon")]);
    df.set_coluna("LAT_RAW", lat_raw);
    df.set_coluna("LON_RAW", lon_raw);
    df
}

fn escolher_coluna(df: &DataFrame, opcoes: &[Option<&String>]) -> Vec<Cell> {
    let n = df.len();
    for o in opcoes.iter().flatten() {
        if df.colunas.iter().any(|c| c.as_str() == o.as_str()) {
            return df.coluna(o);
        }
    }
    vec![Cell::String(String::new()); n]
}

/// Etapa 8: agrupa setores por ERB física (`_etapa_agrupar_erbs`).
pub fn etapa_agrupar_erbs(df: DataFrame, mapa: &MapaColunas) -> DataFrame {
    progresso(60, "AGRUPANDO ESTAÇÕES FÍSICAS (ERBs)", "Medindo VSWR e integrando BBUs...", "");

    // ORDEM = TEC_SIGLA.map(ORDEM_TEC)
    let tec = df.coluna("TEC_SIGLA");
    let ordem: Vec<Cell> = tec
        .iter()
        .map(|v| Value::from(ordem_tec(&celula_para_str(v)) as i64))
        .collect();
    let mut df1 = df.clone();
    df1.set_coluna("ORDEM", ordem);

    // sort_values estável por [UF, MUNICIPIO, OPERADORA, NUM_ESTACAO, ORDEM]
    let mut idx: Vec<usize> = (0..df1.len()).collect();
    let cols_ordem = ["UF", "MUNICIPIO", "OPERADORA", "NUM_ESTACAO", "ORDEM"];
    idx.sort_by(|&a, &b| {
        for c in cols_ordem {
            let ord = cmp_celula(&df1.celula(a, c), &df1.celula(b, c));
            if ord != std::cmp::Ordering::Equal {
                return ord;
            }
        }
        std::cmp::Ordering::Equal
    });
    df1 = df1.selecionar_linhas(&idx);

    // groupby(["UF","MUNICIPIO","OPERADORA","NUM_ESTACAO"], sort=False) preservando 1ª aparição
    let mut grupos: Vec<(Vec<String>, Vec<usize>)> = Vec::new();
    {
        let chave_de = |i: usize| -> Vec<String> {
            ["UF", "MUNICIPIO", "OPERADORA", "NUM_ESTACAO"]
                .iter()
                .map(|c| celula_para_str(&df1.celula(i, c)))
                .collect()
        };
        for i in 0..df1.len() {
            let k = chave_de(i);
            match grupos.iter_mut().find(|(kk, _)| *kk == k) {
                Some((_, ids)) => ids.push(i),
                None => grupos.push((k, vec![i])),
            }
        }
    }

    let first_cell = |col: &str, ids: &[usize]| df1.celula(ids[0], col);
    let mut registros: Vec<Map<String, Cell>> = Vec::with_capacity(grupos.len());
    let tem_extras = get_m(mapa, "freq_tx").is_some() || get_m(mapa, "freq").is_some();

    for (chave, ids) in &grupos {
        let tec_siglas: Vec<String> = ids.iter().map(|&i| celula_para_str(&df1.celula(i, "TEC_SIGLA"))).collect();
        let mut reg: Map<String, Cell> = Map::new();
        reg.insert("UF".into(), Cell::String(chave[0].clone()));
        reg.insert("MUNICIPIO".into(), Cell::String(chave[1].clone()));
        reg.insert("OPERADORA".into(), Cell::String(chave[2].clone()));
        reg.insert("NUM_ESTACAO".into(), Cell::String(chave[3].clone()));
        reg.insert("TECS_RAW".into(), Cell::String(tec_siglas.join(",")));
        reg.insert(
            "TECNOLOGIA".into(),
            Cell::String(if tec_siglas.len() == 4 { "TODAS".to_string() } else { tec_siglas.join(", ") }),
        );
        reg.insert("BAIRRO_RAW".into(), first_cell("BAIRRO_RAW", ids));
        reg.insert("LOGR_RAW".into(), first_cell("LOGR_RAW", ids));
        reg.insert("LAT_RAW".into(), first_cell("LAT_RAW", ids));
        reg.insert("LON_RAW".into(), first_cell("LON_RAW", ids));

        if tem_extras {
            let col_freq = get_m(mapa, "freq_tx").or(get_m(mapa, "freq")).or(get_m(mapa, "largura"));
            let extras: Vec<(&str, Option<&String>)> = vec![
                ("FREQ_MHZ", col_freq),
                ("LARGURA_CANAL", get_m(mapa, "largura")),
                ("CARATER", get_m(mapa, "carater")),
                ("INFRA", get_m(mapa, "infra")),
                ("TEC5G_TIPO", get_m(mapa, "tec5g")),
                ("IBGE", get_m(mapa, "ibge")),
                ("CEP", get_m(mapa, "cep")),
                ("DATA_LIC", get_m(mapa, "data_lic")),
                ("DATA_PRIM_LIC", get_m(mapa, "data_prim")),
            ];
            for (nome, col_orig) in extras {
                let val = match col_orig {
                    Some(c) if df1.colunas.iter().any(|cc| cc == c) => first_cell(c, ids),
                    _ => Cell::Null,
                };
                reg.insert(nome.into(), val);
            }
        }
        registros.push(reg);
    }
    DataFrame::from_registros(registros)
}

/// Etapa 9: normaliza colunas extras (`_etapa_normalizar_colunas_extras`).
pub fn etapa_normalizar_colunas_extras(mut df_erbs: DataFrame) -> DataFrame {
    progresso(68, "NORMALIZANDO FAIXAS E CLASSIFICAÇÕES", "Organizando frequências, infraestrutura e datas...", "");
    let n = df_erbs.len();

    if df_erbs.colunas.iter().any(|c| c == "FREQ_MHZ") {
        let col = df_erbs.coluna("FREQ_MHZ");
        let nums: Vec<Cell> = col.iter().map(|v| match parse_float_br(v) {
            Some(f) => Cell::from(f),
            None => Cell::Null,
        }).collect();
        let faixas: Vec<Cell> = nums.iter().map(|v| Cell::String(faixa_nominal(v))).collect();
        df_erbs.set_coluna("FREQ_MHZ", nums);
        df_erbs.set_coluna("FAIXA_NOMINAL", faixas);
    } else {
        df_erbs.set_coluna("FREQ_MHZ", vec![Cell::Null; n]);
        df_erbs.set_coluna("FAIXA_NOMINAL", vec![Cell::String(String::new()); n]);
    }

    if df_erbs.colunas.iter().any(|c| c == "LARGURA_CANAL") {
        let col = df_erbs.coluna("LARGURA_CANAL");
        let nums: Vec<Cell> = col.iter().map(|v| match parse_float_br(v) {
            Some(f) => Cell::from(f),
            None => Cell::Null,
        }).collect();
        df_erbs.set_coluna("LARGURA_CANAL", nums);
    } else {
        df_erbs.set_coluna("LARGURA_CANAL", vec![Cell::Null; n]);
    }

    if df_erbs.colunas.iter().any(|c| c == "CARATER") {
        let col = df_erbs.coluna("CARATER");
        let v: Vec<Cell> = col.iter().map(|x| Cell::String(normalizar_texto(Some(&celula_para_str(x))))).collect();
        df_erbs.set_coluna("CARATER", v);
    } else {
        df_erbs.set_coluna("CARATER", vec![Cell::String(String::new()); n]);
    }

    for nome in ["INFRA", "TEC5G_TIPO"] {
        if df_erbs.colunas.iter().any(|c| c == nome) {
            let col = df_erbs.coluna(nome);
            let v: Vec<Cell> = col.iter().map(|x| Cell::String(celula_para_str(x).trim().to_uppercase())).collect();
            df_erbs.set_coluna(nome, v);
        } else {
            df_erbs.set_coluna(nome, vec![Cell::String(String::new()); n]);
        }
    }

    if df_erbs.colunas.iter().any(|c| c == "IBGE") {
        let col = df_erbs.coluna("IBGE");
        df_erbs.set_coluna("IBGE", col.iter().map(|x| Cell::String(limpar_ibge(x))).collect());
    } else {
        df_erbs.set_coluna("IBGE", vec![Cell::String(String::new()); n]);
    }

    if df_erbs.colunas.iter().any(|c| c == "CEP") {
        let col = df_erbs.coluna("CEP");
        df_erbs.set_coluna("CEP", col.iter().map(|x| Cell::String(limpar_cep(x))).collect());
    } else {
        df_erbs.set_coluna("CEP", vec![Cell::String(String::new()); n]);
    }

    // Datas: pd.to_datetime(format="%d/%m/%Y", errors="coerce") → NaT = Null.
    // Mantemos a string dd/mm/aaaa quando válida (compatível com os consumidores).
    for col_dt in ["DATA_LIC", "DATA_PRIM_LIC"] {
        if df_erbs.colunas.iter().any(|c| c == col_dt) {
            let col = df_erbs.coluna(col_dt);
            let v: Vec<Cell> = col.iter().map(|x| validar_data_br(x)).collect();
            df_erbs.set_coluna(col_dt, v);
        } else {
            df_erbs.set_coluna(col_dt, vec![Cell::Null; n]);
        }
    }
    df_erbs
}

fn validar_data_br(v: &Cell) -> Cell {
    let s = celula_para_str(v);
    let partes: Vec<&str> = s.split('/').collect();
    if partes.len() == 3
        && partes[0].len() == 2
        && partes[1].len() == 2
        && partes[2].len() == 4
        && partes.iter().all(|p| p.chars().all(|c| c.is_ascii_digit()))
    {
        let (dia, mes, ano): (u32, u32, u32) =
            (partes[0].parse().unwrap(), partes[1].parse().unwrap(), partes[2].parse().unwrap());
        if (1..=12).contains(&mes) && (1..=31).contains(&dia) && ano > 1900 {
            return Cell::String(s);
        }
    }
    Cell::Null
}

/// Etapa 10: extrai bairros de logradouros (`_etapa_extrair_bairros`).
pub fn etapa_extrair_bairros(mut df_erbs: DataFrame) -> DataFrame {
    progresso(72, "EXTRAINDO BAIRROS DE LOGRADOUROS", "Calibrando a potência das RRUs...", "");
    let bairros_raw = df_erbs.coluna("BAIRRO_RAW");
    let logr_raw = df_erbs.coluna("LOGR_RAW");
    let mut cache_pares: HashMap<(String, String), String> = HashMap::new();
    let extraidos: Vec<Cell> = (0..df_erbs.len())
        .map(|i| {
            let b = celula_para_str(&bairros_raw[i]);
            let l = celula_para_str(&logr_raw[i]);
            let par = (b.clone(), l.clone());
            let r = cache_pares
                .entry(par)
                .or_insert_with(|| crate::texto::extrair_bairro_inteligente(Some(&b), Some(&l)))
                .clone();
            Cell::String(r)
        })
        .collect();
    df_erbs.set_coluna("BAIRRO", extraidos);
    df_erbs
}

/// Etapa 11: unifica bairros por município (`_etapa_unificar_bairros`).
pub fn etapa_unificar_bairros(mut df_erbs: DataFrame, forcar_recompilacao: bool) -> DataFrame {
    let unificados = unificar_bairros_por_municipio(&df_erbs, forcar_recompilacao);
    estado::info_set_bairros_unificados(contar_bairros_distintos(&unificados) as i64);
    df_erbs.set_coluna("BAIRRO", unificados.into_iter().map(Cell::String).collect());
    df_erbs
}

fn contar_bairros_distintos(lista: &[String]) -> usize {
    let mut s: HashSet<&String> = HashSet::new();
    for v in lista {
        if !v.is_empty() {
            s.insert(v);
        }
    }
    s.len()
}

/// Etapa 12: indexa endereço combinado (`_etapa_indexar_endereco_busca`).
pub fn etapa_indexar_endereco_busca(mut df_erbs: DataFrame) -> DataFrame {
    progresso(88, "INDEXANDO MALHA RODOVIÁRIA (BRs/ESTADUAIS)", "Mapeando rodovias e filtrando quadras urbanas...", "");
    let logr = df_erbs.coluna("LOGR_RAW");
    let endereco: Vec<String> = logr
        .iter()
        .map(|v| {
            let up = celula_para_str(v).to_uppercase();
            if up.is_empty() || up == "NAN" || up == "NONE" {
                "ENDEREÇO NÃO INFORMADO".to_string()
            } else {
                up
            }
        })
        .collect();
    df_erbs.set_coluna("ENDERECO", endereco.iter().cloned().map(Cell::String).collect());

    let bairro = df_erbs.coluna("BAIRRO");
    let end_comb: Vec<String> = (0..df_erbs.len())
        .map(|i| format!("{} {}", endereco[i], celula_para_str(&bairro[i])))
        .collect();
    let mut mapa_end: HashMap<String, String> = HashMap::new();
    let busca: Vec<Cell> = end_comb
        .iter()
        .map(|v| Cell::String(mapa_end.entry(v.clone()).or_insert_with(|| normalizar_texto(Some(v))).clone()))
        .collect();
    df_erbs.set_coluna("ENDERECO_BUSCA", busca);
    df_erbs
}

/// Etapa 13: converte coordenadas GPS (`_etapa_converter_gps`).
pub fn etapa_converter_gps(mut df_erbs: DataFrame) -> DataFrame {
    progresso(92, "CONVERTENDO COORDENADAS GPS", "Sincronizando handovers na rede...", "");
    let lat_raw = df_erbs.coluna("LAT_RAW");
    let lon_raw = df_erbs.coluna("LON_RAW");
    let n = df_erbs.len();

    // pd.to_numeric(errors="coerce")
    let to_num = |col: &Vec<Cell>| -> Vec<Option<f64>> {
        col.iter().map(|v| match v {
            Cell::Number(_) => v.as_f64(),
            Cell::String(s) => s.trim().parse::<f64>().ok(),
            _ => None,
        }).collect()
    };
    let mut lats = to_num(&lat_raw);
    let mut lons = to_num(&lon_raw);
    let nans = lats.iter().filter(|x| x.is_none()).count();
    if nans as f64 > n as f64 * 0.5 {
        // cai para o parser GMS (converter_coord_anatel)
        let mut mapa_lat: HashMap<String, Option<f64>> = HashMap::new();
        let mut mapa_lon: HashMap<String, Option<f64>> = HashMap::new();
        lats = lat_raw.iter().map(|v| {
            let k = celula_para_str(v);
            *mapa_lat.entry(k.clone()).or_insert_with(|| converter_coord_anatel(&k))
        }).collect();
        lons = lon_raw.iter().map(|v| {
            let k = celula_para_str(v);
            *mapa_lon.entry(k.clone()).or_insert_with(|| converter_coord_anatel(&k))
        }).collect();
    }

    let gps: Vec<Cell> = (0..n)
        .map(|i| match (lats[i], lons[i]) {
            (Some(a), Some(b)) => Cell::String(format!("{:.6}, {:.6}", a, b)),
            _ => Cell::String("Sem GPS".to_string()),
        })
        .collect();
    df_erbs.set_coluna("LAT_NUM", lats.into_iter().map(|x| match x { Some(f) => Cell::from(f), None => Cell::Null }).collect());
    df_erbs.set_coluna("LON_NUM", lons.into_iter().map(|x| match x { Some(f) => Cell::from(f), None => Cell::Null }).collect());
    df_erbs.set_coluna("GPS", gps);

    for c in ["BAIRRO_RAW", "LOGR_RAW", "LAT_RAW", "LON_RAW"] {
        df_erbs = df_erbs.remover_coluna(c);
    }
    df_erbs
}

/// Etapa 14: finaliza identificadores (`_etapa_finalizar_identificadores`).
pub fn etapa_finalizar_identificadores(mut df_erbs: DataFrame) -> DataFrame {
    let op = df_erbs.coluna("OPERADORA");
    let num = df_erbs.coluna("NUM_ESTACAO");
    let id: Vec<Cell> = (0..df_erbs.len())
        .map(|i| Cell::String(format!("{}_{}", celula_para_str(&op[i]), celula_para_str(&num[i]))))
        .collect();
    df_erbs.set_coluna("ID_ERB", id);

    let re_mun = Regex::new(r"\s*-\s*[A-Za-z]{2}$").unwrap();
    let muns = df_erbs.coluna("MUNICIPIO");
    let mun_limpo: Vec<String> = muns
        .iter()
        .map(|v| re_mun.replace(&celula_para_str(v), "").trim().to_string())
        .collect();
    df_erbs.set_coluna("MUNICIPIO_LIMPO", mun_limpo.iter().map(|s| Cell::String(s.to_uppercase())).collect());
    let mut mapa_mun: HashMap<String, String> = HashMap::new();
    let norm: Vec<Cell> = mun_limpo
        .iter()
        .map(|v| Cell::String(mapa_mun.entry(v.clone()).or_insert_with(|| normalizar_texto(Some(v))).clone()))
        .collect();
    df_erbs.set_coluna("MUNICIPIO_NORM", norm);
    df_erbs
}

/// Etapa 15: compila índice de busca global (`_etapa_indexar_busca_global`).
pub fn etapa_indexar_busca_global(mut df_erbs: DataFrame) -> DataFrame {
    progresso(96, "INDEXANDO PESQUISA GLOBAL", "Compilando coluna única de busca (evita lentidão na 1ª consulta)...", "");
    compilar_indice_busca_global(&mut df_erbs);
    df_erbs
}

// ---------------------------------------------------------------------------
// Pipeline principal
// ---------------------------------------------------------------------------

/// Pipeline completo: lê CSV bruto, produz DataFrame consolidado e salva cache
/// (`processar_base_e_salvar_cache`). Retorna `(df_erbs, origem)`.
pub fn processar_base_e_salvar_cache(forcar_recompilacao_bairros: bool) -> Result<(DataFrame, String), String> {
    let csv_path = arquivo_csv_extraido();
    if !csv_path.exists() {
        extrair_csv_do_zip()?;
    }

    // 1) Cabeçalho e encoding
    let (todas_colunas, codificacao) = inspecionar_cabecalho(&csv_path)?;
    // 2) Mapear colunas
    let mapa = etapa_mapear_colunas(&todas_colunas)?;

    let colunas_necessarias: Vec<String> = ["uf", "mun", "estacao", "empresa", "entidade",
        "tec", "ger", "tec5g",
        "bairro", "logr", "num", "compl", "cep",
        "lat_dec", "lon_dec", "lat", "lon",
        "freq", "freq_tx", "freq_rx", "largura",
        "carater", "infra",
        "data_lic", "data_prim", "ibge",
    ]
    .iter()
    .filter_map(|k| get_m(&mapa, k).cloned())
    .collect();

    // 3) Carregar CSV
    let df = carregar_csv_bruto(&csv_path, &codificacao, &colunas_necessarias)?;
    let total_setores = df.len() as i64;

    // 4-7) Processamento incremental
    let df = etapa_processar_tecnologias(df, &mapa);
    let df = etapa_processar_municipio_operadora_uf(df, &mapa);
    let df = etapa_desduplicar(df);
    let df = etapa_preparar_enderecos_coordenadas(df, &mapa);

    // 8) Agrupar ERBs
    let df_erbs = etapa_agrupar_erbs(df, &mapa);

    // 9-15) Normalização e indexação
    let df_erbs = etapa_normalizar_colunas_extras(df_erbs);
    let df_erbs = etapa_extrair_bairros(df_erbs);
    let df_erbs = etapa_unificar_bairros(df_erbs, forcar_recompilacao_bairros);
    let df_erbs = etapa_indexar_endereco_busca(df_erbs);
    let df_erbs = etapa_converter_gps(df_erbs);
    let df_erbs = etapa_finalizar_identificadores(df_erbs);
    let df_erbs = etapa_indexar_busca_global(df_erbs);

    // 16) Persistir cache
    progresso(100, "UFA, PRONTO! SITE CONSTRUÍDO!", "Gravando cache binário de alta velocidade...", "");
    let agora = agora_unix();
    let data_geracao = snap_mod::quebrar_local(agora);
    let pacote = Map::from_iter(vec![
        ("versao".into(), Value::from(VERSAO_CACHE)),
        ("df_erbs".into(), dataframe_para_json(&df_erbs)),
        ("total_setores".into(), Value::from(total_setores)),
        ("bairros_unificados".into(), Value::from(estado::info_bairros_unificados())),
        ("data_geracao".into(), Value::from(data_geracao.clone())),
    ]);
    let json = Value::Object(pacote).to_string();
    std::fs::write(arquivo_cache(), json).map_err(|e| format!("Falha ao gravar cache: {e}"))?;

    // 17) Snapshot para comparação futura
    progresso(99, "GERANDO SNAPSHOT DE NOVIDADES", "Guardando resumo da base para comparar na próxima atualização...", "");
    let data_base = format!("{:02}/{:02}/{}", data_geracao[2], data_geracao[1], data_geracao[0]);
    let snap_novo = snap_mod::gerar_snapshot(Some(&df_erbs), total_setores, &data_base);
    snap_mod::salvar_snapshot(&snap_novo, None);

    sleep_ms(250);
    Ok(atualizar_telemetria_global(df_erbs, total_setores, ORIGEM_CACHE_RECENTE.to_string(), Some(data_base)))
}

fn dataframe_para_json(df: &DataFrame) -> Value {
    let cols: Vec<Value> = df.colunas.iter().map(|c| Value::String(c.clone())).collect();
    let dados: Vec<Value> = df.dados.iter().map(|col| Value::Array(col.clone())).collect();
    Value::Object(Map::from_iter(vec![
        ("colunas".into(), Value::Array(cols)),
        ("dados".into(), Value::Array(dados)),
    ]))
}

fn dataframe_de_json(v: &Value) -> Result<DataFrame, String> {
    let cols: Vec<String> = v
        .get("colunas")
        .and_then(|c| c.as_array())
        .ok_or("cache sem colunas")?
        .iter()
        .map(|s| s.as_str().unwrap_or_default().to_string())
        .collect();
    let dados: Vec<Vec<Cell>> = v
        .get("dados")
        .and_then(|c| c.as_array())
        .ok_or("cache sem dados")?
        .iter()
        .map(|col| col.as_array().cloned().unwrap_or_default())
        .collect();
    Ok(DataFrame { colunas: cols, dados })
}

// ---------------------------------------------------------------------------
// Carga a partir do cache
// ---------------------------------------------------------------------------

/// Carrega base de dados do cache binário (`carregar_do_cache`).
pub fn carregar_do_cache() -> Result<(DataFrame, String), String> {
    progresso(10, "CARREGANDO BASE DE DADOS", "Conectando os cabos...", "");
    sleep_ms(120);
    progresso(15, "CARREGANDO BASE DE DADOS", "Iluminando a fibra óptica...", "");

    let caminho = arquivo_cache();
    let conteudo = std::fs::read_to_string(&caminho)
        .map_err(|e| format!("FileNotFoundError: {e}"))?;
    let pacote: Value = serde_json::from_str(&conteudo)
        .map_err(|e| format!("JSONDecodeError: {e}"))?;

    if pacote.get("versao").and_then(|v| v.as_i64()) != Some(VERSAO_CACHE) {
        return Err(format!(
            "Cache v{:?} incompatível com v{VERSAO_CACHE}.",
            pacote.get("versao")
        ));
    }

    let mut df_erbs = dataframe_de_json(pacote.get("df_erbs").ok_or("KeyError: df_erbs")?)?;

    // Rede de segurança: caches antigos sem __BUSCA_GLOBAL
    if !df_erbs.colunas.iter().any(|c| c == "__BUSCA_GLOBAL") {
        compilar_indice_busca_global(&mut df_erbs);
    }

    let total_setores = pacote.get("total_setores").and_then(|v| v.as_i64()).unwrap_or(df_erbs.len() as i64);
    estado::info_set_bairros_unificados(pacote.get("bairros_unificados").and_then(|v| v.as_i64()).unwrap_or(0));

    let data_ger: i64 = match pacote.get("data_geracao") {
        Some(Value::Array(_)) => timestamp_para_epoch(pacote.get("data_geracao").unwrap()),
        _ => std::fs::metadata(&caminho)
            .and_then(|m| m.modified().map_err(Into::into))
            .map(|t| t.duration_since(UNIX_EPOCH).map(|d| d.as_secs() as i64).unwrap_or(0))
            .unwrap_or_else(|_| agora_unix()),
    };
    let dias = (agora_unix() - data_ger) / 86400;

    for (perc, titulo, frase) in SEQUENCIA_PROGRESSO_CACHE {
        progresso(perc, titulo, frase, "");
        sleep_ms(120);
    }

    let g = snap_mod::quebrar_local(data_ger);
    let origem = format!("{ORIGEM_CACHE_RAPIDO} (há {dias}d)");
    Ok(atualizar_telemetria_global(
        df_erbs,
        total_setores,
        origem,
        Some(format!("{:02}/{:02}/{:04}", g[2], g[1], g[0])),
    ))
}

fn timestamp_para_epoch(v: &Value) -> i64 {
    let a = v.as_array().unwrap();
    let get = |i: usize| a.get(i).and_then(|x| x.as_i64()).unwrap_or(0);
    // reconstrói epoch local aproximado (mesma convenção de snapshot::broken_local)
    let dias = dias_desde_epoch(get(0), get(1) as usize, get(2) as usize);
    dias * 86400 + get(3) * 3600 + get(4) * 60 + get(5)
        - fuso_local().as_secs() as i64
}

fn dias_desde_epoch(ano: i64, mes: usize, dia: usize) -> i64 {
    // algoritmo civil days-from-civil (Howard Hinnant)
    let y = ano - if mes <= 2 { 1 } else { 0 };
    let era = if y >= 0 { y } else { y - 399 } / 400;
    let yoe = y - era * 400;
    let mp = (mes as i64 + 9) % 12;
    let doy = (153 * mp + 2) / 5 + dia as i64 - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146097 + doe - 719468
}

fn fuso_local() -> Duration {
    // offset UTC local via libc localtime_r (mesma fonte usada em snapshot.rs)
    let secs = agora_unix();
    let g = snap_mod::quebrar_local(secs);
    let utc_dias = dias_desde_epoch(g[0], g[1] as usize, g[2] as usize);
    let reconstruido = utc_dias * 86400 + g[3] * 3600 + g[4] * 60 + g[5];
    let diff = reconstruido - secs;
    if diff >= 0 { Duration::from_secs(diff as u64) } else { Duration::ZERO }
}

// ---------------------------------------------------------------------------
// Telemetria global
// ---------------------------------------------------------------------------

/// Atualiza estatísticas globais da base no INFO (`_atualizar_telemetria_global`).
pub fn atualizar_telemetria_global(
    df_erbs: DataFrame,
    total_setores: i64,
    origem_str: String,
    data_atualizacao: Option<String>,
) -> (DataFrame, String) {
    let ufs = df_erbs.n_unique("UF") as i64;
    let municipios = {
        let mut vistos: HashSet<(String, String)> = HashSet::new();
        let a = df_erbs.coluna("UF");
        let b = df_erbs.coluna("MUNICIPIO_NORM");
        for i in 0..df_erbs.len() {
            vistos.insert((celula_para_str(&a[i]), celula_para_str(&b[i])));
        }
        vistos.len() as i64
    };
    let erbs = df_erbs.len() as i64;

    {
        let mut info = estado::info_snapshot();
        info.ufs = ufs;
        info.municipios = municipios;
        info.erbs = erbs;
        info.setores = total_setores;
        info.origem = origem_str.clone();
        if let Some(d) = &data_atualizacao {
            info.data_atualizacao = d.clone();
        }
        estado::definir_info(info);
    }

    estado::definir_base_global(df_erbs.clone());

    if estado::info_bairros_unificados() == 0 {
        let caminho = arquivo_cache_bairros();
        if caminho.exists() {
            match std::fs::read_to_string(&caminho)
                .map_err(|e| e.to_string())
                .and_then(|s| serde_json::from_str::<Value>(&s).map_err(|e| e.to_string()))
            {
                Ok(d_b) => {
                    let soma: i64 = d_b
                        .as_object()
                        .map(|o| o.values().filter_map(|v| v.as_object()).map(|m| m.len() as i64).sum())
                        .unwrap_or(0);
                    estado::info_set_bairros_unificados(soma);
                }
                Err(e) => {
                    let mut info = estado::info_snapshot();
                    info.ultimo_erro = format!("Falha ao ler cache de bairros: {e}");
                    estado::definir_info(info);
                }
            }
        }
    }

    (df_erbs, origem_str)
}

// ---------------------------------------------------------------------------
// Limpeza e bootstrap
// ---------------------------------------------------------------------------

/// Remove arquivos de cache do disco (`limpar_arquivos_cache`).
pub fn limpar_arquivos_cache(apagar_csv_extraido: bool, apagar_cache_bairros: bool) {
    let cache = arquivo_cache();
    if cache.exists() {
        let _ = std::fs::remove_file(&cache);
    }
    if apagar_csv_extraido {
        let csv = arquivo_csv_extraido();
        if csv.exists() {
            let _ = std::fs::remove_file(&csv);
        }
    }
    if apagar_cache_bairros {
        let b = arquivo_cache_bairros();
        if b.exists() {
            let _ = std::fs::remove_file(&b);
        }
    }
}

/// Opções apresentadas pelas caixas de notificação do bootstrap.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EscolhaBootstrap {
    /// Botão 1 (cache/arquivo local instantâneo)
    UsarAtual,
    /// Botão 2 (baixar nova base da Anatel)
    Baixar,
    /// Botão 3 (recompilar bairros)
    RecompilarBairros,
    /// Cancelou/saiu
    Sair,
}

/// Bootstrap completo com a escolha do usuário injetada
/// (`inicializar_base_com_cache` + ramificações `_inicializar_*`).
///
/// A TUI decide qual botão foi pressionado (ver `tui/janelas.rs` quando
/// portado); aqui reproduz-se exatamente a mesma árvore de decisão.
pub fn inicializar_base_com_cache(escolha: Option<EscolhaBootstrap>) -> Result<(DataFrame, String), String> {
    let tem_cache = arquivo_cache().exists();
    let tem_csv = arquivo_csv_extraido().exists();
    let tem_zip = arquivo_zip().exists();

    let escolha = match escolha {
        Some(e) => e,
        None => {
            // Sem TUI: comportamento determinístico equivalente ao botão padrão
            if tem_cache {
                EscolhaBootstrap::UsarAtual
            } else {
                return Err("Nenhum arquivo de base disponível (precisa baixar da Anatel).".into());
            }
        }
    };

    if tem_cache {
        return inicializar_com_cache_existente(tem_zip, escolha);
    }
    if tem_csv || tem_zip {
        return inicializar_com_arquivo_local(tem_zip, escolha);
    }
    inicializar_sem_arquivos(escolha)
}

fn inicializar_com_cache_existente(tem_zip: bool, esc: EscolhaBootstrap) -> Result<(DataFrame, String), String> {
    let ts_ref = arquivo_mtime(&if tem_zip { arquivo_zip() } else { arquivo_cache() });
    let _dias_idade = (agora_unix() - ts_ref) / 86400;
    let g = snap_mod::quebrar_local(ts_ref);
    estado::info_set_data_atualizacao(&format!("{:02}/{:02}/{:04}", g[2], g[1], g[0]));

    match esc {
        EscolhaBootstrap::Baixar => {
            if baixar_zip_anatel() {
                limpar_arquivos_cache(true, true);
                processar_base_e_salvar_cache(true)
            } else {
                carregar_do_cache()
            }
        }
        EscolhaBootstrap::RecompilarBairros => {
            limpar_arquivos_cache(false, true);
            processar_base_e_salvar_cache(true)
        }
        EscolhaBootstrap::Sair => Err("Usuário cancelou a sessão.".into()),
        EscolhaBootstrap::UsarAtual => match carregar_do_cache() {
            Ok(r) => Ok(r),
            Err(e) => {
                estado::info_set_ultimo_erro(&format!("Cache inválido ({e}); recompilando."));
                limpar_arquivos_cache(false, false);
                processar_base_e_salvar_cache(false)
            }
        },
    }
}

fn inicializar_com_arquivo_local(tem_zip: bool, esc: EscolhaBootstrap) -> Result<(DataFrame, String), String> {
    let arq_base = if tem_zip { arquivo_zip() } else { arquivo_csv_extraido() };
    let ts_ref = arquivo_mtime(&arq_base);
    let g = snap_mod::quebrar_local(ts_ref);
    estado::info_set_data_atualizacao(&format!("{:02}/{:02}/{:04}", g[2], g[1], g[0]));

    if esc == EscolhaBootstrap::Baixar {
        baixar_zip_anatel();
    }
    processar_base_e_salvar_cache(false)
}

fn inicializar_sem_arquivos(esc: EscolhaBootstrap) -> Result<(DataFrame, String), String> {
    if esc == EscolhaBootstrap::UsarAtual || esc == EscolhaBootstrap::Baixar {
        if baixar_zip_anatel() {
            return processar_base_e_salvar_cache(false);
        }
    }
    Err("Usuário cancelou o download inicial.".into())
}

fn arquivo_mtime(path: &Path) -> i64 {
    std::fs::metadata(path)
        .and_then(|m| m.modified().map_err(Into::into))
        .map(|t| t.duration_since(UNIX_EPOCH).map(|d| d.as_secs() as i64).unwrap_or(0))
        .unwrap_or_else(|_| agora_unix())
}

/// Garante que o diretório de dados exista (equivalente ao `os.makedirs` implícito).
pub fn garantir_diretorio_dados() -> PathBuf {
    let dir = dados_dir();
    let _ = std::fs::create_dir_all(&dir);
    dir
}

// ---------------------------------------------------------------------------
// Testes
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn faixa_nominal_doc() {
        assert_eq!(faixa_nominal(&json!(1850)), "1800");
        assert_eq!(faixa_nominal(&json!(3500)), "3500");
        assert_eq!(faixa_nominal(&Value::Null), "");
        assert_eq!(faixa_nominal(&json!("26000,5")), "26000");
        assert_eq!(faixa_nominal(&json!(100)), "outra");
    }

    #[test]
    fn parses_doc() {
        assert_eq!(parse_float_br(&json!("1875,00")), Some(1875.0));
        assert_eq!(parse_float_br(&Value::Null), None);
        assert_eq!(limpar_ibge(&json!(2401008.0)), "2401008");
        assert_eq!(limpar_ibge(&Value::Null), "");
        assert_eq!(limpar_cep(&json!("59420000")), "59420000");
        assert_eq!(limpar_cep(&json!("59420-000")), "59420000");
        assert_eq!(limpar_cep(&Value::Null), "");
    }

    #[test]
    fn identificar_coluna_exato_e_parcial() {
        let cols: Vec<String> = ["UF", "Município-UF", "EndBairro"].iter().map(|s| s.to_string()).collect();
        let vazio = HashSet::new();
        assert_eq!(
            identificar_coluna(&cols, &["UF", "SIGLAUF"], None, &vazio).as_deref(),
            Some("UF")
        );
        assert_eq!(
            identificar_coluna(&cols, &["EndBairro", "BAIRRO"], None, &vazio).as_deref(),
            Some("EndBairro")
        );
        assert_eq!(identificar_coluna(&cols, &["NAOEXISTE"], Some(&["TAMBEMNAO"]), &vazio), None);
        // ignorar força próximo match
        let mut ign = HashSet::new();
        ign.insert("UF".to_string());
        assert_eq!(identificar_coluna(&cols, &["UF"], Some(&["SIGLA_UF"]), &ign), None);
    }

    fn csv_minimo() -> String {
        // sep=";" com as colunas essenciais do pipeline
        ";".to_string()
            + &["UF", "Município-UF", "Número Estação", "Empresa Estação", "Tecnologia", "Geração",
                "EndBairro", "EnderecoEstacao", "EndNumero", "EndComplemento", "Cep",
                "Latitude decimal", "Longitude decimal", "FreqTxMHz", "Banda_MHZ",
                "Caráter", "ClassInfraFisica", "Tipo de Tecnologia 5G", "Código IBGE",
                "Data Licenciamento"]
                .join(";")
            + "\n"
            + &["RN", "MOSSORÓ-RN", "1234", "CLARO", "5G NR", "5G",
                "CENTRO", "AV RIO BRANCO", "100", "", "59600000",
                "-5.1890", "-37.3490", "3500,00", "100,00",
                "COMERCIAL", "TORRE", "SA", "2408100", "10/05/2022"]
                .join(";")
            + "\n"
            + &["RN", "MOSSORÓ-RN", "1234", "CLARO", "LTE", "4G",
                "CENTRO", "AV RIO BRANCO", "100", "", "59600000",
                "-5.1890", "-37.3490", "1850,00", "20,00",
                "COMERCIAL", "TORRE", "", "2408100", "10/05/2022"]
                .join(";")
            + "\n"
            + &["RN", "NATAL-RN", "5555", "TIM", "NR", "5G",
                "PETRÓPOLIS", "RxA DAS LARANJEIRAS", "50", "LOJA A", "59020000",
                "-5.8800", "-35.2200", "3500,00", "100,00",
                "RESIDENCIAL", "EDIFÍCIO", "NSA", "2408100", "01/02/2023"]
                .join(";")
            + "\n"
    }

    #[test]
    fn pipeline_completo_em_csv_minimo() {
        let dir = std::env::temp_dir().join(format!("torre_anatel_test_{}", agora_unix_ns()));
        std::fs::create_dir_all(&dir).unwrap();
        std::env::set_var("TORRE_FACIL_DADOS_DIR", &dir);
        let csv = dir.join("base.csv");
        std::fs::write(&csv, csv_minimo()).unwrap();

        let (colunas, codif) = inspecionar_cabecalho(&csv).unwrap();
        assert_eq!(codif, "utf-8-sig");
        let mapa = etapa_mapear_colunas(&colunas).unwrap();
        assert_eq!(mapa.get("mun").and_then(|v| v.as_ref()).unwrap(), "Município-UF");

        let necessarias: Vec<String> = ["uf", "mun", "estacao", "empresa", "tec", "ger", "bairro",
            "logr", "num", "compl", "cep", "lat_dec", "lon_dec", "freq_tx", "largura",
            "carater", "infra", "tec5g", "ibge", "data_lic"]
            .iter()
            .filter_map(|k| get_m(&mapa, k).cloned())
            .collect();
        let df = carregar_csv_bruto(&csv, &codif, &necessarias).unwrap();
        assert_eq!(df.len(), 3);

        let df = etapa_processar_tecnologias(df, &mapa);
        assert_eq!(df.len(), 3);
        let df = etapa_processar_municipio_operadora_uf(df, &mapa);
        assert_eq!(df.celula(0, "UF"), json!("RN"));
        assert_eq!(df.celula(0, "MUNICIPIO"), json!("MOSSORÓ-RN"));
        assert_eq!(df.celula(0, "OPERADORA"), json!("CLARO"));
        assert_eq!(df.celula(0, "NUM_ESTACAO"), json!("1234"));
        let df = etapa_desduplicar(df);
        let df = etapa_preparar_enderecos_coordenadas(df, &mapa);
        let erbs = etapa_agrupar_erbs(df, &mapa);
        // Mossoró 1234 (2 setores) + Natal 5555 (1 setor)
        assert_eq!(erbs.len(), 2);
        let erbs = etapa_normalizar_colunas_extras(erbs);
        let erbs = etapa_extrair_bairros(erbs);
        let erbs = etapa_indexar_endereco_busca(erbs);
        let erbs = etapa_converter_gps(erbs);
        let erbs = etapa_finalizar_identificadores(erbs);
        let erbs = etapa_indexar_busca_global(erbs);

        assert_eq!(erbs.celula(0, "TECS_RAW"), json!("5G,LTE"));
        assert_eq!(erbs.celula(0, "FAIXA_NOMINAL"), json!("3500"));
        assert_eq!(erbs.celula(0, "MUNICIPIO_LIMPO"), json!("MOSSORÓ"));
        assert_eq!(erbs.celula(0, "ID_ERB"), json!("CLARO_1234"));
        let gps = erbs.celula(0, "GPS").as_str().unwrap().to_string();
        assert_eq!(gps, "-5.189000, -37.349000");
        assert!(erbs.colunas.contains(&"__BUSCA_GLOBAL".to_string()));

        let _ = std::fs::remove_dir_all(&dir);
    }

    fn agora_unix_ns() -> u128 {
        SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()
    }

    #[test]
    fn salvar_e_carregar_cache_roundtrip() {
        let dir = std::env::temp_dir().join(format!("torre_anatel_cache_{}", agora_unix_ns()));
        std::fs::create_dir_all(&dir).unwrap();
        std::env::set_var("TORRE_FACIL_DADOS_DIR", &dir);

        let mut df = DataFrame::from_csv_str("UF;MUNICIPIO\nRN;MOSSORO\n").unwrap();
        df.set_coluna("MUNICIPIO_NORM", vec![Cell::String("MOSSORO".into())]);
        let (df2, origem) = atualizar_telemetria_global(df.clone(), 10, "TESTE".into(), Some("01/01/2024".into()));
        assert_eq!(origem, "TESTE");
        assert_eq!(df2.len(), 1);

        // grava cache manualmente no formato do pipeline
        let agora = agora_unix();
        let pacote = serde_json::json!({
            "versao": VERSAO_CACHE,
            "df_erbs": dataframe_para_json(&df),
            "total_setores": 10,
            "bairros_unificados": 3,
            "data_geracao": serde_json::json!(snap_mod::quebrar_local(agora)),
        });
        std::fs::write(arquivo_cache(), pacote.to_string()).unwrap();
        let (carregado, origem) = carregar_do_cache().unwrap();
        assert_eq!(carregado.len(), 1);
        assert!(origem.starts_with("Cache Rápido (há 0d)"));

        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn limpar_arquivos_cache_remove() {
        let dir = std::env::temp_dir().join(format!("torre_anatel_limpa_{}", agora_unix_ns()));
        std::fs::create_dir_all(&dir).unwrap();
        std::env::set_var("TORRE_FACIL_DADOS_DIR", &dir);
        std::fs::write(arquivo_cache(), "x").unwrap();
        std::fs::write(arquivo_csv_extraido(), "x").unwrap();
        std::fs::write(arquivo_cache_bairros(), "{}").unwrap();
        limpar_arquivos_cache(true, true);
        assert!(!arquivo_cache().exists());
        assert!(!arquivo_csv_extraido().exists());
        assert!(!arquivo_cache_bairros().exists());
        let _ = std::fs::remove_dir_all(&dir);
    }
}
