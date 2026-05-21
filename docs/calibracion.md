# Calibración del SO-101

La calibración define para cada joint:

- **Homing position** — el cero lógico.
- **Mid-range** — la posición media del rango.
- **Max-range** — los límites físicos.

Se guarda en archivos JSON bajo `~/.cache/huggingface/lerobot/calibration/<robot_type>/<id>.json`. El `id` viene de `configs/follower.yaml` y `configs/leader.yaml`.

## Por qué importa

LeRobot mapea los ticks del encoder a radianes usando estos límites. Si calibras mal el follower, los comandos del leader llegarán "desfasados" — el brazo no irá donde tu mano va. Si calibras dos veces con `id` distinto, terminarás con dos JSONs y los scripts no sabrán cuál usar.

## Cuándo recalibrar

- Después de armar el brazo por primera vez (obligatorio).
- Si desarmas y vuelves a armar un joint.
- Si los motores pierden referencia (raro, pero pasa si fuerzas el brazo contra un tope con la corriente apagada).
- **No es necesario** entre sesiones normales de uso.

## Procedimiento

Asegúrate de que los puertos están definidos en `configs/*.yaml` y que el `id` es estable (no lo cambies entre corridas).

```bash
# Ambos brazos en secuencia
bash scripts/02_calibrate.sh both

# O uno a la vez
bash scripts/02_calibrate.sh follower
bash scripts/02_calibrate.sh leader
```

El comando es interactivo:

1. Te pide mover el brazo a la posición de "homing" (típicamente brazo extendido hacia adelante, gripper cerrado).
2. Te pide mover cada joint a sus extremos para registrar el rango.
3. Guarda el JSON.

## Versionar las calibraciones

Por defecto LeRobot guarda los JSONs fuera del repo (`~/.cache/...`). Si quieres versionarlos:

```bash
# Después de calibrar
cp ~/.cache/huggingface/lerobot/calibration/so101_follower/follower_principal.json \
   calibrations/

cp ~/.cache/huggingface/lerobot/calibration/so101_leader/leader_principal.json \
   calibrations/

git add calibrations/
git commit -m "calibrate: snapshot inicial"
```

Esto permite que otra computadora reuse la calibración (útil si todos los brazos se calibraron en el mismo lab y los IDs lógicos coinciden).
