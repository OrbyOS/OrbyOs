"""Mejoras del editor: movimiento por marca, palabras de marca, tartamudeos, HDR, volumen y energía de la voz."""
import wave

import numpy as np
from radar import llm
from radar.agentes import identidad
from radar.editor import frases as fr
from radar.editor import graficos, modelo, sonido
from radar.modules import edicion as motor

from .test_radar import _dar_negocio, _otro_cliente, _registrar, app_aislada, sin_claves_reales  # noqa: F401


def _w(word, start, end):
    return {"word": word, "start": start, "end": end}


def test_movimiento_invalido_vuelve_al_de_la_casa():
    m = modelo.movimiento({"gancho": "subida", "choque": "explosion", "otra": "x"})
    assert m["gancho"] == "subida" and m["choque"] == "golpe" and "otra" not in m
    assert modelo.ajustes({"movimiento": {"zooms": "sin"}})["movimiento"]["zooms"] == "sin"
    assert modelo.ajustes({})["movimiento"] == modelo.MOVIMIENTO_BASE


def test_cada_variante_dibuja_sin_romperse():
    for entrada in modelo.MOVIMIENTOS["choque"]:
        c = graficos.Choque("VENDER", 1.5, color="#2F6BFF", entrada=entrada, fondo="velo")
        assert c.fotograma(0.05).getbbox() is not None or entrada != "seco"
        assert c.fotograma(1.0).getbbox() is not None
    for entrada in modelo.MOVIMIENTOS["gancho"]:
        g = graficos.Gancho("Cómo vender sin anuncios", 2.0, color="#2F6BFF", entrada=entrada)
        assert g.fotograma(1.2).getbbox() is not None
    for marca in modelo.MOVIMIENTOS["lista"]:
        assert graficos.Lista(["uno", "dos"], [0, 0.3], 1.5, color="#2F6BFF", marca=marca).fotograma(1).getbbox()


def test_tartamudeo_se_quita_y_se_corta_aunque_no_haya_silencio():
    palabras = [_w("Esto", 0.0, 0.3), _w("que", 0.35, 0.5), _w("que", 0.62, 0.8), _w("lo", 0.85, 1.0),
                _w("no,", 1.1, 1.3), _w("no", 1.4, 1.6), _w("muy", 1.7, 1.9)]
    limpias = motor.sin_tartamudeos(palabras)
    assert [w["word"] for w in limpias] == ["Esto", "que", "lo", "no,", "no", "muy"]
    assert limpias[1]["start"] == 0.62 and limpias[1].get("corte_antes")
    tramos = motor.tramos_hablados(limpias, 2.0, silencio_max=0.4)
    assert len(tramos) == 2 and tramos[0][1] < 0.4 and tramos[1][0] > 0.55


def test_palabras_de_marca_se_escriben_bien():
    palabras = [_w("Uso", 0, .2), _w("many", .3, .5), _w("chat", .5, .7), _w("y", .8, .9), _w("Zernyo.", 1, 1.3),
                _w("casa", 1.4, 1.6)]
    salida = motor.corregir_ortografia(palabras, ["ManyChat", "Zernio"])
    assert [w["word"] for w in salida] == ["Uso", "ManyChat", "y", "Zernio.", "casa"]
    assert salida[1]["start"] == .3 and salida[1]["end"] == .7
    assert identidad.palabras_de("ManyChat, Zernio\nmanychat\n x") == ["ManyChat", "Zernio"]


def test_hdr_solo_se_convierte_si_ffmpeg_sabe(monkeypatch):
    assert motor.filtro_sdr({"hdr": False}) == ""
    monkeypatch.setattr(motor, "_filtros", {"zscale", "tonemap"})
    assert motor.filtro_sdr({"hdr": True}).startswith("zscale=t=linear")
    monkeypatch.setattr(motor, "_filtros", {"tonemap"})
    assert motor.filtro_sdr({"hdr": True}) == ""


def test_volumen_en_dos_pasadas():
    medida = {"input_i": -22.0, "input_tp": -9.0, "input_lra": 4.0, "input_thresh": -32.0, "target_offset": 0.2}
    filtro = sonido.filtro_mezcla([], {}, medida=medida)
    assert "I=-14" in filtro and "measured_I=-22.0" in filtro and "linear=true" in filtro
    assert "measured" not in sonido.filtro_mezcla([], {})


def test_energia_de_la_voz_por_frase(tmp_path):
    tasa = 16000
    t = np.arange(tasa * 3) / tasa
    audio = np.sin(2 * np.pi * 200 * t) * np.where(t < 1, 0.05, np.where(t < 2, 0.6, 0.05))
    ruta = tmp_path / "v.wav"
    with wave.open(str(ruta), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(tasa)
        w.writeframes((audio * 32767).astype(np.int16).tobytes())
    palabras = [_w("bajo.", 0.1, 0.9), _w("FUERTE", 1.1, 1.5), _w("FUERTE.", 1.55, 1.9), _w("bajo.", 2.1, 2.9)]
    frases = fr.partir(palabras)
    fr.medir_voz(ruta, frases, palabras)
    assert frases[1]["energia"] > 0 > frases[0]["energia"]
    assert frases[1]["tropiezos"] == 1 and frases[1]["pausa_antes"] > 0


def test_movimiento_en_el_kit_y_propuesta(app_aislada, monkeypatch):
    _registrar(app_aislada, "duena@ejemplo.com")
    cliente = _otro_cliente(app_aislada, "cliente@ejemplo.com")
    nid = _dar_negocio("cliente@ejemplo.com")
    monkeypatch.setattr(identidad, "preparar_muestra", lambda nid: None)
    r = cliente.post(f"/negocios/{nid}/kit/identidad/movimiento", data={"gancho": "fundido", "zooms": "nada"})
    assert r.status_code in (200, 303)
    m = identidad.leer(nid)["movimiento"]
    assert m["gancho"] == "fundido" and m["zooms"] == "suaves"
    monkeypatch.setattr(llm, "json_con_esquema", lambda *a, **k: {
        "movimiento": {"gancho": "subida", "choque": "foco", "lista": "filete", "subtitulos": "corte",
                       "fondo_texto": "velo", "zooms": "suaves"}, "motivo": "Tu marca es sobria."})
    from radar import db
    ident = identidad.proponer_movimiento(db.negocio(nid))
    assert ident["movimiento"]["choque"] == "foco" and ident["movimiento_propuesto"]


def test_la_muestra_se_hace(app_aislada, tmp_path):
    _registrar(app_aislada, "duena@ejemplo.com")
    _otro_cliente(app_aislada, "cliente@ejemplo.com")
    nid = _dar_negocio("cliente@ejemplo.com")
    destino = identidad.hacer_muestra(nid, tmp_path / "m.mp4")
    assert destino.stat().st_size > 1000


def test_la_muestra_no_esta_lista_mientras_se_escribe(app_aislada, monkeypatch):
    _registrar(app_aislada, "duena@ejemplo.com")
    _otro_cliente(app_aislada, "cliente@ejemplo.com")
    nid = _dar_negocio("cliente@ejemplo.com")
    vistos = []

    def escribiendo(n, destino):
        destino.write_bytes(b"a medias")  # aunque algo deje un archivo, mientras se hace no está «lista»
        vistos.append(identidad.estado_muestra(n))
    monkeypatch.setattr(identidad, "hacer_muestra", escribiendo)
    identidad._haciendo.add(nid)
    identidad._hacer_muestra(nid)
    assert vistos == ["haciendo"] and identidad.estado_muestra(nid) == "lista"
