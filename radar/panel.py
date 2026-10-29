"""Panel en vivo: los recuentos de radar/metricas.py (regalos y newsletter) dentro del área del negocio.

GET /negocios/<id>/panel           la página
GET /negocios/<id>/panel?parcial=1 solo el bloque de cifras (la página lo pide cada 20 s)

Las listas de la newsletter no van ligadas a un negocio: se ven las que en newsletter.json llevan «negocio» con su id
y, si quien mira administra la instalación, todas.
"""
from datetime import date, timedelta

from fastapi import APIRouter, Request

from . import db, metricas, newsletter

router = APIRouter()
_pagina = _espacio = _datos_espacio = None


def configurar(pagina, espacio, datos_espacio):
    global _pagina, _espacio, _datos_espacio
    _pagina, _espacio, _datos_espacio = pagina, espacio, datos_espacio


def _listas(negocio_id: int, admin: bool) -> list[str]:
    ajustes = newsletter.ajustes_listas()
    propias = [n for n, a in ajustes.items() if str((a or {}).get("negocio", "")) == str(negocio_id)]
    if admin:
        with db.conexion() as con:
            propias += [f[0] for f in con.execute("SELECT DISTINCT lista FROM suscriptores ORDER BY lista")]
    return list(dict.fromkeys(propias))


def _dias(n: int = metricas.DIAS) -> list[str]:
    hoy = date.today()
    return [(hoy - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def datos(negocio_id: int, admin: bool) -> dict:
    base = metricas.resumen(negocio_id)
    regalos = base["regalos"]
    total = {k: sum(r[k] for r in regalos) for k in ("comentarios", "privados", "boton", "clics", "correos")}
    dias = _dias()
    clics = [sum(r["clics_por_dia"].get(d, 0) for r in regalos) for d in dias]
    listas = []
    for nombre in _listas(negocio_id, admin):
        n = metricas.resumen(negocio_id, nombre).get("newsletter") or {}
        n["serie"] = [n.get("por_dia", {}).get(d, 0) for d in dias]
        n["hoy"] = n["serie"][-1]
        n["semana"] = sum(n["serie"][-7:])
        listas.append(n)
    altas = [sum(n["serie"][i] for n in listas) for i in range(len(dias))]
    return {"regalos": regalos, "total": total, "dias": dias, "clics": clics, "altas": altas, "listas": listas,
            "clics_hoy": clics[-1], "clics_semana": sum(clics[-7:]), "altas_hoy": altas[-1],
            "altas_semana": sum(altas[-7:]), "pico": max(clics + altas + [1])}


@router.get("/negocios/{negocio_id}/panel")
def ver_panel(request: Request, negocio_id: int, parcial: int = 0):
    u, neg, inf = _espacio(request, negocio_id)
    p = datos(negocio_id, bool(u.get("es_admin")))
    return _pagina(request, "_panel_vivo.html" if parcial else "panel.html", vista="panel", p=p,
                   **_datos_espacio(u, neg, inf))
