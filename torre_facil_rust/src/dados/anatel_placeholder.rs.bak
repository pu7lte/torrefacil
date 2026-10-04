//! Placeholder do módulo `torre_facil/dados/anatel.py`.
//!
//! O pipeline completo de download/parsing da base ANATEL SMP depende de:
//!   - HTTP streaming (requests) — baixar_zip_anatel
//!   - unzip + CSV em baixa memória — extrair_csv_do_zip / _etapa_carregar_csv
//!   - pickle binário do pandas — carregar_do_cache / processar_base_e_salvar_cache
//!   - TUI (janelas/cores/motor) — caixa_notificacao_tui, alerta_tui, splash
//!
//! Este arquivo será substituído pela porta 1:1 quando a camada de I/O e a
//! TUI forem portadas. As funções puras de parsing já estão disponíveis em
//! [`crate::coordenadas`] e [`crate::texto`].

// TODO(anatel): implementar com reqwest + zip + mini-DataFrame persistido em JSON.
