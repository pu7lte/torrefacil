//! Porta 1:1 de `torre_facil/tui/cores.py` - paleta ANSI 256 com 8 temas retro.
//!
//! No Python, `aplicar_paleta` sobrescreve variaveis globais do modulo
//! (`CAIXA_TEXTO`, `BARRA_STATUS_TOPO`, ...). Em Rust isso e modelado como um
//! mapa global atualizado por [`aplicar_paleta`] e lido por [`chave`]; o valor
//! inicial corresponde a `aplicar_paleta("classic")` feito no import original.

use std::collections::{BTreeMap, BTreeSet};
use std::sync::{Mutex, OnceLock};

/// Constantes que NAO mudam com a paleta.
pub const RESET: &str = "\u{1b}[0m";
pub const NEGRITO: &str = "\u{1b}[1m";
pub const CIANO: &str = "\u{1b}[38;5;51m";

/// Chaves obrigatorias em todas as paletas (frozenset `_CHAVES_OBRIGATORIAS`).
pub const CHAVES_OBRIGATORIAS: [&str; 40] = [
    "label",
    "BARRA_STATUS_TOPO",
    "BARRA_SUB_TOPO",
    "FUNDO_DESKTOP",
    "CAIXA_BORDA",
    "CAIXA_TITULO",
    "CAIXA_TEXTO",
    "CAIXA_CIANO",
    "CAIXA_VERDE",
    "CAIXA_AMARELO",
    "CAIXA_SELECAO",
    "CAIXA_BOTAO_ATIVO",
    "CAIXA_BOTAO_INATIVO",
    "CAIXA_CAMPO_ATIVO",
    "CAIXA_CAMPO_INATIVO",
    "BARRA_ALERTA",
    "BARRA_VERDE",
    "BARRA_ERRO",
    "SOMBRA_3D",
    "DROPLIST_BORDA",
    "DROPLIST_ITEM",
    "DROPLIST_SEL",
    "COR_OURO",
    "COR_PRATA",
    "COR_BRONZE",
    "COR_DEMAIS",
    "MENU_BARRA",
    "MENU_BARRA_HOT",
    "MENU_BARRA_ATIVO",
    "MENU_BARRA_ATIVO_HOT",
    "MENU_ITEM",
    "MENU_ITEM_HOT",
    "MENU_ITEM_SEL",
    "MENU_ITEM_SEL_HOT",
    "MENU_ITEM_OFF",
    "MENU_BORDA",
    "LOGO_AZUL",
    "LOGO_CIANO",
    "LOGO_CINZA",
    "LOGO_VERDE",
];

/// Ordem de exibicao no seletor (`ORDEM_PALETAS`).
pub const ORDEM_PALETAS: [&str; 8] = ["classic", "norton", "turbo", "dos_azul", "dos_cinza", "verde", "ambar", "claro"];

/// Dicionario com todas as paletas disponiveis (`PALETAS`).
///
/// Nome da paleta -> (chave -> valor ANSI). A chave especial `"label"` traz o
/// nome legivel do tema e nao vira variavel de cor.
pub fn paletas() -> &'static BTreeMap<String, BTreeMap<String, String>> {
    static P: OnceLock<BTreeMap<String, BTreeMap<String, String>>> = OnceLock::new();
    P.get_or_init(|| {
        let mut m: BTreeMap<String, BTreeMap<String, String>> = BTreeMap::new();
        { // paleta "classic"
            let mut q = BTreeMap::new();
            q.insert("label".to_string(), "Classic ERP (azul-noite + cinza claro)".to_string());
            q.insert("BARRA_STATUS_TOPO".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("BARRA_SUB_TOPO".to_string(), "\u{1b}[1;38;5;231;48;5;24m".to_string());
            q.insert("FUNDO_DESKTOP".to_string(), "\u{1b}[38;5;252;48;5;17m".to_string());
            q.insert("CAIXA_BORDA".to_string(), "\u{1b}[1;38;5;252;48;5;17m".to_string());
            q.insert("CAIXA_TITULO".to_string(), "\u{1b}[1;38;5;231;48;5;17m".to_string());
            q.insert("CAIXA_TEXTO".to_string(), "\u{1b}[38;5;253;48;5;17m".to_string());
            q.insert("CAIXA_CIANO".to_string(), "\u{1b}[1;38;5;159;48;5;17m".to_string());
            q.insert("CAIXA_VERDE".to_string(), "\u{1b}[1;38;5;120;48;5;17m".to_string());
            q.insert("CAIXA_AMARELO".to_string(), "\u{1b}[1;38;5;227;48;5;17m".to_string());
            q.insert("CAIXA_SELECAO".to_string(), "\u{1b}[1;38;5;232;48;5;250m".to_string());
            q.insert("CAIXA_BOTAO_ATIVO".to_string(), "\u{1b}[1;38;5;232;48;5;255m".to_string());
            q.insert("CAIXA_BOTAO_INATIVO".to_string(), "\u{1b}[38;5;250;48;5;238m".to_string());
            q.insert("CAIXA_CAMPO_ATIVO".to_string(), "\u{1b}[1;38;5;232;48;5;250m".to_string());
            q.insert("CAIXA_CAMPO_INATIVO".to_string(), "\u{1b}[38;5;250;48;5;236m".to_string());
            q.insert("BARRA_ALERTA".to_string(), "\u{1b}[1;38;5;232;48;5;222m".to_string());
            q.insert("BARRA_VERDE".to_string(), "\u{1b}[1;38;5;232;48;5;120m".to_string());
            q.insert("BARRA_ERRO".to_string(), "\u{1b}[1;38;5;231;48;5;124m".to_string());
            q.insert("SOMBRA_3D".to_string(), "\u{1b}[38;5;236;48;5;236m".to_string());
            q.insert("DROPLIST_BORDA".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("DROPLIST_ITEM".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("DROPLIST_SEL".to_string(), "\u{1b}[1;38;5;231;48;5;24m".to_string());
            q.insert("COR_OURO".to_string(), "\u{1b}[1;38;5;220;48;5;17m".to_string());
            q.insert("COR_PRATA".to_string(), "\u{1b}[1;38;5;253;48;5;17m".to_string());
            q.insert("COR_BRONZE".to_string(), "\u{1b}[1;38;5;215;48;5;17m".to_string());
            q.insert("COR_DEMAIS".to_string(), "\u{1b}[38;5;250;48;5;17m".to_string());
            q.insert("MENU_BARRA".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("MENU_BARRA_HOT".to_string(), "\u{1b}[1;4;38;5;24;48;5;250m".to_string());
            q.insert("MENU_BARRA_ATIVO".to_string(), "\u{1b}[1;38;5;231;48;5;232m".to_string());
            q.insert("MENU_BARRA_ATIVO_HOT".to_string(), "\u{1b}[1;4;38;5;231;48;5;232m".to_string());
            q.insert("MENU_ITEM".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("MENU_ITEM_HOT".to_string(), "\u{1b}[1;4;38;5;24;48;5;250m".to_string());
            q.insert("MENU_ITEM_SEL".to_string(), "\u{1b}[1;38;5;231;48;5;232m".to_string());
            q.insert("MENU_ITEM_SEL_HOT".to_string(), "\u{1b}[1;4;38;5;231;48;5;232m".to_string());
            q.insert("MENU_ITEM_OFF".to_string(), "\u{1b}[38;5;245;48;5;250m".to_string());
            q.insert("MENU_BORDA".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("LOGO_AZUL".to_string(), "\u{1b}[1;38;5;117;48;5;17m".to_string());
            q.insert("LOGO_CIANO".to_string(), "\u{1b}[1;38;5;159;48;5;17m".to_string());
            q.insert("LOGO_CINZA".to_string(), "\u{1b}[38;5;245;48;5;17m".to_string());
            q.insert("LOGO_VERDE".to_string(), "\u{1b}[1;38;5;120;48;5;17m".to_string());
            m.insert("classic".to_string(), q);
        }
        { // paleta "norton"
            let mut q = BTreeMap::new();
            q.insert("label".to_string(), "Norton Commander (azul forte + ciano)".to_string());
            q.insert("BARRA_STATUS_TOPO".to_string(), "\u{1b}[1;38;5;231;48;5;25m".to_string());
            q.insert("BARRA_SUB_TOPO".to_string(), "\u{1b}[1;38;5;231;48;5;24m".to_string());
            q.insert("FUNDO_DESKTOP".to_string(), "\u{1b}[38;5;253;48;5;17m".to_string());
            q.insert("CAIXA_BORDA".to_string(), "\u{1b}[1;38;5;51;48;5;17m".to_string());
            q.insert("CAIXA_TITULO".to_string(), "\u{1b}[1;38;5;231;48;5;17m".to_string());
            q.insert("CAIXA_TEXTO".to_string(), "\u{1b}[38;5;253;48;5;17m".to_string());
            q.insert("CAIXA_CIANO".to_string(), "\u{1b}[1;38;5;51;48;5;17m".to_string());
            q.insert("CAIXA_VERDE".to_string(), "\u{1b}[1;38;5;120;48;5;17m".to_string());
            q.insert("CAIXA_AMARELO".to_string(), "\u{1b}[1;38;5;227;48;5;17m".to_string());
            q.insert("CAIXA_SELECAO".to_string(), "\u{1b}[1;38;5;232;48;5;51m".to_string());
            q.insert("CAIXA_BOTAO_ATIVO".to_string(), "\u{1b}[1;38;5;232;48;5;51m".to_string());
            q.insert("CAIXA_BOTAO_INATIVO".to_string(), "\u{1b}[38;5;51;48;5;17m".to_string());
            q.insert("CAIXA_CAMPO_ATIVO".to_string(), "\u{1b}[1;38;5;232;48;5;51m".to_string());
            q.insert("CAIXA_CAMPO_INATIVO".to_string(), "\u{1b}[38;5;51;48;5;17m".to_string());
            q.insert("BARRA_ALERTA".to_string(), "\u{1b}[1;38;5;232;48;5;227m".to_string());
            q.insert("BARRA_VERDE".to_string(), "\u{1b}[1;38;5;232;48;5;120m".to_string());
            q.insert("BARRA_ERRO".to_string(), "\u{1b}[1;38;5;231;48;5;124m".to_string());
            q.insert("SOMBRA_3D".to_string(), "\u{1b}[38;5;236;48;5;236m".to_string());
            q.insert("DROPLIST_BORDA".to_string(), "\u{1b}[38;5;232;48;5;51m".to_string());
            q.insert("DROPLIST_ITEM".to_string(), "\u{1b}[38;5;232;48;5;51m".to_string());
            q.insert("DROPLIST_SEL".to_string(), "\u{1b}[1;38;5;231;48;5;24m".to_string());
            q.insert("COR_OURO".to_string(), "\u{1b}[1;38;5;227;48;5;17m".to_string());
            q.insert("COR_PRATA".to_string(), "\u{1b}[1;38;5;231;48;5;17m".to_string());
            q.insert("COR_BRONZE".to_string(), "\u{1b}[1;38;5;215;48;5;17m".to_string());
            q.insert("COR_DEMAIS".to_string(), "\u{1b}[38;5;51;48;5;17m".to_string());
            q.insert("MENU_BARRA".to_string(), "\u{1b}[1;38;5;231;48;5;25m".to_string());
            q.insert("MENU_BARRA_HOT".to_string(), "\u{1b}[1;4;38;5;227;48;5;25m".to_string());
            q.insert("MENU_BARRA_ATIVO".to_string(), "\u{1b}[1;38;5;232;48;5;51m".to_string());
            q.insert("MENU_BARRA_ATIVO_HOT".to_string(), "\u{1b}[1;4;38;5;232;48;5;51m".to_string());
            q.insert("MENU_ITEM".to_string(), "\u{1b}[38;5;253;48;5;17m".to_string());
            q.insert("MENU_ITEM_HOT".to_string(), "\u{1b}[1;4;38;5;227;48;5;17m".to_string());
            q.insert("MENU_ITEM_SEL".to_string(), "\u{1b}[1;38;5;232;48;5;51m".to_string());
            q.insert("MENU_ITEM_SEL_HOT".to_string(), "\u{1b}[1;4;38;5;232;48;5;51m".to_string());
            q.insert("MENU_ITEM_OFF".to_string(), "\u{1b}[38;5;245;48;5;17m".to_string());
            q.insert("MENU_BORDA".to_string(), "\u{1b}[38;5;51;48;5;17m".to_string());
            q.insert("LOGO_AZUL".to_string(), "\u{1b}[1;38;5;51;48;5;17m".to_string());
            q.insert("LOGO_CIANO".to_string(), "\u{1b}[1;38;5;231;48;5;17m".to_string());
            q.insert("LOGO_CINZA".to_string(), "\u{1b}[38;5;245;48;5;17m".to_string());
            q.insert("LOGO_VERDE".to_string(), "\u{1b}[1;38;5;120;48;5;17m".to_string());
            m.insert("norton".to_string(), q);
        }
        { // paleta "turbo"
            let mut q = BTreeMap::new();
            q.insert("label".to_string(), "Turbo Vision / Borland (azul acinzentado)".to_string());
            q.insert("BARRA_STATUS_TOPO".to_string(), "\u{1b}[1;38;5;232;48;5;250m".to_string());
            q.insert("BARRA_SUB_TOPO".to_string(), "\u{1b}[1;38;5;231;48;5;24m".to_string());
            q.insert("FUNDO_DESKTOP".to_string(), "\u{1b}[38;5;250;48;5;24m".to_string());
            q.insert("CAIXA_BORDA".to_string(), "\u{1b}[1;38;5;231;48;5;24m".to_string());
            q.insert("CAIXA_TITULO".to_string(), "\u{1b}[1;38;5;231;48;5;24m".to_string());
            q.insert("CAIXA_TEXTO".to_string(), "\u{1b}[38;5;253;48;5;24m".to_string());
            q.insert("CAIXA_CIANO".to_string(), "\u{1b}[1;38;5;159;48;5;24m".to_string());
            q.insert("CAIXA_VERDE".to_string(), "\u{1b}[1;38;5;120;48;5;24m".to_string());
            q.insert("CAIXA_AMARELO".to_string(), "\u{1b}[1;38;5;227;48;5;24m".to_string());
            q.insert("CAIXA_SELECAO".to_string(), "\u{1b}[1;38;5;232;48;5;250m".to_string());
            q.insert("CAIXA_BOTAO_ATIVO".to_string(), "\u{1b}[1;38;5;232;48;5;231m".to_string());
            q.insert("CAIXA_BOTAO_INATIVO".to_string(), "\u{1b}[38;5;250;48;5;238m".to_string());
            q.insert("CAIXA_CAMPO_ATIVO".to_string(), "\u{1b}[1;38;5;232;48;5;250m".to_string());
            q.insert("CAIXA_CAMPO_INATIVO".to_string(), "\u{1b}[38;5;250;48;5;238m".to_string());
            q.insert("BARRA_ALERTA".to_string(), "\u{1b}[1;38;5;232;48;5;222m".to_string());
            q.insert("BARRA_VERDE".to_string(), "\u{1b}[1;38;5;232;48;5;120m".to_string());
            q.insert("BARRA_ERRO".to_string(), "\u{1b}[1;38;5;231;48;5;124m".to_string());
            q.insert("SOMBRA_3D".to_string(), "\u{1b}[38;5;236;48;5;236m".to_string());
            q.insert("DROPLIST_BORDA".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("DROPLIST_ITEM".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("DROPLIST_SEL".to_string(), "\u{1b}[1;38;5;231;48;5;24m".to_string());
            q.insert("COR_OURO".to_string(), "\u{1b}[1;38;5;220;48;5;24m".to_string());
            q.insert("COR_PRATA".to_string(), "\u{1b}[1;38;5;253;48;5;24m".to_string());
            q.insert("COR_BRONZE".to_string(), "\u{1b}[1;38;5;215;48;5;24m".to_string());
            q.insert("COR_DEMAIS".to_string(), "\u{1b}[38;5;250;48;5;24m".to_string());
            q.insert("MENU_BARRA".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("MENU_BARRA_HOT".to_string(), "\u{1b}[1;4;38;5;24;48;5;250m".to_string());
            q.insert("MENU_BARRA_ATIVO".to_string(), "\u{1b}[1;38;5;231;48;5;232m".to_string());
            q.insert("MENU_BARRA_ATIVO_HOT".to_string(), "\u{1b}[1;4;38;5;231;48;5;232m".to_string());
            q.insert("MENU_ITEM".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("MENU_ITEM_HOT".to_string(), "\u{1b}[1;4;38;5;24;48;5;250m".to_string());
            q.insert("MENU_ITEM_SEL".to_string(), "\u{1b}[1;38;5;231;48;5;232m".to_string());
            q.insert("MENU_ITEM_SEL_HOT".to_string(), "\u{1b}[1;4;38;5;231;48;5;232m".to_string());
            q.insert("MENU_ITEM_OFF".to_string(), "\u{1b}[38;5;245;48;5;250m".to_string());
            q.insert("MENU_BORDA".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("LOGO_AZUL".to_string(), "\u{1b}[1;38;5;231;48;5;24m".to_string());
            q.insert("LOGO_CIANO".to_string(), "\u{1b}[1;38;5;159;48;5;24m".to_string());
            q.insert("LOGO_CINZA".to_string(), "\u{1b}[38;5;250;48;5;24m".to_string());
            q.insert("LOGO_VERDE".to_string(), "\u{1b}[1;38;5;120;48;5;24m".to_string());
            m.insert("turbo".to_string(), q);
        }
        { // paleta "dos_azul"
            let mut q = BTreeMap::new();
            q.insert("label".to_string(), "DOS Azul (fundo azul, texto branco)".to_string());
            q.insert("BARRA_STATUS_TOPO".to_string(), "\u{1b}[1;38;5;232;48;5;250m".to_string());
            q.insert("BARRA_SUB_TOPO".to_string(), "\u{1b}[1;38;5;231;48;5;18m".to_string());
            q.insert("FUNDO_DESKTOP".to_string(), "\u{1b}[38;5;253;48;5;18m".to_string());
            q.insert("CAIXA_BORDA".to_string(), "\u{1b}[1;38;5;231;48;5;18m".to_string());
            q.insert("CAIXA_TITULO".to_string(), "\u{1b}[1;38;5;231;48;5;18m".to_string());
            q.insert("CAIXA_TEXTO".to_string(), "\u{1b}[38;5;253;48;5;18m".to_string());
            q.insert("CAIXA_CIANO".to_string(), "\u{1b}[1;38;5;51;48;5;18m".to_string());
            q.insert("CAIXA_VERDE".to_string(), "\u{1b}[1;38;5;120;48;5;18m".to_string());
            q.insert("CAIXA_AMARELO".to_string(), "\u{1b}[1;38;5;227;48;5;18m".to_string());
            q.insert("CAIXA_SELECAO".to_string(), "\u{1b}[1;38;5;232;48;5;250m".to_string());
            q.insert("CAIXA_BOTAO_ATIVO".to_string(), "\u{1b}[1;38;5;232;48;5;250m".to_string());
            q.insert("CAIXA_BOTAO_INATIVO".to_string(), "\u{1b}[38;5;250;48;5;18m".to_string());
            q.insert("CAIXA_CAMPO_ATIVO".to_string(), "\u{1b}[1;38;5;232;48;5;250m".to_string());
            q.insert("CAIXA_CAMPO_INATIVO".to_string(), "\u{1b}[38;5;250;48;5;18m".to_string());
            q.insert("BARRA_ALERTA".to_string(), "\u{1b}[1;38;5;232;48;5;222m".to_string());
            q.insert("BARRA_VERDE".to_string(), "\u{1b}[1;38;5;232;48;5;120m".to_string());
            q.insert("BARRA_ERRO".to_string(), "\u{1b}[1;38;5;231;48;5;124m".to_string());
            q.insert("SOMBRA_3D".to_string(), "\u{1b}[38;5;236;48;5;236m".to_string());
            q.insert("DROPLIST_BORDA".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("DROPLIST_ITEM".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("DROPLIST_SEL".to_string(), "\u{1b}[1;38;5;231;48;5;18m".to_string());
            q.insert("COR_OURO".to_string(), "\u{1b}[1;38;5;220;48;5;18m".to_string());
            q.insert("COR_PRATA".to_string(), "\u{1b}[1;38;5;231;48;5;18m".to_string());
            q.insert("COR_BRONZE".to_string(), "\u{1b}[1;38;5;215;48;5;18m".to_string());
            q.insert("COR_DEMAIS".to_string(), "\u{1b}[38;5;250;48;5;18m".to_string());
            q.insert("MENU_BARRA".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("MENU_BARRA_HOT".to_string(), "\u{1b}[1;4;38;5;18;48;5;250m".to_string());
            q.insert("MENU_BARRA_ATIVO".to_string(), "\u{1b}[1;38;5;231;48;5;232m".to_string());
            q.insert("MENU_BARRA_ATIVO_HOT".to_string(), "\u{1b}[1;4;38;5;231;48;5;232m".to_string());
            q.insert("MENU_ITEM".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("MENU_ITEM_HOT".to_string(), "\u{1b}[1;4;38;5;18;48;5;250m".to_string());
            q.insert("MENU_ITEM_SEL".to_string(), "\u{1b}[1;38;5;231;48;5;232m".to_string());
            q.insert("MENU_ITEM_SEL_HOT".to_string(), "\u{1b}[1;4;38;5;231;48;5;232m".to_string());
            q.insert("MENU_ITEM_OFF".to_string(), "\u{1b}[38;5;245;48;5;250m".to_string());
            q.insert("MENU_BORDA".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("LOGO_AZUL".to_string(), "\u{1b}[1;38;5;51;48;5;18m".to_string());
            q.insert("LOGO_CIANO".to_string(), "\u{1b}[1;38;5;231;48;5;18m".to_string());
            q.insert("LOGO_CINZA".to_string(), "\u{1b}[38;5;250;48;5;18m".to_string());
            q.insert("LOGO_VERDE".to_string(), "\u{1b}[1;38;5;120;48;5;18m".to_string());
            m.insert("dos_azul".to_string(), q);
        }
        { // paleta "dos_cinza"
            let mut q = BTreeMap::new();
            q.insert("label".to_string(), "DOS Cinza / Clipper (cinza claro + preto)".to_string());
            q.insert("BARRA_STATUS_TOPO".to_string(), "\u{1b}[1;38;5;232;48;5;250m".to_string());
            q.insert("BARRA_SUB_TOPO".to_string(), "\u{1b}[1;38;5;231;48;5;232m".to_string());
            q.insert("FUNDO_DESKTOP".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("CAIXA_BORDA".to_string(), "\u{1b}[1;38;5;232;48;5;250m".to_string());
            q.insert("CAIXA_TITULO".to_string(), "\u{1b}[1;38;5;231;48;5;232m".to_string());
            q.insert("CAIXA_TEXTO".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("CAIXA_CIANO".to_string(), "\u{1b}[1;38;5;18;48;5;250m".to_string());
            q.insert("CAIXA_VERDE".to_string(), "\u{1b}[1;38;5;22;48;5;250m".to_string());
            q.insert("CAIXA_AMARELO".to_string(), "\u{1b}[1;38;5;130;48;5;250m".to_string());
            q.insert("CAIXA_SELECAO".to_string(), "\u{1b}[1;38;5;231;48;5;232m".to_string());
            q.insert("CAIXA_BOTAO_ATIVO".to_string(), "\u{1b}[1;38;5;231;48;5;232m".to_string());
            q.insert("CAIXA_BOTAO_INATIVO".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("CAIXA_CAMPO_ATIVO".to_string(), "\u{1b}[1;38;5;231;48;5;18m".to_string());
            q.insert("CAIXA_CAMPO_INATIVO".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("BARRA_ALERTA".to_string(), "\u{1b}[1;38;5;232;48;5;222m".to_string());
            q.insert("BARRA_VERDE".to_string(), "\u{1b}[1;38;5;232;48;5;120m".to_string());
            q.insert("BARRA_ERRO".to_string(), "\u{1b}[1;38;5;231;48;5;124m".to_string());
            q.insert("SOMBRA_3D".to_string(), "\u{1b}[38;5;240;48;5;240m".to_string());
            q.insert("DROPLIST_BORDA".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("DROPLIST_ITEM".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("DROPLIST_SEL".to_string(), "\u{1b}[1;38;5;231;48;5;18m".to_string());
            q.insert("COR_OURO".to_string(), "\u{1b}[1;38;5;130;48;5;250m".to_string());
            q.insert("COR_PRATA".to_string(), "\u{1b}[1;38;5;232;48;5;250m".to_string());
            q.insert("COR_BRONZE".to_string(), "\u{1b}[1;38;5;94;48;5;250m".to_string());
            q.insert("COR_DEMAIS".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("MENU_BARRA".to_string(), "\u{1b}[1;38;5;231;48;5;232m".to_string());
            q.insert("MENU_BARRA_HOT".to_string(), "\u{1b}[1;4;38;5;250;48;5;232m".to_string());
            q.insert("MENU_BARRA_ATIVO".to_string(), "\u{1b}[1;38;5;231;48;5;18m".to_string());
            q.insert("MENU_BARRA_ATIVO_HOT".to_string(), "\u{1b}[1;4;38;5;231;48;5;18m".to_string());
            q.insert("MENU_ITEM".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("MENU_ITEM_HOT".to_string(), "\u{1b}[1;4;38;5;18;48;5;250m".to_string());
            q.insert("MENU_ITEM_SEL".to_string(), "\u{1b}[1;38;5;231;48;5;18m".to_string());
            q.insert("MENU_ITEM_SEL_HOT".to_string(), "\u{1b}[1;4;38;5;231;48;5;18m".to_string());
            q.insert("MENU_ITEM_OFF".to_string(), "\u{1b}[38;5;245;48;5;250m".to_string());
            q.insert("MENU_BORDA".to_string(), "\u{1b}[38;5;232;48;5;250m".to_string());
            q.insert("LOGO_AZUL".to_string(), "\u{1b}[1;38;5;18;48;5;250m".to_string());
            q.insert("LOGO_CIANO".to_string(), "\u{1b}[1;38;5;232;48;5;250m".to_string());
            q.insert("LOGO_CINZA".to_string(), "\u{1b}[38;5;240;48;5;250m".to_string());
            q.insert("LOGO_VERDE".to_string(), "\u{1b}[1;38;5;22;48;5;250m".to_string());
            m.insert("dos_cinza".to_string(), q);
        }
        { // paleta "verde"
            let mut q = BTreeMap::new();
            q.insert("label".to_string(), "Terminal Verde (fósforo P1)".to_string());
            q.insert("BARRA_STATUS_TOPO".to_string(), "\u{1b}[1;38;5;16;48;5;118m".to_string());
            q.insert("BARRA_SUB_TOPO".to_string(), "\u{1b}[1;38;5;118;48;5;16m".to_string());
            q.insert("FUNDO_DESKTOP".to_string(), "\u{1b}[38;5;118;48;5;16m".to_string());
            q.insert("CAIXA_BORDA".to_string(), "\u{1b}[1;38;5;118;48;5;16m".to_string());
            q.insert("CAIXA_TITULO".to_string(), "\u{1b}[1;38;5;231;48;5;16m".to_string());
            q.insert("CAIXA_TEXTO".to_string(), "\u{1b}[38;5;118;48;5;16m".to_string());
            q.insert("CAIXA_CIANO".to_string(), "\u{1b}[1;38;5;156;48;5;16m".to_string());
            q.insert("CAIXA_VERDE".to_string(), "\u{1b}[1;38;5;231;48;5;16m".to_string());
            q.insert("CAIXA_AMARELO".to_string(), "\u{1b}[1;38;5;190;48;5;16m".to_string());
            q.insert("CAIXA_SELECAO".to_string(), "\u{1b}[1;38;5;16;48;5;118m".to_string());
            q.insert("CAIXA_BOTAO_ATIVO".to_string(), "\u{1b}[1;38;5;16;48;5;118m".to_string());
            q.insert("CAIXA_BOTAO_INATIVO".to_string(), "\u{1b}[38;5;22;48;5;16m".to_string());
            q.insert("CAIXA_CAMPO_ATIVO".to_string(), "\u{1b}[1;38;5;16;48;5;118m".to_string());
            q.insert("CAIXA_CAMPO_INATIVO".to_string(), "\u{1b}[38;5;22;48;5;16m".to_string());
            q.insert("BARRA_ALERTA".to_string(), "\u{1b}[1;38;5;16;48;5;190m".to_string());
            q.insert("BARRA_VERDE".to_string(), "\u{1b}[1;38;5;16;48;5;118m".to_string());
            q.insert("BARRA_ERRO".to_string(), "\u{1b}[1;38;5;231;48;5;124m".to_string());
            q.insert("SOMBRA_3D".to_string(), "\u{1b}[38;5;22;48;5;22m".to_string());
            q.insert("DROPLIST_BORDA".to_string(), "\u{1b}[38;5;16;48;5;118m".to_string());
            q.insert("DROPLIST_ITEM".to_string(), "\u{1b}[38;5;16;48;5;118m".to_string());
            q.insert("DROPLIST_SEL".to_string(), "\u{1b}[1;38;5;16;48;5;231m".to_string());
            q.insert("COR_OURO".to_string(), "\u{1b}[1;38;5;190;48;5;16m".to_string());
            q.insert("COR_PRATA".to_string(), "\u{1b}[1;38;5;118;48;5;16m".to_string());
            q.insert("COR_BRONZE".to_string(), "\u{1b}[1;38;5;148;48;5;16m".to_string());
            q.insert("COR_DEMAIS".to_string(), "\u{1b}[38;5;70;48;5;16m".to_string());
            q.insert("MENU_BARRA".to_string(), "\u{1b}[1;38;5;16;48;5;118m".to_string());
            q.insert("MENU_BARRA_HOT".to_string(), "\u{1b}[1;4;38;5;16;48;5;118m".to_string());
            q.insert("MENU_BARRA_ATIVO".to_string(), "\u{1b}[1;38;5;118;48;5;16m".to_string());
            q.insert("MENU_BARRA_ATIVO_HOT".to_string(), "\u{1b}[1;4;38;5;118;48;5;16m".to_string());
            q.insert("MENU_ITEM".to_string(), "\u{1b}[38;5;118;48;5;16m".to_string());
            q.insert("MENU_ITEM_HOT".to_string(), "\u{1b}[1;4;38;5;231;48;5;16m".to_string());
            q.insert("MENU_ITEM_SEL".to_string(), "\u{1b}[1;38;5;16;48;5;118m".to_string());
            q.insert("MENU_ITEM_SEL_HOT".to_string(), "\u{1b}[1;4;38;5;16;48;5;118m".to_string());
            q.insert("MENU_ITEM_OFF".to_string(), "\u{1b}[38;5;22;48;5;16m".to_string());
            q.insert("MENU_BORDA".to_string(), "\u{1b}[38;5;118;48;5;16m".to_string());
            q.insert("LOGO_AZUL".to_string(), "\u{1b}[1;38;5;118;48;5;16m".to_string());
            q.insert("LOGO_CIANO".to_string(), "\u{1b}[1;38;5;156;48;5;16m".to_string());
            q.insert("LOGO_CINZA".to_string(), "\u{1b}[38;5;70;48;5;16m".to_string());
            q.insert("LOGO_VERDE".to_string(), "\u{1b}[1;38;5;231;48;5;16m".to_string());
            m.insert("verde".to_string(), q);
        }
        { // paleta "ambar"
            let mut q = BTreeMap::new();
            q.insert("label".to_string(), "Terminal Âmbar (fósforo P3)".to_string());
            q.insert("BARRA_STATUS_TOPO".to_string(), "\u{1b}[1;38;5;16;48;5;214m".to_string());
            q.insert("BARRA_SUB_TOPO".to_string(), "\u{1b}[1;38;5;214;48;5;16m".to_string());
            q.insert("FUNDO_DESKTOP".to_string(), "\u{1b}[38;5;214;48;5;16m".to_string());
            q.insert("CAIXA_BORDA".to_string(), "\u{1b}[1;38;5;214;48;5;16m".to_string());
            q.insert("CAIXA_TITULO".to_string(), "\u{1b}[1;38;5;231;48;5;16m".to_string());
            q.insert("CAIXA_TEXTO".to_string(), "\u{1b}[38;5;214;48;5;16m".to_string());
            q.insert("CAIXA_CIANO".to_string(), "\u{1b}[1;38;5;227;48;5;16m".to_string());
            q.insert("CAIXA_VERDE".to_string(), "\u{1b}[1;38;5;231;48;5;16m".to_string());
            q.insert("CAIXA_AMARELO".to_string(), "\u{1b}[1;38;5;227;48;5;16m".to_string());
            q.insert("CAIXA_SELECAO".to_string(), "\u{1b}[1;38;5;16;48;5;214m".to_string());
            q.insert("CAIXA_BOTAO_ATIVO".to_string(), "\u{1b}[1;38;5;16;48;5;214m".to_string());
            q.insert("CAIXA_BOTAO_INATIVO".to_string(), "\u{1b}[38;5;130;48;5;16m".to_string());
            q.insert("CAIXA_CAMPO_ATIVO".to_string(), "\u{1b}[1;38;5;16;48;5;214m".to_string());
            q.insert("CAIXA_CAMPO_INATIVO".to_string(), "\u{1b}[38;5;130;48;5;16m".to_string());
            q.insert("BARRA_ALERTA".to_string(), "\u{1b}[1;38;5;16;48;5;227m".to_string());
            q.insert("BARRA_VERDE".to_string(), "\u{1b}[1;38;5;16;48;5;214m".to_string());
            q.insert("BARRA_ERRO".to_string(), "\u{1b}[1;38;5;231;48;5;124m".to_string());
            q.insert("SOMBRA_3D".to_string(), "\u{1b}[38;5;94;48;5;94m".to_string());
            q.insert("DROPLIST_BORDA".to_string(), "\u{1b}[38;5;16;48;5;214m".to_string());
            q.insert("DROPLIST_ITEM".to_string(), "\u{1b}[38;5;16;48;5;214m".to_string());
            q.insert("DROPLIST_SEL".to_string(), "\u{1b}[1;38;5;16;48;5;231m".to_string());
            q.insert("COR_OURO".to_string(), "\u{1b}[1;38;5;227;48;5;16m".to_string());
            q.insert("COR_PRATA".to_string(), "\u{1b}[1;38;5;214;48;5;16m".to_string());
            q.insert("COR_BRONZE".to_string(), "\u{1b}[1;38;5;180;48;5;16m".to_string());
            q.insert("COR_DEMAIS".to_string(), "\u{1b}[38;5;130;48;5;16m".to_string());
            q.insert("MENU_BARRA".to_string(), "\u{1b}[1;38;5;16;48;5;214m".to_string());
            q.insert("MENU_BARRA_HOT".to_string(), "\u{1b}[1;4;38;5;16;48;5;214m".to_string());
            q.insert("MENU_BARRA_ATIVO".to_string(), "\u{1b}[1;38;5;214;48;5;16m".to_string());
            q.insert("MENU_BARRA_ATIVO_HOT".to_string(), "\u{1b}[1;4;38;5;214;48;5;16m".to_string());
            q.insert("MENU_ITEM".to_string(), "\u{1b}[38;5;214;48;5;16m".to_string());
            q.insert("MENU_ITEM_HOT".to_string(), "\u{1b}[1;4;38;5;231;48;5;16m".to_string());
            q.insert("MENU_ITEM_SEL".to_string(), "\u{1b}[1;38;5;16;48;5;214m".to_string());
            q.insert("MENU_ITEM_SEL_HOT".to_string(), "\u{1b}[1;4;38;5;16;48;5;214m".to_string());
            q.insert("MENU_ITEM_OFF".to_string(), "\u{1b}[38;5;94;48;5;16m".to_string());
            q.insert("MENU_BORDA".to_string(), "\u{1b}[38;5;214;48;5;16m".to_string());
            q.insert("LOGO_AZUL".to_string(), "\u{1b}[1;38;5;214;48;5;16m".to_string());
            q.insert("LOGO_CIANO".to_string(), "\u{1b}[1;38;5;227;48;5;16m".to_string());
            q.insert("LOGO_CINZA".to_string(), "\u{1b}[38;5;130;48;5;16m".to_string());
            q.insert("LOGO_VERDE".to_string(), "\u{1b}[1;38;5;231;48;5;16m".to_string());
            m.insert("ambar".to_string(), q);
        }
        { // paleta "claro"
            let mut q = BTreeMap::new();
            q.insert("label".to_string(), "Clássico Claro (branco + preto)".to_string());
            q.insert("BARRA_STATUS_TOPO".to_string(), "\u{1b}[1;38;5;16;48;5;252m".to_string());
            q.insert("BARRA_SUB_TOPO".to_string(), "\u{1b}[1;38;5;231;48;5;18m".to_string());
            q.insert("FUNDO_DESKTOP".to_string(), "\u{1b}[38;5;16;48;5;255m".to_string());
            q.insert("CAIXA_BORDA".to_string(), "\u{1b}[1;38;5;16;48;5;255m".to_string());
            q.insert("CAIXA_TITULO".to_string(), "\u{1b}[1;38;5;18;48;5;255m".to_string());
            q.insert("CAIXA_TEXTO".to_string(), "\u{1b}[38;5;16;48;5;255m".to_string());
            q.insert("CAIXA_CIANO".to_string(), "\u{1b}[1;38;5;18;48;5;255m".to_string());
            q.insert("CAIXA_VERDE".to_string(), "\u{1b}[1;38;5;22;48;5;255m".to_string());
            q.insert("CAIXA_AMARELO".to_string(), "\u{1b}[1;38;5;130;48;5;255m".to_string());
            q.insert("CAIXA_SELECAO".to_string(), "\u{1b}[1;38;5;231;48;5;18m".to_string());
            q.insert("CAIXA_BOTAO_ATIVO".to_string(), "\u{1b}[1;38;5;231;48;5;18m".to_string());
            q.insert("CAIXA_BOTAO_INATIVO".to_string(), "\u{1b}[38;5;16;48;5;250m".to_string());
            q.insert("CAIXA_CAMPO_ATIVO".to_string(), "\u{1b}[1;38;5;231;48;5;18m".to_string());
            q.insert("CAIXA_CAMPO_INATIVO".to_string(), "\u{1b}[38;5;16;48;5;252m".to_string());
            q.insert("BARRA_ALERTA".to_string(), "\u{1b}[1;38;5;16;48;5;222m".to_string());
            q.insert("BARRA_VERDE".to_string(), "\u{1b}[1;38;5;16;48;5;120m".to_string());
            q.insert("BARRA_ERRO".to_string(), "\u{1b}[1;38;5;231;48;5;124m".to_string());
            q.insert("SOMBRA_3D".to_string(), "\u{1b}[38;5;245;48;5;245m".to_string());
            q.insert("DROPLIST_BORDA".to_string(), "\u{1b}[38;5;16;48;5;255m".to_string());
            q.insert("DROPLIST_ITEM".to_string(), "\u{1b}[38;5;16;48;5;255m".to_string());
            q.insert("DROPLIST_SEL".to_string(), "\u{1b}[1;38;5;231;48;5;18m".to_string());
            q.insert("COR_OURO".to_string(), "\u{1b}[1;38;5;130;48;5;255m".to_string());
            q.insert("COR_PRATA".to_string(), "\u{1b}[1;38;5;16;48;5;255m".to_string());
            q.insert("COR_BRONZE".to_string(), "\u{1b}[1;38;5;94;48;5;255m".to_string());
            q.insert("COR_DEMAIS".to_string(), "\u{1b}[38;5;16;48;5;255m".to_string());
            q.insert("MENU_BARRA".to_string(), "\u{1b}[38;5;16;48;5;252m".to_string());
            q.insert("MENU_BARRA_HOT".to_string(), "\u{1b}[1;4;38;5;18;48;5;252m".to_string());
            q.insert("MENU_BARRA_ATIVO".to_string(), "\u{1b}[1;38;5;231;48;5;18m".to_string());
            q.insert("MENU_BARRA_ATIVO_HOT".to_string(), "\u{1b}[1;4;38;5;231;48;5;18m".to_string());
            q.insert("MENU_ITEM".to_string(), "\u{1b}[38;5;16;48;5;255m".to_string());
            q.insert("MENU_ITEM_HOT".to_string(), "\u{1b}[1;4;38;5;18;48;5;255m".to_string());
            q.insert("MENU_ITEM_SEL".to_string(), "\u{1b}[1;38;5;231;48;5;18m".to_string());
            q.insert("MENU_ITEM_SEL_HOT".to_string(), "\u{1b}[1;4;38;5;231;48;5;18m".to_string());
            q.insert("MENU_ITEM_OFF".to_string(), "\u{1b}[38;5;245;48;5;255m".to_string());
            q.insert("MENU_BORDA".to_string(), "\u{1b}[38;5;16;48;5;255m".to_string());
            q.insert("LOGO_AZUL".to_string(), "\u{1b}[1;38;5;18;48;5;255m".to_string());
            q.insert("LOGO_CIANO".to_string(), "\u{1b}[1;38;5;24;48;5;255m".to_string());
            q.insert("LOGO_CINZA".to_string(), "\u{1b}[38;5;240;48;5;255m".to_string());
            q.insert("LOGO_VERDE".to_string(), "\u{1b}[1;38;5;22;48;5;255m".to_string());
            m.insert("claro".to_string(), q);
        }
        m
    })
}

/// Mapa chave->cor da paleta indicada, sem a chave `"label"`.
fn mapa_da_paleta(nome: &str) -> BTreeMap<String, String> {
    let mut m = BTreeMap::new();
    if let Some(paleta) = paletas().get(nome) {
        for (k, v) in paleta {
            if k != "label" {
                m.insert(k.clone(), v.clone());
            }
        }
    }
    m
}

/// Estado global: cores aplicadas (equivale as variaveis globais de `cores.py`).
fn cores_atuais() -> &'static Mutex<BTreeMap<String, String>> {
    static C: OnceLock<Mutex<BTreeMap<String, String>>> = OnceLock::new();
    C.get_or_init(|| {
        let mut g = mapa_da_paleta("classic");
        if let Some(lab) = paletas().get("classic").and_then(|p| p.get("label")) {
            g.insert("label".to_string(), lab.clone());
        }
        Mutex::new(g)
    })
}

fn paleta_atual_ref() -> &'static Mutex<String> {
    static PA: OnceLock<Mutex<String>> = OnceLock::new();
    PA.get_or_init(|| Mutex::new("classic".to_string()))
}

/// Valida que todas as paletas tem as chaves obrigatorias
/// (`_validar_paletas`, chamada no import do Python).
pub fn validar_paletas() -> Result<(), String> {
    let obr: BTreeSet<&str> = CHAVES_OBRIGATORIAS.iter().copied().collect();
    for (nome, paleta) in paletas() {
        let faltando: Vec<&str> = obr.iter().copied()
            .filter(|k| !paleta.contains_key(*k))
            .collect();
        if !faltando.is_empty() {
            return Err(format!("Paleta {:?} esta faltando chaves: {:?}", nome, faltando));
        }
        for (chave, valor) in paleta {
            if chave != chave.trim() {
                eprintln!("[WARN] Paleta {:?}: chave {:?} tem espacos extras", nome, chave);
            }
            if valor != valor.trim() {
                eprintln!("[WARN] Paleta {:?}: valor de {:?} tem espacos extras", nome, chave);
            }
        }
    }
    Ok(())
}

/// Troca as variaveis globais de cor para a paleta indicada (`aplicar_paleta`).
///
/// Retorna `true` se aplicou com sucesso, `false` se o nome nao existe.
pub fn aplicar_paleta(nome: &str) -> bool {
    let todas = paletas();
    let Some(paleta) = todas.get(nome) else {
        eprintln!("[WARN] Paleta {:?} nao encontrada", nome);
        return false;
    };
    let mut m = mapa_da_paleta(nome);
    if let Some(lab) = paleta.get("label") {
        m.insert("label".to_string(), lab.clone());
    }
    *cores_atuais().lock().unwrap() = m;
    *paleta_atual_ref().lock().unwrap() = nome.to_string();
    true
}

/// Retorna o nome da paleta atualmente em uso (`paleta_atual`).
pub fn paleta_atual() -> String {
    paleta_atual_ref().lock().unwrap().clone()
}

/// Le uma variavel de cor global (ex.: `chave("CAIXA_TEXTO")`).
/// Devolve string vazia se a chave nao foi aplicada.
pub fn chave(nome: &str) -> String {
    cores_atuais().lock().unwrap().get(nome).cloned().unwrap_or_default()
}

/// Envolve o texto com o estilo ANSI e reseta no final (`pinta`).
pub fn pinta(texto: &str, estilo: &str) -> String {
    format!("{estilo}{texto}{RESET}")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn paletas_validas_e_completas() {
        assert_eq!(validar_paletas(), Ok(()));
        assert_eq!(paletas().len(), 8);
        for nome in ORDEM_PALETAS {
            assert!(paletas().contains_key(nome), "falta paleta {}", nome);
        }
    }

    #[test]
    fn valores_batem_com_python() {
        // amostras extraidas de torre_facil/tui/cores.py
        let p = paletas();
        assert_eq!(p["classic"]["CAIXA_TEXTO"], "\u{1b}[38;5;253;48;5;17m");
        assert_eq!(p["norton"]["CAIXA_BORDA"], "\u{1b}[1;38;5;51;48;5;17m");
        assert_eq!(p["verde"]["BARRA_STATUS_TOPO"], "\u{1b}[1;38;5;16;48;5;118m");
        assert_eq!(p["ambar"]["LOGO_VERDE"], "\u{1b}[1;38;5;231;48;5;16m");
        assert_eq!(p["claro"]["SOMBRA_3D"], "\u{1b}[38;5;245;48;5;245m");
        assert_eq!(p["dos_cinza"]["CAIXA_CAMPO_ATIVO"], "\u{1b}[1;38;5;231;48;5;18m");
        assert_eq!(p["turbo"]["FUNDO_DESKTOP"], "\u{1b}[38;5;250;48;5;24m");
        assert_eq!(p["dos_azul"]["DROPLIST_SEL"], "\u{1b}[1;38;5;231;48;5;18m");
    }

    #[test]
    fn aplicar_paleta_troca_cores() {
        // docstring do Python: aplicar_paleta("norton") -> True; inexistente -> False
        assert!(aplicar_paleta("norton"));
        assert_eq!(paleta_atual(), "norton");
        assert_eq!(chave("CAIXA_BORDA"), "\u{1b}[1;38;5;51;48;5;17m");
        assert!(!aplicar_paleta("inexistente"));
        assert_eq!(paleta_atual(), "norton"); // permaneceu
        aplicar_paleta("classic");
        assert_eq!(chave("CAIXA_TEXTO"), "\u{1b}[38;5;253;48;5;17m");
    }

    #[test]
    fn pinta_envolve_e_reseta() {
        let estilo = "\u{1b}[38;5;253;48;5;17m";
        assert_eq!(pinta("Ola", estilo), "\u{1b}[38;5;253;48;5;17mOla\u{1b}[0m");
    }
}
