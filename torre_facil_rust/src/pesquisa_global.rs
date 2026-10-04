//! Cache global de pesquisa — porta parcial de `torre_facil/pesquisa_global.py`.
//!
//! Nesta etapa da migração 1:1, apenas o invalidador de cache é fornecido,
//! espelhando o comportamento do módulo Python quando ainda não há entradas
//! em cache (a implementação completa das rotinas de busca será acoplada à TUI).

use std::sync::Mutex;

/// Cache de resultados de pesquisa global (equivalente ao dict memoizado do Python).
static CACHE_PESQUISA: Mutex<Vec<String>> = Mutex::new(Vec::new());

/// Invalida todo o cache de pesquisa (`invalidar_cache_pesquisa()` do Python).
pub fn invalidar_cache_pesquisa() {
    if let Ok(mut c) = CACHE_PESQUISA.lock() {
        c.clear();
    }
}
