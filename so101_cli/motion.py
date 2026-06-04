"""Interpolación de movimientos suaves para el follower."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from . import viz
from .poses import JOINTS, positions_to_action

if TYPE_CHECKING:
    from lerobot.robots.so_follower.so_follower import SOFollower


def read_current(robot: "SOFollower") -> dict[str, float]:
    """Posición actual del follower como dict joint -> grados."""
    obs = robot.get_observation()
    current = {j: obs[f"{j}.pos"] for j in JOINTS}
    viz.log_positions(current, source="follower")
    return current


def interpolate_move(
    robot: "SOFollower",
    target: dict[str, float],
    duration: float,
    rate: float,
    max_deg_per_s: float,
    verbose: bool = True,
) -> None:
    """Mueve suavemente desde la posición actual hasta target en `duration` segundos.

    Usa perfil smoothstep (arranca y termina con velocidad cero) y respeta
    `max_deg_per_s` como velocidad pico — si la duración pedida implica más,
    la extiende automáticamente.
    """
    start = read_current(robot)

    max_delta = max(abs(target[j] - start[j]) for j in JOINTS)
    min_duration_for_speed = max_delta / max_deg_per_s if max_deg_per_s > 0 else 0.0
    if duration < min_duration_for_speed:
        if verbose:
            print(
                f"  (extendiendo duración: {duration:.2f}s -> {min_duration_for_speed:.2f}s "
                f"para respetar {max_deg_per_s}°/s)"
            )
        duration = min_duration_for_speed

    if duration <= 0:
        action = positions_to_action(target)
        robot.send_action(action)
        viz.log_positions(action, source="target")
        return

    n_steps = max(2, int(duration * rate))
    dt = duration / n_steps
    for k in range(1, n_steps + 1):
        alpha = k / n_steps
        s = alpha * alpha * (3.0 - 2.0 * alpha)  # smoothstep
        action = {f"{j}.pos": start[j] + s * (target[j] - start[j]) for j in JOINTS}
        robot.send_action(action)
        viz.log_positions(action, source="target")
        time.sleep(dt)
