# Armado del SO-101

Esta guía solo apunta a la documentación oficial y resume los puntos críticos. Para el procedimiento completo paso a paso (incluye videos por joint), seguir:

- **Docs oficial (instrucciones detalladas + videos):** https://huggingface.co/docs/lerobot/so101
- **Repo de hardware (CAD, BOM, STLs):** https://github.com/TheRobotStudio/SO-ARM100

## Tabla de motores

Ambos brazos comparten geometría, **pero los engranajes del leader son distintos** para que se mueva con poca fuerza.

| Joint           | ID | Follower | Leader |
|-----------------|:--:|:--------:|:------:|
| shoulder_pan    | 1  | 1/345    | 1/191  |
| shoulder_lift   | 2  | 1/345    | 1/345  |
| elbow_flex      | 3  | 1/345    | 1/191  |
| wrist_flex      | 4  | 1/345    | 1/147  |
| wrist_roll      | 5  | 1/345    | 1/147  |
| gripper         | 6  | 1/345    | 1/147  |

**Importante al armar:** verifica que cada motor del leader vaya en el joint correcto según la columna de la derecha. Si los confundes, la teleoperación funcionará pero el balanceo del brazo leader será incómodo.

## Bus eléctrico

- Daisy-chain TTL half-duplex entre los 6 motores (cable JST-XH 3-pin).
- El adaptador Waveshare USB-to-TTL se conecta al primer motor de la cadena.
- **Jumper en canal B (USB)** del adaptador Waveshare — viene marcado en el board.
- Fuente de poder externa por brazo (5V o 7.4V según versión de los motores; ver BOM).

## Identificación de los adaptadores

Cada adaptador tiene un serial leíble por udev. Para distinguir cuál es cuál, ver `udev/99-so101.rules` en este repo.
