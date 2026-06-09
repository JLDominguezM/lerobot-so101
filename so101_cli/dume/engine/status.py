"""Sonda de conexión: envuelve diagnostics (abrir→ping→cerrar) SIN retener hardware.

Cada sonda abre, consulta y cierra de inmediato — no se queda con el bus serial
ni con las cámaras (son recursos exclusivos; retenerlos rompería teleop/record).
Pensado para correr dentro de un worker con hilo, porque las llamadas a
diagnostics son bloqueantes.

Reusa, sin tocarlas, las funciones de so101_cli/diagnostics.py, que ya atrapan
sus propios errores de hardware y devuelven una tupla (label, ok, detail).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProbeResult:
    label: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class ConnectionStatus:
    follower: ProbeResult
    leader: ProbeResult
    front: ProbeResult
    lateral: ProbeResult

    @property
    def items(self) -> list[ProbeResult]:
        return [self.follower, self.leader, self.front, self.lateral]

    @property
    def n_ok(self) -> int:
        return sum(1 for r in self.items if r.ok)

    @property
    def n_total(self) -> int:
        return len(self.items)

    @property
    def all_ok(self) -> bool:
        return all(r.ok for r in self.items)


def _safe(label: str, fn, *args) -> ProbeResult:
    """Llama a una función de diagnostics y nunca propaga: degrada a ✗ con motivo."""
    try:
        rlabel, ok, detail = fn(*args)
        return ProbeResult(label=rlabel or label, ok=bool(ok), detail=detail)
    except Exception as e:  # defensa extra: diagnostics ya atrapa, pero por si acaso
        return ProbeResult(label=label, ok=False, detail=f"error: {e}")


def probe_connection(
    check_leader: bool = True,
    check_front: bool = True,
    check_lateral: bool = True,
) -> ConnectionStatus:
    """Sondea follower/leader/front/lateral una vez. Seguro sin hardware."""
    from ... import diagnostics

    follower = _safe("follower (motores)", diagnostics._check_arm, "follower")
    leader = (
        _safe("leader (motores)", diagnostics._check_arm, "leader")
        if check_leader
        else ProbeResult("leader (motores)", False, "omitido")
    )
    front = (
        _safe("front (RealSense)", diagnostics._check_front)
        if check_front
        else ProbeResult("front (RealSense)", False, "omitido")
    )
    lateral = (
        _safe("lateral (OAK-D)", diagnostics._check_lateral)
        if check_lateral
        else ProbeResult("lateral (OAK-D)", False, "omitido")
    )
    return ConnectionStatus(follower, leader, front, lateral)
