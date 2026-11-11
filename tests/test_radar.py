"""Lo que sigue de la app de antes: cuentas, la ficha del negocio, el motor de edición y los conectores."""
import pytest
from fastapi.testclient import TestClient

from radar import auth, config, db, gasto, jobs, llm
from radar.connectors import youtube
from radar.editor import frases as editor_frases
from radar.editor import modelo as editor_modelo
from radar.editor import montaje as editor_montaje
from radar.editor import plan as editor_plan
from radar.modules import edicion, ficha

CLAVES = ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "YOUTUBE_API_KEY", "META_AD_LIBRARY_TOKEN",
          "INSTAGRAM_TOKEN", "INSTAGRAM_USER_ID", "APIFY_TOKEN"]


@pytest.fixture(autouse=True)
def sin_claves_reales(monkeypatch):
    """Las pruebas nunca llaman a Claude, YouTube ni Apify de verdad: se quitan las claves del .env y cada prueba pone
    las que simula."""
    for c in CLAVES:
        monkeypatch.delenv(c, raising=False)


def test_youtube_outlier_y_duracion():
    assert youtube.ratio_outlier(50_000, 10_000) == 5.0
    assert youtube.ratio_outlier(100, 0) == 0.0
    assert youtube.segundos("PT1H2M3S") == 3723
    assert youtube.segundos("PT45S") == 45


def test_leer_competidores():
    cs = ficha.leer_competidores("Clínica Sonrisa, clinicasonrisa.es, @clinicasonrisa\n@otra_marca")
    assert cs[0] == {"nombre": "Clínica Sonrisa", "web": "clinicasonrisa.es", "instagram": "clinicasonrisa",
                     "linkedin": "", "youtube": "", "motivo": "Lo indicó el negocio"}
    assert cs[1]["nombre"] == "otra_marca"


def test_normalizar_reel_y_tiktok():
    from radar.connectors import apify_social
    r = apify_social.normalizar_reel({"ownerUsername": "clinica", "caption": "Antes y después", "videoPlayCount": 5000,
                                      "likesCount": 120, "videoDuration": 23.4, "shortCode": "ABC", "timestamp": "2026-09-01T10:00:00Z"})
    assert r["cuenta"] == "clinica" and r["vistas"] == 5000 and r["segundos"] == 23 and r["url"].endswith("/reel/ABC/")
    t = apify_social.normalizar_tiktok({"authorMeta": {"name": "dra"}, "text": "3 mitos", "playCount": 90000, "diggCount": 4000,
                                        "collectCount": 800, "shareCount": 50, "webVideoUrl": "https://tiktok.com/@dra/video/1",
                                        "createTimeISO": "2026-08-15T00:00:00.000Z", "videoMeta": {"duration": 31}})
    assert t["cuenta"] == "dra" and t["vistas"] == 90000 and t["guardados"] == 800 and t["fecha"] == "2026-08-15"
    assert apify_social.usuario_instagram("https://www.instagram.com/clinica.sonrisa/?hl=es") == "clinica.sonrisa"
    assert apify_social.usuario_instagram("@marca") == "marca" and apify_social.usuario_instagram("no vale!") == ""


def test_ratio_de_reels_por_cuenta():
    from radar.connectors import apify_social
    reels = [{"cuenta": "a", "vistas": 100}, {"cuenta": "a", "vistas": 100}, {"cuenta": "a", "vistas": 1000},
             {"cuenta": "b", "vistas": 10}]
    top = apify_social._con_ratio(reels, agrupar_por_cuenta=True)
    assert top[0]["vistas"] == 1000 and top[0]["ratio"] == 10.0


def test_ficha_combina_competidores_nuevos():
    perfil = ficha.perfil_basico({"que_vende": "x", "competidores": "Clínica Sonrisa, clinicasonrisa.es"})
    nueva = {"competidores": "Clínica Sonrisa, @clinicasonrisa\nOtra Clínica, otra.es, @otraclinica", "palabras_clave": "alineadores"}
    combinado = ficha.combinar(perfil, nueva)
    assert [c["instagram"] for c in combinado["competidores"]] == ["clinicasonrisa", "otraclinica"]
    assert combinado["palabras_clave"][0] == "alineadores"


def test_contrasenas_con_scrypt():
    guardada = auth.cifrar("una-clave-larga")
    assert guardada.startswith("scrypt$") and "una-clave-larga" not in guardada
    assert auth.comprobar("una-clave-larga", guardada) and not auth.comprobar("otra", guardada)


def test_cortes_de_silencios_y_subtitulos():
    palabras = [{"start": 0.5, "end": 0.9, "word": "Hola"}, {"start": 1.0, "end": 1.3, "word": "eh"},
                {"start": 3.0, "end": 3.4, "word": "esto"}, {"start": 3.45, "end": 3.9, "word": "funciona."}]
    tramos = edicion.tramos_hablados(palabras, 5.0, 0.4)
    assert len(tramos) == 2 and tramos[0][0] == pytest.approx(0.4) and tramos[1][0] == pytest.approx(2.9)
    mapeadas = edicion.mapear(palabras, tramos)
    assert [w["word"] for w in mapeadas] == ["Hola", "esto", "funciona."]  # la muletilla se va
    assert mapeadas[1]["start"] < 1.5  # el silencio ya no está
    assert [len(b) for b in edicion.bloques(mapeadas, 1)] == [1, 2]


def test_plantilla_de_estilo_incompleta_se_completa():
    e = edicion.completar_estilo({"ritmo": "rarísimo", "subtitulos": {"posicion": "lateral", "color_texto": "rojo",
                                                                    "palabras_por_bloque": 20}})
    s = e["subtitulos"]
    assert e["ritmo"] == "medio" and s["posicion"] == "abajo" and s["color_texto"] == "#FFFFFF" and s["palabras_por_bloque"] == 6


def test_gasto_de_claude_y_apify():
    from types import SimpleNamespace
    gasto.empezar()
    gasto.sumar_claude(SimpleNamespace(input_tokens=1_000_000, output_tokens=100_000, cache_read_input_tokens=0,
                                       cache_creation_input_tokens=0, server_tool_use=None))
    gasto.sumar_apify("valev-lab~facebook-ads-library", 100)
    u = gasto.uso()
    assert u["coste_claude"] == 6.0 and u["apify_coste"] == pytest.approx(0.045) and u["coste"] == pytest.approx(6.045)


def al_instante(funcion, *args):
    """En las pruebas, los análisis y las ediciones se hacen en el acto, sin hilos."""
    funcion(*args)


@pytest.fixture
def app_aislada(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "prueba.db")
    monkeypatch.setattr(config, "EDICIONES_DIR", tmp_path / "ediciones")
    monkeypatch.setattr(config, "ADMIN_EMAILS", set())
    monkeypatch.setattr(config, "EDITOR_PUBLICO", True)  # las pruebas registran clientes; se apaga donde se prueba
    for c in CLAVES:
        monkeypatch.delenv(c, raising=False)
    monkeypatch.setattr(jobs, "en_segundo_plano", al_instante)
    monkeypatch.setattr(edicion, "en_segundo_plano", al_instante)
    db.iniciar()
    from radar.main import app
    return TestClient(app)


FICHA = {"nombre": "Mentora Prueba", "que_vende": "Mentoría para coaches que quieren vender online", "web": "mentoraprueba.es",
         "competidores": "Clínica Sonrisa, clinicasonrisa.es, @clinicasonrisa", "ticket": "alto",
         "precio_principal": "Mentoría de 3 meses · 3.000 €", "modelo_venta": "llamada", "tipo_negocio": "consultoria",
         "seguidores": "2.500"}


def _registrar(cliente: TestClient, email: str) -> TestClient:
    r = cliente.post("/registro", data={"email": email, "nombre": email.split("@")[0], "clave": "clave-de-prueba"},
                     follow_redirects=False)
    assert r.status_code == 303
    return cliente


def _otro_cliente(app_aislada: TestClient, email: str, tipo: str = "negocio") -> TestClient:
    """Otra persona: quien administra le crea la cuenta y ella entra con su contraseña."""
    _registrar(app_aislada, email)  # app_aislada es la sesión de administración
    cliente = TestClient(app_aislada.app)
    assert cliente.post("/entrar", data={"email": email, "clave": "clave-de-prueba"}, follow_redirects=False).status_code == 303
    uid = db.usuario_por_email(email)["id"]
    db.actualizar_usuario(uid, tipo=tipo, plan=config.plan_inicial(tipo))
    return cliente


def _dar_negocio(email: str, ficha: dict | None = None) -> int:
    """El negocio que el equipo crea en la llamada de onboarding."""
    return db.crear_negocio(dict(ficha or FICHA), db.usuario_por_email(email)["id"])


def test_guardar_la_ficha_conserva_campos_antiguos(app_aislada):
    _registrar(app_aislada, "duena@ejemplo.com")
    neg_id = db.crear_negocio({"nombre": "Viejo", "que_vende": "x", "precios": "desde 2.900 €", "trafico": "calidad"},
                              db.usuario_por_email("duena@ejemplo.com")["id"])
    app_aislada.post(f"/negocios/{neg_id}/ficha", data=dict(FICHA, nombre="Viejo"))
    f = db.negocio(neg_id)["ficha"]
    assert f["precios"] == "desde 2.900 €" and f["ticket"] == "alto"


def test_admin_cambia_el_plan(app_aislada):
    _registrar(app_aislada, "duena@ejemplo.com")
    _otro_cliente(app_aislada, "cliente@ejemplo.com")
    uid = db.usuario_por_email("cliente@ejemplo.com")["id"]
    app_aislada.post(f"/admin/usuarios/{uid}", data={"plan": "growth", "activo": "1"})
    assert db.usuario(uid)["plan"] == "growth"
    assert "Cuentas del proyecto" in app_aislada.get("/admin").text


PALABRAS_PRUEBA = [
    {"start": 0.2, "end": 0.5, "word": "Tres"}, {"start": 0.55, "end": 0.9, "word": "errores."},
    {"start": 1.6, "end": 1.9, "word": "Eh,"}, {"start": 1.95, "end": 2.3, "word": "repito."},
    {"start": 3.0, "end": 3.4, "word": "Primero"}, {"start": 3.45, "end": 3.9, "word": "la"},
    {"start": 3.95, "end": 4.4, "word": "oferta."}, {"start": 5.2, "end": 5.6, "word": "Segundo"},
    {"start": 5.65, "end": 6.1, "word": "el"}, {"start": 6.15, "end": 6.6, "word": "funnel."},
]


def _frases():
    return editor_frases.partir([dict(w) for w in PALABRAS_PRUEBA])


def test_frases_y_texto_corregido():
    fs = _frases()
    assert [f["texto"] for f in fs] == ["Tres errores.", "Eh, repito.", "Primero la oferta.", "Segundo el funnel."]
    fs[2]["texto"] = "Primero, tu oferta."
    nuevas = editor_frases.palabras_de(fs[2], PALABRAS_PRUEBA)
    assert [w["word"] for w in nuevas] == ["Primero,", "tu", "oferta."] and nuevas[0]["start"] == 3.0
    fs[1]["quitada"] = True
    assert len(editor_frases.palabras_que_quedan(fs, PALABRAS_PRUEBA)) == 8


def test_trozo_del_video_largo(monkeypatch):
    fs = _frases()
    monkeypatch.setattr(llm, "json_con_esquema", lambda *a, **k: {"desde": "f3", "hasta": "f3", "titulo": "T", "motivo": "m",
                                                                  "duracion_aproximada": 1})
    trozo = editor_frases.elegir_trozo(fs, minimo=2, maximo=10)
    assert trozo["desde"] == "f3" and trozo["hasta"] == "f4"  # se alarga hasta la duración mínima
    editor_frases.aplicar_trozo(fs, trozo)
    assert [f["quitada"] for f in fs] == [True, True, False, False] and fs[0]["fuera"]


def test_plan_siempre_bien_formado():
    fs = _frases()
    fs[1]["quitada"] = True
    datos = {"bloques": [
        {"frases": ["f1"], "tipo": "choque", "texto": ""},          # un choque no puede abrir el reel
        {"frases": ["f3", "f4"], "tipo": "lista", "items": ["Uno"]},  # una lista de un elemento no es lista
        {"frases": ["f9"], "tipo": "zoom"},                          # frase que no existe
    ]}
    p = editor_plan.normalizar(datos, fs, modo="camara", capturas=[], efectos_max=1)
    assert [b["tipo"] for b in p["bloques"]] == ["gancho", "subtitulo"]  # el reel abre siempre con gancho
    assert [b["frases"] for b in p["bloques"]] == [["f1"], ["f3", "f4"]]
    p = editor_plan.normalizar({"bloques": [{"frases": ["f1"], "tipo": "gancho"}, {"frases": ["f3"], "tipo": "choque"},
                                            {"frases": ["f4"], "tipo": "pantalla", "web": "ejemplo.com"}]},
                               fs, modo="camara", capturas=[], efectos_max=1)
    assert p["bloques"][1]["texto"] == "PRIMERO" and p["bloques"][2]["tipo"] == "pantalla"
    assert any("se pierde la sorpresa" in a for a in p["avisos"])
    assert editor_plan.basico(fs, modo="voz")["bloques"][0]["tipo"] == "gancho"


def test_ajustes_del_editor_se_quedan_en_rango():
    a = editor_modelo.ajustes({"estilo": "nada", "color": "rojo", "subtitulos": {"tamano_pct": 500, "posicion": "lado"}})
    assert a["estilo"] == "impacto" and a["color"] == "#2F6BFF"
    assert a["subtitulos"]["tamano_pct"] == 180 and a["subtitulos"]["posicion"] == "abajo"
    assert editor_modelo.ajustes({"estilo": "editorial"})["efectos_max"] == 2


def test_revision_automatica_del_reel():
    vents = [{"tipo": "gancho", "inicio": 0, "fin": 2}, {"tipo": "subtitulo", "inicio": 2, "fin": 12},
             {"tipo": "choque", "inicio": 12, "fin": 14}, {"tipo": "subtitulo", "inicio": 14, "fin": 20}]
    assert editor_montaje.tramos_quietos(vents, [6.0], 20) == [(2, 6.0), (6.0, 12), (14, 20)]
    r = editor_montaje.revisar(vents, [6.0], 20, modo="camara", zoom_suave=True)
    assert len(r["zooms"]) == 3 and "zoom suave" in r["arreglos"][0]
    assert any("solo la persona" in a for a in r["avisos"])


def test_competidores_en_filas_y_el_texto_antiguo(app_aislada):
    from starlette.datastructures import FormData
    from radar import onboarding
    # Cada competidor en su fila, con un campo por dato: una coma en el nombre ya no lo parte.
    filas = onboarding.competidores_del_formulario(FormData(
        [("competidores_filas", "1")]
        + [(f"comp_{k}", v) for k, v in (("nombre", "Pérez, García y Asociados"), ("web", "perezgarcia.es"),
                                          ("instagram", "@perezgarcia"), ("linkedin", ""), ("youtube", "https://www.youtube.com/@perezgarcia"))]
        + [(f"comp_{k}", "") for k in onboarding.CAMPOS_COMPETIDOR]  # una fila vacía
        + [(f"comp_{k}", v) for k, v in (("nombre", ""), ("web", ""), ("instagram", "https://instagram.com/ana.ruiz/"),
                                          ("linkedin", "linkedin.com/in/anaruiz"), ("youtube", ""))]))
    assert len(filas) == 2 and filas[0]["nombre"] == "Pérez, García y Asociados"
    assert onboarding.competidores_del_formulario(FormData([("competidores", "A, a.es")])) is None
    cs = ficha.leer_competidores(filas)
    assert cs[0] == {"nombre": "Pérez, García y Asociados", "web": "perezgarcia.es", "instagram": "perezgarcia",
                     "linkedin": "", "youtube": "https://www.youtube.com/@perezgarcia", "motivo": "Lo indicó el negocio"}
    assert cs[1]["nombre"] == "ana.ruiz" and cs[1]["linkedin"] == "https://www.linkedin.com/in/anaruiz/"
    assert onboarding.completitud({"competidores": filas}) > onboarding.completitud({"competidores": []})

    # La ficha ya no tiene pantalla (la rellena el onboarding), pero se sigue pudiendo guardar.
    _registrar(app_aislada, "duena@ejemplo.com")
    neg = _dar_negocio("duena@ejemplo.com")

    # Al guardar la ficha, se guardan como filas y los análisis las leen igual.
    datos = {k: v for k, v in FICHA.items() if k != "competidores"}
    datos.update(competidores_filas="1", comp_nombre=["Pérez, García y Asociados", ""], comp_web=["perezgarcia.es", ""],
                 comp_instagram=["@perezgarcia", ""], comp_linkedin=["", ""], comp_youtube=["", ""])
    app_aislada.post(f"/negocios/{neg}/ficha", data=datos)
    f = db.negocio(neg)["ficha"]
    assert f["competidores"] == [{"nombre": "Pérez, García y Asociados", "web": "perezgarcia.es",
                                  "instagram": "@perezgarcia", "tiktok": "", "linkedin": "", "youtube": ""}]
    assert ficha.perfil_basico(f)["competidores"][0]["instagram"] == "perezgarcia"
    # Un informe anterior se combina con las filas nuevas sin repetir competidores.
    combinado = ficha.combinar({"competidores": [{"nombre": "Pérez, García y Asociados", "web": "", "instagram": ""}]}, f)
    assert len(combinado["competidores"]) == 1 and combinado["competidores"][0]["instagram"] == "perezgarcia"


class _Consumo:
    input_tokens, output_tokens, cache_creation_input_tokens, cache_read_input_tokens, server_tool_use = 1000, 200, 0, 0, None


def _vega_simulada(monkeypatch, vistos: list):
    def conversar(system, mensajes, **k):
        vistos.append((system, mensajes))
        for trozo in ["Hola. ", "Tu punto de partida es **cero**."]:
            yield trozo
        k["al_terminar"](_Consumo())
    monkeypatch.setattr(llm, "disponible", lambda: True)
    monkeypatch.setattr(llm, "conversar", conversar)



# ---------------------------------------------------------------- la app centrada en el equipo de contenido

def test_instalacion_nueva_primera_cuenta_y_primer_negocio(app_aislada):
    anonimo = TestClient(app_aislada.app)
    assert anonimo.get("/", follow_redirects=False).headers["location"] == "/entrar"
    assert anonimo.get("/entrar", follow_redirects=False).headers["location"] == "/registro"  # aún no hay nadie
    r = anonimo.post("/registro", data={"email": "duena@ejemplo.com", "nombre": "Julia", "clave": "clave-de-prueba"},
                     follow_redirects=False)
    assert db.usuario_por_email("duena@ejemplo.com")["es_admin"]
    cliente = anonimo
    assert cliente.get("/app", follow_redirects=False).headers["location"] == "/negocios/nuevo"
    r = cliente.post("/negocios", data=FICHA, follow_redirects=False)
    assert r.headers["location"].startswith("/negocios/1/kit")
    assert cliente.get("/app", follow_redirects=False).headers["location"] == "/negocios/1/hoy"
    pagina = cliente.get("/negocios/1/hoy").text
    for seccion in ("Inicio", "Por revisar", "Ideas", "Grabar", "Editar", "Publicar", "Comunidad", "Kit de marca"):
        assert seccion in pagina
    for vieja in ("Funnel y oferta", "/equipo", "/contenido\"", "Ventas"):
        assert vieja not in pagina
    # Después de la primera, el registro queda cerrado salvo para quien administra.
    otro = TestClient(app_aislada.app)
    assert otro.get("/registro", follow_redirects=False).headers["location"] == "/entrar"
    r = cliente.post("/registro", data={"email": "socia@ejemplo.com", "nombre": "Socia", "clave": "clave-de-prueba"},
                     follow_redirects=False)
    assert "/admin" in r.headers["location"] and not db.usuario_por_email("socia@ejemplo.com")["es_admin"]


def test_lo_de_antes_ya_no_esta(app_aislada):
    _registrar(app_aislada, "duena@ejemplo.com")
    app_aislada.post("/negocios", data=FICHA)
    for ruta in ("/negocios/1/equipo", "/negocios/1/contenido", "/negocios/1/funnel", "/negocios/1/edicion",
                 "/editor", "/admin/solicitudes", "/admin/onboarding", "/c/x"):
        assert app_aislada.get(ruta, follow_redirects=False).status_code == 404, ruta
    assert app_aislada.get("/negocios/1", follow_redirects=False).headers["location"] == "/negocios/1/hoy"


def test_cada_cliente_ve_solo_sus_negocios(app_aislada):
    _registrar(app_aislada, "duena@ejemplo.com")
    cliente = _otro_cliente(app_aislada, "cliente@ejemplo.com")
    _dar_negocio("cliente@ejemplo.com")
    otro = _otro_cliente(app_aislada, "otro@ejemplo.com")
    for ruta in ("/negocios/1/hoy", "/negocios/1/kit", "/negocios/1/guiones", "/negocios/1/ficha"):
        assert otro.get(ruta).status_code == 404 and cliente.get(ruta).status_code == 200
    assert app_aislada.get("/negocios/1/hoy").status_code == 200  # quien administra ve todos


def test_eliminar_un_negocio(app_aislada):
    _registrar(app_aislada, "duena@ejemplo.com")
    cliente = _otro_cliente(app_aislada, "cliente@ejemplo.com")
    _dar_negocio("cliente@ejemplo.com")
    ed = db.crear_edicion(1, "Vídeo", {})
    db.actualizar_edicion(ed, estado="listo")
    (edicion.carpeta(ed) / "final.mp4").write_bytes(b"x")
    assert 'id="eliminar"' in cliente.get("/negocios/1/conectores").text
    assert _otro_cliente(app_aislada, "otro@ejemplo.com").post("/negocios/1/eliminar",
                                                              data={"confirmar": FICHA["nombre"]}).status_code == 404
    r = cliente.post("/negocios/1/eliminar", data={"confirmar": "otra cosa"}, follow_redirects=True)
    assert "nombre exacto" in r.text and db.negocio(1)
    r = cliente.post("/negocios/1/eliminar", data={"confirmar": FICHA["nombre"].upper()}, follow_redirects=True)
    assert r.status_code == 200 and db.negocio(1) is None and db.ediciones_de(1) == []
    assert not edicion.carpeta(ed).joinpath("final.mp4").exists()


def test_estilo_de_edicion_en_el_kit(app_aislada):
    _registrar(app_aislada, "duena@ejemplo.com")
    app_aislada.post("/negocios", data=FICHA)
    assert "Estilo de edición" in app_aislada.get("/negocios/1/kit").text
    app_aislada.post("/negocios/1/kit/estilo", data={"estilo": "editorial", "color": "#FF0055",
                                                     "preferencias": "sin música\nsubtítulos pequeños"})
    m = db.marca(1)
    assert m["ajustes"]["estilo"] == "editorial" and m["color"] == "#FF0055" and m["preferencias"] == ["sin música", "subtítulos pequeños"]
    from radar.editor import flujo
    ajustes = flujo.ajustes_de({"negocio_id": 1, "datos": {}})
    assert ajustes["estilo"] == "editorial" and ajustes["color"].upper() == "#FF0055"


def test_hablar_con_vega(app_aislada, monkeypatch):
    from radar import vega
    vistos = []
    _vega_simulada(monkeypatch, vistos)
    _registrar(app_aislada, "duena@ejemplo.com")
    cliente_ = _otro_cliente(app_aislada, "mentora@ejemplo.com")
    _dar_negocio("mentora@ejemplo.com")
    assert "Pregúntale a Orby" in cliente_.get("/negocios/1/hoy").text
    assert cliente_.post("/negocios/1/vega", data={"texto": "  "}).status_code == 400
    r = cliente_.post("/negocios/1/vega", data={"texto": "¿Por dónde empiezo?"})
    assert r.status_code == 200 and r.text == "Hola. Tu punto de partida es **cero**."
    system, mensajes = vistos[0]
    assert mensajes == [{"role": "user", "content": "¿Por dónde empiezo?"}]
    assert "Mentora Prueba" in system[1]["text"] and "Carriles de contenido" in system[1]["text"]  # el Kit va en el contexto
    assert "Buenos días" in system[1]["text"]  # y el resumen del día
    cliente_.post("/negocios/1/vega", data={"texto": "¿Y después?"})
    assert [m["role"] for m in vistos[1][1]] == ["user", "assistant", "user"]
    monkeypatch.setattr(vega, "MAX_DIA", 2)
    assert cliente_.post("/negocios/1/vega", data={"texto": "Una más"}).status_code == 429
    cliente_.post("/negocios/1/vega/nueva")
    assert cliente_.get("/negocios/1/vega").json()["mensajes"] == []



def test_una_cuenta_un_negocio(app_aislada):
    _registrar(app_aislada, "duena@ejemplo.com")
    app_aislada.post("/negocios", data=FICHA)
    assert app_aislada.get("/negocios/nuevo", follow_redirects=False).headers["location"] == "/app"
    app_aislada.post("/negocios", data=dict(FICHA, nombre="Otro"))
    assert len(db.negocios(db.usuario_por_email("duena@ejemplo.com")["id"])) == 1
    pagina = app_aislada.get("/negocios/1/hoy").text
    assert "Añadir negocio" not in pagina and "Mis negocios" not in pagina


def test_entrar_y_registro_se_enlazan_si_el_registro_esta_abierto(app_aislada, monkeypatch):
    _registrar(app_aislada, "duena@ejemplo.com")
    from fastapi.testclient import TestClient
    from radar.main import app
    anonimo = TestClient(app)
    monkeypatch.setattr(config, "REGISTRO_ABIERTO", False)
    assert 'href="/registro"' not in anonimo.get("/entrar").text
    monkeypatch.setattr(config, "REGISTRO_ABIERTO", True)
    assert "¿No tienes cuenta?" in anonimo.get("/entrar").text and 'href="/registro"' in anonimo.get("/entrar").text
    registro = anonimo.get("/registro").text
    assert "¿Ya tienes cuenta?" in registro and 'href="/entrar"' in registro and "Da de alta a otra persona" not in registro
    # Quien administra da de alta a otra persona: sin el enlace de entrar.
    assert "¿Ya tienes cuenta?" not in app_aislada.get("/registro").text
