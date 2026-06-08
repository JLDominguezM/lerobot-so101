"""Subcomando top-level: ./cal eval-viz

Corre la policy entrenada en el robot real y la visualiza en rerun.

  - Policy ACT (ResNet-18): muestra un heatmap de activaciones por cámara — la
    magnitud L2 del último conv. Indica si el modelo mira el cable o el fondo.
    (No es "atención" transformer.)
  - Policy SmolVLA (SigLIP + transformer): el heatmap de ResNet NO aplica, así
    que se muestran solo los streams de cámara crudos mientras la policy corre.
    Útil igual para ver qué ven las cámaras en el momento de decidir el pick.

El tipo se detecta automáticamente del config.json del checkpoint.

No necesita el brazo leader conectado.

Ejemplo:
    ./cal eval-viz --color red
    ./cal eval-viz --color black --n 3 --fps 15
    ./cal eval-viz --color green --no-lateral
    ./cal eval-viz --color red --n-action-steps 15   # más reactivo (SmolVLA)
"""

from __future__ import annotations

import argparse
import time

# Registra el tipo de cámara "depthai" antes de cualquier import de LeRobot
# que toque el registro de CameraConfig.
from so101_cli import depthaicamera  # noqa: F401

from .config import load_arm_config

POLICY_DEFAULT = "armandomm09/smolvla_terminal_sort"
TASK_TEMPLATE  = "pick the {color} cable and place it in the {color} box"


def add_eval_viz_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "eval-viz",
        help="Corre la policy en el robot y visualiza el mapa de activaciones en rerun.",
        description=(
            "Ejecuta la policy en el follower y la muestra en rerun.\n"
            "ACT: heatmap de activaciones ResNet (attention/<cam>/image|attention|overlay).\n"
            "SmolVLA: solo streams de cámara (cameras/<cam>); el heatmap ResNet no aplica.\n\n"
            "Ejemplos:\n"
            "  ./cal eval-viz --color red\n"
            "  ./cal eval-viz --color black --n 3\n"
        ),
    )
    p.add_argument(
        "--color", required=True, choices=["black", "green", "red"],
        help="Color del cable a recoger.",
    )
    p.add_argument(
        "--policy", default=POLICY_DEFAULT,
        help=f"HF repo_id de la policy (default: {POLICY_DEFAULT}).",
    )
    p.add_argument("--n", type=int, default=1,
                   help="Número de episodios (default 1).")
    p.add_argument("--duration", type=float, default=60.0,
                   help="Segundos máximos por episodio (default 60).")
    p.add_argument("--fps", type=int, default=15,
                   help="FPS del loop de control (default 15; más bajo = más margen CPU).")
    p.add_argument("--front-index", type=int, default=0,
                   help="Índice OpenCV de la cámara 'front' (RealSense) (default 0).")
    p.add_argument("--no-lateral", action="store_true",
                   help="No usar la cámara lateral (OAK-D).")
    p.add_argument("--device", default="cpu",
                   help="Dispositivo torch para la policy (default: cpu; usa cuda/mps si tienes GPU).")
    p.add_argument(
        "--n-action-steps", type=int, default=None,
        help="Override de cuántas acciones del chunk ejecutar antes de re-observar "
             "(SmolVLA/ACT traen 50). Bajarlo (p.ej. 15) hace al robot más reactivo. "
             "No requiere reentrenar.",
    )
    p.add_argument(
        "--num-steps", type=int, default=None,
        help="Override de pasos de integración del flow-matching (solo SmolVLA; "
             "el checkpoint trae 10). Subirlo da acciones más nítidas. No reentrena.",
    )
    p.set_defaults(func=cmd_eval_viz)


def cmd_eval_viz(args: argparse.Namespace) -> int:
    import json

    import torch
    import numpy as np
    from huggingface_hub import hf_hub_download

    from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig
    from lerobot.policies.factory import get_policy_class, make_pre_post_processors
    from lerobot.policies.utils import build_inference_frame, make_robot_action
    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
    from lerobot.utils.feature_utils import hw_to_dataset_features
    from lerobot.utils.robot_utils import precise_sleep
    from lerobot.utils.visualization_utils import init_rerun

    from so101_cli.depthaicamera import DepthAICameraConfig

    task   = TASK_TEMPLATE.format(color=args.color)
    device = torch.device(args.device)
    cfg    = load_arm_config("follower")

    # Detecta el tipo de policy desde el config.json del checkpoint (sin
    # depender del registro lazy de draccus). "act" → heatmap ResNet; cualquier
    # otra (smolvla, ...) → solo streams de cámara.
    cfg_path    = hf_hub_download(args.policy, "config.json")
    policy_type = json.load(open(cfg_path))["type"]
    is_act      = policy_type == "act"

    # Cámaras para el robot
    cameras: dict = {
        "front": OpenCVCameraConfig(
            index_or_path=args.front_index,
            width=640, height=480, fps=args.fps,
        ),
    }
    if not args.no_lateral:
        cameras["lateral"] = DepthAICameraConfig(
            width=640, height=480, fps=args.fps,
        )

    follower_config = SO101FollowerConfig(
        port=cfg["port"],
        id=cfg["id"],
        cameras=cameras,
    )
    follower = SO101Follower(follower_config)

    print(f"=== eval-viz ===")
    print(f"  color   : {args.color}")
    print(f"  task    : {task!r}")
    print(f"  policy  : {args.policy}  (type={policy_type})")
    print(f"  device  : {device}")
    print(f"  viz     : {'heatmap ResNet' if is_act else 'solo cámaras (SmolVLA: heatmap ResNet no aplica)'}")
    print(f"  fps     : {args.fps}  ({args.n} episodio(s) × {args.duration}s)")
    print(f"  cámaras : front" + ("" if args.no_lateral else " + lateral"))
    print()
    print("Cargando policy desde HF Hub...")
    policy_cls = get_policy_class(policy_type)
    policy = policy_cls.from_pretrained(args.policy)
    # Overrides de inferencia (se leen vivos del config en cada select_action).
    if args.n_action_steps is not None:
        policy.config.n_action_steps = args.n_action_steps
        print(f"  → n_action_steps override: {args.n_action_steps}")
    if args.num_steps is not None and hasattr(policy.config, "num_steps"):
        policy.config.num_steps = args.num_steps
        print(f"  → num_steps override: {args.num_steps}")
    policy.to(device)
    policy.eval()

    action_feats  = hw_to_dataset_features(follower.action_features, "action", use_video=False)
    obs_feats     = hw_to_dataset_features(follower.observation_features, "observation", use_video=True)
    ds_features   = {**action_feats, **obs_feats}

    preprocessor, postprocessor = make_pre_post_processors(
        policy_cfg=policy.config,
        pretrained_path=args.policy,
        preprocessor_overrides={"device_processor": {"device": str(device)}},
    )

    init_rerun(session_name=f"eval_viz_{args.color}")

    print("Conectando robot...")
    follower.connect()
    print("Robot conectado. Ctrl-C para parar.\n")

    interval = 1.0 / args.fps

    # El heatmap ResNet solo existe para ACT. Para SmolVLA usamos un context
    # vacío y logueamos las cámaras crudas con rerun directamente.
    if is_act:
        from lerobot_attention_visualizer import ACTAttention
        viz = ACTAttention(policy)
    else:
        import contextlib
        import rerun as rr
        viz = contextlib.nullcontext()

    def _bare_images(obs: dict) -> dict:
        """Extrae las imágenes de cámara como uint8 HWC (sin prefijo)."""
        bare: dict = {}
        for k, v in obs.items():
            if k in cameras:  # "front", "lateral"
                img = np.asarray(v)
                if img.ndim == 3 and img.shape[0] == 3:
                    img = img.transpose(1, 2, 0)  # CHW → HWC
                if img.dtype != np.uint8:
                    img = (img * 255).clip(0, 255).astype(np.uint8)
                bare[k] = img
        return bare

    try:
        with viz:
            for ep in range(args.n):
                print(f"  Episodio {ep + 1}/{args.n} — {task}")
                policy.reset()
                t_end = time.perf_counter() + args.duration

                while time.perf_counter() < t_end:
                    t0 = time.perf_counter()

                    obs = follower.get_observation()

                    obs_frame = build_inference_frame(
                        observation=obs,
                        device=device,
                        ds_features=ds_features,
                        task=task,
                        robot_type="so101_follower",
                    )
                    obs_frame = preprocessor(obs_frame)
                    action = policy.select_action(obs_frame)
                    action_post = postprocessor(action).squeeze(0)
                    action_dict = make_robot_action(action_post.unsqueeze(0), ds_features)
                    follower.send_action(action_dict)

                    bare_obs = _bare_images(obs)
                    if is_act:
                        # log_overlay espera el dict raw uint8 HWC (lo que da
                        # get_observation antes del preprocessor).
                        viz.log_overlay(bare_obs)
                    else:
                        for k, img in bare_obs.items():
                            rr.log(f"cameras/{k}", rr.Image(img))

                    precise_sleep(max(0.0, interval - (time.perf_counter() - t0)))

                print(f"  Episodio {ep + 1} terminado.")

    except KeyboardInterrupt:
        print("\nInterrumpido.")
    finally:
        follower.disconnect()
        print("Robot desconectado.")

    return 0
