"""El Kit genérico: presets por tipo de negocio, los campos del onboarding (límites, ángulos, llamada a la acción…)
y cómo entran desde las llamadas."""
from radar import db
from radar.agentes import aprobaciones as ap
from radar.agentes import kit, llamadas

from .test_radar import _dar_negocio, _otro_cliente, _registrar, app_aislada, sin_claves_reales  # noqa: F401


def _negocio(app_aislada):
    _registrar(app_aislada, "duena@ejemplo.com")
    _otro_cliente(app_aislada, "cliente@ejemplo.com")
    return _dar_negocio("cliente@ejemplo.com")


def test_un_kit_nuevo_es_neutro_y_sin_emojis(app_aislada):
    nid = _negocio(app_aislada)
    k = kit.leer(nid)
    assert k["carriles"] == kit.CARRILES_INICIALES and k["modo_grabacion"] == "estructura"
    assert k["limites"]["cifras_propias"] and k["cta"]["principal"] == "palabra_clave"
    assert "👇" not in k["comunidad"]["mensaje_dm"] and k["voz"]["ppm"] == 150


def test_el_preset_solo_pisa_lo_que_sigue_como_al_empezar(app_aislada):
    nid = _negocio(app_aislada)
    k = kit.aplicar_preset(nid, "agencia")
    assert k["nicho"] == "agencia" and k["carriles"][0]["id"] == "error" and k["cta"]["principal"] == "llamada"
    assert k["fuentes"] and k["mezcla"] == kit.PRESETS["agencia"]["mezcla"]
    kit.cambiar(nid, carriles=[{"id": "mio", "nombre": "Lo mío", "cuota": 3, "etapa": "tofu", "descripcion": ""}])
    k = kit.aplicar_preset(nid, "servicios")
    assert k["carriles"][0]["id"] == "mio" and k["cta"]["principal"] == "dm"


def test_sin_cifras_propias_no_hay_cifras_y_el_contexto_lo_dice(app_aislada):
    nid = _negocio(app_aislada)
    kit.anadir_prueba(nid, {"titulo": "Laura", "cifra": "12 clientes", "fuente": "Stripe"})
    assert kit.cifras_permitidas(kit.leer(nid)) == ["12 clientes"]
    kit.cambiar(nid, **kit.limpiar_estrategia({"limites": {"cifras_propias": "no", "temas_vetados": ["política"]},
                                               "angulos": {"principal": "La tecnología es un regalo", "sub": ["contexto"]},
                                               "hashtags": ["#IA", "marketing digital"]}))
    k = kit.leer(nid)
    assert kit.cifras_permitidas(k) == []
    texto = kit.contexto({"id": nid, "ficha": {}}, k)
    assert "NADA de cifras propias" in texto and "política" in texto and "La tecnología es un regalo" in texto
    assert "#ia #marketingdigital" in texto


def test_la_estrategia_de_las_llamadas_entra_sin_pisar_lo_que_no_trae(app_aislada):
    nid = _negocio(app_aislada)
    kit.cambiar(nid, cta={"principal": "dm", "web": "https://mia.es", "prefijo_utm": "mia"})
    extraido = {"tacos": "suaves", "emojis": "sin_dato", "camara": "cara", "modo_grabacion": "guion",
                "posiciones": ["Publicar menos y mejor"], "dia_grabacion": "lunes",
                "limites": {"temas_vetados": [], "no_se_dicen": ["mi exsocio"], "afirmaciones_prohibidas": [],
                            "cifras_propias": "no"},
                "cta_principal": "palabra_clave", "formatos": ["reels", "carrusel"], "hashtags": ["#ventas"],
                "ofertas": [{"nombre": "Mentoría", "url": "https://mia.es/m", "cta": "Agenda una llamada"}],
                "angulos": {"principal": "", "sub": []}, "nunca_prometer": [], "fuentes": []}
    est = llamadas.estrategia_de(extraido)
    assert "emojis" not in est["voz"] and "angulos" not in est and est["limites"]["cifras_propias"] is False
    a = ap.pedir(nid, "jefa", "kit", "Kit", {"estrategia": est, "origen": "prueba"})
    ap.decidir(a["id"], "aprobar", por="cliente@ejemplo.com")
    k = kit.leer(nid)
    assert k["voz"]["tacos"] == "suaves" and k["voz"]["emojis"] == "pocos" and k["voz"]["posiciones"]
    assert k["cta"] == {"principal": "palabra_clave", "web": "https://mia.es", "prefijo_utm": "mia"}
    assert k["formatos"]["carrusel"] and k["formatos"]["reels"] and not k["formatos"]["historias"]
    assert k["modo_grabacion"] == "guion" and k["dia_grabacion"] == "lunes" and k["ofertas"][0]["nombre"] == "Mentoría"
    assert k["limites"]["no_se_dicen"] == ["mi exsocio"] and not k["limites"]["cifras_propias"]


def test_el_tipo_de_cada_cuenta_de_la_competencia(app_aislada):
    from radar.agentes import analista
    nid = _negocio(app_aislada)
    a = ap.pedir(nid, "jefa", "kit", "Kit", {"competencia": [
        {"nombre": "Rival", "instagram": "@rival", "tiktok": "", "youtube": "", "tipo": "directa"},
        {"nombre": "Grande", "instagram": "grande", "tiktok": "", "youtube": "", "tipo": "aspiracional"}]})
    ap.decidir(a["id"], "aprobar", por="cliente@ejemplo.com")
    with db.conexion() as con:
        tipos = {f["usuario"]: f["tipo"] for f in con.execute("SELECT usuario, tipo FROM cuentas WHERE negocio_id = ?", (nid,))}
    assert tipos == {"rival": "directa", "grande": "aspiracional"}
    assert {c["usuario"] for c in analista.cuentas(nid)} >= {"rival", "grande"}


def test_el_onboarding_pide_el_tipo_de_negocio_y_como_graba(app_aislada):
    nid = _negocio(app_aislada)
    v = llamadas.vista(nid)
    campos = {c["clave"]: c for p in v["preguntas"] for c in p["campos"]}
    assert campos["nicho"]["opciones"] == list(kit.PRESETS) and campos["nicho"]["etiquetas"]["coach"] == "Coach o consultor"
    llamadas.guardar_preguntas(nid, {"nicho": "infoproducto", "modo_grabacion": "guion", "camara": "voz",
                                     "instagram": "@mia", "videos_semana": "7"})
    k = kit.leer(nid)
    assert k["nicho"] == "infoproducto" and k["carriles"][0]["id"] == "leccion"
    assert k["modo_grabacion"] == "guion" and k["voz"]["camara"] == "voz"
    assert "nicho" not in db.negocio(nid)["ficha"] and llamadas.vista(nid)["paso"] == "llamadas"


def test_reels_de_prueba_apagados_hasta_que_se_activan(app_aislada):
    nid = _negocio(app_aislada)
    assert kit.leer(nid)["reels_prueba"] == kit.REELS_PRUEBA and "reels_prueba" in ap.TIPOS
    llamadas.guardar_preguntas(nid, {"reels_prueba": "si"})
    r = kit.leer(nid)["reels_prueba"]
    assert r["activa"] and r["al_dia"] == 9 and r["desde"] == "08:00"
    assert kit.limpiar_estrategia({"reels_prueba": {"al_dia": 99, "desde": "25:00"}})["reels_prueba"]["al_dia"] == 20


def test_la_identidad_guarda_subtitulos_musica_y_nunca(app_aislada):
    from radar.agentes import identidad
    _registrar(app_aislada, "duena@ejemplo.com")
    cliente = _otro_cliente(app_aislada, "cliente@ejemplo.com")
    nid = _dar_negocio("cliente@ejemplo.com")
    cliente.post(f"/negocios/{nid}/kit/identidad", data={"colores": "#112233 principal", "subtitulos": "simple",
                                                        "musica": "si", "sonidos": "no", "nunca": "Cajas\nEmojis"})
    i = identidad.leer(nid)
    assert i["subtitulos"] == "simple" and i["musica"] is True and i["sonidos"] is False and i["nunca"] == ["Cajas", "Emojis"]
    cliente.post(f"/negocios/{nid}/kit/identidad", data={"colores": "#112233 principal"})
    assert identidad.leer(nid)["nunca"] == ["Cajas", "Emojis"]  # sin esos campos, no se tocan


def test_con_la_web_y_las_redes_lupi_propone_ficha_y_cuentas(app_aislada, monkeypatch):
    from radar import jobs, llm
    from radar.agentes import analista_web
    nid = _negocio(app_aislada)
    lanzados = []
    monkeypatch.setattr(llm, "disponible", lambda: True)
    monkeypatch.setattr(jobs, "en_segundo_plano", lambda f, *a: lanzados.append(a[0].__name__))
    monkeypatch.setattr(analista_web, "trabajo_borrador_ficha", lambda nid, url="": None)
    monkeypatch.setattr(analista_web, "trabajo_sugerir_cuentas", lambda nid: None)
    llamadas.guardar_preguntas(nid, {"web": "https://mia.es", "instagram": "@mia"})
    assert len(lanzados) == 2  # la ficha desde la web y las cuentas desde las redes
    lanzados.clear()
    llamadas.guardar_preguntas(nid, {"web": "https://mia.es", "instagram": "@mia"})  # sin cambios: nada
    assert lanzados == []


def test_como_trabajas_se_guarda_desde_el_kit(app_aislada):
    _registrar(app_aislada, "duena@ejemplo.com")
    cliente = _otro_cliente(app_aislada, "cliente@ejemplo.com")
    nid = _dar_negocio("cliente@ejemplo.com")
    r = cliente.post(f"/negocios/{nid}/kit/negocio", data={
        "cifras_propias": "no", "limites_temas": "política\nfútbol", "tacos": "suaves", "ppm": "170",
        "posiciones": "Publicar menos y mejor", "formatos_enviado": "1", "formatos": ["reels", "carrusel"],
        "cta_principal": "llamada", "cta_web": "https://mia.es", "hashtags": "#IA marketing",
        "fuentes": "rss https://blog.es/feed\nnovedades de IA", "ofertas": "Mentoría | https://mia.es/m | Agenda una llamada",
        "reels_prueba_activa": "1", "modo_grabacion": "guion"})
    assert r.status_code == 200
    k = kit.leer(nid)
    assert not k["limites"]["cifras_propias"] and k["limites"]["temas_vetados"] == ["política", "fútbol"]
    assert k["voz"]["tacos"] == "suaves" and k["voz"]["ppm"] == 170 and k["voz"]["posiciones"] == ["Publicar menos y mejor"]
    assert k["formatos"] == {"reels": True, "carrusel": True, "historias": False, "texto": False}
    assert k["cta"]["principal"] == "llamada" and k["cta"]["web"] == "https://mia.es"
    assert k["fuentes"] == [{"tipo": "rss", "valor": "https://blog.es/feed"}, {"tipo": "busqueda", "valor": "novedades de IA"}]
    assert k["ofertas"][0]["url"] == "https://mia.es/m" and k["reels_prueba"]["activa"] and k["modo_grabacion"] == "guion"
    cliente.post(f"/negocios/{nid}/kit/negocio", data={"tacos": "no"})  # lo que no llega no se toca
    k = kit.leer(nid)
    assert k["voz"]["tacos"] == "no" and k["voz"]["ppm"] == 170 and k["limites"]["temas_vetados"] == ["política", "fútbol"]


def test_reaprovechar_una_grabacion_desde_estrategia(app_aislada, monkeypatch):
    from radar import jobs, llm
    from radar.agentes import estratega
    _registrar(app_aislada, "duena@ejemplo.com")
    cliente = _otro_cliente(app_aislada, "cliente@ejemplo.com")
    nid = _dar_negocio("cliente@ejemplo.com")
    llamadas_ = []
    monkeypatch.setattr(llm, "disponible", lambda: True)
    monkeypatch.setattr(jobs, "en_segundo_plano", lambda f, *a: f(*a))
    monkeypatch.setattr(estratega, "reaprovechar", lambda neg, texto, titulo, **k: llamadas_.append((titulo, k)) or (None, ""))
    r = cliente.post(f"/negocios/{nid}/estrategia/reaprovechar", data={"texto": "corto"})
    assert "muy corto" in r.text and not llamadas_
    cliente.post(f"/negocios/{nid}/estrategia/reaprovechar", data={"texto": "palabra " * 200, "titulo": "Mi pódcast",
                                                                  "video_propio": "0"})
    assert llamadas_ == [("Mi pódcast", {"video_propio": False})]
