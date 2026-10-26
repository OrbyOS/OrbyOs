#!/usr/bin/env bash
# Publica la app en un servidor Ubuntu con un solo comando, desde tu ordenador:
#   ./desplegar.sh 203.0.113.10                  (sin dominio: https://203-0-113-10.sslip.io)
#   ./desplegar.sh 203.0.113.10 app.midominio.com (con un dominio que apunte a esa IP)
# Instala Docker si falta, copia la app (sin tus datos locales ni tu .env), crea el .env del servidor la primera vez y
# arranca Radar con https. Volver a lanzarlo actualiza la app sin tocar los datos del servidor.
set -euo pipefail
IP="${1:?Uso: ./desplegar.sh <IP del servidor> [dominio]}"
DOMINIO="${2:-$(echo "$IP" | tr . -).sslip.io}"
CLAVE="${RADAR_CLAVE_SSH:-$HOME/.ssh/radar_servidor}"
SSH=(ssh -i "$CLAVE" -o StrictHostKeyChecking=accept-new "root@$IP")
cd "$(dirname "$0")"

echo "→ Copiando la app a $IP…"
"${SSH[@]}" "mkdir -p /opt/radar"
rsync -az --delete -e "ssh -i $CLAVE -o StrictHostKeyChecking=accept-new" \
  --exclude .venv --exclude data --exclude datos --exclude .env --exclude '__pycache__' --exclude '.pytest_cache' --exclude node_modules \
  --exclude tests ./ "root@$IP:/opt/radar/"

echo "→ Preparando el servidor…"
"${SSH[@]}" DOMINIO="$DOMINIO" bash -s <<'REMOTO'
set -euo pipefail
cd /opt/radar
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
if command -v ufw >/dev/null; then
  ufw allow 22/tcp >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null; ufw --force enable >/dev/null
fi
mkdir -p datos
if [ ! -f .env ]; then
  cp .env.example .env
  echo "→ .env nuevo para https://$DOMINIO"
fi
# Si cambia la dirección, la antigua queda redirigiendo a la nueva (los enlaces ya enviados siguen funcionando).
ANTERIOR=$(grep '^RADAR_DOMINIO=' .env | cut -d= -f2- || true)
if [ -n "$ANTERIOR" ] && [ "$ANTERIOR" != "$DOMINIO" ]; then
  grep -q '^RADAR_DOMINIO_ANTIGUO=' .env && sed -i "s|^RADAR_DOMINIO_ANTIGUO=.*|RADAR_DOMINIO_ANTIGUO=$ANTERIOR|" .env || \
    echo "RADAR_DOMINIO_ANTIGUO=$ANTERIOR" >> .env
  echo "→ $ANTERIOR redirigirá a https://$DOMINIO"
fi
grep -q '^RADAR_DOMINIO=' .env && sed -i "s|^RADAR_DOMINIO=.*|RADAR_DOMINIO=$DOMINIO|" .env || echo "RADAR_DOMINIO=$DOMINIO" >> .env
# Abierta a más gente: cada cuenta conecta sus claves (Claude por la API, Apify, YouTube, Zernio, ManyChat).
for ajuste in RADAR_CLAVES_COMPARTIDAS=0 RADAR_MOTOR=api RADAR_REGISTRO_ABIERTO=1; do
  grep -q "^${ajuste%%=*}=" .env && sed -i "s|^${ajuste%%=*}=.*|$ajuste|" .env || echo "$ajuste" >> .env
done
# El nombre de la app (sale en la landing y en toda la app). Solo si aún no se ha puesto otro a mano.
grep -q '^APP_NOMBRE=' .env || echo "APP_NOMBRE=Orby" >> .env
grep -q '^RADAR_URL_GITHUB=' .env || echo "RADAR_URL_GITHUB=https://github.com/OrbyOS/OrbyOs" >> .env
grep -q '^RADAR_URL_SOLICITAR=' .env || echo "RADAR_URL_SOLICITAR=/#solicitar" >> .env   # el formulario de la propia landing
grep -q '^RADAR_URL_PUBLICA=' .env && sed -i "s|^RADAR_URL_PUBLICA=.*|RADAR_URL_PUBLICA=https://$DOMINIO|" .env || \
  echo "RADAR_URL_PUBLICA=https://$DOMINIO" >> .env
# Lo guardado desde la app (datos/.env) manda sobre el .env: que tampoco se quede con la dirección antigua.
[ -f datos/.env ] && sed -i "s|^RADAR_URL_PUBLICA=.*|RADAR_URL_PUBLICA=https://$DOMINIO|" datos/.env || true
docker compose up -d --build
# Caddy no se reinicia solo si solo cambia el Caddyfile: que lo vuelva a leer.
docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile >/dev/null 2>&1 || true
docker image prune -f >/dev/null  # las imágenes de versiones anteriores no se quedan ocupando disco
docker compose ps
REMOTO
echo
echo "Listo: https://$DOMINIO"
echo "La primera cuenta que se registre allí es la de administración: entra tú primero."
