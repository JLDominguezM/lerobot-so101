"""Subcomando top-level: ./cal eval-viz

Corre la policy ACT entrenada en el robot real y muestra en rerun un heatmap
de activaciones del backbone ResNet-18 por cada cámara — así puedes ver qué
zonas de la imagen son las que más influyen en la decisión de la policy.

No es "atención" en sentido transformer: es la magnitud del canal L2 en la
última capa conv de ResNet. Aun así indica bien si el modelo está mirando el
cable o el fondo.

No necesita el brazo leader conectado.

Ejemplo:
    ./cal eval-viz --color red
    ./cal eval-viz --color black --n 3 --fps 15
    ./cal eval-viz --color green --no-lateral
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
            "Ejecuta ACT en el follower y muestra en rerun tres streams por cámara:\n"
            "  attention/<cam>/image    — imagen raw\n"
            "  attention/<cam>/attention — heatmap (rojo = alta activación)\n"
            "  attention/<cam>/overlay  — mezcla 50/50\n\n"
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
                   help="Dispositivo torch para la policy (default: cpu; usa cuda si tienes GPU).")
    p.set_defaults(func=cmd_eval_viz)


def cmd_eval_viz(args: argparse.Namespace) -> int:
    import torch
    import numpy as np

    from lerobot.cameras.opencv.configuration_opencv import OpenCVCameraConfig
    from lerobot.policies.act.modeling_act import ACTPolicy
    from lerobot.policies.factory import make_pre_post_processors
    from lerobot.policies.utils import build_inference_frame, make_robot_action
    from lerobot.robots.so_follower import SO101Follower, SO101FollowerConfig
    from lerobot.utils.feature_utils import hw_to_dataset_features
    from lerobot.utils.robot_utils import precise_sleep
    from lerobot.utils.visualization_utils import init_rerun
    from lerobot_attention_visualizer import ACTAttention

    from so101_cli.depthaicamera import DepthAICameraConfig

    task   = TASK_TEMPLATE.format(color=args.color)
    device = torch.device(args.device)
    cfg    = load_arm_config("follower")

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
    print(f"  policy  : {args.policy}")
    print(f"  device  : {device}")
    print(f"  fps     : {args.fps}  ({args.n} episodio(s) × {args.duration}s)")
    print(f"  cámaras : front" + ("" if args.no_lateral else " + lateral"))
    print()
    print("Cargando policy desde HF Hub...")
    policy = ACTPolicy.from_pretrained(args.policy)
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
    viz = ACTAttention(policy)

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

                    # log_overlay espera el dict raw (claves sin prefijo) con
                    # imágenes en uint8 HWC — que es exactamente lo que devuelve
                    # get_observation() antes de pasar por el preprocessor.
                    bare_obs: dict = {}
                    for k, v in obs.items():
                        if k in cameras:  # "front", "lateral"
                            img = np.asarray(v)
                            if img.ndim == 3 and img.shape[0] == 3:
                                img = img.transpose(1, 2, 0)  # CHW → HWC
                            if img.dtype != np.uint8:
                                img = (img * 255).clip(0, 255).astype(np.uint8)
                            bare_obs[k] = img

                    viz.log_overlay(bare_obs)

                    precise_sleep(max(0.0, interval - (time.perf_counter() - t0)))

                print(f"  Episodio {ep + 1} terminado.")

    except KeyboardInterrupt:
        print("\nInterrumpido.")
    finally:
        follower.disconnect()
        print("Robot desconectado.")

    return 0
