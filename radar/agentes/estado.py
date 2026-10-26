"""El estado de cada agente en cada negocio: si está trabajando, cuándo terminó lo último y qué avisos dejó."""
import json
from datetime import datetime

from .. import db


def leer(negocio_id: int, agente: str) -> dict:
    with db.conexion() as con:
        f = con.execute("SELECT datos FROM estado_agentes WHERE negocio_id = ? AND agente = ?",
                        (negocio_id, agente)).fetchone()
    return json.loads(f["datos"]) if f else {}


def cambiar(negocio_id: int, agente: str, **partes) -> dict:
    datos = {**leer(negocio_id, agente), **partes}
    with db.conexion() as con:
        con.execute("INSERT INTO estado_agentes (negocio_id, agente, actualizado, datos) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(negocio_id, agente) DO UPDATE SET actualizado = excluded.actualizado, datos = excluded.datos",
                    (negocio_id, agente, datetime.now().isoformat(timespec="seconds"), json.dumps(datos, ensure_ascii=False)))
    return datos


def interrumpidos():
    """Al arrancar la app, lo que estaba en marcha ya no va a terminar."""
    with db.conexion() as con:
        filas = con.execute("SELECT negocio_id, agente, datos FROM estado_agentes").fetchall()
    for f in filas:
        datos = json.loads(f["datos"])
        if datos.get("trabajando"):
            cambiar(f["negocio_id"], f["agente"], trabajando=False,
                    avisos=(datos.get("avisos") or []) + ["Se cortó: la app se cerró mientras trabajaba."])
