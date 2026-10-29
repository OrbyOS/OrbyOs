"""Enlaces cortos de la instalación (<dirección>/r/<nombre>) que llevan a otro sitio y cuentan los clics por día.

Sirven para los regalos de la palabra clave: el DM lleva el enlace corto, y así se sabe cuántos lo abren. Se añaden y
se cambian sin desplegar, desde el servidor:
    docker compose exec -T radar python -m radar.cortos --ayuda
No cuentan las visitas de robots (las vistas previas de Instagram, WhatsApp o Telegram al pegar el enlace).
"""
import re
import sys
from datetime import date, datetime, timedelta

from . import db

ROBOTS = re.compile(r"bot|crawl|spider|preview|facebookexternalhit|meta-externalagent|whatsapp|telegram|slack|discord|"
                    r"curl|wget|python|httpx", re.I)


def _nombre(nombre: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", (nombre or "").strip().lower())[:40]


def poner(nombre: str, destino: str, negocio_id: int = 0) -> dict:
    nombre, destino = _nombre(nombre), (destino or "").strip()
    if not nombre or not destino.startswith(("https://", "http://")):
        raise ValueError("Hace falta un nombre (letras, números o guiones) y un destino que empiece por https://.")
    with db.conexion() as con:
        con.execute("INSERT INTO enlaces_cortos (nombre, destino, creado, negocio_id) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(nombre) DO UPDATE SET destino = excluded.destino",
                    (nombre, destino, datetime.now().isoformat(timespec="seconds"), negocio_id))
    return {"nombre": nombre, "destino": destino}


def quitar(nombre: str) -> bool:
    with db.conexion() as con:
        return con.execute("DELETE FROM enlaces_cortos WHERE nombre = ?", (_nombre(nombre),)).rowcount > 0


def destino(nombre: str) -> str:
    with db.conexion() as con:
        f = con.execute("SELECT destino FROM enlaces_cortos WHERE nombre = ?", (_nombre(nombre),)).fetchone()
    return f["destino"] if f else ""


def contar(nombre: str, agente: str = "", dia: date | None = None) -> bool:
    if ROBOTS.search(agente or ""):
        return False
    with db.conexion() as con:
        con.execute("INSERT INTO clics_cortos (nombre, dia, clics) VALUES (?, ?, 1) "
                    "ON CONFLICT(nombre, dia) DO UPDATE SET clics = clics + 1",
                    (_nombre(nombre), (dia or date.today()).isoformat()))
    return True


def todos() -> list[dict]:
    with db.conexion() as con:
        return [dict(f) for f in con.execute(
            "SELECT e.nombre, e.destino, e.creado, COALESCE(SUM(c.clics), 0) AS clics FROM enlaces_cortos e "
            "LEFT JOIN clics_cortos c ON c.nombre = e.nombre GROUP BY e.nombre ORDER BY e.nombre")]


def clics(nombre: str = "", dias: int = 14) -> list[dict]:
    """[{nombre, dia, clics}] de los últimos `dias` días, del más reciente al más antiguo."""
    desde = (date.today() - timedelta(days=dias - 1)).isoformat()
    sql, args = "SELECT nombre, dia, clics FROM clics_cortos WHERE dia >= ?", [desde]
    if nombre:
        sql, args = sql + " AND nombre = ?", args + [_nombre(nombre)]
    with db.conexion() as con:
        return [dict(f) for f in con.execute(sql + " ORDER BY dia DESC, nombre", args)]


AYUDA = """Uso (dentro del contenedor: docker compose exec -T radar python -m radar.cortos …):
  lista                          los enlaces, su destino y sus clics en total
  poner <nombre> <destino>       crea o cambia /r/<nombre>
  quitar <nombre>
  clics [<nombre>] [--dias N]    clics por enlace y día (14 días por defecto)"""


def main(args: list[str]) -> int:
    db.iniciar()
    dias = 14
    if "--dias" in args:
        i = args.index("--dias")
        dias = int(args[i + 1])
        del args[i:i + 2]
    orden = args[0] if args else ""
    if orden == "lista":
        for e in todos():
            print(f"/r/{e['nombre']:<12} {e['clics']:>6} clics  → {e['destino']}")
    elif orden == "poner" and len(args) == 3:
        e = poner(args[1], args[2])
        print(f"/r/{e['nombre']} → {e['destino']}")
    elif orden == "quitar" and len(args) == 2:
        print("quitado" if quitar(args[1]) else "no estaba")
    elif orden == "clics":
        for f in clics(args[1] if len(args) > 1 else "", dias):
            print(f"{f['dia']}  /r/{f['nombre']:<12} {f['clics']}")
    else:
        print(AYUDA)
        return 0 if orden in ("", "--ayuda", "-h") else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
