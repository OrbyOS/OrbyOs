"""Plan gratis: lo que cuesta a la instalación lleva a su puerta falsa y apunta el interés; el resto, igual."""
from radar import db, newsletter, planes

from .test_radar import _dar_negocio, _otro_cliente, _registrar, app_aislada, sin_claves_reales  # noqa: F401


def test_puertas_falsas_del_plan_gratis(app_aislada):
    _registrar(app_aislada, "admin@ejemplo.com")
    cliente = _otro_cliente(app_aislada, "gratis@ejemplo.com")
    uid = db.usuario_por_email("gratis@ejemplo.com")["id"]
    db.actualizar_usuario(uid, plan="gratis")
    nid = _dar_negocio("gratis@ejemplo.com")
    r = cliente.post(f"/negocios/{nid}/investigacion/escanear", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == f"/negocios/{nid}/mejorar?funcion=investigacion"
    assert cliente.post(f"/negocios/{nid}/produccion/subir", follow_redirects=False).headers["location"].endswith("edicion")
    assert cliente.get(f"/negocios/{nid}/conectores/instagram/conectar",
                       follow_redirects=False).headers["location"].endswith("funcion=comunidad")
    assert cliente.get(f"/negocios/{nid}/mejorar?funcion=edicion").status_code == 200
    # Ver páginas y lo que solo usa su Claude sigue igual
    assert cliente.get(f"/negocios/{nid}/investigacion").status_code == 200
    assert planes.funcion_de("POST", f"/negocios/{nid}/guiones/pedir") is None
    newsletter._recientes.clear()
    r = cliente.post(f"/negocios/{nid}/mejorar", data={"funcion": "edicion", "acepto": "si"}, follow_redirects=False)
    assert r.headers["location"].endswith("apuntado=1")
    assert newsletter.suscriptores("orby")[0]["email"] == "gratis@ejemplo.com"
    resumen = {f["funcion"]: f for f in planes.resumen_interes()}
    assert resumen["edicion"]["intentos"] == 1 and resumen["edicion"]["avisame"] == 1
    assert resumen["investigacion"]["intentos"] == 1


def test_sin_puertas_fuera_del_plan_gratis(app_aislada):
    _registrar(app_aislada, "admin@ejemplo.com")
    nid = _dar_negocio("admin@ejemplo.com")
    r = app_aislada.post(f"/negocios/{nid}/investigacion/escanear", follow_redirects=False)
    assert "/mejorar" not in r.headers.get("location", "")


def test_aviso_emergente(app_aislada):
    _registrar(app_aislada, "admin@ejemplo.com")
    cliente = _otro_cliente(app_aislada, "gratis@ejemplo.com")
    db.actualizar_usuario(db.usuario_por_email("gratis@ejemplo.com")["id"], plan="gratis")
    nid = _dar_negocio("gratis@ejemplo.com")
    r = cliente.post(f"/negocios/{nid}/produccion/subir", headers={"Accept": "application/json"})
    assert r.status_code == 402 and r.json()["puerta"] == "edicion" and "premium" in r.json()["texto"]
    newsletter._recientes.clear()
    r = cliente.post(f"/negocios/{nid}/mejorar", headers={"Accept": "application/json"},
                     data={"funcion": "edicion", "acepto": "si", "email": "otra@ejemplo.com"})
    assert r.json() == {"ok": True} and newsletter.suscriptores("orby")[0]["email"] == "otra@ejemplo.com"
