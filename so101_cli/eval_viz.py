"""Subcomando top-level: ./cal eval-viz

Corre la policy entrenada en el robot real y la visualiza en rerun.

  - Policy ACT (ResNet-18): muestra un heatmap de activaciones por cámara — la
    magnitud L2 del último conv. Indica si el modelo mira el cable o el fondo.
    (No es "atención" transformer.)
  - Policy SmolVLA (SigLIP + transformer): heatmap de la magnitud L2 por patch
    del vision encoder SigLIP (rejilla 32x32; imagen 512, patch 16) — el análogo
    VLA del heatmap de ResNet. Muestra qué parches "encienden" al decidir la
    acción.

Ambos tipos comparten la misma salida: rerun en <cam>/image|attention|overlay
(con blueprint propio) y, además, una rejilla mp4 en outputs/ + ventana en vivo
con --cv2. El tipo se detecta automáticamente del config.json del checkpoint.

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


def _compose_grid_bgr(bare_obs, last_hm, order):
    """Rejilla BGR para OpenCV/mp4: una fila por cámara = [image | attention | overlay].

    `bare_obs` y `last_hm` vienen en RGB; aquí convertimos a BGR (lo que esperan
    cv2.imshow / VideoWriter). Si aún no hay heatmap para una cámara, las columnas
    attention/overlay salen en negro / imagen cruda.
    """
    import cv2
    import numpy as np

    rows = []
    for name in order:
        img = bare_obs.get(name)
        if img is None:
            continue
        img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        hm = last_hm.get(name)
        if hm is not None:
            hm_bgr = cv2.cvtColor(hm, cv2.COLOR_RGB2BGR)
            ov_bgr = cv2.addWeighted(img_bgr, 0.55, hm_bgr, 0.45, 0)
        else:
            hm_bgr = np.zeros_like(img_bgr)
            ov_bgr = img_bgr.copy()
        trio = []
        for panel, lbl in [(img_bgr, f"{name} image"),
                           (hm_bgr, f"{name} attention"),
                           (ov_bgr, f"{name} overlay")]:
            p = panel.copy()
            cv2.rectangle(p, (0, 0), (p.shape[1], 24), (0, 0, 0), -1)
            cv2.putText(p, lbl, (6, 17), cv2.FONT_HERSHEY_SIMPLEX,
                        0.55, (255, 255, 255), 1, cv2.LINE_AA)
            trio.append(p)
        rows.append(np.hstack(trio))
    if not rows:
        return None
    w = max(r.shape[1] for r in rows)
    rows = [r if r.shape[1] == w
            else cv2.copyMakeBorder(r, 0, 0, 0, w - r.shape[1], cv2.BORDER_CONSTANT)
            for r in rows]
    return np.vstack(rows)


def _tokens_to_heat_rgb(lhs, out_hw):
    """Tokens de patch del SigLIP -> heatmap RGB uint8 (out_hw=(H,W)).

    Toma la magnitud L2 por patch del last_hidden_state [B,N,D], la reacomoda a la
    rejilla cuadrada (N=1024 -> 32x32), normaliza 0..1, la sube al tamaño de la
    cámara y le aplica un colormap JET. Es el análogo SmolVLA del heatmap ResNet
    de ACT: parches "calientes" = zonas con activación alta del encoder.
    """
    import math

    import cv2
    import numpy as np

    feat = lhs[0].detach().float().cpu().numpy()        # [N, D]
    mag = np.linalg.norm(feat, axis=-1)                 # [N]
    g = int(math.isqrt(mag.shape[0]))
    grid = mag[: g * g].reshape(g, g)
    lo, hi = float(grid.min()), float(grid.max())
    grid = (grid - lo) / (hi - lo + 1e-8)
    heat = cv2.resize((grid * 255).astype(np.uint8), (out_hw[1], out_hw[0]),
                      interpolation=cv2.INTER_CUBIC)
    heat_bgr = cv2.applyColorMap(heat, cv2.COLORMAP_JET)
    return cv2.cvtColor(heat_bgr, cv2.COLOR_BGR2RGB)


def _act_heat_rgb(heat_2d, out_hw):
    """Feature map de ResNet (ACT) -> heatmap RGB uint8 (out_hw=(H,W)).

    `heat_2d` es la magnitud L2 por celda del último conv (H',W'). La subimos a
    la resolución de la cámara (clip al percentil 95 para que los bordes no
    dominen) y le aplicamos un colormap JET — el análogo ACT de
    `_tokens_to_heat_rgb`. Celdas calientes = donde el CNN responde más fuerte.
    """
    import cv2
    import numpy as np
    from lerobot_attention_visualizer import patch_heatmap_to_image

    h = patch_heatmap_to_image(heat_2d, target_hw=tuple(out_hw))  # float [0,1] HxW
    heat_bgr = cv2.applyColorMap((h * 255).astype(np.uint8), cv2.COLORMAP_JET)
    return cv2.cvtColor(heat_bgr, cv2.COLOR_BGR2RGB)


def add_eval_viz_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "eval-viz",
        help="Corre la policy en el robot y visualiza el mapa de activaciones en rerun.",
        description=(
            "Ejecuta la policy en el follower y la muestra en rerun.\n"
            "ACT: heatmap de activaciones ResNet (<cam>/image|attention|overlay).\n"
            "SmolVLA: heatmap de magnitud por patch del encoder SigLIP (<cam>/attention|overlay|image).\n\n"
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
    p.add_argument("--online", action="store_true",
                   help="Permite peticiones a HF Hub. Por defecto corre OFFLINE "
                        "(solo cache local) para evitar el crash por DNS sin internet.")
    p.add_argument("--cv2", action="store_true",
                   help="Muestra una ventana OpenCV en vivo con la rejilla "
                        "image|attention|overlay por cámara (más fiable que rerun).")
    p.add_argument("--no-video", action="store_true",
                   help="No guardar el mp4 de la rejilla (por defecto se guarda en outputs/).")
    p.set_defaults(func=cmd_eval_viz)


def cmd_eval_viz(args: argparse.Namespace) -> int:
    import os

    # Offline por defecto: hay que setear las env vars ANTES de importar
    # huggingface_hub / transformers (las leen al importarse). Evita el crash
    # por HEAD a HF Hub cuando el robot no tiene internet (Errno 8).
    if not args.online:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

    import json

    import time as _time
    from pathlib import Path

    import cv2
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
    print(f"  hub     : {'online (permite descargas)' if args.online else 'OFFLINE (solo cache)'}")
    print(f"  viz     : {'heatmap ResNet (ACT)' if is_act else 'heatmap SigLIP por patch (SmolVLA)'}")
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

    # ACT: heatmap de activaciones ResNet (paquete externo).
    # SmolVLA: hookeamos el vision_model (SigLIP) para capturar el last_hidden_state
    # por imagen y construir un heatmap de magnitud L2 por patch.
    import contextlib
    import rerun as rr

    hook_handle = None
    captured: list = []          # last_hidden_state por imagen, en orden de embed
    embed_order: list[str] = []  # nombres de cámara en el orden que el modelo embebe
    last_hm: dict = {}           # cam -> heatmap RGB (persiste entre forwards del VLM)
    writer = None                # cv2.VideoWriter (lazy: lo abrimos al 1er frame)
    save_video = not args.no_video
    video_path = Path("outputs") / f"eval_viz_{args.color}_{int(_time.time())}.mp4"
    if is_act:
        from lerobot_attention_visualizer import ACTAttention
        viz = ACTAttention(policy)
        embed_order = [k for k in viz.camera_keys() if k in cameras]
        print(f"  → ACT heatmap ResNet por celda sobre: {embed_order}")
    else:
        viz = contextlib.nullcontext()
        vision_model = policy.model.vlm_with_expert.get_vlm_model().vision_model
        hook_handle = vision_model.register_forward_hook(
            lambda m, i, o: captured.append(o.last_hidden_state)
        )
        _short = lambda k: k.split(".")[-1]  # noqa: E731
        embed_order = [_short(k) for k in policy.config.image_features
                       if _short(k) in cameras]
        print(f"  → SmolVLA heatmap SigLIP por patch sobre: {embed_order}")

    # Forzamos un blueprint propio (ACT y SmolVLA): rerun a veces recuerda un
    # layout viejo y deja los paneles en blanco aunque la data SÍ esté logueada.
    # Esto los ata a nuestras entidades <cam>/image|attention|overlay en rejilla.
    try:
        import rerun.blueprint as rrb
        views = []
        for name in embed_order:
            views += [
                rrb.Spatial2DView(origin=f"{name}/image", name=f"{name} image"),
                rrb.Spatial2DView(origin=f"{name}/attention", name=f"{name} attention"),
                rrb.Spatial2DView(origin=f"{name}/overlay", name=f"{name} overlay"),
            ]
        rr.send_blueprint(rrb.Blueprint(rrb.Grid(*views, grid_columns=3)))
    except Exception as e:
        print(f"  (blueprint rerun no aplicado: {e})")

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
                    captured.clear()  # solo nos importan los forwards de ESTE paso

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

                    # Actualiza last_hm (cam -> heatmap RGB) según el tipo de
                    # policy. En ambos casos el heatmap solo se recalcula cuando
                    # hubo un forward fresco del backbone (la cola de action
                    # chunking se vació); si no, se conserva el último para que
                    # los paneles no parpadeen.
                    if is_act:
                        # ACT corre el ResNet una vez por cámara al refrescar la
                        # cola; viz._capture juntó los feature maps de ese forward.
                        heats = viz._capture.activation_heatmaps()
                        if heats and len(heats) == len(embed_order):
                            for name, heat in zip(embed_order, heats):
                                if name in bare_obs:
                                    last_hm[name] = _act_heat_rgb(
                                        heat[0], bare_obs[name].shape[:2])
                        viz._capture.clear()
                    else:
                        if captured and len(captured) == len(embed_order):
                            for name, lhs in zip(embed_order, captured):
                                if name in bare_obs:
                                    last_hm[name] = _tokens_to_heat_rgb(
                                        lhs, bare_obs[name].shape[:2])

                    # Salida unificada (ACT y SmolVLA): rerun + rejilla mp4/cv2.
                    for k, img in bare_obs.items():
                        rr.log(f"cameras/{k}", rr.Image(img))
                        rr.log(f"{k}/image", rr.Image(img))
                        hm = last_hm.get(k)
                        if hm is not None:
                            overlay = cv2.addWeighted(img, 0.55, hm, 0.45, 0)
                            rr.log(f"{k}/attention", rr.Image(hm))
                            rr.log(f"{k}/overlay", rr.Image(overlay))

                    # Rejilla OpenCV (image|attention|overlay) a mp4 y, si --cv2,
                    # también ventana en vivo.
                    grid = _compose_grid_bgr(bare_obs, last_hm, embed_order)
                    if grid is not None:
                        if save_video and writer is None:
                            video_path.parent.mkdir(parents=True, exist_ok=True)
                            writer = cv2.VideoWriter(
                                str(video_path),
                                cv2.VideoWriter_fourcc(*"mp4v"),
                                float(args.fps),
                                (grid.shape[1], grid.shape[0]),
                            )
                        if writer is not None:
                            writer.write(grid)
                        if args.cv2:
                            cv2.imshow("eval-viz  [image | attention | overlay]", grid)
                            cv2.waitKey(1)

                    precise_sleep(max(0.0, interval - (time.perf_counter() - t0)))

                print(f"  Episodio {ep + 1} terminado.")

    except KeyboardInterrupt:
        print("\nInterrumpido.")
    finally:
        if hook_handle is not None:
            hook_handle.remove()
        if writer is not None:
            writer.release()
            print(f"Video guardado: {video_path}")
        if args.cv2:
            cv2.destroyAllWindows()
        # disconnect() puede tirar "Overload error" en un motor (p.ej. el gripper
        # forzado por la extensión): lo atrapamos para no abortar feo el proceso
        # — la grabación de rerun ya está en el viewer de todos modos.
        try:
            follower.disconnect()
            print("Robot desconectado.")
        except Exception as e:
            print(f"Aviso: disconnect() falló ({e}). "
                  f"Revisa el motor reportado (puede estar en sobrecarga).")

    return 0
