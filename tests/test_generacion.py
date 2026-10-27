"""La sección de generación de vídeos está oculta mientras el interruptor esté apagado."""
from .test_agentes import _negocio_con_cliente
from .test_radar import app_aislada, sin_claves_reales  # noqa: F401


def test_generacion_oculta_con_el_interruptor_apagado(app_aislada, monkeypatch):
    monkeypatch.delenv("RADAR_GENERACION", raising=False)
    cliente, nid = _negocio_con_cliente(app_aislada)
    assert cliente.get(f"/negocios/{nid}/generacion").status_code == 404
    for pagina in ("kit", "hoy"):
        r = cliente.get(f"/negocios/{nid}/{pagina}")
        assert "/generacion" not in r.text, pagina


def test_generacion_se_ve_con_el_interruptor_encendido(app_aislada, monkeypatch):
    monkeypatch.setenv("RADAR_GENERACION", "1")
    cliente, nid = _negocio_con_cliente(app_aislada)
    assert cliente.get(f"/negocios/{nid}/generacion").status_code == 200


def test_tiempos_de_las_palabras():
    from radar.agentes import generacion
    ws = generacion._palabras_repartidas("Una: buscar ideas", 3.0)
    assert [w["texto"] for w in ws] == ["Una:", "buscar", "ideas"] and ws[0]["t"] == 0 and abs(ws[-1]["fin"] - 3.0) < 0.01
    texto = "Hola mundo"
    ws = generacion._palabras_de_caracteres(texto, [i * 0.1 for i in range(10)], [i * 0.1 + 0.1 for i in range(10)])
    assert ws == [{"texto": "Hola", "t": 0.0, "fin": 0.4}, {"texto": "mundo", "t": 0.5, "fin": 1.0}]


def test_la_voz_pagada_no_se_paga_dos_veces(tmp_path, monkeypatch):
    from radar.agentes import generacion
    llamadas = []

    def falsa(texto, destino, clave, voz):
        llamadas.append(texto)
        destino.write_bytes(b"audio")
        return [{"texto": "Hola", "t": 0.0, "fin": 0.4}]

    monkeypatch.setenv("ELEVENLABS_API_KEY", "prueba")
    monkeypatch.setenv("ELEVENLABS_VOZ", "voz-prueba")
    monkeypatch.setattr(generacion, "VOCES_DIR", tmp_path / "voces")
    monkeypatch.setattr(generacion, "voz_elevenlabs", falsa)
    for i in range(2):
        assert generacion._voz("Hola", tmp_path / f"escena_{i}.wav")[0]["texto"] == "Hola"
        assert (tmp_path / f"escena_{i}.wav").read_bytes() == b"audio"
    assert llamadas == ["Hola"]


def test_el_guion_marca_enfasis_y_golpes():
    from radar.agentes import generacion
    assert generacion._fichas("Uno ^investiga, otro *escribe* y *lo que nunca* ^dirías.") == [
        ("Uno", False, False), ("investiga,", False, True), ("otro", False, False), ("escribe", True, False),
        ("y", False, False), ("lo", True, False), ("que", True, False), ("nunca", True, False), ("dirías.", False, True)]


def test_los_efectos_caen_donde_entra_cada_cosa():
    from radar.agentes import generacion
    planos = [{"tipo": "objetos", "objetos": ["lupa"], "inicio": 0, "fin": 2},
              {"tipo": "lista", "items": ["a", "b"], "golpes": [6, 30], "inicio": 2, "fin": 4}]
    ev = generacion.eventos_de_sonido(planos)
    assert ev[0] == (1.88, "barrido")  # el primer plano es la portada: no suena
    assert [e for _, e in ev[1:]] == ["tic", "tic"] and abs(ev[1][0] - (2 + 14 / 30)) < 1e-9
