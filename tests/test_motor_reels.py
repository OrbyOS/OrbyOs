"""El estilo «De editor»: motor_reels enganchado al editor del SaaS (plan por palabras, saneado, kit desde la
identidad visual y el flujo de Monti con el render simulado)."""
import subprocess

import pytest

from motor_reels.motor import desde_palabras
from motor_reels.motor import validar as motor_validar
from radar import config, db, llm
from radar.agentes import identidad
from radar.editor import flujo, montaje_motor, plan_motor
from radar.modules import edicion

from .test_radar import FICHA, PALABRAS_PRUEBA, _frases, _registrar, al_instante, app_aislada  # noqa: F401


def _ia_simulada(monkeypatch):
    """Claude simulado: devuelve una respuesta mínima que cumple cualquier esquema."""
    def falso(esquema: dict):
        if "enum" in esquema:
            return esquema["enum"][0]
        t = esquema["type"]
        if t == "object":
            return {k: falso(v) for k, v in esquema["properties"].items()}
        if t == "array":
            return [falso(esquema["items"])]
        return {"string": "texto de ejemplo", "number": 1, "integer": 1, "boolean": True}[t]
    monkeypatch.setattr(llm, "disponible", lambda: True)
    monkeypatch.setattr(llm, "json_con_esquema", lambda system, peticion, esquema, **k: falso(esquema))


def _quedan_y_todas():
    frases = _frases()
    frases[1]["quitada"] = True  # «Eh, repito.»
    return plan_motor.material(frases, [dict(w) for w in PALABRAS_PRUEBA])


def test_planos_por_palabras_a_segundos():
    quedan, todas = _quedan_y_todas()
    assert [w["word"] for w in quedan][:3] == ["Tres", "errores.", "Primero"]
    # Un solo plano para todo: se parte en los silencios y en la frase quitada, y cada corte cambia el encuadre.
    m = desde_palabras.convertir({"planos": [{"desde": 0, "hasta": 0, "modo": "recorte", "zoom": 1.0,
                                              "grafico": {"tipo": "titular", "palabra": "Errores", "kicker": 1}}]},
                                 quedan, todas, bruto="b.mp4", kit="k")
    planos = m["planos"]
    assert len(planos) == 3  # «Tres errores.» | «Primero la oferta.» | «Segundo el funnel.»
    assert planos[0]["grafico"]["palabra"] == "Errores" and planos[0]["grafico"]["en"] == planos[0]["src"][0]
    assert planos[0]["zoom"] != planos[1]["zoom"]
    # Ningún tramo pisa «Eh, repito.» (1.6-2.3 s), que se ha quitado.
    assert all(not (p["src"][0] < 2.3 and p["src"][1] > 1.6) for p in planos)
    assert motor_validar.validar(m)[0] == []


def test_sanear_cumple_el_manual():
    titular = {"tipo": "titular", "palabra": "X", "kicker": [], "en": 0}
    m = {"bruto": "b", "kit": "k", "planos": [
        {"id": f"p{i}", "src": [i, i + 1.0], "modo": "recorte", "zoom": 1.0, "entrada": "latigo",
         "grafico": dict(titular, en=i)} for i in range(5)]}
    errores, _ = motor_validar.validar(m)
    assert any("titular" in e for e in errores) and any("transicion" in e for e in errores)
    limpio, hechos = desde_palabras.sanear(m)
    assert motor_validar.validar(limpio)[0] == [] and hechos
    m["planos"][2]["src"] = [0.5, 1.5]  # el discurso no se reordena nunca
    assert any("reordena" in e for e in motor_validar.validar(m)[0])


def test_kit_del_motor_sale_de_la_identidad_visual(app_aislada):
    _registrar(app_aislada, "cliente@ejemplo.com")
    app_aislada.post("/negocios", data=FICHA)
    # Sin paleta: todo se deriva del color de marca (fondo muy oscuro y texto casi blanco).
    kit = identidad.kit_motor(1, "#2F6BFF")
    c = kit["colores"]
    assert sum(int(c["fondo"][i:i + 2], 16) for i in (1, 3, 5)) < 120 and c["texto"] == identidad.TEXTO_MOTOR
    assert kit["fuentes"]["titular"] == identidad.FUENTES_MOTOR["titular"]
    # Con paleta: cada rol sale del «uso» de su color.
    identidad.cambiar(1, colores="#2F6BFF principal\n#081528 fondo\n#A8C0E4 acento\n#FFFFFF texto")
    c = identidad.kit_motor(1)["colores"]
    assert (c["fondo"], c["acento"], c["texto"]) == ("#081528", "#A8C0E4", "#FFFFFF")
    assert c["apagado"].startswith("#FFFFFF") and len(c["apagado"]) == 9


def test_plan_de_editor_con_ia_simulada(monkeypatch):
    _ia_simulada(monkeypatch)
    frases = _frases()
    plan = plan_motor.proponer(frases, [dict(w) for w in PALABRAS_PRUEBA], preferencias=[], bruto="b.mp4", kit="k")
    assert plan["segundos"]["planos"] and motor_validar.validar(plan["segundos"])[0] == []
    basico = plan_motor.basico(frases, [dict(w) for w in PALABRAS_PRUEBA], bruto="b.mp4", kit="k")
    assert basico["segundos"]["planos"][0]["grafico"]["tipo"] == "titular"
    assert motor_validar.validar(basico["segundos"])[0] == []


def test_sin_motor_en_el_servidor_se_monta_con_el_editor_clasico(monkeypatch):
    monkeypatch.setattr(config, "motor_reels_activo", lambda: False)
    from radar.editor import modelo
    assert not modelo.usa_motor({"estilo": "editor"}, "camara")
    monkeypatch.setattr(config, "motor_reels_activo", lambda: True)
    assert modelo.usa_motor({"estilo": "editor"}, "camara") and not modelo.usa_motor({"estilo": "editor"}, "voz")


def _bruto_de_prueba(ruta):
    subprocess.run([config.FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30",
                    "-f", "lavfi", "-i", "sine=frequency=300", "-t", "7", "-shortest", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(ruta)], check=True)


def _negocio_de_editor(app_aislada, monkeypatch):
    """Un negocio con «De editor» recordado en su Kit, Claude simulado y el render de Remotion simulado."""
    _ia_simulada(monkeypatch)
    monkeypatch.setattr(flujo, "en_segundo_plano", al_instante)
    monkeypatch.setattr(edicion, "transcribir", lambda wav, *a, **k: [dict(w) for w in PALABRAS_PRUEBA])
    monkeypatch.setattr(config, "motor_reels_activo", lambda: True)
    recibido = {}

    def render_falso(dir_, *, frases, palabras, montaje_, kit, paso, **k):  # el render de Remotion se prueba aparte
        recibido.update(montaje=montaje_, kit=kit)
        (dir_ / "final.mp4").write_bytes(b"")
        return {"duracion_original": 7.0, "duracion_final": 5.1, "cortes": 2, "efectos": 1, "estilo": "editor",
                "revision": {"arreglos": [], "avisos": []}, "texto": ""}
    monkeypatch.setattr(montaje_motor, "montar", render_falso)
    _registrar(app_aislada, "cliente@ejemplo.com")
    app_aislada.post("/negocios", data=FICHA)
    app_aislada.post("/negocios/1/kit/estilo", data={"estilo": "editor", "color": "#2F6BFF", "preferencias": ""})
    assert db.marca(1)["ajustes"]["estilo"] == "editor"
    identidad.cambiar(1, colores="#2F6BFF principal\n#081528 fondo")
    return recibido


@pytest.mark.skipif(not config.ffmpeg_activo(), reason="hace falta ffmpeg")
def test_el_motor_monta_una_edicion_que_no_es_de_monti(app_aislada, monkeypatch):
    recibido = _negocio_de_editor(app_aislada, monkeypatch)
    ed = db.crear_edicion(1, "Mi reel", {}, modo="camara", datos={"usuario_id": None})
    _bruto_de_prueba(edicion.carpeta(ed) / "bruto.mp4")
    flujo.procesar(ed)
    flujo.preparar_plan(ed, montar_despues=True)
    e = db.edicion(ed)
    assert e["fase"] == "listo" and e["resultado"]["estilo"] == "editor", e.get("registro")
    assert e["datos"]["montaje"]["segundos"]["planos"]
    assert motor_validar.validar(recibido["montaje"])[0] == [] and recibido["kit"]["colores"]["fondo"] == "#081528"
    assert flujo.pedir_cambio(ed, "más dinámico")
    assert db.edicion(ed)["datos"]["cambios"][-1]["pedido"] == "más dinámico"


@pytest.mark.skipif(not config.ffmpeg_activo(), reason="hace falta ffmpeg")
def test_monti_con_de_editor_recordado_monta_por_la_via_normal(app_aislada, monkeypatch):
    from radar.agentes import produccion
    from radar.editor import montaje
    recibido = _negocio_de_editor(app_aislada, monkeypatch)
    clasico = {}

    def montaje_falso(dir_, **k):
        clasico.update(k)
        (dir_ / "final.mp4").write_bytes(b"")
        return {"duracion_original": 7.0, "duracion_final": 5.0, "cortes": 1, "efectos": 0, "estilo": k["ajustes"]["estilo"],
                "revision": {"arreglos": [], "avisos": []}, "texto": ""}
    monkeypatch.setattr(montaje, "montar", montaje_falso)
    ed = produccion.crear_toma(1, "Toma de Monti", None)
    _bruto_de_prueba(edicion.carpeta(ed) / "bruto.mp4")
    # Lo mismo que hace Monti con cada toma.
    flujo.procesar(ed)
    flujo.preparar_plan(ed, montar_despues=True)
    e = db.edicion(ed)
    assert e["fase"] == "listo" and not recibido and clasico["ajustes"]["estilo"] == "natural", e.get("registro")
    assert "montaje" not in e["datos"]
    # La v2 con la nota del cliente, recordándola, no borra la elección «De editor» de la marca. Claude (simulado)
    # deja el estilo con el que salió el reel, «natural», y solo cambia los subtítulos.
    falso = llm.json_con_esquema

    def mantiene_estilo(system, peticion, esquema, **k):
        datos = falso(system, peticion, esquema, **k)
        if isinstance(datos.get("ajustes"), dict):
            datos["ajustes"]["estilo"] = "natural"
        return datos
    monkeypatch.setattr(llm, "json_con_esquema", mantiene_estilo)
    flujo.pedir_cambio(ed, "subtítulos más grandes", recordar=True)
    assert db.marca(1)["ajustes"]["estilo"] == "editor"


def test_planos_contados_para_el_cliente(monkeypatch):
    _ia_simulada(monkeypatch)
    frases = _frases()
    palabras = [dict(w) for w in PALABRAS_PRUEBA]
    plan = plan_motor.basico(frases, palabras, bruto="b.mp4", kit="k")
    vista = plan_motor.para_ver({"frases": frases, "montaje": plan}, palabras)
    assert vista and vista[0]["como"] == "Recortado sobre tu color" and vista[0]["grafico"].startswith("Titular")
    assert "Tres" in vista[0]["dice"] and plan_motor.para_ver({"frases": frases}, palabras) == []


def test_sin_emoticonos_en_ningun_texto():
    m = {"bruto": "b", "kit": "k", "planos": [
        {"id": "p1", "src": [0, 1.0], "modo": "recorte", "grafico": {"tipo": "titular", "palabra": "Vende 🚀", "kicker": ["Así 🔥"], "en": 0}},
        {"id": "p2", "src": [1.0, 2.0], "modo": "real", "zoom": 1.3,
         "grafico": {"tipo": "ficha", "filas": [{"etiqueta": "Clientes ✅", "valor": "27", "en": 1.2}]}}]}
    errores, _ = motor_validar.validar(m)
    assert sum("emoticonos" in e for e in errores) == 2
    limpio, _ = desde_palabras.sanear(m)
    assert motor_validar.validar(limpio)[0] == []
    assert limpio["planos"][0]["grafico"]["palabra"] == "Vende" and limpio["planos"][0]["grafico"]["kicker"] == ["Así"]


def test_imagen_real_propia_o_ninguna(tmp_path, monkeypatch):
    from motor_reels.motor import imagenes
    # Sin red en las pruebas: Wikipedia y la captura de webs no encuentran nada.
    monkeypatch.setattr(imagenes, "de_wikipedia", lambda *a, **k: None)
    monkeypatch.setattr(imagenes, "de_web", lambda *a, **k: None)
    foto = tmp_path / "resultado.jpg"
    foto.write_bytes(b"jpg")
    m = {"planos": [
        {"id": "p1", "src": [0, 1], "modo": "real", "grafico": {"tipo": "imagen", "en": 0.2, "propia": "Resultado", "pie": "Mis ventas"}},
        {"id": "p2", "src": [1, 2], "modo": "real", "grafico": {"tipo": "imagen", "en": 1.2, "wikipedia": "Steve Jobs"}}]}
    m, avisos = imagenes.resolver(m, tmp_path / "imgs", {"Resultado": foto})
    assert m["planos"][0]["grafico"]["archivo"] == "p1.jpg" and (tmp_path / "imgs" / "p1.jpg").exists()
    # Lo que no aparece exacto no se pone: el plano se queda sin imagen y se avisa.
    assert "grafico" not in m["planos"][1] and "Steve Jobs" in avisos[0]


def test_la_imagen_se_senala_por_palabra():
    quedan, todas = _quedan_y_todas()
    m = desde_palabras.convertir({"planos": [
        {"desde": 0, "hasta": 1, "modo": "recorte", "zoom": 1.0, "grafico": {"tipo": "titular", "palabra": "Errores"}},
        {"desde": 2, "hasta": 4, "modo": "real", "zoom": 1.0,
         "grafico": {"tipo": "imagen", "en": 4, "wikipedia": "Sales funnel", "pie": "La oferta", "forma": "pantalla"}},
        {"desde": 5, "hasta": 7, "modo": "real", "zoom": 1.3}]}, quedan, todas, bruto="b", kit="k")
    g = m["planos"][1]["grafico"]
    assert g["tipo"] == "imagen" and g["forma"] == "pantalla" and g["wikipedia"] == "Sales funnel"
    assert abs(g["en"] - 3.95) < 0.01  # «oferta.» empieza en 3,95 s
    assert motor_validar.validar(m)[0] == []


def test_las_capturas_de_verificacion_se_descartan(tmp_path, monkeypatch):
    import httpx
    from PIL import Image, ImageDraw
    from radar.editor import montaje

    def pagina(ruta, en_blanco):
        img = Image.new("RGB", (1200, 1500), "white")
        if not en_blanco:  # una web de verdad: bloques de color y texto
            d = ImageDraw.Draw(img)
            for i in range(12):
                d.rectangle([40, 60 + i * 120, 1160, 140 + i * 120], fill=(20 * i, 60, 200 - 10 * i))
        img.save(ruta, "PNG")
        return ruta.read_bytes()

    contenido = {}
    monkeypatch.setattr(httpx, "get", lambda *a, **k: httpx.Response(200, content=contenido["x"],
                                                                     headers={"content-type": "image/png"}))
    contenido["x"] = pagina(tmp_path / "blanca.png", True) + b"0" * 6000
    assert not montaje.captura_web("manychat.com", tmp_path / "a.png") and not (tmp_path / "a.png").exists()
    contenido["x"] = pagina(tmp_path / "web.png", False)
    assert montaje.captura_web("stripe.com", tmp_path / "b.png")


def test_gancho_de_mas_adelante_y_cortes_de_frases_enteras():
    quedan, todas = _quedan_y_todas()  # «Tres errores.» | «Primero la oferta.» | «Segundo el funnel.» (la 2.ª, quitada)
    m = desde_palabras.convertir({"planos": [
        # Gancho: «Segundo el funnel.» abre el reel, aunque se dice al final.
        {"desde": 5, "hasta": 7, "gancho": True, "modo": "recorte", "fondo": "rejilla",
         "grafico": {"tipo": "titular", "palabra": "Funnel"}},
        {"desde": 2, "hasta": 4, "modo": "real", "zoom": 1.2},  # «Tres errores.» (0-1) se deja fuera entero: corte
    ]}, quedan, todas, bruto="b", kit="k")
    planos = m["planos"]
    assert planos[0]["gancho"] and planos[0]["src"][0] > 5 and planos[0]["fondo"] == "rejilla"
    assert len(planos) == 2 and planos[1]["src"][0] > 2.9  # «Tres errores.» no está; «Segundo el funnel.» no se repite
    assert motor_validar.validar(m)[0] == []
    # Un plano que repite el tramo del gancho no vale.
    m["planos"].append({"id": "p9", "src": [5.3, 6.7], "modo": "real", "zoom": 1.0})
    assert any("gancho" in e for e in motor_validar.validar(m)[0])
    # Dejar fuera media frase es un descuido: esas palabras vuelven a su plano.
    m2 = desde_palabras.convertir({"planos": [{"desde": 0, "hasta": 0, "modo": "real", "zoom": 1.0},
                                              {"desde": 2, "hasta": 7, "modo": "real", "zoom": 1.3}]},
                                  quedan, todas, bruto="b", kit="k")
    assert m2["planos"][0]["src"][1] >= 0.9  # «errores.» sigue dentro


def test_efectos_y_sus_composiciones():
    quedan, todas = _quedan_y_todas()
    efecto = {"tipo": "efecto", "clase": "proceso", "lugar": "partida", "titulo": "Cómo vender", "en": 2,
              "elementos": [{"texto": "Oferta", "en": 4}, {"texto": "Funnel", "en": 7}]}
    m = desde_palabras.convertir({"planos": [
        {"desde": 0, "hasta": 1, "modo": "recorte", "zoom": 1.0, "grafico": {"tipo": "titular", "palabra": "Errores"}},
        {"desde": 2, "hasta": 7, "modo": "real", "zoom": 1.0, "grafico": efecto}]}, quedan, todas, bruto="b", kit="k")
    g = next(p["grafico"] for p in m["planos"] if (p.get("grafico") or {}).get("tipo") == "efecto")
    assert g["clase"] == "proceso" and g["lugar"] == "partida" and [x["texto"] for x in g["elementos"]] == ["Oferta", "Funnel"]
    assert motor_validar.validar(m)[0] == []
    # Máximos por minuto: en un reel corto, como mucho una pantalla completa; la segunda pasa a partida al sanear.
    completa = lambda i: {"id": f"c{i}", "src": [i * 3.0, i * 3.0 + 2], "modo": "real", "zoom": 1.0 + (i % 2) * 0.3,
                          "grafico": {"tipo": "efecto", "clase": "cifra", "lugar": "completa", "en": i * 3.0,
                                      "elementos": [{"texto": "x", "valor": "3", "en": i * 3.0}]}}
    gancho = {"id": "g", "src": [0.0, 2.5], "modo": "recorte", "zoom": 1.0,
              "grafico": {"tipo": "titular", "palabra": "Tres", "kicker": [], "en": 0.0}}
    m3 = {"bruto": "b", "kit": "k", "planos": [gancho] + [completa(i) for i in range(1, 4)]}
    assert any("completa" in e for e in motor_validar.validar(m3)[0])
    limpio, _ = desde_palabras.sanear(m3)
    assert motor_validar.validar(limpio)[0] == []
    assert [p["grafico"]["lugar"] for p in limpio["planos"][1:]] == ["completa", "partida", "partida"]


def test_limpieza_de_brutos_con_varias_tomas(monkeypatch):
    from radar.editor import frases as fr
    # Bruto de 3 minutos: la parte 1 se graba dos veces (la primera, con un tropiezo).
    frases = [
        {"id": "f1", "inicio": 0.0, "fin": 4.0, "texto": "Tres errores al vender.", "tropiezos": 1, "energia": -0.5},
        {"id": "f2", "inicio": 4.5, "fin": 8.0, "texto": "El primero es el precio.", "tropiezos": 0, "energia": -0.4},
        {"id": "f3", "inicio": 9.0, "fin": 13.0, "texto": "Tres errores al vender.", "tropiezos": 0, "energia": 0.8},
        {"id": "f4", "inicio": 13.5, "fin": 180.0, "texto": "El primero es el precio.", "tropiezos": 0, "energia": 0.9},
    ]
    visto = {}

    def claude(system, peticion, esquema, **k):
        visto.update(peticion=peticion, effort=k.get("effort"), system=system)
        return {"frases": [{"id": "f1", "parte": "P1", "quitar": True, "motivo": "toma 1 de P1: se traba"},
                           {"id": "f2", "parte": "P1", "quitar": True, "motivo": "toma 1 de P1"},
                           {"id": "f3", "parte": "P1", "quitar": False, "motivo": ""},
                           {"id": "f4", "parte": "P1", "quitar": False, "motivo": ""}]}
    monkeypatch.setattr(llm, "json_con_esquema", claude)
    fr.limpiar(frases)
    assert '"tropiezos": 1' in visto["peticion"] and visto["effort"] == "medium"
    assert "toma más completa y fluida" in visto["system"]
    assert [f.get("quitada", False) for f in frases] == [True, True, False, False]  # se quita la toma entera
    assert all(f["parte"] == "P1" for f in frases)


def test_varios_reels_de_un_bruto(tmp_path):
    from motor_reels.motor import montar as motor_montar
    reel = lambda tramos, tipo, gancho=None: {"serie": {"tipo": tipo}, "planos": (  # noqa: E731
        ([{"id": "g", "src": list(gancho), "modo": "recorte"}] if gancho else [])
        + [{"id": f"p{i}", "src": list(t), "modo": "real"} for i, t in enumerate(tramos)])}
    completo = reel([(0, 30), (30, 60)], "completo", gancho=(100, 104))
    punto = reel([(30, 60)], "punto", gancho=(61, 64))
    otro = reel([(70, 100)], "idea", gancho=(105, 108))
    corto = reel([(110, 120)], "idea")
    errores, avisos = motor_validar.validar_serie({"completo": completo, "punto": punto, "otra": otro})
    assert errores == [] and any("permitido" in a for a in avisos)  # completo y de un punto: mismo texto, otro gancho
    # Dos ideas que comparten casi todo, o un reel demasiado corto, no valen.
    errores, _ = motor_validar.validar_serie({"a": otro, "b": reel([(72, 100)], "idea", gancho=(1, 4)), "c": corto})
    assert any("comparten" in e for e in errores) and any("25 s" in e for e in errores)
    # Mismo gancho en dos reels: no.
    errores, _ = motor_validar.validar_serie({"a": completo, "b": reel([(70, 100)], "idea", gancho=(100, 104))})
    assert any("mismo gancho" in e for e in errores)
    # Cada reel en su subcarpeta usa la preparación (fotogramas y transcripción) de la carpeta del bruto.
    (tmp_path / "frames").mkdir()
    (tmp_path / "reel_1").mkdir()
    assert motor_montar.preparacion(tmp_path / "reel_1") == tmp_path
    assert motor_montar.preparacion(tmp_path) == tmp_path


def test_mapa_de_reels_del_saas(monkeypatch):
    frases = [{"id": f"f{i}", "inicio": i * 10.0, "fin": i * 10.0 + 9.5, "texto": f"Frase {i}."} for i in range(12)]
    monkeypatch.setattr(llm, "json_con_esquema", lambda *a, **k: {"reels": [
        {"tipo": "completo", "titulo": "Los 3 errores", "desde": "f0", "hasta": "f11", "gancho": "f5", "motivo": "m"},
        {"tipo": "punto", "titulo": "El precio", "desde": "f3", "hasta": "f6", "gancho": "f3", "motivo": "m"},
        {"tipo": "punto", "titulo": "Muy corto", "desde": "f8", "hasta": "f8", "gancho": "f8", "motivo": "m"},
        {"tipo": "idea", "titulo": "Repite gancho", "desde": "f9", "hasta": "f11", "gancho": "f5", "motivo": "m"},
        {"tipo": "idea", "titulo": "Inventado", "desde": "f40", "hasta": "f41", "gancho": "f40", "motivo": "m"}]})
    mapa = plan_motor.mapa_de_reels(frases)
    assert [r["titulo"] for r in mapa] == ["Los 3 errores", "El precio"]  # fuera: corto, gancho repetido e inventado
    assert mapa[0]["gancho"] == "f5"


def test_el_gancho_del_reel_viene_de_fuera_de_su_tramo(monkeypatch):
    # Reel de una toma con varios: su tramo es «Tres errores. Primero la oferta.» y su gancho, «Segundo el funnel.»
    # (f4), que va después y Monti deja fuera (quitada) porque no está en el tramo.
    frases = _frases()
    for f in frases:
        f["quitada"] = f["id"] in ("f2", "f4")
    palabras = [dict(w) for w in PALABRAS_PRUEBA]
    plan = plan_motor.basico(frases, palabras, bruto="b", kit="k", gancho="f4")
    planos = plan["segundos"]["planos"]
    assert planos[0].get("gancho") and planos[0]["src"][0] >= 5.0 and planos[0]["grafico"]["tipo"] == "titular"
    assert all(p["src"][1] <= 5.0 for p in planos[1:])  # luego, su tramo; «Eh, repito.» sigue fuera
    assert motor_validar.validar(plan["segundos"])[0] == []
    _ia_simulada(monkeypatch)
    con_ia = plan_motor.proponer(frases, palabras, preferencias=[], bruto="b", kit="k", gancho="f4")
    assert con_ia["segundos"]["planos"][0].get("gancho") and motor_validar.validar(con_ia["segundos"])[0] == []
    # Sin reel (o con el gancho ya al principio) no cambia nada.
    assert not plan_motor.basico(_frases(), palabras, bruto="b", kit="k")["segundos"]["planos"][0].get("gancho")


def test_mapa_de_reels_usa_la_estructura_como_pista(monkeypatch):
    frases = [{"id": f"f{i}", "inicio": i * 10.0, "fin": i * 10.0 + 9.5, "texto": f"Frase {i}."} for i in range(6)]
    visto = {}
    monkeypatch.setattr(llm, "json_con_esquema", lambda system, peticion, esquema, **k: visto.update(p=peticion) or {
        "reels": [{"tipo": "punto", "titulo": "Precio", "desde": "f0", "hasta": "f5", "gancho": "f0", "motivo": "m"}]})
    plan_motor.mapa_de_reels(frases, "Idea: vender más\\n1. El precio\\n- puntos")
    assert "1. El precio" in visto["p"] and "pista" in visto["p"]
    plan_motor.mapa_de_reels(frases)
    assert "Estructura" not in visto["p"]


def test_dos_efectos_seguidos_conservan_sus_tiempos():
    # Regresión: tras un primer efecto, los tiempos del segundo caían todos en la primera palabra.
    quedan, todas = _quedan_y_todas()
    lista = lambda en: {"tipo": "efecto", "clase": "lista", "lugar": "encima", "en": en,  # noqa: E731
                        "elementos": [{"texto": "a", "en": en}, {"texto": "b", "en": en + 1}]}
    m = desde_palabras.convertir({"planos": [{"desde": 0, "hasta": 1, "modo": "real", "zoom": 1.0, "grafico": lista(0)},
                                             {"desde": 2, "hasta": 7, "modo": "real", "zoom": 1.3, "grafico": lista(5)}]},
                                 quedan, todas, bruto="b", kit="k")
    segundo = [p for p in m["planos"] if p.get("grafico")][1]["grafico"]
    assert [round(x["en"], 2) for x in segundo["elementos"]] == [5.2, 5.65]


def test_la_pantalla_partida_empieza_con_su_primer_elemento():
    quedan, todas = _quedan_y_todas()
    efecto = {"tipo": "efecto", "clase": "comparacion", "lugar": "partida", "en": 4,
              "elementos": [{"texto": "Antes", "valor": "x", "en": 4}, {"texto": "Ahora", "valor": "y", "en": 7}]}
    m = desde_palabras.convertir({"planos": [{"desde": 0, "hasta": 1, "modo": "recorte", "grafico": {"tipo": "titular", "palabra": "X"}},
                                             {"desde": 2, "hasta": 7, "modo": "real", "zoom": 1.0, "grafico": efecto}]},
                                 quedan, todas, bruto="b", kit="k")
    con = next(p for p in m["planos"] if (p.get("grafico") or {}).get("tipo") == "efecto")
    assert con["src"][0] >= 3.9  # «Primero la» va antes, con la cara entera
    assert any(p["src"][0] < 3.5 and not p.get("grafico") for p in m["planos"][1:])


def test_golpes_iconos_y_transicion_del_azul(tmp_path):
    from motor_reels.motor import montar as motor_montar
    quedan, todas = _quedan_y_todas()
    m = desde_palabras.convertir({"planos": [
        {"desde": 0, "hasta": 1, "modo": "recorte", "fondo": "luz", "grafico": {"tipo": "titular", "palabra": "Tres"}},
        {"desde": 2, "hasta": 4, "modo": "real", "zoom": 1.0, "golpe": 4,
         "grafico": {"tipo": "icono", "icono": "reloj", "en": 3, "texto": "Hoy", "lado": "derecha"}},
        {"desde": 5, "hasta": 7, "modo": "real", "zoom": 1.3}]}, quedan, todas, bruto="b", kit="k")
    p2 = next(p for p in m["planos"] if p.get("grafico", {}).get("tipo") == "icono")
    assert p2["golpe"] >= 3.9 and p2["grafico"]["icono"] == "reloj"
    assert motor_validar.validar(m)[0] == []
    m["planos"][1]["grafico"]["icono"] = "unicornio"
    assert any("no existe" in e for e in motor_validar.validar(m)[0])
    m["planos"][1]["grafico"]["icono"] = "reloj"
    # El recorte azul que da paso a vídeo real sale «revelando» la habitación, no en seco.
    palabras = [{"t": w["start"], "fin": w["end"], "w": w["word"]} for w in todas]
    (tmp_path / "frames").mkdir()
    from PIL import Image
    for i in range(0, 260):
        Image.new("RGBA", (1080, 1920), (0, 0, 0, 255)).save(tmp_path / "frames" / f"m_{i:05d}.png")
    datos, eventos = motor_montar.props(m, {"colores": {}, "fuentes": {}}, palabras, tmp_path / "frames")
    assert datos["planos"][0]["salida"] == "revela" and datos["planos"][1]["golpe"] > 0
    # Golpe y transición caen a menos de 3 s: suena solo el de más prioridad (la transición), como manda el manual.
    assert [k for _, k, _ in eventos] == ["whoosh_soft"]


def test_identidad_subtitulos_sonido_y_nunca(app_aislada, tmp_path, monkeypatch):
    from motor_reels.motor import montar as motor_montar
    _registrar(app_aislada, "cliente@ejemplo.com")
    app_aislada.post("/negocios", data=FICHA)
    # Sin dato: valores neutros, y siempre están las claves.
    reglas = identidad.kit_motor(1)["reglas"]
    assert reglas == {"subtitulos": "resaltado", "musica": False, "sonidos": True, "nunca": []}
    identidad.cambiar(1, subtitulos="sin", sonidos=False, musica=True, nunca="Cajas\nemoticonos\ncajas\n-")
    ident = identidad.leer(1)
    assert (ident["subtitulos"], ident["sonidos"], ident["musica"]) == ("sin", False, True)
    assert ident["nunca"] == ["Cajas", "emoticonos"]
    identidad.cambiar(1, subtitulos="raro", notas="x")  # un valor que no existe no pisa el guardado
    assert identidad.leer(1)["subtitulos"] == "sin"
    # El motor: sin subtítulos en ningún plano.
    quedan, todas = _quedan_y_todas()
    m = desde_palabras.convertir({"planos": [{"desde": 0, "hasta": 4, "modo": "real", "zoom": 1.0}]},
                                 quedan, todas, bruto="b", kit="k")
    palabras = [{"t": w["start"], "fin": w["end"], "w": w["word"]} for w in todas]
    (tmp_path / "frames").mkdir()
    from PIL import Image
    for i in range(0, 200):
        Image.new("RGBA", (1080, 1920), (0, 0, 0, 255)).save(tmp_path / "frames" / f"m_{i:05d}.png")
    kit = {"colores": {}, "fuentes": {}, "reglas": identidad.kit_motor(1)["reglas"]}
    datos, _ = motor_montar.props(m, kit, palabras, tmp_path / "frames")
    assert not any(p["subtitulos"] for p in datos["planos"])
    assert motor_montar.reglas_de({})["sonidos"] is True
    # «nunca» llega a Monti cuando planifica.
    vistas = []
    _ia_simulada(monkeypatch)
    real = llm.json_con_esquema
    monkeypatch.setattr(llm, "json_con_esquema", lambda s, p, e, **k: vistas.append(p) or real(s, p, e, **k))
    plan_motor.proponer(_frases(), [dict(w) for w in PALABRAS_PRUEBA], preferencias=[], bruto="b", kit="k",
                        nunca=["Cajas"])
    assert "Cajas" in vistas[0]


def test_zona_segura_rotulos_y_gancho_visible(tmp_path):
    from motor_reels.motor import montar as motor_montar
    assert motor_validar.cajas_fuera_de_zona() == []
    quedan, todas = _quedan_y_todas()
    # Sin titular en el primer plano, el conversor pone uno con lo que se dice: el gancho se ve desde el primer fotograma.
    m = desde_palabras.convertir({"planos": [{"desde": 0, "hasta": 3, "modo": "real", "zoom": 1.0},
                                             {"desde": 4, "hasta": 7, "modo": "real", "zoom": 1.3}]},
                                 quedan, todas, bruto="b", kit="k")
    assert m["planos"][0]["grafico"]["tipo"] == "titular" and motor_validar.validar(m)[0] == []
    palabras = [{"t": w["start"], "fin": w["end"], "w": w["word"]} for w in todas]
    (tmp_path / "frames").mkdir()
    from PIL import Image
    for i in range(0, 260):
        Image.new("RGBA", (1080, 1920), (0, 0, 0, 255)).save(tmp_path / "frames" / f"m_{i:05d}.png")
    datos, _ = motor_montar.props(m, {"colores": {}, "fuentes": {}}, palabras, tmp_path / "frames")
    assert datos["planos"][0]["grafico"]["f"] <= -8  # ya asentado en el fotograma 0
    # Rótulos de más de seis palabras: error; sanear los recorta.
    m["planos"][1]["grafico"] = {"tipo": "efecto", "clase": "lista", "lugar": "encima", "en": m["planos"][1]["src"][0],
                                 "titulo": "uno dos tres cuatro cinco seis siete",
                                 "elementos": [{"texto": "a", "valor": "", "en": m["planos"][1]["src"][0]}]}
    assert any("6 como mucho" in e for e in motor_validar.validar(m)[0])
    limpio, _ = desde_palabras.sanear(m)
    assert limpio["planos"][1]["grafico"]["titulo"] == "uno dos tres cuatro cinco seis"
    # Emoticonos según la voz del cliente: sin dato, nunca; «libre», se dejan.
    m["planos"][1]["grafico"]["titulo"] = "Hola \U0001F680"
    assert any("emoticonos" in e for e in motor_validar.validar(m)[0])
    m["reglas"] = {"emojis": "libre"}
    assert not any("emoticonos" in e for e in motor_validar.validar(m)[0])


def test_el_gancho_del_mapa_sale_puntuado(monkeypatch):
    textos = ["Hola a todos, hoy vengo a contaros una cosa.", "El 90 % de los coaches cobra la mitad de lo que podría.",
              "Y eso pasa por una razón.", "Te explico cómo subir el precio sin perder clientes.", "Bueno, pues eso."]
    frases = [{"id": f"f{i}", "inicio": i * 8.0, "fin": i * 8.0 + 7.5, "texto": t} for i, t in enumerate(textos)]
    # Claude propone el saludo; la frase con cifra y a quién va gana la puntuación.
    monkeypatch.setattr(llm, "json_con_esquema", lambda *a, **k: {"reels": [
        {"tipo": "completo", "titulo": "Precio", "desde": "f0", "hasta": "f4", "gancho": "f0", "candidatos": ["f3"],
         "motivo": "m"}]})
    r = plan_motor.mapa_de_reels(frases)[0]
    assert r["gancho"] != "f0" and r["gancho_nota"]["nota"] > 0 and "formula" in r["gancho_nota"]


def test_variantes_para_reels_de_prueba(tmp_path):
    from radar.editor import variantes
    final = tmp_path / "final.mp4"
    subprocess.run([config.FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=1080x1920:d=1:r=30",
                    "-f", "lavfi", "-i", "sine=d=1", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(final)],
                   check=True)
    hechas = variantes.de_imagen(final, tmp_path, nunca=["Nada de etalonaje"])
    assert [h.name for h in hechas] == ["velocidad.mp4", "encuadre.mp4"]  # el color, vetado por su «nunca»
    assert variantes.de_imagen(final, tmp_path, velocidad_actual=1.1)[0].name == "color.mp4"  # ya va a x1,1
    m = {"planos": [{"id": "p1", "src": [0, 2], "modo": "real", "zoom": 1.1,
                     "grafico": {"tipo": "titular", "palabra": "Criterio", "kicker": ["lo", "único", "diferencial"],
                                 "en": 0}}]}
    alt = variantes.titular_alternativo(m)
    assert alt["planos"][0]["modo"] == "recorte" and alt["planos"][0]["grafico"]["palabra"] == "Diferencial"
    assert m["planos"][0]["modo"] == "real"  # el original no se toca


def test_cola_de_renders(tmp_path, monkeypatch):
    import threading

    from motor_reels import cola
    from radar.editor import modelo
    hechos = []
    monkeypatch.setattr(cola, "ejecutar", lambda e: hechos.append(e["salida"]) or {"duracion": 30.0, "avisos": []})
    # La web encarga y espera; el worker lo hace (de uno en uno, por orden de llegada).
    nombre = cola.encolar(tmp_path, {"montaje": "m.json", "salida": "a.mp4", "kit": {}})
    segundo = cola.encolar(tmp_path, {"montaje": "m.json", "salida": "b.mp4", "kit": {}})
    assert cola.delante(tmp_path, segundo) == 1
    hilo = threading.Thread(target=lambda: [cola.trabajar(tmp_path, una_vez=True) for _ in range(2)])
    hilo.start()
    assert cola.esperar(tmp_path, nombre, espera_max=20)["duracion"] == 30.0
    hilo.join()
    assert hechos == ["a.mp4", "b.mp4"]
    # Un encargo que falla devuelve su error y no para la cola.
    monkeypatch.setattr(cola, "ejecutar", lambda e: 1 / 0)
    roto = cola.encolar(tmp_path, {"montaje": "m.json", "salida": "c.mp4", "kit": {}})
    cola.trabajar(tmp_path, una_vez=True)
    with pytest.raises(RuntimeError, match="ZeroDivision"):
        cola.esperar(tmp_path, roto, espera_max=5)
    # Con worker de renders, Monti ya usa el estilo «De editor»; sin él, sigue por la vía clásica.
    monkeypatch.setattr(config, "ffmpeg_activo", lambda: True)
    monkeypatch.setattr(config, "motor_reels_local", lambda: False)
    monti = {"produccion": {}}
    monkeypatch.delenv("RADAR_COLA_RENDERS", raising=False)
    assert not modelo.usa_motor({"estilo": "editor"}, "camara", monti)
    monkeypatch.setenv("RADAR_COLA_RENDERS", str(tmp_path))
    assert modelo.usa_motor({"estilo": "editor"}, "camara", monti)


def test_los_kits_de_clientes_van_fuera_del_repositorio(tmp_path, monkeypatch):
    import json

    from motor_reels.motor import montar as motor_montar
    assert motor_montar.cargar_kit("ejemplo")["cliente"] == "Ejemplo"
    (tmp_path / "cliente.json").write_text(json.dumps({"cliente": "Otro", "colores": {}, "fuentes": {}}))
    monkeypatch.setenv("MOTOR_REELS_KITS", str(tmp_path))
    assert motor_montar.cargar_kit("cliente")["cliente"] == "Otro"
    with pytest.raises(FileNotFoundError):
        motor_montar.cargar_kit("no-existe")
