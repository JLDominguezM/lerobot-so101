"""DUM-E: TUI rica en iconos para el SO-101 (front-end amistoso de `cal`).

Subpaquete autocontenido. NO modifica el CLI `cal`: lo reusa importando sus
helpers (diagnostics, config, poses, record_dataset) y, para ops pesadas o
interactivas, suspendiendo la TUI y corriendo `./cal <subcmd>` con TTY completo.
"""
