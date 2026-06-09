# DUM-E — `dume`, la TUI del SO-101

`dume` (DUM-E) es una TUI rica en iconos (Textual) que sirve de front-end amistoso
para el proyecto. **No reemplaza ni modifica `cal`**: lo reusa por debajo (importa sus
helpers y, para ops pesadas/interactivas, suspende la TUI y corre `./cal <subcmd>` con el
terminal completo). `cal` sigue siendo la interfaz scriptable.

## Uso

```bash
source .venv/bin/activate
./dume                 # abre el cockpit (home)
./dume teleop          # salta directo a una vista (placeholder hasta la Fase 2)
./dume --ascii         # sin Nerd Font ni imágenes inline (terminales básicos)
```

Atajos: `1-8` saltan de vista, `↑/↓ + Enter` navegan el sidebar, `r` refresca el cockpit,
`c`/`f`/`s`/`S` corren `cal check` / `find-ports` / `scan-bus follower|leader` (suspenden la
TUI), `?` ayuda, `q` salir.

El cockpit **no retiene el hardware**: sondea la conexión una vez al entrar y con `r`
(cada sonda abre→pinga→cierra). Sin robot conectado, todo degrada a ✗ / "ninguno" y no crashea.

## Fase 1 (este milestone)

Foundation + Home cockpit: cards de conexión, brazos+calibración, datasets, modelos, quick
actions y un smoke test de imagen inline. Teleop, formularios de record/eval/train y los
browsers llegan en fases siguientes (aparecen en el sidebar como "próxima fase").

## Distribución

El proyecto ya trae el scaffolding de empaquetado (build backend `hatchling`, entry points
`cal` y `dume`, nombre de distribución `so101-dume`).

### PyPI

`[tool.uv.sources]` (el clone editable de `./lerobot`) es **solo para dev**: hatchling lo
ignora, así que el wheel publicado depende de `lerobot[feetech]` desde PyPI.

```bash
uv build                      # o: python -m build  → dist/so101_dume-0.1.0-{whl,tar.gz}
python -m twine upload dist/* # requiere credenciales de PyPI
```

Instalación para usuarias finales (da los comandos `dume` y `cal`):

```bash
pipx install so101-dume       # o, sin publicar: pipx install 'git+https://github.com/<user>/<repo>'
uv tool install so101-dume
```

### Homebrew

`Formula/dume.rb` es una plantilla (tap). Para una fórmula real, publicá en PyPI, completá
`url`/`sha256`, y generá los `resource` con `brew update-python-resources Formula/dume.rb`
(LeRobot arrastra torch/depthai, por eso una fórmula bottled completa es pesada). El arm y las
cámaras siguen siendo necesarios en runtime.
