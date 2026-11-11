#!/bin/bash
# Arranca Radar en http://localhost:8000
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3.12 -m venv .venv
fi
./.venv/bin/pip install -q -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo "He creado el archivo .env: añade tus claves y vuelve a arrancar."
fi
exec ./.venv/bin/uvicorn radar.main:app --port "${PORT:-8000}"
