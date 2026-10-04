//! Porta 1:1 do pacote `torre_facil.dados`.
//!
//! - [`bairros`]: motor de unificação de bairros por município (`bairros.py`)
//! - [`snapshot`]: snapshot e comparação da base ANATEL (`snapshot.py`)
//! - [`anatel`]: download, parsing e cache da base ANATEL SMP (`anatel.py`)

pub mod anatel;
pub mod bairros;
pub mod snapshot;
