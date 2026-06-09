# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Operation of the SO-101 robotic arm (leader + follower, 6 DOF each, Feetech STS3215 motors) using Hugging Face's LeRobot framework. **No ROS2** — deliberate decision: LeRobot already covers teleop/recording/training/eval. There is no CI and no test suite; "tests" are physical executions on the hardware.

## Environment

- Python `>=3.12,<3.13`, managed with `uv`.
- LeRobot is consumed as an **editable path dependency** at `./lerobot` (sibling clone vendored into the repo). `pyproject.toml` declares `lerobot[feetech]` and `[tool.uv.sources]` rewires it to the local path.
- `setup.sh` bootstraps everything: installs `uv`, ensures Python 3.12, clones `huggingface/lerobot` into `./lerobot/`, and runs `uv sync`.
- Secrets live in `.env` (`HUGGINGFACE_TOKEN`, `HF_USER`); `scripts/_lib.sh` auto-loads it. `HF_USER` is required by record/train/eval scripts.

## Common commands

Activate the venv first: `source .venv/bin/activate`.

```bash
# LeRobot CLI wrappers (numbered scripts/) — one-shot operations driven by configs/{follower,leader}.yaml
bash scripts/00_find_ports.sh                                # detect USB ports
bash scripts/01_setup_motors.sh follower|leader              # one-time motor ID assignment
bash scripts/02_calibrate.sh follower|leader|both            # range calibration
bash scripts/03_teleoperate.sh [--display_data=true]         # raw lerobot-teleoperate
bash scripts/05_record.sh "<task>" <num_ep> <dataset_name>   # record demos → HF Hub
bash scripts/06_replay.sh <dataset_name> <ep_idx>            # replay episode on follower
bash scripts/07_train_act.sh <dataset_name> [policy_name]    # train ACT (needs CUDA)
bash scripts/09_train_smolvla.sh <dataset_name> [policy_name] # train SmolVLA (task-conditioned VLM; CUDA, or --policy.device=mps on Mac)
bash scripts/08_eval.sh <policy_name> "<task>" [num_ep]      # roll out policy on robot
bash scripts/install_calibrations.sh                         # symlink calibrations/*.json → ~/.cache/huggingface/lerobot/calibration/
python scripts/scan_bus.py follower|leader                   # ping motor IDs 1..6; useful after partial setup_motors crash
python scripts/setup_one_motor.py follower|leader <name>     # configure a single motor by joint name (recovery tool)

# Project's own CLI (so101_cli package), invoked via the `cal` wrapper:
./cal find-ports                                            # identify which USB port is which arm (wraps lerobot-find-port)
./cal setup-motors follower|leader                          # assign motor IDs 1..6 (all, interactive)
./cal setup-motors follower|leader --motor gripper          # reconfigure ONE motor by joint name (recovery)
./cal scan-bus follower|leader                              # ping the bus; report which motor IDs 1..6 respond
./cal check [--no-leader] [--no-front] [--no-lateral]       # connectivity health check: both arms + both cameras
./cal follower move --pose home                              # move follower to a named pose
./cal follower move 0 -30 -60 0 0 0 --hold-time 2            # move to explicit joint angles (deg)
./cal follower move --tune                                   # interactive joint tuning
./cal follower replay paths/x.json                           # replay waypoints OR trajectory file
./cal leader record-waypoint paths/wp.json [--append]        # capture static poses ('s' to save, 'q' to finish)
./cal leader record-trajectory paths/t.json --rate 30        # capture continuous motion ('r' start/stop)
./cal teleop [--rate 30] [--record [--out base]]             # live leader→follower, optional .json+.rrd recording
./cal record-dataset ...                                     # wrapper over lerobot-record for VLA demos
./cal record-batch [--batches N] [--push]                   # structured session: batches of 3 episodes (negro/verde/rojo)
./cal eval --color red|green|black [--n N] [--record]        # run trained policy on follower (no leader needed)
./cal eval-viz --color red|green|black [--fps 15]            # same as eval + rerun ResNet-18 activation heatmap
./cal delete-batch N [--dry-run]                             # delete 3 episodes of batch N (1-indexed) from local dataset
./cal push dataset|model [...]                               # upload dataset or trained checkpoint to HF Hub
./cal pull dataset|model [--repo-id ID]                      # download dataset (→ lerobot cache) or model (→ hub cache)
./cal train [--type smolvla|act] [--device cuda]             # wrap lerobot-train; default → <HF_USER>/smolvla_terminal_sort
./cal dataset-stats [--repo-id ID]                           # episodes/frames balance per color (pre-train sanity check)
```

Full flag reference for all `cal` subcommands: `so101_cli/COMMANDS.md`.

```bash
# DUM-E: TUI rica en iconos (Textual), front-end de `cal`. NO modifica `cal`.
./dume                 # cockpit (home): conexión, brazos, datasets, modelos, quick actions
./dume <view>          # salta a una vista (teleop/record/... son placeholder hasta fases sig.)
./dume --ascii         # sin Nerd Font ni imágenes inline
```

Detalles de `dume` (arquitectura, fases, empaquetado PyPI/brew): `docs/dume.md`. La TUI vive
en `so101_cli/dume/` y reusa `diagnostics`/`config`/`poses`/`record_dataset` por import + suspende
y corre `./cal` para ops pesadas. `cal` queda intacto.

There is no lint/test target — don't invent one.

## Architecture

### Two layers, one robot

1. **LeRobot wrappers (`scripts/*.sh`)** — thin bash over the official `lerobot-*` CLIs (calibrate, record, train, replay, teleoperate). These read `configs/{follower,leader}.yaml` via `scripts/_lib.sh::load_arm_config` (a deliberately flat `awk`-based YAML reader — don't nest the configs) and pass `--robot.*` / `--teleop.*` flags. Use these for anything that touches the LeRobot dataset/training pipeline.

2. **`so101_cli/` Python package** — project-owned CLI (`cal` / `python -m so101_cli`) for custom motion behavior LeRobot doesn't ship: smooth interpolated moves to named poses, leader-side keyboard-driven recording, replay with smoothstep blending, and rerun-based visualization. It imports LeRobot's robot/teleop classes directly (`SOFollower`, `SOLeader`), bypassing the LeRobot CLI.

`cli.py` builds the argparse tree; each subcommand lives in its own module and registers via `add_*_parser(sub)`. The dispatch convention is `args.func(args)` — every parser sets `set_defaults(func=...)`.

### Single source of truth for joints

`so101_cli/poses.py` defines the canonical `JOINTS` list (order matters — it's the daisy-chain order matching motor IDs 1..6) and the `HOME` / named poses. Two conversion helpers bridge LeRobot's action dict format (keys like `shoulder_pan.pos`) and the project's positional `list[float]`:

- `positions_to_action(values)` — list-or-dict → `{joint.pos: value}` (what LeRobot wants).
- `action_to_positions(action)` — inverse, in `JOINTS` order.

**Always go through these helpers**; never hand-roll the `.pos` suffix.

### Trajectory file format

`so101_cli/io.py` defines two on-disk JSON shapes, both tagged with `type`:

- `waypoints`: discrete named poses, replayed with `interpolate_move` between each.
- `trajectory`: timestamped samples at `rate_hz`, replayed honoring original timing (the follower's first-sample approach is interpolated separately).

`io.load()` validates that `joints` matches the current `JOINTS` list — incompatible files fail loud rather than silently mis-mapping motors.

### Smooth motion

`so101_cli/motion.py::interpolate_move` is the only path that should drive the follower from point A to point B. It reads current state via `robot.get_observation()`, applies a smoothstep profile (`s = α²(3-2α)`), and **auto-extends `duration`** if `max_deg_per_s` would be violated. New movement commands should reuse this rather than calling `robot.send_action` in raw loops.

### Calibration is external state

Calibration JSONs live in `calibrations/` (versioned) but LeRobot reads them from `~/.cache/huggingface/lerobot/calibration/<robot_type>/<id>.json`. `scripts/install_calibrations.sh` **symlinks** (not copies) so that re-running `lerobot-calibrate` updates the repo file directly. The `id` field in `configs/{follower,leader}.yaml` (e.g. `papu`, `leader_principal`) is the join key. The follower connects with `calibrate=False`, relying on this cached file.

### Visualization

`so101_cli/viz.py` is a tolerant rerun wrapper: import-guarded so missing `rerun-sdk` makes the log calls no-ops. Single `init()` per process; entity paths follow `follower/<joint>`, `leader/<joint>`, `target/<joint>`, `cameras/<name>`, `events`. New commands should call `viz.init("<cmd-name>")` at the top and use `viz.log_positions(...)` / `viz.log_event(...)` rather than touching `rerun` directly.

### Interactive tuning REPL

`so101_cli/tune.py::tune_loop` is the `--tune` REPL. Accepts per-joint deltas (`j3 +10`), absolute sets (`j3 =0`), full pose (`all v1..v6`), `speed`/`dur`/`step` config changes, and `save` (prints a one-shot `./cal follower move` command for the current pose). `hold` exits with torque on; `q` releases torque. Only ever called from `follower.py` move command.

### Keyboard input

`so101_cli/keys.py` provides `cbreak()` (context manager for raw tty mode) and `read_key(timeout)`. Used by interactive subcommands (`leader record-*`, `teleop`, `follower move --tune`). Quit conventions: `q` or Ctrl-C (`\x03`); status lines refresh at ~10 Hz via `last_show` throttling.

## Conventions worth knowing

- **`configs/*.yaml` are flat key:value only for bash scripts** — `scripts/_lib.sh::yaml_get` uses awk and doesn't handle nesting; `so101_cli/config.py::load_arm_config` uses `yaml.safe_load` and could handle nesting, but keep configs flat so both readers work. Add new fields at top level.
- **Two-arm scripts load both configs sequentially** into shell vars prefixed `F_*` (follower) and `L_*` (leader); see `03_teleoperate.sh` for the pattern.
- **Two cameras, two roles → consistent names `front` / `lateral` everywhere.** `front` = Intel RealSense D435i (color over AVFoundation/UVC; only delivers a clean frame at 640×480 — higher res tears the bottom half). `lateral` = OAK-D Pro (DepthAI over USB, NOT a UVC device; was on the gripper, now fixed to the side). These names are the rerun entity paths AND the LeRobotDataset camera keys.
  - **Live preview** (`so101_cli/cameras.py`, used only by `./cal teleop`): `FrontCamera` and `LateralCamera` share `start() / read() → BGR ndarray / stop()` and support `with` blocks. Teleop opens both, logs them to rerun as `cameras/front` / `cameras/lateral`; disable with `--no-front` / `--no-lateral`. These are preview-only — the dataset does NOT use them.
  - **Dataset capture** goes through `lerobot-record`, which reads every camera inside the robot's `get_observation()` each tick → all signals (motors + both cameras) are time-coordinated by that one loop. `front` uses LeRobot's built-in `opencv` camera type; `lateral` uses a project-owned **LeRobot camera type `depthai`** in `so101_cli/depthaicamera.py` (`DepthAICameraConfig` + `DepthAICamera`, registered via `@CameraConfig.register_subclass`). LeRobot resolves it through `make_device_from_device_class`, so the module/class names (`depthaicamera.py` / `DepthAICamera`) are load-bearing — don't rename them in isolation.
  - **Two subprocess shims register `depthai` before draccus parses flags:** `so101_cli/_record_entry.py` is used by `record-dataset` (wraps `lerobot.scripts.lerobot_record`), and `so101_cli/_rollout_entry.py` is used by `eval` (wraps `lerobot.scripts.lerobot_rollout`). Both import `depthaicamera` as their first action. Add a new shim whenever a new `lerobot-*` CLI needs the `depthai` camera type.
  - Standalone preview scripts at the repo root: `realsense_rgb.py`, `oakd_rgb.py` (both use `maxSize=1`/640×480 to avoid the lag/tearing pitfalls above).
- **Output paths default to `paths/teleop_<timestamp>`** for `./cal teleop --record`. `paths/`, `poses/` (recorded `trajectory` JSONs like `wave.json`, `salute.json`), `outputs/`, `zed_captures/`, the root `photo*.png`, and `x.py` are scratch/capture artifacts — not part of the architecture; don't wire them into commands.
- **Dataset viz: use pyav, not torchcodec.** `lerobot-dataset-viz` defaults to `torchcodec`, which is broken on this Mac (ABI mismatch with the installed torch + its FFmpeg isn't on the dylib rpath). Decode with `pyav` instead (the `av` package works). Root script `view_dataset.py --repo-id <id> --episode <n>` builds the `LeRobotDataset` with `video_backend="pyav"` and reuses LeRobot's own `visualize_dataset` (motors + both cameras in rerun). The recorded mp4s are standard files — `open <dataset>/videos/observation.images.<cam>/chunk-000/file-000.mp4` plays all episodes of a camera concatenated for a quick eyeball.
- **LeRobot v3.x dataset layout batches episodes into shared files.** All episodes of a dataset live in one `data/chunk-000/file-000.parquet` and one `.mp4` per camera (`videos/observation.images.<cam>/chunk-000/file-000.mp4`); per-episode boundaries are in `meta/episodes/`. "One file" ≠ "one episode" — check `meta/info.json::total_episodes`.
- **`Dockerfile`** is a minimal `python:3.11-slim` image with libusb/libgl + RealSense/OpenCV deps for the standalone camera scripts only — it is NOT the project runtime (the arm runs under `uv` on the host per `setup.sh`).
- Spanish is the primary language for comments and CLI help text — keep that consistency when editing existing files.
