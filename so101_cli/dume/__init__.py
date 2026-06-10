"""DUM-E: TUI rica en iconos para el SO-101, con un CLI scriptable `dume run`.

Dos modos sobre los mismos módulos de `so101_cli`: la TUI (`dume`) y el CLI
(`dume run <subcmd>`, antes `cal`). La TUI reusa los helpers (diagnostics, config,
poses, record_dataset) por import y, para ops pesadas o interactivas, suspende y
corre `dume run <subcmd>` con TTY completo.
"""
