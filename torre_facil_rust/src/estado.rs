//! Estado da sessão e contexto da aplicação.
//!
//! Porta 1:1 de `torre_facil/estado.py`.
//!
//! Define:
//!   - `EstatisticasBase`: contadores e metadados da base carregada.
//!   - `AppContext`: contexto principal passado entre módulos.
//!   - `AbrirMenuOutroModo`: exceção de controle de fluxo (F12) — modelada
//!     como variante de resultado (`TuiOutcome`) em Rust idiomático, mas a
//!     semântica de propagação é a mesma do `raise`/`except` originais.

use std::sync::Mutex;

use crate::dataframe::DataFrame;

// ---------------------------------------------------------------------------
// Exceções de controle de fluxo
// ---------------------------------------------------------------------------

/// Control flow equivalente à exceção Python `AbrirMenuOutroModo`.
///
/// Levantada quando o usuário pressiona F12 para trocar de modo (loja ↔ analista).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct AbrirMenuOutroModo;

/// Resultado padrão das telas da TUI: sucesso com valor, ou pedido de troca de modo.
pub type TelaResult<T> = Result<T, AbrirMenuOutroModo>;

// ---------------------------------------------------------------------------
// Estatísticas da base
// ---------------------------------------------------------------------------

/// Contadores e metadados da base de estações carregada.
#[derive(Debug, Clone)]
pub struct EstatisticasBase {
    pub ufs: i64,
    pub municipios: i64,
    pub erbs: i64,
    pub setores: i64,
    pub bairros_unificados: i64,
    pub data_atualizacao: String,
    pub origem: String,
    pub podio_completo: Vec<String>,
    pub podio_contexto: String,
    pub modulo_atual: String,
    pub ultimo_erro: String,
    pub base: Option<DataFrame>,
}

impl Default for EstatisticasBase {
    fn default() -> Self {
        Self {
            ufs: 0,
            municipios: 0,
            erbs: 0,
            setores: 0,
            bairros_unificados: 0,
            data_atualizacao: "N/D".into(),
            origem: "AGUARDANDO CARGA...".into(),
            podio_completo: Vec::new(),
            podio_contexto: String::new(),
            modulo_atual: "INICIALIZAÇÃO".into(),
            ultimo_erro: String::new(),
            base: None,
        }
    }
}

/// Formata inteiro com separador de milhar '.' (estilo pt-BR: f"{n:,}".replace(",", ".")).
pub fn formatar_milhar(n: i64) -> String {
    let digits = n.abs().to_string();
    let mut partes: Vec<String> = Vec::new();
    let bytes: Vec<char> = digits.chars().collect();
    let inicio = bytes.len() % 3;
    let inicio = if inicio == 0 && !bytes.is_empty() { 3 } else { inicio };
    if inicio > 0 {
        partes.push(bytes[..inicio].iter().collect());
    }
    let mut i = inicio;
    while i < bytes.len() {
        partes.push(bytes[i..i + 3].iter().collect());
        i += 3;
    }
    let sep = partes.join(".");
    if n < 0 {
        format!("-{sep}")
    } else {
        sep
    }
}

impl EstatisticasBase {
    /// Retorna resumo legível das estatísticas para exibição na TUI.
    pub fn resumo_formatado(&self) -> String {
        format!(
            "UFs: {} | Municípios: {} | ERBs: {} | Setores: {} | Bairros: {}",
            formatar_milhar(self.ufs),
            formatar_milhar(self.municipios),
            formatar_milhar(self.erbs),
            formatar_milhar(self.setores),
            formatar_milhar(self.bairros_unificados),
        )
    }
}

// ---------------------------------------------------------------------------
// Contexto da aplicação
// ---------------------------------------------------------------------------

/// Contexto principal da aplicação, passado entre todos os módulos.
#[derive(Debug, Clone)]
pub struct AppContext {
    pub df_erbs: DataFrame,
    pub resumo_status: String,
    pub modo: String,
    pub stats: EstatisticasBase,
    pub modulo_atual: String,
}

impl AppContext {
    /// Constrói o contexto validando o modo (`__post_init__` do dataclass).
    ///
    /// Panics com a mesma mensagem do ValueError original se modo inválido.
    pub fn novo(df_erbs: DataFrame, resumo_status: &str, modo: &str) -> Self {
        assert!(
            modo == "loja" || modo == "analista",
            "Modo inválido: '{modo}'. Use 'loja' ou 'analista'."
        );
        Self {
            df_erbs,
            resumo_status: resumo_status.to_string(),
            modo: modo.to_string(),
            stats: EstatisticasBase::default(),
            modulo_atual: "INICIALIZAÇÃO".into(),
        }
    }

    /// Alterna entre modo loja e analista. Retorna o novo modo.
    pub fn alternar_modo(&mut self) -> String {
        self.modo = if self.modo == "loja" {
            "analista".into()
        } else {
            "loja".into()
        };
        log_info(&format!("Modo alternado para '{}'.", self.modo));
        self.modo.clone()
    }

    /// Atualiza estatísticas da base de forma parcial (None = mantém valor).
    #[allow(clippy::too_many_arguments)]
    pub fn atualizar_stats(
        &mut self,
        ufs: Option<i64>,
        municipios: Option<i64>,
        erbs: Option<i64>,
        setores: Option<i64>,
        bairros_unificados: Option<i64>,
        data_atualizacao: Option<&str>,
        origem: Option<&str>,
    ) {
        if let Some(v) = ufs {
            self.stats.ufs = v;
        }
        if let Some(v) = municipios {
            self.stats.municipios = v;
        }
        if let Some(v) = erbs {
            self.stats.erbs = v;
        }
        if let Some(v) = setores {
            self.stats.setores = v;
        }
        if let Some(v) = bairros_unificados {
            self.stats.bairros_unificados = v;
        }
        if let Some(v) = data_atualizacao {
            self.stats.data_atualizacao = v.to_string();
        }
        if let Some(v) = origem {
            self.stats.origem = v.to_string();
        }
    }
}

fn log_info(msg: &str) {
    eprintln!("[INFO] estado: {msg}");
}

// ---------------------------------------------------------------------------
// Registro central do contexto da aplicação (substitui estado global legado)
// ---------------------------------------------------------------------------

static CTX_ATIVO: Mutex<Option<AppContext>> = Mutex::new(None);
/// ``EstadoSistema`` é o nome histórico da classe de estado global; hoje os
/// campos vivem em ``EstatisticasBase``. Prefira ``AppContext`` em código novo.
static INFO: Mutex<EstatisticasBase> = Mutex::new(EstatisticasBase {
    ufs: 0,
    municipios: 0,
    erbs: 0,
    setores: 0,
    bairros_unificados: 0,
    data_atualizacao: String::new(),
    origem: String::new(),
    podio_completo: Vec::new(),
    podio_contexto: String::new(),
    modulo_atual: String::new(),
    ultimo_erro: String::new(),
    base: None,
});

/// Registra o `AppContext` ativo da aplicação.
///
/// Deve ser chamado uma única vez, logo após o carregamento da base, e sempre
/// que a base for recarregada/substituída. Espelha as estatísticas no estado
/// legado (INFO) para telas antigas.
pub fn definir_contexto(ctx: Option<AppContext>) {
    let mut g = CTX_ATIVO.lock().unwrap();
    *g = ctx.clone();
    drop(g);
    if let Some(ctx) = ctx {
        let st = ctx.stats;
        let mut info = INFO.lock().unwrap();
        info.ufs = st.ufs;
        info.municipios = st.municipios;
        info.erbs = st.erbs;
        info.setores = st.setores;
        info.bairros_unificados = st.bairros_unificados;
        info.data_atualizacao = st.data_atualizacao;
        info.origem = st.origem;
        info.podio_completo = st.podio_completo;
        info.podio_contexto = st.podio_contexto;
        info.base = Some(ctx.df_erbs.clone());
        drop(info);
        log_info("Contexto da aplicação registrado (AppContext ativo).");
    }
}

/// Retorna o `AppContext` ativo, ou None se ainda não definido.
pub fn obter_contexto() -> Option<AppContext> {
    CTX_ATIVO.lock().unwrap().clone()
}

/// Retorna `ctx.df_erbs` do contexto ativo (ou fallback INFO.base legado).
pub fn base_do_contexto() -> Option<DataFrame> {
    if let Some(ctx) = obter_contexto() {
        // Em Python: `ctx.df_erbs is not None` — aqui o DataFrame pode estar vazio.
        return Some(ctx.df_erbs.clone());
    }
    INFO.lock().unwrap().base.clone()
}

// ---------------------------------------------------------------------------
// Compatibilidade com código legado (shims)
// ---------------------------------------------------------------------------

/// Atualiza a base do contexto ativo (shim de compatibilidade).
pub fn definir_base_global(df_erbs: DataFrame) {
    {
        let mut g = CTX_ATIVO.lock().unwrap();
        if let Some(ctx) = g.as_mut() {
            ctx.df_erbs = df_erbs.clone();
        }
    }
    INFO.lock().unwrap().base = Some(df_erbs);
    // Equivalente ao import dinâmico com try/except ImportError do Python.
    crate::pesquisa_global::invalidar_cache_pesquisa();
}

/// Retorna a base de estações (shim de compatibilidade).
pub fn obter_base_global() -> Option<DataFrame> {
    base_do_contexto()
}

/// Acesso ao estado legado INFO (equivalente ao objeto módulo-level).
pub fn info_snapshot() -> EstatisticasBase {
    INFO.lock().unwrap().clone()
}

/// Substitui o conteúdo do estado legado INFO (`INFO.<campo> = ...` em bloco).
pub fn definir_info(novo: EstatisticasBase) {
    let mut info = INFO.lock().unwrap();
    let base_preservada = info.base.take();
    *info = novo;
    if info.base.is_none() {
        info.base = base_preservada;
    }
}

/// `INFO.bairros_unificados = v`
pub fn info_set_bairros_unificados(v: i64) {
    INFO.lock().unwrap().bairros_unificados = v;
}

/// `v = INFO.bairros_unificados`
pub fn info_bairros_unificados() -> i64 {
    INFO.lock().unwrap().bairros_unificados
}

/// `INFO.data_atualizacao = v`
pub fn info_set_data_atualizacao(v: &str) {
    INFO.lock().unwrap().data_atualizacao = v.to_string();
}

/// `INFO.ultimo_erro = v`
pub fn info_set_ultimo_erro(v: &str) {
    INFO.lock().unwrap().ultimo_erro = v.to_string();
}

/// `INFO.modulo_atual = v`
pub fn info_set_modulo_atual(v: &str) {
    INFO.lock().unwrap().modulo_atual = v.to_string();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn milhar_ptbr() {
        assert_eq!(formatar_milhar(1234567), "1.234.567");
        assert_eq!(formatar_milhar(999), "999");
        assert_eq!(formatar_milhar(0), "0");
    }

    #[test]
    fn resumo_formatado_doc() {
        let mut st = EstatisticasBase::default();
        st.ufs = 27;
        st.municipios = 5570;
        st.erbs = 123456;
        st.setores = 300000;
        st.bairros_unificados = 10000;
        assert_eq!(
            st.resumo_formatado(),
            "UFs: 27 | Municípios: 5.570 | ERBs: 123.456 | Setores: 300.000 | Bairros: 10.000"
        );
    }

    #[test]
    fn alternar_modo() {
        let mut ctx = AppContext::novo(DataFrame::new(), "ok", "analista");
        assert_eq!(ctx.alternar_modo(), "loja");
        assert_eq!(ctx.alternar_modo(), "analista");
    }

    #[test]
    #[should_panic(expected = "Modo inválido")]
    fn modo_invalido() {
        AppContext::novo(DataFrame::new(), "ok", "outro");
    }

    #[test]
    fn contexto_global() {
        let mut ctx = AppContext::novo(DataFrame::new(), "ok", "loja");
        ctx.stats.erbs = 42;
        definir_contexto(Some(ctx));
        assert_eq!(obter_contexto().unwrap().stats.erbs, 42);
        assert_eq!(info_snapshot().erbs, 42);
        definir_contexto(None);
        assert!(obter_contexto().is_none());
    }
}
