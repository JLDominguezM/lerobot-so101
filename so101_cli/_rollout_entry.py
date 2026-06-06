"""Shim para lerobot-rollout que registra el tipo de cámara 'depthai' antes del parseo."""

from __future__ import annotations

from so101_cli import depthaicamera  # noqa: F401  (registra el tipo "depthai")

from lerobot.scripts.lerobot_rollout import main

if __name__ == "__main__":
    main()
