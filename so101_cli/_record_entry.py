"""Punto de entrada del subproceso de grabación.

`record-dataset` y `record-batch` lanzan ESTE módulo en vez de
`lerobot.scripts.lerobot_record` directamente por dos razones:

1. Importamos `depthaicamera` antes que nada para registrar el tipo de cámara
   "depthai" en el ChoiceRegistry de LeRobot. Sin esto draccus falla al parsear
   `--robot.cameras='{lateral:{type:depthai,...}}'`.

2. Si la variable de entorno SO101_QUIET=1 está activa (la pone `record-batch`),
   silenciamos el logging de nivel INFO de lerobot. El principal ofensor es
   `logging.info(pformat(asdict(cfg)))` en lerobot_record.py que vuelca toda la
   config en pantalla. Dejamos WARNING+ intacto para que los errores reales sigan
   siendo visibles.
"""

from __future__ import annotations

import os

from so101_cli import depthaicamera  # noqa: F401  (registra el tipo "depthai")

if os.environ.get("SO101_QUIET") == "1":
    # Monkey-patch init_logging ANTES de que lerobot_record lo importe y llame.
    # Reemplazamos el console_level por defecto de INFO a WARNING.
    import lerobot.utils.utils as _lu

    _orig_init_logging = _lu.init_logging

    def _quiet_init_logging(*args, **kwargs):
        kwargs.setdefault("console_level", "WARNING")
        return _orig_init_logging(*args, **kwargs)

    _lu.init_logging = _quiet_init_logging

    # También parchamos la referencia que lerobot_record ya importó con `from ... import`.
    import lerobot.scripts.lerobot_record as _lr
    _lr.init_logging = _quiet_init_logging

from lerobot.scripts.lerobot_record import main

if __name__ == "__main__":
    main()
