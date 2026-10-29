"""Newsletter de una landing: guarda el correo una vez, con su consentimiento, sin la IP y sin robots."""
from radar import newsletter

from .test_radar import app_aislada, sin_claves_reales  # noqa: F401

FORM = {"nombre": "Julia", "email": "Julia@Ejemplo.com ", "acepto": "si", "origen": "puerta"}


def test_suscribir_una_vez_y_exportar(app_aislada, capsys):
    newsletter._recientes.clear()
    r = app_aislada.post("/newsletter/landing/suscribir", data=FORM)
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert app_aislada.post("/newsletter/landing/suscribir", data=FORM).json() == {"ok": True}  # repetido: no duplica
    s = newsletter.suscriptores("landing")
    assert len(s) == 1 and s[0]["email"] == "julia@ejemplo.com" and s[0]["origen"] == "PUERTA"
    assert s[0]["consentimiento"] == newsletter.TEXTO_POR_DEFECTO and s[0]["consentimiento_en"]
    newsletter.main(["exportar", "landing"])
    assert "julia@ejemplo.com" in capsys.readouterr().out and "1.1.1.1" not in str(s)


def test_trampa_faltan_y_limite(app_aislada):
    newsletter._recientes.clear()
    assert app_aislada.post("/newsletter/landing/suscribir", data={**FORM, "web": "http://spam"}).json() == {"ok": True}
    assert not newsletter.suscriptores("landing")
    assert app_aislada.post("/newsletter/landing/suscribir", data={**FORM, "acepto": ""}).status_code == 400
    assert app_aislada.post("/newsletter/landing/suscribir", data={**FORM, "email": "no"}).status_code == 400
    assert app_aislada.post("/newsletter/LISTA MAL/suscribir", data=FORM).status_code == 404
    for i in range(newsletter.POR_IP_HORA):
        assert newsletter.suscribir("landing", {**FORM, "email": f"p{i}@ejemplo.com"}, "2.2.2.2") == "ok"
    assert newsletter.suscribir("landing", {**FORM, "email": "otra@ejemplo.com"}, "2.2.2.2") == "espera"
    assert newsletter.dar_de_baja("landing", "P0@ejemplo.com") and len(newsletter.suscriptores("landing")) == 4


def test_altas_a_kit_con_etiqueta_secuencia_y_reintento(app_aislada, monkeypatch):
    from radar import jobs
    from radar.connectors import kit
    newsletter._recientes.clear()
    monkeypatch.setattr(jobs, "en_segundo_plano", lambda f, *a: f(*a))
    altas, falla = [], {"si": True}

    def alta(clave, email, nombre, *, etiqueta="", secuencia=""):
        if falla["si"]:
            raise kit.ErrorKit("Kit ha respondido 500")
        altas.append((clave, email, nombre, etiqueta, secuencia))
    monkeypatch.setattr(kit, "alta", alta)
    assert newsletter.suscribir("landing", FORM, "1.1.1.1") == "ok"  # sin clave: queda pendiente
    monkeypatch.setenv("RADAR_KIT_API_KEY", "clave-de-prueba")
    assert newsletter.a_kit_pendientes() == 0  # Kit falla: se guarda el error y se reintenta luego
    assert newsletter.suscriptores("landing")[0]["email"] == "julia@ejemplo.com"
    falla["si"] = False
    assert newsletter.a_kit_pendientes() == 1
    assert altas == [("clave-de-prueba", "julia@ejemplo.com", "Julia", "PUERTA", "Bienvenida")]
    assert newsletter.a_kit_pendientes() == 0  # ya enviada: no se repite
    monkeypatch.setenv("RADAR_KIT_LISTAS", "gravity")  # otra lista no va a Kit
    assert newsletter.suscribir("otra", {**FORM, "email": "b@ejemplo.com"}, "1.1.1.2") == "ok" and len(altas) == 1


def test_clave_de_kit_desde_el_servidor(app_aislada, monkeypatch, tmp_path, capsys):
    import io
    from radar.connectors import kit
    archivo = tmp_path / ".env"
    monkeypatch.setenv("RADAR_ENV_FILE", str(archivo))
    monkeypatch.delenv("RADAR_KIT_API_KEY", raising=False)
    monkeypatch.setattr(kit, "comprobar", lambda c: "Gravity" if c == "buena" else (_ for _ in ()).throw(kit.ErrorKit("no")))
    monkeypatch.setattr("sys.stdin", io.StringIO("mala\n"))
    assert newsletter.main(["clave-kit"]) == 1 and not archivo.exists()
    monkeypatch.setattr("sys.stdin", io.StringIO("buena\n"))
    assert newsletter.main(["clave-kit"]) == 0
    assert "buena" not in capsys.readouterr().out and newsletter._ajuste("RADAR_KIT_API_KEY") == "buena"


def test_con_formulario_el_alta_la_manda_el_navegador(app_aislada, monkeypatch, tmp_path):
    from radar import config, jobs
    from radar.connectors import kit
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.delenv("RADAR_KIT_API_KEY", raising=False)
    monkeypatch.setattr(jobs, "en_segundo_plano", lambda f, *a: f(*a))
    newsletter._recientes.clear()
    enviados = []
    monkeypatch.setattr(kit, "alta_por_formulario", lambda f, e, n: enviados.append((f, e, n)))
    assert newsletter.suscribir("gravity", FORM, "1.1.1.1") == "ok" and not enviados  # aún sin formulario: pendiente
    assert newsletter.main(["kit-formulario", "gravity", "10109923"]) == 0
    # Kit pone en cuarentena lo que llega de un servidor: con formulario, lo manda el navegador desde la landing
    assert not enviados
    assert newsletter.suscribir("gravity", {**FORM, "email": "b@ejemplo.com"}, "1.1.1.4") == "ok" and not enviados
    from radar import db
    with db.conexion() as con:
        assert {f[0] for f in con.execute("SELECT kit FROM suscriptores WHERE lista = 'gravity'")} == {"navegador"}
