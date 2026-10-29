"""Métricas de solo lectura: solo recuentos, sin datos personales, y solo con el token."""
from radar import config, cortos, metricas, newsletter
from radar.agentes import regalos

from .test_radar import _dar_negocio, _registrar, app_aislada, sin_claves_reales  # noqa: F401


def test_metricas_sin_datos_personales(app_aislada, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    _registrar(app_aislada, "duena@ejemplo.com")
    nid = _dar_negocio("duena@ejemplo.com")
    regalos.guardar(nid, palabra="SKILL", destino="https://gravity.ejemplo/?r=SKILL")
    cortos.contar("skill", "Mozilla iPhone")
    newsletter._recientes.clear()
    newsletter.suscribir("gravity", {"nombre": "Ana", "email": "ana@ejemplo.com", "acepto": "si", "origen": "skill"}, "1")
    assert app_aislada.get("/metricas/malo.json?negocio=1").status_code == 404
    r = app_aislada.get(f"/metricas/{metricas.token()}.json", params={"negocio": nid, "lista": "gravity"})
    assert r.status_code == 200
    d = r.json()
    assert d["regalos"][0]["palabra"] == "SKILL" and d["regalos"][0]["clics"] == 1 and d["regalos"][0]["correos"] == 1
    assert d["newsletter"]["altas"] == 1 and d["newsletter"]["por_origen"] == {"SKILL": 1}
    assert "ana" not in r.text.lower()
