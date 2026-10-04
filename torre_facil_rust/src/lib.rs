//! Torre Fácil ERP — porta Rust 1:1 do pacote Python `torre_facil`.
//!
//! Módulos já migrados (camada de dados e utilidades):
//! - [`config`]: constantes e caminhos globais (`config.py`)
//! - [`config_usuario`]: persistência de preferências (`config_usuario.py`)
//! - [`coordenadas`]: conversões de coordenadas e operadoras (`coordenadas.py`)
//! - [`dicionarios`]: dicionários carregáveis (`dicionarios.py`)
//! - [`dados_dicionarios`]: dados brutos dos dicionários padrão
//! - [`dataframe`]: mini-DataFrame (substituto do pandas)
//! - [`estado`]: contexto da sessão (`estado.py`)
//! - [`texto`]: normalização e extração de bairros (`texto.py`)
//! - [`dados`]: pacote de dados (`torre_facil/dados/`): ANATEL, bairros, snapshot

pub mod config;
pub mod config_usuario;
pub mod coordenadas;
pub mod dados;
pub mod dados_dicionarios;
pub mod dataframe;
pub mod dicionarios;
pub mod estado;
pub mod pesquisa_global;
pub mod texto;
