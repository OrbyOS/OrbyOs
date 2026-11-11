"""Chati: reglas de escritura, entrega de la palabra clave, guía, seguimientos, DMs a mano y comentarios."""
from datetime import datetime, timedelta

import pytest
from radar import db, llm
from radar.agentes import aprobaciones as ap
from radar.agentes import comentarios, comunidad, kit

from .test_agentes import _negocio_con_cliente
from .test_radar import app_aislada, sin_claves_reales  # noqa: F401


def _con_claude(monkeypatch, respuesta):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "prueba")
    peticiones = []
    monkeypatch.setattr(llm, "json_con_esquema", lambda s, p, e, **k: peticiones.append((s, p)) or (
        respuesta(p) if callable(respuesta) else respuesta))
    return peticiones


def test_texto_limpio_aplica_las_reglas_del_kit(app_aislada, monkeypatch):
    _, nid = _negocio_con_cliente(app_aislada)
    monkeypatch.setattr(comunidad.config, "URL_PUBLICA", "https://app.ejemplo.com")
    neg = db.negocio(nid)
    assert comunidad.texto_limpio("Cuesta 300 € al mes", neg) == ""  # nunca un precio
    assert comunidad.texto_limpio("Mira esto https://otra.com/x", neg) == ""  # ningún enlace ajeno
    assert comunidad.texto_limpio("Tu guía: https://app.ejemplo.com/g/abc", neg).endswith("/g/abc")
    assert comunidad.texto_limpio("Es así — y funciona", neg) == "Es así, y funciona"
    # Por defecto, «pocos»: uno como mucho, y en una respuesta solo si la otra persona los usa.
    assert comunidad.texto_limpio("Genial 🔥 de verdad 🙌", neg) == "Genial 🔥 de verdad"
    assert comunidad.texto_limpio("Genial 🔥", neg, suyos="me encantó") == "Genial"
    assert comunidad.texto_limpio("Genial 🔥", neg, suyos="me encantó 😍") == "Genial 🔥"
    k = kit.leer(nid)
    kit.cambiar(nid, prohibidas=["sin excusas"])
    assert comunidad.texto_limpio("Hazlo sin excusas", neg) == ""
    kit.cambiar(nid, voz={**kit.leer(nid)["voz"], "emojis": "nunca"}, limites={"temas_vetados": ["política"],
                                                                             "cifras_propias": False})
    assert comunidad.texto_limpio("Genial 🔥", neg, suyos="😍") == "Genial"
    r = comunidad.reglas(kit.leer(nid))
    assert "Sin emojis" in r and "política" in r and "ninguna cifra propia" in r


def test_la_entrega_de_la_palabra_va_primero_con_uso_y_pregunta(app_aislada):
    _, nid = _negocio_con_cliente(app_aislada)
    neg = db.negocio(nid)
    kit.cambiar(nid, comunidad={**comunidad.ajustes(nid), "mensaje_dm": "{nombre}, aquí la tienes:"})
    comunidad.guardar_entrega(nid, "cierre", uso="Empieza por el paso 2.", pregunta="¿Vendes por llamada?")
    t = comunidad.texto_entrega(neg, "CIERRE", "https://app.ejemplo.com/g/x", "Laura Gómez")
    assert t == "Laura, aquí la tienes: https://app.ejemplo.com/g/x\n\nEmpieza por el paso 2.\n\n¿Vendes por llamada?"
    assert comunidad.texto_entrega(neg, "CIERRE", "https://e.com/g", "").startswith("Aquí la tienes: https://e.com/g")


def test_la_guia_sale_con_el_formato_de_la_casa(app_aislada, monkeypatch):
    _, nid = _negocio_con_cliente(app_aislada)
    gid = 7
    monkeypatch.setattr(comunidad.guionista, "guion", lambda n, i: {"id": i, "palabra_clave": "CIERRE",
                                                                    "texto": "Cómo cerrar más llamadas"})
    _con_claude(monkeypatch, {
        "titulo": "Cierra más llamadas", "subtitulo": "Cinco preguntas para cerrar sin presionar.",
        "que_hay": ["Uno", "Dos", "Tres", "Cuatro"], "de_que_va": ["El problema.", "Por qué ahora.", "Qué hace."],
        "pasos": [{"titulo": "Prepara", "puntos": ["a"]}, {"titulo": "Pregunta", "puntos": ["b"]}],
        "llamada_medio": "Pruébalo en tu próxima llamada.", "siguiente_problema": "Ahora te faltan llamadas.",
        "siguiente_paso": "La mentoría empieza con una llamada.", "uso": "Léela antes de tu próxima llamada — dura 5 min.",
        "pregunta": "¿Cuántas llamadas haces?"})
    g = comunidad.redactar_guia(db.negocio(nid), gid)
    tipos = [b["tipo"] for b in comunidad.bloques(g["contenido"])]
    titulos = [b["texto"] for b in comunidad.bloques(g["contenido"]) if b["tipo"] == "titulo"]
    assert titulos == ["Qué vas a encontrar", "De qué va", "1. Prepara", "2. Pregunta", "Lo que acabas de ver"]
    assert tipos[0] == "parrafo" and "Pruébalo en tu próxima llamada." in g["contenido"]
    assert g["contenido"].index("Pruébalo") < g["contenido"].index("2. Pregunta")  # la llamada, a mitad
    assert comunidad.ajustes(nid)["entregas"]["CIERRE"]["uso"] == "Léela antes de tu próxima llamada, dura 5 min."


def test_lo_que_no_necesita_respuesta_no_pasa_por_claude():
    assert comunidad.filtro(["¡Gracias!"], set())["intencion"] == "sin_respuesta"
    assert comunidad.filtro(["🔥🔥"], set())["temperatura"] == "frio"
    assert comunidad.filtro(["Gracias, ¿y cómo empiezo?"], set()) is None


def _conversacion(nid, *, dias_nuestro: float, intencion="duda", temperatura="templado", suscriptor="31"):
    ahora = datetime.now()
    suyo = (ahora - timedelta(days=dias_nuestro + 0.1)).isoformat(timespec="seconds")
    nuestro = (ahora - timedelta(days=dias_nuestro)).isoformat(timespec="seconds")
    with db.conexion() as con:
        cid = con.execute("INSERT INTO conversaciones (negocio_id, externo_id, cuenta, plataforma, participante, usuario, "
                          "ultima, ultima_entrante, temperatura, intencion, resumen) VALUES (?, ?, 'manychat', 'instagram', "
                          "'marta', 'marta', ?, ?, ?, ?, 'Pregunta por el método')",
                          (nid, f"mc:{suscriptor}", nuestro, suyo, temperatura, intencion)).lastrowid
        con.execute("INSERT INTO mensajes_dm (negocio_id, conversacion_id, externo_id, direccion, texto, creado, origen) "
                    "VALUES (?, ?, ?, 'entrante', '¿Esto sirve si empiezo de cero?', ?, 'dm')", (nid, cid, f"e{cid}", suyo))
        con.execute("INSERT INTO mensajes_dm (negocio_id, conversacion_id, externo_id, direccion, texto, creado, origen) "
                    "VALUES (?, ?, ?, 'saliente', 'Sí, justo para eso. ¿Qué has probado?', ?, 'dm')",
                    (nid, cid, f"s{cid}", nuestro))
    return cid


def test_dos_seguimientos_como_maximo(app_aislada, monkeypatch):
    _, nid = _negocio_con_cliente(app_aislada)
    neg = db.negocio(nid)
    cid = _conversacion(nid, dias_nuestro=5)
    _conversacion(nid, dias_nuestro=5, intencion="palabra_clave", suscriptor="32")  # solo pidió la guía: no se le persigue
    _conversacion(nid, dias_nuestro=2, suscriptor="33")  # aún no toca
    peticiones = _con_claude(monkeypatch, lambda p: {"seguimientos": [
        {"numero": 1, "texto": "Te dejo un ejemplo de alguien que empezó de cero."}]} if "tipo 1" in p else {
        "seguimientos": [{"numero": 1, "texto": "No te escribo más; aquí estoy si te encaja."}]})
    assert comunidad.preparar_seguimientos(neg) == 1
    s1 = [a for a in ap.pendientes(nid) if a["datos"].get("seguimiento")]
    assert len(s1) == 1 and s1[0]["datos"]["conversacion_id"] == cid and s1[0]["datos"]["a_mano"]
    assert comunidad.preparar_seguimientos(neg) == 0  # con uno esperando, no se pide otro
    ap.decidir(s1[0]["id"], "aprobar")  # lo manda el dueño a mano: Radar lo apunta
    assert comunidad.mensajes_de(cid)[-1]["origen"] == "seguimiento"
    segundos = lambda: [a for a in ap.pendientes(nid) if a["datos"].get("seguimiento") == 2]  # noqa: E731
    comunidad.preparar_seguimientos(neg, datetime.now() + timedelta(days=3))  # (a la de hace 2 días le toca el primero)
    assert segundos() == []  # el segundo, 6 días después del primero
    comunidad.preparar_seguimientos(neg, datetime.now() + timedelta(days=7))
    s2 = segundos()
    assert len(s2) == 1 and s2[0]["datos"]["conversacion_id"] == cid and "tipo 2" in peticiones[-1][1]
    ap.decidir(s2[0]["id"], "aprobar")
    a_los_30 = comunidad.seguimientos_pendientes(nid, datetime.now() + timedelta(days=30))
    assert cid not in [c["id"] for c in a_los_30]  # no hay tercero


def test_si_el_dueno_rechaza_un_seguimiento_no_se_insiste(app_aislada, monkeypatch):
    _, nid = _negocio_con_cliente(app_aislada)
    neg = db.negocio(nid)
    _conversacion(nid, dias_nuestro=5)
    _con_claude(monkeypatch, {"seguimientos": [{"numero": 1, "texto": "Te paso una idea nueva."}]})
    comunidad.preparar_seguimientos(neg)
    ap.decidir(ap.pendientes(nid)[0]["id"], "rechazar", por="cliente@ejemplo.com")
    assert comunidad.preparar_seguimientos(neg, datetime.now() + timedelta(days=20)) == 0


def test_dm_a_mano_pide_motivo_y_trae_sus_seguimientos(app_aislada, monkeypatch):
    _, nid = _negocio_con_cliente(app_aislada)
    neg = db.negocio(nid)
    with pytest.raises(ValueError, match="motivo"):
        comunidad.escribir_dm(neg, "primer", "@pepe", "")
    with pytest.raises(ValueError, match="idea"):
        comunidad.escribir_dm(neg, "colaboracion", "pepe", "Hace directos sobre ventas cada martes")
    peticiones = _con_claude(monkeypatch, {"mensaje": "Pepe, lo que dijiste del seguimiento me hizo pensar. Te paso la "
                                           "plantilla que uso. ¿Te sirve?", "seguimiento_1": "Otra idea: …",
                                           "seguimiento_2": "No insisto más."})
    a = comunidad.escribir_dm(neg, "primer", "@pepe", "Comentó en mi reel que no sabe hacer seguimiento")
    assert a["tipo"] == "dm" and a["estado"] == "pendiente" and a["datos"]["a_mano"]
    assert [s["dia"] for s in a["datos"]["seguimientos"]] == [
        (datetime.now().date() + timedelta(days=d)).isoformat() for d in (4, 10)]
    assert "<motivo>" in peticiones[0][1]


def test_comentarios_se_ordenan_y_contestan_en_orden(app_aislada, monkeypatch):
    _, nid = _negocio_con_cliente(app_aislada)
    comunidad.guardar_guia(nid, "CIERRE", "Guía", "- Uno")
    pegados = comentarios.leer_pegados(
        "@ana: CIERRE\n@bea: cierre!\n@promo_ya: DM for promo, we grow your followers\n"
        "@carla: Me pasa justo esto, cierro 1 de cada 10 (3 me gusta)\n"
        "@dani: ¿Y si te dicen que lo tienen que pensar? (40 me gusta)\n@eva: 🔥🔥")
    assert pegados[3] == {"usuario": "carla", "texto": "Me pasa justo esto, cierro 1 de cada 10", "likes": 3}
    peticiones = _con_claude(monkeypatch, {"comentarios": [
        {"numero": 1, "grupo": "lead", "respuesta": "Carla, lo primero es preguntar antes de proponer.", "reel": False},
        {"numero": 2, "grupo": "pregunta", "respuesta": "Pregúntale qué necesita pensar en concreto.", "reel": False},
        {"numero": 3, "grupo": "apoyo", "respuesta": "Gracias 🔥", "reel": False}],
        "para_palabra": ["Enviada, Ana.", "Ya la tienes."]})
    a = comentarios.ordenar(db.negocio(nid), pegados)
    grupos = {g["grupo"]: g["comentarios"] for g in a["datos"]["grupos"]}
    assert [g["grupo"] for g in a["datos"]["grupos"]] == ["palabra", "lead", "pregunta", "apoyo", "ruido"]
    assert {c["usuario"] for c in grupos["palabra"]} == {"ana", "bea"}
    assert grupos["palabra"][0]["respuesta"] != grupos["palabra"][1]["respuesta"]  # misma calidez, no copiar y pegar
    assert grupos["ruido"][0]["usuario"] == "promo_ya" and grupos["ruido"][0]["respuesta"] == ""
    assert grupos["pregunta"][0]["reel"] and a["datos"]["reels"][0]["usuario"] == "dani"  # 40 me gusta: un reel
    assert "promo" not in peticiones[0][1]  # el spam y la palabra no se mandan a Claude
    assert a["tipo"] == "comentarios" and a["estado"] == "pendiente"


def test_rutas_de_comunidad_para_dm_y_comentarios(app_aislada, monkeypatch):
    cliente, nid = _negocio_con_cliente(app_aislada)
    r = cliente.post(f"/negocios/{nid}/comunidad/dm", data={"tipo": "primer", "usuario": "pepe", "motivo": ""})
    assert "motivo" in r.text
    _con_claude(monkeypatch, {"comentarios": [{"numero": 1, "grupo": "pregunta", "respuesta": "Así.", "reel": False}],
                              "para_palabra": []})
    r = cliente.post(f"/negocios/{nid}/comunidad/comentarios", data={"texto": "@ana: ¿Cómo empiezo?"})
    assert "Comentarios ordenados" in r.text
    assert cliente.post(f"/negocios/{nid}/comunidad/ronda", data={"cuentas": "@lucia"}).status_code in (404, 405)
    assert {a["tipo"] for a in ap.pendientes(nid)} == {"comentarios"}
