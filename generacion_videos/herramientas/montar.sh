#!/bin/bash
# Monta explicativos de uno en uno, cada uno como la versión siguiente a la última que haya en la carpeta de entrega,
# siempre a través del turno pesado único del equipo si existe (un solo trabajo pesado a la vez: espera a que el Mac esté
# tranquilo y lo lanza con prioridad baja). Uso: generacion_videos/herramientas/montar.sh 59 60
# Solo cuando la dirección general dé turno. La voz y el modelo salen del motor (radar/agentes/generacion.py y el entorno).
# Carpetas: GUIONES, ENTREGA y TURNO_PESADO en el entorno; por defecto, las de la carpeta de la marca (cinco niveles arriba).
cd "$(dirname "$0")/../.." || exit 1
RAIZ="${RAIZ_MARCA:-$(cd ../../.. && pwd)}"
G="${GUIONES:-$RAIZ/Contenido/guiones/orby-explicativos-2026-11}"
O="${ENTREGA:-$RAIZ/Edicion/reels/ENTREGA/orby-explicativos}"
T="${TURNO_PESADO:-$RAIZ/Edicion/herramientas/turno_pesado.sh}"
for num in "$@"; do
  f=$(ls "$G"/${num}_*.json | head -1); n=$(basename "$f" .json)
  v=$(ls "$O" | sed -n "s/^${n}_v\([0-9]*\)\.mp4$/\1/p" | sort -n | tail -1); v=$(( ${v:-0} + 1 ))
  echo "== ${n}_v${v} $(date +%H:%M:%S)"
  if [ -f "$T" ]; then turno=(bash "$T"); else turno=(); fi
  "${turno[@]}" .venv/bin/python -m radar.agentes.generacion "$f" "$O/${n}_v${v}.mp4" 2>&1 | grep -v "older than macOS" | tail -6
  echo "fin ${n}_v${v} $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$O/${n}_v${v}.mp4")"
done
