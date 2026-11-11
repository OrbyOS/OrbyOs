"""Las pantallas (plantillas) que piden las sesiones de cada agente: que se pinten con sus datos."""
from datetime import datetime, timedelta

from radar.agentes import aprobaciones as ap
from radar.agentes import identidad

from .test_agentes import _negocio_con_cliente
from .test_radar import app_aislada, sin_claves_reales  # noqa: F401


def test_el_kit_pide_como_se_editan_los_reels(app_aislada):
    cliente, nid = _negocio_con_cliente(app_aislada)
    identidad.cambiar(nid, subtitulos="simple", musica=True, sonidos=False, nunca="cajas\nemoticonos")
    kit = cliente.get(f"/negocios/{nid}/kit").text
    assert 'name="subtitulos" value="simple" checked' in kit and 'name="musica" value="1" checked' in kit
    assert 'name="sonidos" value="0" checked' in kit and "cajas\nemoticonos</textarea>" in kit


def test_comunidad_prepara_dm_y_comentarios_a_mano(app_aislada):
    cliente, nid = _negocio_con_cliente(app_aislada)
    pagina = cliente.get(f"/negocios/{nid}/comunidad").text
    for ancla, ruta in (("mensajes", "dm"), ("comentarios", "comentarios")):
        assert f'id="{ancla}"' in pagina and f'action="/negocios/{nid}/comunidad/{ruta}"' in pagina, ancla
    assert 'name="tipo" value="colaboracion"' in pagina and 'name="motivo" rows="3" required' in pagina
    assert 'name="traer" value="1"' in pagina and "gasta de tu Apify" in pagina
    assert 'id="ronda"' not in pagina  # la ronda de comentarios en otras cuentas ya no existe

    hoy = datetime.now()
    ap.pedir(nid, "comunidad", "dm", "DM a @laura", {
        "a_mano": True, "texto": "Vi tu comentario sobre precios.", "caracteres": 31, "motivo": "Comentó en mi reel",
        "seguimientos": [{"dia": (hoy + timedelta(days=3)).isoformat(), "texto": "¿Lo pudiste mirar?"}]})
    ap.pedir(nid, "comunidad", "comentarios", "Comentarios del reel", {"a_mano": True, "reels": ["¿Y si vendo por WhatsApp?"], "grupos": [
        {"grupo": "pregunta", "nombre": "Pregunta", "comentarios": [
            {"usuario": "ana", "texto": "¿Y si vendo por WhatsApp?", "likes": 18, "respuesta": "Te lo cuento en un reel", "reel": True}]},
        {"grupo": "ruido", "nombre": "Ruido", "comentarios": [{"usuario": "bot", "texto": "🔥", "likes": 0, "respuesta": "", "reel": False}]}]})
    ap.pedir(nid, "comunidad", "respuesta", "Seguimiento a @pablo", {"a_mano": True, "seguimiento": 1, "texto": "¿Te sirvió?"})
    pagina = cliente.get(f"/negocios/{nid}/aprobaciones").text
    assert 'data-copia="Vi tu comentario sobre precios."' in pagina and "Seguimiento 1 ·" in pagina
    assert "Piden un reel de respuesta" in pagina and "No contestar: les da alcance." in pagina
    assert "Seguimiento 1 de 2: mándalo tú desde Instagram" in pagina and "Caduca" not in pagina


def test_investigacion_ensena_noticias_formulas_y_nota_del_perfil(app_aislada, monkeypatch):
    from radar.main import plantillas
    cliente, nid = _negocio_con_cliente(app_aislada)
    pronto = (datetime.now() + timedelta(hours=20)).isoformat(timespec="seconds")
    datos = {
        "TIPOS_CUENTA": {"directa": "Directa (mismo nicho, algo por delante)"},
        "VISUALES": {"captura_fuente": "Captura de la fuente", "a_camara": "A cámara"},
        "ESTADOS_DATO": {"confirmado": "Lo dice la fuente tal cual", "sin_comprobar": "No se ha podido comprobar"},
        "noticias": [{"id": "n1", "titulo": "Meta cambia el algoritmo", "url": "https://ejemplo.test/n1", "medio": "Xataka",
                      "cobertura": 3, "calor": 8.6, "motivo": "Afecta a tus clientes", "lista": True, "fallos": [],
                      "grabar_antes": pronto, "guion": {"cabecera": "Instagram premia los reels largos", "gancho": "Lo que cambió ayer",
                      "pasos": [{"texto": "Enseña el anuncio", "visual": "captura_fuente"}], "angulo": "Qué hace un coach",
                      "comprobaciones": [{"dato": "Desde el 1 de noviembre", "estado": "confirmado"}]}}],
        "perfil": {"total": 62, "sobre": 90, "antes": 55, "sin_ver": 10, "creado": "2026-10-26T10:00:00",
                   "arreglos": ["bio", "enlace"], "partes": [
                       {"id": "bio", "nombre": "La bio", "maximo": 20, "puntos": 8, "motivo": "No dice para quién", "arreglo": "Empieza por a quién ayudas", "sin_datos": False},
                       {"id": "enlace", "nombre": "El enlace", "maximo": 10, "puntos": None, "motivo": "", "arreglo": "Un solo enlace", "sin_datos": True},
                       {"id": "foto", "nombre": "La foto", "maximo": 10, "puntos": 10, "motivo": "", "arreglo": "", "sin_datos": False}]},
        "formulas": {"posts": 48, "cuentas": 7, "confianza": "suficiente", "palabras_gancho": {"arriba": 9, "abajo": 14},
                     "destacan": [{"formula": "f3", "nombre": "El error que todos cometen", "arriba": 6, "abajo": 1, "usos": 7, "empuje": 1.8,
                                   "ejemplos": [{"gancho": "El error que hunde tus ventas", "cuenta": "rival", "x": 7.2, "url": "https://ig.test/1"}]}],
                     "sin_formula": [{"gancho": "Raro pero funciona", "cuenta": "otra", "x": 5, "url": "https://ig.test/2"}]}}
    monkeypatch.setitem(plantillas.env.globals, "lupi_de", lambda n: datos)
    pagina = cliente.get(f"/negocios/{nid}/investigacion").text
    assert 'id="noticias"' in pagina and "Instagram premia los reels largos" in pagina and "quedan 19 h para grabarla" in pagina
    assert "Captura de la fuente" in pagina and "Lo dice la fuente tal cual" in pagina and "3 medios" in pagina
    assert 'id="formulas"' in pagina and "El error que todos cometen" in pagina and "Muestra suficiente" in pagina
    assert "×1,8" in pagina and "7 usos" in pagina
    assert "Raro pero funciona" in pagina and "unas 9 palabras" in pagina
    assert 'id="perfil"' in pagina and "<b>62</b>" in pagina and "+7 desde la última" in pagina
    assert pagina.index("La bio") < pagina.index("El enlace") and "No se ve desde fuera" in pagina
    assert "Ya está bien: La foto." in pagina

    ap.pedir(nid, "analista", "kit", "Borrador desde la web", {
        "fuentes_nuevas": [{"tipo": "rss", "valor": "https://blog.test/feed", "motivo": "Publica cada semana"}],
        "preguntas_abiertas": ["¿Cuánto cobras por la mentoría?"]})
    ap.pedir(nid, "analista", "cuentas", "Cuentas por tipo", {"consultas": [], "cuentas": [
        {"plataforma": "instagram", "usuario": "mentora", "tipo": "adyacente", "motivo": "Mismo público"}]})
    aprob = cliente.get(f"/negocios/{nid}/aprobaciones").text
    assert "https://blog.test/feed" in aprob and "¿Cuánto cobras por la mentoría?" in aprob and ">Adyacente<" in aprob


def test_las_pantallas_pendientes_de_cada_agente(app_aislada, monkeypatch):
    from radar import db as _db
    from radar.agentes import kit as kit_marca
    from radar.main import plantillas
    from .test_agentes import _guion_aprobado
    cliente, nid = _negocio_con_cliente(app_aislada)
    # Kit: lo que falta (Orby) y cómo trabajas.
    kit_marca.cambiar(nid, angulos={"principal": "Vender sin perseguir", "sub": []}, hashtags=["#ventas"],
                      ofertas=[{"id": "o1", "nombre": "Mentoría", "url": "https://web.test/m", "cta": "Agenda una llamada"}])
    kit = cliente.get(f"/negocios/{nid}/kit").text
    assert 'id="falta"' in kit and "Lo que falta en el Kit" in kit and "Completar" in kit
    assert 'id="negocio"' in kit and "Vender sin perseguir" in kit and "Mentoría" in kit and "Agenda una llamada" in kit
    # Investigación: los botones de Lupi.
    inv = cliente.get(f"/negocios/{nid}/investigacion").text
    for ruta in ("borrador-ficha", "sugerir-cuentas", "perfil"):
        assert f"/investigacion/{ruta}" in inv, ruta
    assert "Puntuar mi perfil" in inv and "Leer mi web" in inv and "Sugerir cuentas" in inv
    # Publicación: el ensayo y los reels de prueba.
    monkeypatch.setitem(plantillas.env.globals, "reels_prueba_de", lambda n: {"activa": True, "comprobado": False, "al_dia": 9,
                                                                              "desde": "08:00", "hasta": "21:00"})
    pub = cliente.get(f"/negocios/{nid}/publicacion").text
    assert "No salió en mi perfil" in pub and "/publicacion/reels-prueba/fuera-del-perfil" in pub
    # Escri en modo guion: «Guion», los ganchos con su nota y el carrusel.
    monkeypatch.setitem(plantillas.env.globals, "modo_de", lambda n: "guion")
    gid, _ = _guion_aprobado(nid, "Llamadas", "Si tus llamadas no cierran es por esto.")
    with _db.conexion() as con:
        con.execute("UPDATE guiones SET validacion = ?, ganchos = ?, textos = ? WHERE id = ?", (
            '{"modo": "guion", "palabras": 120, "segundos": 48}',
            '[{"gancho": "Tus llamadas no cierran por esto", "nota": 82, "veredicto": "intriga", "formula": 1, "peor": "", "en_pantalla": "No cierras"}]',
            '{"carrusel": [{"titular": "El error", "texto": "Hablar de precio al final"}], "post_texto": "Un post que se sostiene solo."}', gid))
    guion = cliente.get(f"/negocios/{nid}/guiones/{gid}").text
    assert "El guion" in guion and 'id="ganchos"' in guion and "Tus llamadas no cierran por esto" in guion and ">82<" in guion
    assert "No cierras" in guion and 'id="carrusel"' in guion and "Hablar de precio al final" in guion and 'id="post-texto"' in guion
    assert "Guiones" in cliente.get(f"/negocios/{nid}/guiones").text
    # El modo demo, en el menú de cualquier página.
    assert "data-demo-boton" in guion and 'class="selector-nombre" data-privado' in guion


def test_la_landing_sale_en_la_raiz_sin_sesion(app_aislada, monkeypatch):
    from fastapi.testclient import TestClient
    from radar.main import app, plantillas
    from .test_radar import _registrar
    _registrar(app_aislada, "duena@ejemplo.com")
    anonimo = TestClient(app)
    r = anonimo.get("/", follow_redirects=False)
    assert r.status_code == 200 and "Conoce a Orby." in r.text and "Solicitar implementación" in r.text
    assert "data-orby3d" in r.text and "/static/landing3d.js" in r.text  # Orby en 3D en la portada
    assert "Ver el código en GitHub" in r.text and 'href="/registro">Empieza gratis' in r.text  # gratis arriba; GitHub en «Código abierto»
    assert "data-escaparate" in r.text and "/static/escaparate/sala.json" in r.text  # la oficina de verdad, con datos de ejemplo
    for seccion in ("producto", "equipo", "como", "control", "implementacion", "preguntas", "solicitar"):
        assert f'id="{seccion}"' in r.text, seccion
    assert "A medida" in r.text  # el precio, hasta que se ponga uno
    for agente in ("Lupi", "Plani", "Escri", "Monti", "Publi", "Chati"):
        assert f"<h3>{agente}</h3>" in r.text, agente
    assert "/static/marca/agentes/analista.webp" in r.text  # los renders 3D del equipo
    # Sin la ruta /solicitar, el botón lleva al enlace configurado (o al registro).
    monkeypatch.setitem(plantillas.env.globals, "ruta_existe", lambda ruta, metodo="POST": False)
    sin_ruta = anonimo.get("/").text
    assert 'href="/registro"' in sin_ruta and 'action="/solicitar"' not in sin_ruta
    monkeypatch.setitem(plantillas.env.globals, "URL_SOLICITAR", "https://citas.test/orby")
    monkeypatch.setitem(plantillas.env.globals, "URL_GITHUB", "https://github.test/orby")
    r = anonimo.get("/").text
    assert 'href="https://citas.test/orby"' in r and 'href="https://github.test/orby"' in r
    # Con la ruta /solicitar, el formulario en la propia página.
    monkeypatch.setitem(plantillas.env.globals, "ruta_existe", lambda ruta, metodo="POST": ruta == "/solicitar")
    r = anonimo.get("/").text
    assert 'action="/solicitar"' in r and 'name="negocio"' in r and 'name="redes"' in r and 'href="#solicitar"' in r
    assert "Recibido." in anonimo.get("/?solicitud=gracias").text
    # Con sesión, a la app.
    assert app_aislada.get("/", follow_redirects=False).headers["location"] == "/app"


def test_como_trabajas_se_edita_y_se_reaprovecha_una_grabacion(app_aislada):
    from radar.agentes import kit as kit_marca
    cliente, nid = _negocio_con_cliente(app_aislada)
    kit = cliente.get(f"/negocios/{nid}/kit").text
    form = kit.split(f'action="/negocios/{nid}/kit/negocio"')[1].split("</form>")[0]
    for campo in ("angulo_principal", "posiciones", "modo_grabacion", "camara", "ppm", "tacos", "emojis", "formatos",
                  "ofertas", "cta_principal", "cta_web", "nunca_prometer", "limites_temas", "cifras_propias", "hashtags",
                  "fuentes", "zona", "reels_prueba_activa"):
        assert f'name="{campo}"' in form, campo
    # Lo que se guarda vuelve a salir en el formulario.
    cliente.post(f"/negocios/{nid}/kit/negocio", data={"angulo_principal": "Vender sin perseguir", "formatos_enviado": "1",
                                                      "formatos": ["reels", "carrusel"], "ofertas": "Mentoría | https://web.test/m | Reserva una llamada"})
    k = kit_marca.leer(nid)
    assert k["angulos"]["principal"] == "Vender sin perseguir" and k["formatos"]["carrusel"] and not k["formatos"]["historias"]
    kit = cliente.get(f"/negocios/{nid}/kit").text
    assert 'value="Vender sin perseguir"' in kit and 'value="carrusel" checked' in kit and "Mentoría | https://web.test/m | Reserva una llamada" in kit
    # Reaprovechar una grabación larga, en «Graba hoy».
    estrategia = cliente.get(f"/negocios/{nid}/estrategia").text
    assert 'id="reaprovechar"' in estrategia and f'action="/negocios/{nid}/estrategia/reaprovechar"' in estrategia
    assert 'name="video_propio"' in estrategia and 'name="texto"' in estrategia


def test_administracion_ensena_las_solicitudes(app_aislada):
    from radar import db
    from .test_radar import _registrar
    _registrar(app_aislada, "admin@ejemplo.test")
    sid = db.crear_solicitud({"nombre": "Laura", "email": "laura@ejemplo.test", "negocio": "Mentoría", "web": "web.test",
                              "redes": "instagram.com/laura", "mensaje": "Quiero publicar más", "origen": "landing"})
    pagina = app_aislada.get("/admin").text
    assert 'id="solicitudes"' in pagina and "Laura" in pagina and "Quiero publicar más" in pagina and "1 nueva" in pagina
    assert f'action="/admin/solicitudes/{sid}"' in pagina and 'name="notas"' in pagina


def test_instagram_sin_manychat_en_conectores_y_comunidad(app_aislada):
    from radar.agentes import instagram_dm
    cliente, nid = _negocio_con_cliente(app_aislada)
    conectores = cliente.get(f"/negocios/{nid}/conectores").text
    assert 'id="instagram"' in conectores and 'name="token" type="password"' in conectores and 'name="secreto" type="password"' in conectores
    assert "Desconectar Instagram" not in conectores
    comunidad = cliente.get(f"/negocios/{nid}/comunidad").text
    assert 'id="instagram"' in comunidad and f'{nid}/conectores#instagram' in comunidad and "data-ig-palabra>" not in comunidad

    # Conectado (sin llamar a Meta): el token no se vuelve a enseñar y salen las palabras, los ajustes y los envíos.
    instagram_dm._guardar(nid, {"token": "IGAA-secreto", "secreto": "s3", "usuario": "marca", "id": "17", "suscrito": True})
    instagram_dm.poner_palabra(nid, "guía", "https://ejemplo.test/guia", mensaje="Toma {enlace}")
    conectores = cliente.get(f"/negocios/{nid}/conectores").text
    assert "Conectado con @marca" in conectores and "IGAA-secreto" not in conectores and "Desconectar Instagram" in conectores
    comunidad = cliente.get(f"/negocios/{nid}/comunidad").text
    assert "<strong>GUIA</strong>" in comunidad and "En todos los reels" in comunidad and "data-ig-palabra>" in comunidad
    assert f'action="/negocios/{nid}/comunidad/instagram/ajustes"' in comunidad and "IGAA-secreto" not in comunidad


def test_paginas_publicas_de_privacidad_y_borrado(app_aislada):
    cliente, _ = _negocio_con_cliente(app_aislada)
    cliente.cookies.clear()
    privacidad = cliente.get("/privacidad")
    assert privacidad.status_code == 200 and "No guardamos el texto de tu comentario" in privacidad.text
    assert "hola@orbyos.es" in privacidad.text and 'href="/borrar-datos"' in privacidad.text
    borrar = cliente.get("/borrar-datos")
    assert borrar.status_code == 200 and "Borrar mis datos" in borrar.text and "nombre de usuario de Instagram" in borrar.text


def test_instagram_con_boton_si_la_instalacion_tiene_su_app(app_aislada, monkeypatch):
    from radar.agentes import instagram_dm
    cliente, nid = _negocio_con_cliente(app_aislada)
    monkeypatch.setattr(instagram_dm, "boton_disponible", lambda: True)
    pagina = cliente.get(f"/negocios/{nid}/conectores").text
    assert f'href="/negocios/{nid}/conectores/instagram/conectar"' in pagina and "Conectar Instagram" in pagina
    assert "Pegar el token a mano" in pagina and 'name="token" type="password"' in pagina


def test_ideas_adaptar_a_mi_voz_y_grabar_enlaza_su_estructura(app_aislada):
    from radar import db
    cliente, nid = _negocio_con_cliente(app_aislada)
    with db.conexion() as con:
        cid = con.execute("INSERT INTO cuentas (negocio_id, plataforma, usuario, propia, nivel) VALUES (?, 'instagram', 'ana', 0, 2)", (nid,)).lastrowid
        pid = con.execute("INSERT INTO posts (negocio_id, cuenta_id, plataforma, url, publicado, texto, vistas, x, destaca, ritmo, despega, encaje, actualizado) "
                          "VALUES (?, ?, 'instagram', 'https://instagram.com/p/x', '2026-10-27T10:00:00', 'Un reel que despega', 9000, 4, 1, 4, 1, 'si', '2026-10-27T10:00:00')",
                          (nid, cid)).lastrowid
    ideas = cliente.get(f"/negocios/{nid}/investigacion").text
    assert f'action="/negocios/{nid}/investigacion/posts/{pid}/adaptar"' in ideas and "Adaptar a mi voz" in ideas


def test_comunidad_regalos_en_tarjetas_con_sus_numeros(app_aislada):
    from radar.agentes import regalos
    cliente, nid = _negocio_con_cliente(app_aislada)
    pagina = cliente.get(f"/negocios/{nid}/comunidad").text
    assert '<a href="#regalos"' in pagina and "Aún no tienes regalos" in pagina and f'action="/negocios/{nid}/regalos"' in pagina
    r = regalos.guardar(nid, palabra="skill", destino="https://ejemplo.test/skills", activa=True, exacta=False)
    pagina = cliente.get(f"/negocios/{nid}/comunidad").text
    assert '<b class="rg-palabra">SKILL</b>' in pagina and "/r/" in pagina and "privados" in pagina
    assert f'action="/negocios/{nid}/regalos/{r["id"] if isinstance(r, dict) else r}/quitar"' in pagina


def test_panel_en_vivo_con_regalos_y_newsletter(app_aislada):
    from radar import newsletter
    from radar.agentes import regalos
    cliente, nid = _negocio_con_cliente(app_aislada)
    pagina = cliente.get(f"/negocios/{nid}/panel").text
    assert f'href="/negocios/{nid}/panel"' in pagina and "Aún no hay palabras clave" in pagina and "?parcial=1" in pagina
    regalos.guardar(nid, palabra="skill", destino="https://ejemplo.test/skills", activa=True, exacta=False)
    newsletter.poner_formulario("demo", "1")
    datos = newsletter.ajustes_listas()
    datos["demo"]["negocio"] = nid
    newsletter._listas_archivo().write_text(__import__("json").dumps(datos))
    newsletter.suscribir("demo", {"nombre": "Ana", "email": "ana@ejemplo.test", "acepto": "si", "origen": "SKILL"}, "127.0.0.1")
    parcial = cliente.get(f"/negocios/{nid}/panel?parcial=1").text
    assert 'id="panel-vivo"' in parcial and "<html" not in parcial
    assert "<b>SKILL</b>" in parcial and "Newsletter · demo" in parcial and "SKILL</b><span>1 alta" in parcial


def test_plan_gratis_puerta_falsa_y_candados(app_aislada):
    from radar import db
    from .test_radar import _dar_negocio, _otro_cliente, _registrar
    _registrar(app_aislada, "admin@ejemplo.com")
    cliente = _otro_cliente(app_aislada, "gratis@ejemplo.com")
    db.actualizar_usuario(db.usuario_por_email("gratis@ejemplo.com")["id"], plan="gratis")
    nid = _dar_negocio("gratis@ejemplo.com")
    puerta = cliente.get(f"/negocios/{nid}/mejorar?funcion=edicion").text
    assert "<h1>Edición de tus vídeos</h1>" in puerta and 'name="acepto" value="si" required' in puerta
    assert f'action="/negocios/{nid}/mejorar"' in puerta and "Publicación automática" in puerta
    assert "Te avisaremos" in cliente.get(f"/negocios/{nid}/mejorar?funcion=edicion&apuntado=1").text
    ideas = cliente.get(f"/negocios/{nid}/investigacion").text
    assert "pl-candado" in ideas and 'id="pl-aviso"' in ideas and 'value="gratis@ejemplo.com"' in ideas
    r = cliente.post(f"/negocios/{nid}/investigacion/escanear", headers={"X-Orby-Puerta": "1"})
    assert r.status_code == 402 and r.json()["plan"] == "premium"
    from fastapi.testclient import TestClient
    landing = TestClient(app_aislada.app).get("/").text
    assert 'href="/registro">Empieza gratis' in landing and "Gratis o completo" in landing


def test_sin_candados_fuera_del_plan_gratis(app_aislada):
    cliente, nid = _negocio_con_cliente(app_aislada)
    pagina = cliente.get(f"/negocios/{nid}/investigacion").text
    assert "pl-candado" not in pagina and 'id="pl-aviso"' not in pagina
