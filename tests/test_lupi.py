"""Lupi: fórmulas de gancho que funcionan, tipos de cuenta, mesa de noticias, cuentas sugeridas, borrador de la ficha
desde la web y nota del perfil. Todo con datos simulados: ni internet, ni Apify, ni Claude de verdad."""
import json
from datetime import datetime, timedelta

from radar import db as _db
from radar import llm
from radar.agentes import analista, analista_web, estado, ganchos, noticias
from radar.agentes import aprobaciones as ap

from .test_agentes import _negocio_con_cliente, db_negocio
from .test_radar import app_aislada, sin_claves_reales  # noqa: F401


def _hace(**kw) -> str:
    return (datetime.now() - timedelta(**kw)).isoformat(timespec="seconds")


def _cuenta_con_posts(nid, usuario, ganchos_y_x, *, propia=False, vistas=10_000, tipo=""):
    analista.anadir_cuenta(nid, "instagram", usuario, propia=propia, tipo=tipo)
    c = next(c for c in analista.cuentas(nid) if c["usuario"] == usuario)
    analista._guardar_posts(nid, c, [{"url": f"{usuario}{i}", "cuenta": usuario, "vistas": vistas, "texto": g,
                                      "publicado": _hace(days=5 + i)} for i, (g, _) in enumerate(ganchos_y_x)])
    with _db.conexion() as con:
        for i, (_, x) in enumerate(ganchos_y_x):
            con.execute("UPDATE posts SET x = ? WHERE url = ?", (x, f"{usuario}{i}"))
    return c


# ---------------------------------------------------------------- fórmulas de gancho

def test_que_formulas_de_gancho_funcionan_en_el_nicho(app_aislada):
    _, nid = _negocio_con_cliente(app_aislada)
    _cuenta_con_posts(nid, "yo", [("Mi día", 1)] * 3, propia=True, vistas=1_000)
    _cuenta_con_posts(nid, "rival", [
        ("Nadie te cuenta que vender por llamada cansa.", 9), ("Nobody tells you this about sales calls.", 7),
        ("Nadie te dice cuánto cobrar al empezar.", 2),
        ("Respondo a vuestros comentarios de hoy.", 6),  # destaca sin fórmula: puede ser una nueva
        ("Deja de mandar audios a tus clientes.", 1.2), ("Deja de grabar en horizontal.", 0.9),
        ("Deja de usar plantillas.", 1.0), ("Mi café de la mañana.", 0.8)], vistas=5_000)
    _cuenta_con_posts(nid, "gigante", [("Nadie te cuenta lo de los gigantes.", 20)] * 3, vistas=900_000)
    assert analista.fuera_de_escala(nid) == {next(c["id"] for c in analista.cuentas(nid) if c["usuario"] == "gigante")}
    r = analista.formulas_que_funcionan(nid)
    assert r["posts"] == 8 and r["cuentas"] == 1 and r["confianza"] == "poca"  # la gigante no cuenta: juega otra liga
    nadie = ganchos.clasificar("Nadie te cuenta que vender por llamada cansa.")
    assert [d["formula"] for d in r["destacan"]] == [nadie]  # «Deja de» se usa mucho pero no empuja
    d = r["destacan"][0]
    assert d["usos"] == 3 and d["arriba"] == 2 and d["abajo"] == 1 and d["empuje"] > 1.3
    assert [x["gancho"] for x in r["sin_formula"]] == ["Respondo a vuestros comentarios de hoy."]
    texto = analista.formulas_en_texto(nid)
    assert "Nadie te cuenta" in texto and "Muestra pequeña" in texto


def test_cada_plantilla_y_post_llevan_su_formula_tambien_en_ingles(app_aislada):
    # Las fórmulas son las del catálogo común (ganchos.py): aquí solo se mira que Lupi las use, sea cual sea su número.
    assert analista.clasificar_gancho("Nobody tells you your first 30 reels will flop")
    assert analista.clasificar_gancho("OpenAI acaba de lanzar un modelo que razona solo")
    assert analista.clasificar_gancho("Hoy os traigo algo") is None
    _, nid = _negocio_con_cliente(app_aislada)
    _cuenta_con_posts(nid, "rival", [("Stop posting every day. Do this instead.", 4)])
    with _db.conexion() as con:
        pid = con.execute("SELECT id FROM posts WHERE negocio_id = ?", (nid,)).fetchone()[0]
    p = analista.post(nid, pid)
    assert p["formula"] == ganchos.clasificar("Stop posting every day. Do this instead.") and p["formula_nombre"]


def test_el_tipo_de_cuenta_pone_su_prioridad(app_aislada):
    _, nid = _negocio_con_cliente(app_aislada)
    analista.anadir_cuenta(nid, "tiktok", "grande", tipo="aspiracional")
    analista.anadir_cuenta(nid, "tiktok", "par", tipo="directa")
    cs = {c["usuario"]: c for c in analista.cuentas(nid)}
    assert cs["grande"]["nivel"] == 3 and cs["par"]["nivel"] == 1
    assert cs["grande"]["tipo"] == "aspiracional"
    assert analista.fuera_de_escala(nid) == {cs["grande"]["id"]}


# ---------------------------------------------------------------- mesa de noticias

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>OpenAI lanza un modelo que edita vídeo solo - El Diario</title><link>https://eldiario.example/a</link>
<pubDate>{fecha}</pubDate><description>El modelo cuesta 20 dólares al mes y edita vídeos de 10 minutos.</description></item>
</channel></rss>"""


def test_leer_un_rss_de_google_noticias():
    fecha = (datetime.now() - timedelta(hours=3)).strftime("%a, %d %b %Y %H:%M:%S +0000")
    items = noticias.leer_rss(RSS.format(fecha=fecha), "busqueda:ia")
    assert items[0]["titulo"] == "OpenAI lanza un modelo que edita vídeo solo" and items[0]["medio"] == "El Diario"
    assert items[0]["publicado"] and "20 dólares" in items[0]["resumen"]
    assert noticias.leer_rss("esto no es xml", "x") == []


def test_solo_se_leen_direcciones_publicas():
    for url in ("http://localhost:8000/", "http://127.0.0.1/admin", "file:///etc/passwd", "http://10.0.0.1/", ""):
        assert not noticias.url_publica(url)


def test_la_misma_noticia_en_varios_medios_es_una_historia():
    base = {"publicado": _hace(hours=2), "resumen": "", "origen": "x", "puntos": 0}
    hs = noticias.agrupar([
        {**base, "titulo": "OpenAI lanza un modelo que edita vídeo solo", "url": "u1", "medio": "A"},
        {**base, "titulo": "OpenAI lanza su modelo que edita vídeo", "url": "u2", "medio": "B"},
        {**base, "titulo": "Google cambia las búsquedas en España", "url": "u3", "medio": "A"}])
    assert sorted(h["cobertura"] for h in hs) == [1, 2]
    caliente = max(hs, key=lambda h: h["cobertura"])
    assert noticias.calor(caliente) > noticias.calor(min(hs, key=lambda h: h["cobertura"]))


def _guion(gancho, pasos=None, comprobaciones=None, cabecera="Un modelo que edita vídeo solo"):
    pasos = pasos or [{"texto": "OpenAI ha sacado un modelo que edita vídeos de 10 minutos sin que toques nada.",
                       "visual": "captura_fuente"},
                      {"texto": "Cuesta 20 dólares al mes y, según El Diario, ya lo usan agencias.", "visual": "a_camara"},
                      {"texto": "Para tu negocio, esto significa grabar más y editar menos cada semana.", "visual": "texto"}]
    return {"numero": 1, "sirve": True, "motivo": "Le importa a su cliente", "cabecera": cabecera, "gancho": gancho,
            "pasos": pasos, "angulo": "Editar ya no es la excusa para no publicar.",
            "comprobaciones": comprobaciones or [{"dato": "20 dólares al mes", "estado": "confirmado"}]}


def _guion(gancho="OpenAI acaba de sacar un modelo que edita tus vídeos por ti.", titular="Un modelo que edita solo",
           comprobaciones=None, **cambios):
    return {"numero": 1, "sirve": True, "motivo": "Le cambia cómo graba", "titular": titular, "gancho": gancho,
            "que_paso": "OpenAI ha sacado un modelo que edita vídeos de 10 minutos sin tocar nada. Cuesta 20 dólares al "
                        "mes y, según El Diario, ya lo prueban agencias.",
            "como_se_ve": "demo",
            "por_que_importa": "Si grabas para vender, editar ya no es la excusa para publicar una vez al mes.",
            "tu_lectura": "Yo lo probaría con los brutos de esta semana y miraría solo una cosa: si mantiene tu forma "
                          "de hablar o la aplana.",
            "cierre": "Si quieres, la semana que viene te enseño la prueba.",
            "comprobaciones": comprobaciones or [{"dato": "20 dólares al mes", "estado": "confirmado"}], **cambios}


def test_el_guion_de_una_noticia_se_comprueba_en_codigo():
    fuente = "OpenAI lanza un modelo que edita vídeo solo. El modelo cuesta 20 dólares al mes y edita vídeos de 10 minutos."
    assert noticias.validar(_guion(), fuente) == []
    inventado = _guion("Un modelo que edita vídeo y ya tiene 3 millones de usuarios.")
    assert any("3" in f for f in noticias.validar(inventado, fuente))
    sin_comprobar = _guion(comprobaciones=[{"dato": "lo prueban agencias", "estado": "sin_comprobar"}])
    assert any("sin comprobar" in f for f in noticias.validar(sin_comprobar, fuente))
    assert any("titular" in f for f in noticias.validar(_guion(titular="Un titular demasiado largo para leerlo de un vistazo"), fuente))
    assert any("tu_lectura" in f for f in noticias.validar(_guion(tu_lectura=""), fuente))
    assert any("dura" in f for f in noticias.validar(_guion(), fuente, ppm=60))  # muy despacio: se pasa de largo


def test_la_hora_limite_sale_de_cuando_se_publico():
    ahora = datetime(2026, 10, 26, 12, 0)
    assert noticias.hora_limite("2026-10-26T10:00:00", ahora) == datetime(2026, 10, 28, 2, 0)  # 40 h desde que salió
    assert noticias.hora_limite("2026-10-24T12:00:00", ahora) == datetime(2026, 10, 26, 18, 0)  # vieja: margen de 6 h


def test_la_mesa_elige_escribe_y_no_repite(app_aislada, monkeypatch):
    _, nid = _negocio_con_cliente(app_aislada)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "prueba")
    leidas = []
    item = {"titulo": "OpenAI lanza un modelo que edita vídeo solo", "url": "https://eldiario.example/a",
            "medio": "El Diario", "publicado": _hace(hours=3), "origen": "busqueda:ia", "puntos": 0,
            "resumen": "El modelo cuesta 20 dólares al mes y edita vídeos de 10 minutos."}
    monkeypatch.setattr(noticias, "LEER", lambda f, kit: leidas.append(f) or [item])
    pedidas = []
    monkeypatch.setattr(llm, "json_con_esquema", lambda s, p, e, **k: pedidas.append(p) or {"noticias": [_guion()]})
    _db.actualizar_negocio(nid, {**db_negocio(nid)["ficha"], "palabras_clave": "inteligencia artificial"})
    r = noticias.mesa(db_negocio(nid))
    assert leidas == [{"tipo": "busqueda", "valor": "inteligencia artificial"}]  # sin fuentes en el Kit, las de su cliente
    assert len(r["nuevas"]) == 1 and "DATOS" in noticias.SISTEMA and "<noticia" in pedidas[0]
    n = noticias.noticias(nid)[0]
    assert n["lista"] and n["url"] == "https://eldiario.example/a"
    assert datetime.fromisoformat(n["grabar_antes"]) - datetime.fromisoformat(item["publicado"]) == timedelta(hours=40)
    assert n["guion"]["cabecera"] == "Un modelo que edita solo" and n["guion"]["pasos"][0]["visual"] == "demo"
    assert "grabar antes del" in noticias.noticias_en_texto(nid)
    assert noticias.mesa(db_negocio(nid))["nuevas"] == [] and len(pedidas) == 1  # la misma noticia no se paga dos veces


# ---------------------------------------------------------------- cuentas sugeridas por tipo

def test_lupi_sugiere_cuentas_reales_por_tipo_y_fuentes(app_aislada, monkeypatch):
    _, nid = _negocio_con_cliente(app_aislada)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "prueba")
    analista.anadir_cuenta(nid, "instagram", "yasigo")
    informe = ("@experta.ventas (https://www.instagram.com/experta.ventas/) hace reels de cierre por llamada. "
               "@yasigo también. Subforo r/sales. RSS: https://blog.example/feed.xml")
    monkeypatch.setattr(llm, "investigar", lambda s, p, **k: informe)
    monkeypatch.setattr(llm, "json_con_esquema", lambda s, p, e, **k: {
        "cuentas": [{"plataforma": "instagram", "usuario": "@experta.ventas", "tipo": "directa", "motivo": "Cierre"},
                    {"plataforma": "instagram", "usuario": "inventada_99", "tipo": "adyacente", "motivo": "Nada"},
                    {"plataforma": "instagram", "usuario": "yasigo", "tipo": "directa", "motivo": "Ya"}],
        "fuentes": [{"tipo": "reddit", "valor": "r/sales", "motivo": "Preguntas"},
                    {"tipo": "rss", "valor": "https://blog.example/feed.xml", "motivo": "Blog"},
                    {"tipo": "rss", "valor": "https://inventado.example/rss", "motivo": "No salió"}]})
    r = analista_web.sugerir_cuentas(db_negocio(nid))
    assert r["cuentas"] == 1 and r["fuentes"] == 2
    a = next(x for x in ap.pendientes(nid) if x["tipo"] == "cuentas")
    assert a["datos"]["cuentas"] == [{"plataforma": "instagram", "usuario": "experta.ventas", "tipo": "directa",
                                      "motivo": "Cierre", "tema": analista.TIPOS_CUENTA["directa"]}]
    f = next(x for x in ap.pendientes(nid) if x["tipo"] == "kit")
    ap.decidir(f["id"], "aprobar")
    from radar.agentes import kit
    assert {(x["tipo"], x["valor"]) for x in kit.leer(nid)["fuentes"]} >= {("reddit", "sales"),
                                                                            ("rss", "https://blog.example/feed.xml")}


# ---------------------------------------------------------------- borrador de la ficha desde la web

WEB = """## https://ana.example
Ana Ruiz · Mentoría de ventas para coaches
Ayudo a coaches que ya tienen clientes a cerrar más llamadas sin sonar a vendedor.
Mentoría 1:1 de 12 semanas. Reserva tu llamada gratuita.
"Pasé de cerrar 2 de cada 10 llamadas a 5 de cada 10 en tres meses" - Laura, coach
No es para quien empieza de cero."""


def test_el_borrador_de_la_ficha_solo_dice_lo_que_dice_la_web(app_aislada, monkeypatch):
    _, nid = _negocio_con_cliente(app_aislada)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "prueba")
    _db.actualizar_negocio(nid, {**db_negocio(nid)["ficha"], "web": "https://ana.example", "a_quien": "Ya escrito"})
    monkeypatch.setattr(analista_web, "leer_web", lambda url: (WEB, ["https://ana.example/reserva"]))
    monkeypatch.setattr(llm, "json_con_esquema", lambda s, p, e, **k: {
        "nombre": "Ana Ruiz", "que_vende": "Mentoría para que los coaches cierren más llamadas.",
        "para_quien": "Coaches con clientes", "situacion": "Suenan a vendedor", "lo_que_consigue": "Cerrar más",
        "frenos": "", "no_es_para": "Quien empieza de cero",
        "ofertas": [{"nombre": "Mentoría 1:1", "detalle": "12 semanas", "precio": "1.500 €",
                     "url": "https://ana.example/inventada", "como_se_compra": "llamada"}],
        "testimonios": ["Pasé de cerrar 2 de cada 10 llamadas a 5 de cada 10 en tres meses", "Ana me cambió la vida"],
        "afirmaciones": ["De 2 a 5 de cada 10 llamadas", "Facturé 50.000 € más"], "por_preguntar": []})
    b = analista_web.borrador_de_la_ficha(db_negocio(nid))
    assert b["ofertas"][0]["precio"] == "" and b["ofertas"][0]["url"] == ""  # ni precio ni enlace inventados
    assert any("Cuánto cuesta" in q for q in b["por_preguntar"])
    assert b["testimonios"] == ["Pasé de cerrar 2 de cada 10 llamadas a 5 de cada 10 en tres meses"]
    assert b["afirmaciones"] == ["De 2 a 5 de cada 10 llamadas"]
    a = next(x for x in ap.pendientes(nid) if x["tipo"] == "kit")
    assert "a_quien" not in a["datos"]["ficha"] and a["datos"]["preguntas_abiertas"]  # lo ya escrito no se pisa
    ap.decidir(a["id"], "aprobar")
    ficha = db_negocio(nid)["ficha"]
    assert ficha["no_es_para"] == "Quien empieza de cero" and ficha["a_quien"] == "Ya escrito"


def test_el_texto_de_una_web_sin_codigo():
    html = "<html><head><style>.x{}</style><script>alert(1)</script></head><body><h1>Hola</h1><p>Vendo&nbsp;cursos</p></body>"
    assert analista_web.texto_de_html(html) == "Hola\nVendo cursos"


# ---------------------------------------------------------------- nota del perfil

def test_la_nota_del_perfil_sobre_100(app_aislada, monkeypatch):
    _, nid = _negocio_con_cliente(app_aislada)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "prueba")
    _db.actualizar_negocio(nid, {**db_negocio(nid)["ficha"], "videos_semana": "2"})
    analista.anadir_cuenta(nid, "instagram", "ana.ruiz", propia=True)
    analista.anadir_cuenta(nid, "tiktok", "anaruiz_99", propia=True)
    perfil = {"usuario": "ana.ruiz", "nombre": "Ana", "biografia": "Coach | Café", "enlace": "", "categoria": "",
              "seguidores": 900, "imagen": "",
              "ultimas": [{"fecha": _hace(days=d)[:10], "texto": "x", "imagen": ""} for d in (2, 9, 16, 40)]}
    pedidas = []
    monkeypatch.setattr(llm, "json_con_esquema", lambda s, p, e, **k: pedidas.append(p) or {"partes": [
        {"id": "quien", "puntos": 2, "motivo": "Solo el nombre", "arreglo": "Ana Ruiz | Ventas para coaches"},
        {"id": "promesa", "puntos": 50, "motivo": "Exagerado", "arreglo": "x"},  # se recorta a su máximo
        {"id": "siguiente_paso", "puntos": 0, "motivo": "Sin enlace", "arreglo": "Un enlace a la reserva"}]})
    r = analista_web.puntuar(db_negocio(nid), perfil)
    assert "Temas fijos" in pedidas[0] and "Llamada a la acción principal" in pedidas[0]  # se mide contra su Kit
    partes = {p["id"]: p for p in r["partes"]}
    assert partes["promesa"]["puntos"] == 15
    assert partes["ritmo"]["puntos"] == 4  # 3 posts en 4 semanas, de 8 que pide su plan
    assert partes["mismo_usuario"]["puntos"] == 0 and partes["profesional"]["puntos"] == 0
    assert partes["fijados"]["puntos"] is None
    assert r["sobre"] == 95 and r["sin_ver"] == 5 and r["total"] == 2 + 15 + 4
    assert r["arreglos"][0] == "coherencia" and r["arreglos"][-1] == "fijados"  # sin juzgar: 15 puntos por ganar
    assert analista_web.perfil_guardado(nid)["total"] == r["total"]
    assert analista_web.puntuar(db_negocio(nid), perfil)["antes"] == r["total"]


def test_sin_cuenta_de_instagram_no_se_puntua(app_aislada):
    _, nid = _negocio_con_cliente(app_aislada)
    assert "Instagram" in analista_web.puntuar_perfil(db_negocio(nid))["aviso"]
    assert estado.leer(nid, analista.AGENTE).get("perfil") is None
    assert len(analista_web.RUBRICA) == 11
    assert sum(r["puntos"] for r in analista_web.RUBRICA) == 100


# ---------------------------------------------------------------- desmontaje

def test_el_desmontaje_no_deja_colar_lo_del_creador():
    fuente = "Soy Marta de VentaPro y mi método Cierre10 te lo explico. Primero, cobra más. Luego vende."
    plantilla = {"gancho_literal": "Soy Marta de VentaPro", "del_creador": ["Marta", "VentaPro", "Cierre10"],
                 "pasos": [{"desde": 0, "hasta": 3, "papel": "gancho", "que_hace": "Se presenta", "dice": "[su nombre]"},
                           {"desde": 3, "hasta": 9, "papel": "desarrollo", "que_hace": "Explica Cierre10",
                            "dice": "su método en dos pasos"}]}
    assert any("del creador" in f for f in analista.validar_plantilla(plantilla, fuente, 10))
    plantilla["pasos"][1]["que_hace"] = "Explica [su método]"
    assert analista.validar_plantilla(plantilla, fuente, 10) == []


def test_el_ritmo_se_mide_en_codigo():
    palabras = json.dumps([{"word": "x", "start": i * 0.5, "end": i * 0.5 + 0.4} for i in range(21)])
    medido = analista.medir_ritmo(palabras, 30, {"pasos": [{"papel": "gancho", "desde": 0}, {"papel": "reenganche", "desde": 9}]})
    assert medido == {"palabras_por_segundo": round(21 / 10.4, 2), "reenganche_en": 30}
    assert analista.texto_del_post("Comenta PLAN y te lo mando\n#ventas #ia")["hashtags"] == 2


# ---------------------------------------------------------------- botones de Investigación

def test_botones_de_lupi_lanzan_su_trabajo(app_aislada, monkeypatch):
    cliente, nid = _negocio_con_cliente(app_aislada)
    from radar import jobs
    lanzados = []
    monkeypatch.setattr(jobs, "en_segundo_plano", lambda fn, *args: lanzados.append((fn.__name__, args)))
    r = cliente.post(f"/negocios/{nid}/investigacion/sugerir-cuentas", follow_redirects=False)
    assert "clave%20de%20Claude" in r.headers["location"] and not lanzados  # sin Claude no se lanza nada
    monkeypatch.setenv("ANTHROPIC_API_KEY", "prueba")
    r = cliente.post(f"/negocios/{nid}/investigacion/sugerir-cuentas", follow_redirects=False)
    assert r.headers["location"].endswith("#cuentas") and lanzados[-1] == ("trabajo_sugerir_cuentas", (nid,))
    r = cliente.post(f"/negocios/{nid}/investigacion/perfil", follow_redirects=False)
    assert "Apify" in __import__("urllib.parse").parse.unquote(r.headers["location"]) and len(lanzados) == 1
    monkeypatch.setenv("APIFY_TOKEN", "prueba")
    cliente.post(f"/negocios/{nid}/investigacion/perfil", follow_redirects=False)
    assert lanzados[-1] == ("trabajo_perfil", (nid,))
    _db.actualizar_negocio(nid, {**db_negocio(nid)["ficha"], "web": ""})
    r = cliente.post(f"/negocios/{nid}/investigacion/borrador-ficha", data={"url": ""}, follow_redirects=False)
    assert "Falta%20la%20web" in r.headers["location"]
    _db.actualizar_negocio(nid, {**db_negocio(nid)["ficha"], "web": "https://ana.example"})
    cliente.post(f"/negocios/{nid}/investigacion/borrador-ficha", data={"url": ""}, follow_redirects=False)
    assert lanzados[-1] == ("trabajo_borrador_ficha", (nid, "https://ana.example"))
    cliente.post(f"/negocios/{nid}/investigacion/borrador-ficha", data={"url": "otra.example"}, follow_redirects=False)
    assert lanzados[-1] == ("trabajo_borrador_ficha", (nid, "otra.example"))
