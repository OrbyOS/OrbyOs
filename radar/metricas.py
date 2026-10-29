"""Métricas de solo lectura para un panel externo: GET /metricas/<token>.json?negocio=<id>&lista=<lista>.

Solo recuentos, sin correos, nombres, usuarios ni IPs. El token se crea solo la primera vez (en la carpeta de datos, no
en el repositorio) y se ve desde el servidor con:  python -m radar.metricas
"""
import secrets
import sys
from datetime import date, timedelta

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from . import config, db

router = APIRouter()
DIAS = 30


def token() -> str:
    archivo = config.DATA_DIR / ".token_metricas"
    if not archivo.exists():
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(secrets.token_urlsafe(24))
    return archivo.read_text().strip()


def resumen(negocio_id: int, lista: str = "") -> dict:
    from .agentes import regalos
    desde = (date.today() - timedelta(days=DIAS - 1)).isoformat()
    salida = {"negocio": negocio_id, "generado": date.today().isoformat(), "regalos": []}
    with db.conexion() as con:
        for r in regalos.lista(negocio_id):
            boton = con.execute("SELECT COUNT(*) FROM envios_ig WHERE negocio_id = ? AND palabra = ? AND fase IN "
                                "('enlace', 'preguntado', 'caducado') AND enlace_en != ''",
                                (negocio_id, r["palabra"])).fetchone()[0]
            clics_dia = {f["dia"]: f["clics"] for f in con.execute(
                "SELECT dia, clics FROM clics_cortos WHERE nombre = ? AND dia >= ? ORDER BY dia", (r["corto"], desde))}
            salida["regalos"].append({"palabra": r["palabra"], "activa": r["activa"], "enlace": r["enlace_corto"],
                                      "comentarios": r["comentarios"], "privados": r["privados"], "boton": boton,
                                      "clics": r["clics"], "clics_por_dia": clics_dia, "correos": r["correos"],
                                      "ultimo": r["ultimo"]})
        if lista:
            def contar(sql: str, *args) -> int:
                return con.execute(sql, (lista,) + args).fetchone()[0]
            salida["newsletter"] = {
                "lista": lista,
                "altas": contar("SELECT COUNT(*) FROM suscriptores WHERE lista = ?"),
                "activas": contar("SELECT COUNT(*) FROM suscriptores WHERE lista = ? AND baja = ''"),
                "bajas": contar("SELECT COUNT(*) FROM suscriptores WHERE lista = ? AND baja != ''"),
                "por_dia": {f[0]: f[1] for f in con.execute(
                    "SELECT substr(creado, 1, 10), COUNT(*) FROM suscriptores WHERE lista = ? AND creado >= ? "
                    "GROUP BY 1 ORDER BY 1", (lista, desde))},
                "por_origen": {(f[0] or "-"): f[1] for f in con.execute(
                    "SELECT origen, COUNT(*) FROM suscriptores WHERE lista = ? GROUP BY origen ORDER BY 2 DESC", (lista,))},
                "kit": {"ok": contar("SELECT COUNT(*) FROM suscriptores WHERE lista = ? AND kit = 'ok'"),
                        "desde_navegador": contar("SELECT COUNT(*) FROM suscriptores WHERE lista = ? AND "
                                                  "kit = 'navegador'"),
                        "pendientes": contar("SELECT COUNT(*) FROM suscriptores WHERE lista = ? AND kit = '' AND "
                                             "kit_error = ''"),
                        "fallidos": contar("SELECT COUNT(*) FROM suscriptores WHERE lista = ? AND kit = '' AND "
                                           "kit_error != ''"),
                        "ultimo_error": (con.execute("SELECT kit_error FROM suscriptores WHERE lista = ? AND "
                                                     "kit_error != '' ORDER BY id DESC LIMIT 1", (lista,)).fetchone()
                                         or [""])[0]},
            }
    return salida


@router.get("/metricas/{valor}.json")
def metricas(valor: str, negocio: int = 0, lista: str = ""):
    if not secrets.compare_digest(valor, token()) or not negocio:
        return JSONResponse({"error": "no encontrado"}, status_code=404)
    return resumen(negocio, lista)


if __name__ == "__main__":
    db.iniciar()
    print(f"{config.URL_PUBLICA or 'https://<tu-dominio>'}/metricas/{token()}.json?negocio=1&lista=gravity  "
          "(cambia el número del negocio y la lista si hace falta)")
    sys.exit(0)
