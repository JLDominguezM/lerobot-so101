# DUM-E — `dume`, la TUI del SO-101

`dume` (DUM-E) es una TUI rica en iconos (Textual) y, a la vez, un CLI scriptable
(`dume run <subcmd>`): **dos modos sobre los mismos módulos `so101_cli`**. La TUI no
reimplementa la lógica del robot; la reusa por import para lo de solo lectura y, para
ops pesadas/interactivas, suspende la TUI y corre `dume run <subcmd>` con el terminal
completo. (`dume run` reemplaza 1:1 al antiguo comando `cal`, que se eliminó.)

## Uso

```bash
source .venv/bin/activate
./dume                 # abre el cockpit (home)  [modo TUI]
./dume teleop          # salta directo a una vista TUI
./dume --ascii         # sin Nerd Font ni imágenes inline (terminales básicos)
./dume run <subcmd>    # modo CLI scriptable (teleop/record-batch/eval/train/...)
```

Atajos: `1-8` saltan de vista, `↑/↓ + Enter` navegan el sidebar, `r` refresca el cockpit,
`c`/`f`/`s`/`S` corren `dume run check` / `find-ports` / `scan-bus follower|leader` (suspenden
la TUI), `?` ayuda, `q` salir.

El cockpit **no retiene el hardware**: sondea la conexión una vez al entrar y con `r`
(cada sonda abre→pinga→cierra). Sin robot conectado, todo degrada a ✗ / "ninguno" y no crashea.

## Fase 1

Foundation + Home cockpit: cards de conexión, brazos+calibración, datasets, modelos, quick
actions y un smoke test de imagen inline.

## Fase 2 — Teleop (este milestone)

Primera vista-formulario (`./dume teleop` o tecla `2`). Patrón que reusarán record/eval/train:
campos editables (rate, grabar a disco + out, cámaras front/lateral, front-index) → un
`CommandPreview` que re-compone `$ dume run teleop …` en vivo → **Lanzar** suspende la TUI y corre
`dume run teleop <flags>` con el TTY completo (lerobot toma teclado y la ventana de rerun). No
reimplementa teleop: delega 1:1 en el subcomando `dume run teleop`. El botón **Comprobar conexión** hace
un pre-vuelo bajo demanda (`probe_connection()` en un worker: abre→pinga→cierra, sin retener el
bus ni las cámaras) y avisa si falta leader/follower antes de lanzar.

Los formularios de record/eval/train y los browsers de datasets/modelos llegan en fases
siguientes (aparecen en el sidebar como "próxima fase", marcados con `·`).

## Distribución

El proyecto ya trae el scaffolding de empaquetado (build backend `hatchling`, un único entry
point `dume` —que cubre TUI y `dume run`—, nombre de distribución `dume`).

### PyPI

`[tool.uv.sources]` (el clone editable de `./lerobot`) es **solo para dev**: hatchling lo
ignora, así que el wheel publicado depende de `lerobot[feetech]` desde PyPI.

```bash
uv build                      # o: python -m build  → dist/so101_dume-0.1.0-{whl,tar.gz}
python -m twine upload dist/* # requiere credenciales de PyPI
```

Instalación para usuarias finales (da el comando `dume`, con TUI y `dume run`):

```bash
pipx install dume       # o, sin publicar: pipx install 'git+https://github.com/<user>/<repo>'
uv tool install dume
```

### Homebrew

`Formula/dume.rb` es una plantilla (tap). Para una fórmula real, publicá en PyPI, completá
`url`/`sha256`, y generá los `resource` con `brew update-python-resources Formula/dume.rb`
(LeRobot arrastra torch/depthai, por eso una fórmula bottled completa es pesada). El arm y las
cámaras siguen siendo necesarios en runtime.
