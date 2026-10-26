#!/bin/bash
# Instala Radar en este ordenador (macOS o Linux) y lo abre en el navegador.
#   bash instalar.sh
set -e
cd "$(dirname "$0")"
DIR="$(pwd)"
echo "Instalando Radar en $DIR"

# 1. Python 3.11 o más reciente
PY=""
for p in python3.12 python3.13 python3.11 python3; do
  if command -v "$p" >/dev/null 2>&1 && "$p" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then PY="$p"; break; fi
done
if [ -z "$PY" ]; then
  echo "Falta Python 3.11 o más reciente."
  if [ "$(uname)" = "Darwin" ]; then echo "Instálalo con:  brew install python@3.12   (o desde python.org) y vuelve a ejecutar este archivo."
  else echo "Instálalo con:  sudo apt install python3.12 python3.12-venv   y vuelve a ejecutar este archivo."; fi
  exit 1
fi

# 2. ffmpeg, para editar los vídeos
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Falta ffmpeg (lo usa el editor de vídeo)."
  if [ "$(uname)" = "Darwin" ]; then echo "Instálalo con:  brew install ffmpeg   y vuelve a ejecutar este archivo."
  else echo "Instálalo con:  sudo apt install ffmpeg   y vuelve a ejecutar este archivo."; fi
  exit 1
fi

# 3. Entorno y dependencias
[ -d .venv ] || "$PY" -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
chmod 600 .env

# 4. Un acceso directo para abrirlo con doble clic (macOS)
if [ "$(uname)" = "Darwin" ]; then
  cat > "Abrir Radar.command" <<LANZADOR
#!/bin/bash
# Doble clic para abrir Radar. Para cerrarlo, cierra esta ventana.
URL="http://localhost:8000"
if curl -s -o /dev/null "\$URL"; then open "\$URL"; exit 0; fi
cd "$DIR" || exit 1
( for i in \$(seq 1 40); do sleep 1; curl -s -o /dev/null "\$URL" && open "\$URL" && break; done ) &
./arrancar.sh
LANZADOR
  chmod +x "Abrir Radar.command"
  echo "Listo. Para abrirlo: doble clic en «Abrir Radar.command»."
fi

# 5. Claude: con tu plan (Claude Code) o con una clave de la API
if command -v claude >/dev/null 2>&1; then
  echo "He encontrado Claude Code: en Administración → Claves y ajustes puedes elegir «Mi plan de Claude»."
else
  echo "Para usar tu plan de Claude, instala Claude Code (https://code.claude.com). Si no, pega una clave de la API en la app."
fi

URL="http://localhost:${PORT:-8000}"
echo "Arrancando Radar en $URL … La primera cuenta que crees será la de administración."
( for i in $(seq 1 60); do sleep 1; curl -s -o /dev/null "$URL" && { command -v open >/dev/null && open "$URL" || xdg-open "$URL" >/dev/null 2>&1 || true; } && break; done ) &
exec ./arrancar.sh
