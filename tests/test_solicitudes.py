"""«Solicitar implementación» desde la landing: se guarda, se ve en Administración, avisa por Telegram y frena el spam."""
from radar import db, solicitudes
from radar.agentes import jefa

from .test_radar import _dar_negocio, _registrar, app_aislada, sin_claves_reales  # noqa: F401

FORM = {"nombre": "Laura", "email": "laura@ejemplo.com", "negocio": "Mentoría de ventas", "web": "https://laura.es",
        "redes": "@laura", "mensaje": "Quiero el equipo para mi marca."}


def test_la_solicitud_se_guarda_se_ve_y_avisa(app_aislada, monkeypatch):
    admin = _registrar(app_aislada, "duena@ejemplo.com")
    nid = _dar_negocio("duena@ejemplo.com")
    avisos = []
    monkeypatch.setattr(jefa, "conectado", lambda n: n == nid)
    monkeypatch.setattr(jefa, "encolar", lambda n, texto, **k: avisos.append((n, texto)))
    solicitudes._recientes.clear()
    r = app_aislada.post("/solicitar", data=FORM, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/?solicitud=gracias#solicitar"
    s = db.solicitudes()[0]
    assert s["datos"]["negocio"] == "Mentoría de ventas" and s["estado"] == "nueva" and s["datos"]["origen"] == "landing"
    assert avisos and avisos[0][0] == nid and "Laura" in avisos[0][1]
    assert admin.get("/admin").status_code == 200  # la lista la pinta Front-end con `solicitudes`
    admin.post(f"/admin/solicitudes/{s['id']}", data={"estado": "contactada", "notas": "Llamar el lunes"})
    assert db.solicitudes()[0]["estado"] == "contactada" and db.solicitudes()[0]["notas"] == "Llamar el lunes"


def test_trampa_datos_y_limite_por_ip(app_aislada):
    solicitudes._recientes.clear()
    assert solicitudes.recibir({**FORM, "sitio": "http://spam"}, "1.1.1.1") == "gracias" and not db.solicitudes()
    assert solicitudes.recibir({**FORM, "email": "no-es-correo"}, "1.1.1.1") == "faltan"
    for _ in range(solicitudes.POR_IP_HORA):
        assert solicitudes.recibir(FORM, "2.2.2.2") == "gracias"
    assert solicitudes.recibir(FORM, "2.2.2.2") == "espera" and len(db.solicitudes()) == solicitudes.POR_IP_HORA
