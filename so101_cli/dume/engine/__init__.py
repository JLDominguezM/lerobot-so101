"""Engine de DUM-E: sondeo de estado, inventario local y runner suspend-and-run.

Capa sin UI — sólo lee estado o lanza subprocesos. Las vistas Textual la usan
desde workers para no bloquear el hilo de render.
"""
