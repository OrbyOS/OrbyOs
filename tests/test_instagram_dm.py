"""La palabra clave de Instagram sin ManyChat: avisos firmados de Meta, una respuesta privada por persona y tope diario."""
import hashlib
import hmac
import json

from radar import db
from radar.agentes import instagram_dm
from radar.connectors import instagram

from .test_radar import _dar_negocio, _registrar, app_aislada, sin_claves_reales  # noqa: F401

SECRETO = "secreto-de-prueba"


def _conectar(monkeypatch, nid: int, modo: str = "directo") -> list:
    enviados = []
    monkeypatch.setattr(instagram, "cuenta", lambda t: {"id": "1784", "usuario": "cuenta_prueba"})
    monkeypatch.setattr(instagram, "suscribir", lambda t: True)
    monkeypatch.setattr(instagram, "responder_en_privado", lambda t, cuenta, comentario, texto, botones=None:
                        enviados.append(("privado", comentario, texto) + ((botones,) if botones else ())) or "m1")
    monkeypatch.setattr(instagram, "responder_en_publico",
                        lambda t, comentario, texto: enviados.append(("publico", comentario, texto)) or "r1")
    monkeypatch.setattr(instagram, "enviar_mensaje",
                        lambda t, cuenta, a, texto: enviados.append(("mensaje", a, texto)) or "m2")
    instagram_dm.conectar(nid, "token-de-prueba", SECRETO)
    instagram_dm.ajustar(nid, modo_=modo)
    return enviados


def _aviso(comentario_id: str, texto: str, autor_id: str = "55", media_id: str = "900") -> bytes:
    return json.dumps({"object": "instagram", "entry": [{"id": "1784", "time": 1, "changes": [{"field": "comments", "value": {
        "id": comentario_id, "text": texto, "from": {"id": autor_id, "username": "alguien"},
        "media": {"id": media_id, "media_product_type": "REELS"}}}]}]}).encode()


def _firmar(cuerpo: bytes) -> str:
    return "sha256=" + hmac.new(SECRETO.encode(), cuerpo, hashlib.sha256).hexdigest()


def test_comprobacion_y_firma(app_aislada, monkeypatch):
    _registrar(app_aislada, "duena@ejemplo.com")
    nid = _dar_negocio("duena@ejemplo.com")
    _conectar(monkeypatch, nid)
    token = instagram_dm.token_aviso(nid)
    r = app_aislada.get(f"/ig/{token}", params={"hub.mode": "subscribe", "hub.verify_token": token, "hub.challenge": "42"})
    assert r.status_code == 200 and r.text == "42"
    assert app_aislada.get(f"/ig/{token}", params={"hub.mode": "subscribe", "hub.verify_token": "otro",
                                                   "hub.challenge": "42"}).status_code == 403
    cuerpo = _aviso("c1", "ORBY")
    assert app_aislada.post(f"/ig/{token}", content=cuerpo, headers={"x-hub-signature-256": "sha256=mal"}).status_code == 403
    assert app_aislada.post("/ig/no-existe", content=cuerpo).status_code == 404
    estado = app_aislada.get(f"/negocios/{nid}/conectores/instagram").json()
    assert estado["usuario"] == "cuenta_prueba" and "token" not in json.dumps(estado).replace("verify_token", "")


def test_palabra_una_vez_por_persona_y_reel(app_aislada, monkeypatch):
    _registrar(app_aislada, "duena@ejemplo.com")
    nid = _dar_negocio("duena@ejemplo.com")
    enviados = _conectar(monkeypatch, nid)
    instagram_dm.poner_palabra(nid, "skill", "https://ejemplo.com/regalo", mensaje="Aquí la tienes:",
                               publica="Te lo he mandado por privado")
    token = instagram_dm.token_aviso(nid)
    for cid, texto in (("c1", "quiero la skill!"), ("c1", "quiero la skill!"), ("c2", "SKILL otra vez"), ("c3", "hola")):
        cuerpo = _aviso(cid, texto)
        assert app_aislada.post(f"/ig/{token}", content=cuerpo, headers={"x-hub-signature-256": _firmar(cuerpo)}).status_code == 200
    privados = [e for e in enviados if e[0] == "privado"]
    assert len(privados) == 1 and privados[0][1] == "c1" and privados[0][2] == "Aquí la tienes: https://ejemplo.com/regalo"
    assert ("publico", "c1", "Te lo he mandado por privado") in enviados
    estados = {e["comentario_id"]: e["estado"] for e in instagram_dm.envios(nid)}
    assert estados == {"c1": "enviado", "c2": "repetido"}
    # En otro reel, la misma persona sí lo recibe; los comentarios de la propia cuenta, nunca.
    neg = db.negocio(nid)
    assert instagram_dm.atender(neg, instagram.comentarios(json.loads(_aviso("c4", "skill", media_id="901")))[0]) == "enviado"
    assert instagram_dm.atender(neg, instagram.comentarios(json.loads(_aviso("c5", "skill", autor_id="1784")))[0]) == "propio"


def test_palabra_de_un_reel_y_tope(app_aislada, monkeypatch):
    _registrar(app_aislada, "duena@ejemplo.com")
    nid = _dar_negocio("duena@ejemplo.com")
    enviados = _conectar(monkeypatch, nid)
    instagram_dm.poner_palabra(nid, "Guía", "https://ejemplo.com/a", media_id="900")
    instagram_dm.poner_palabra(nid, "GUIA", "https://ejemplo.com/b", mensaje="Toma: {enlace}")
    assert instagram_dm.regla_para(nid, "la guía porfa", "900")["enlace"] == "https://ejemplo.com/a"
    assert instagram_dm.regla_para(nid, "la guía porfa", "777")["enlace"] == "https://ejemplo.com/b"
    assert instagram_dm.regla_para(nid, "guiaaa", "777") is None
    neg = db.negocio(nid)
    assert instagram_dm.atender(neg, instagram.comentarios(json.loads(_aviso("c0", "guia", "54", "900")))[0]) == "enviado"
    assert "https://ejemplo.com/a" in enviados[-1][2]  # sin mensaje propio: la apertura del Kit y el enlace
    instagram_dm.ajustar(nid, tope=2)
    assert instagram_dm.atender(neg, instagram.comentarios(json.loads(_aviso("c1", "guia", media_id="777")))[0]) == "enviado"
    assert enviados[-1] == ("privado", "c1", "Toma: https://ejemplo.com/b")
    assert instagram_dm.atender(neg, instagram.comentarios(json.loads(_aviso("c2", "guia", "56", "777")))[0]) == "tope"
    instagram_dm.ajustar(nid, activa=False)
    assert instagram_dm.atender(neg, instagram.comentarios(json.loads(_aviso("c3", "guia", "57", "777")))[0]) == "apagado"


def test_fallo_y_renovacion(app_aislada, monkeypatch):
    _registrar(app_aislada, "duena@ejemplo.com")
    nid = _dar_negocio("duena@ejemplo.com")
    _conectar(monkeypatch, nid)
    instagram_dm.poner_palabra(nid, "orby", "https://ejemplo.com")

    def falla(*a):
        raise instagram.ErrorInstagram("Instagram no da permiso")
    monkeypatch.setattr(instagram, "responder_en_privado", falla)
    neg = db.negocio(nid)
    assert instagram_dm.atender(neg, instagram.comentarios(json.loads(_aviso("c1", "orby")))[0]) == "fallido"
    assert instagram_dm.envios(nid)[0]["error"] == "Instagram no da permiso"
    from datetime import datetime, timedelta
    monkeypatch.setattr(instagram, "renovar", lambda t: {"token": "token-nuevo", "segundos": 5184000})
    assert instagram_dm.renovar_tokens() == 0  # recién conectado
    assert instagram_dm.renovar_tokens(datetime.now() + timedelta(days=21)) == 1
    assert instagram_dm.conexion(nid)["token"] == "token-nuevo"


def test_desde_el_servidor(app_aislada, monkeypatch, capsys):
    _registrar(app_aislada, "duena@ejemplo.com")
    nid = _dar_negocio("duena@ejemplo.com")
    _conectar(monkeypatch, nid)
    assert instagram_dm.main(["poner", str(nid), "SKILL", "https://ejemplo.com/s", "--reel", "900"]) == 0
    assert instagram_dm.palabras(nid) == [{"palabra": "SKILL", "enlace": "https://ejemplo.com/s", "mensaje": "",
                                           "media_id": "900"}]
    assert instagram_dm.main(["quitar", str(nid), "skill", "--reel", "900"]) == 0 and not instagram_dm.palabras(nid)
    assert "token-de-prueba" not in capsys.readouterr().out


def test_enlaces_cortos(app_aislada, capsys):
    from radar import cortos
    assert cortos.main(["poner", "Skill", "https://github.com/OrbyOS/orby-skills"]) == 0
    navegador = {"user-agent": "Mozilla/5.0 (iPhone) Instagram 300"}
    r = app_aislada.get("/r/skill", headers=navegador, follow_redirects=False)
    assert r.status_code == 302 and r.headers["location"] == "https://github.com/OrbyOS/orby-skills"
    app_aislada.get("/r/skill", headers={"user-agent": "facebookexternalhit/1.1"}, follow_redirects=False)
    assert app_aislada.get("/r/nada", follow_redirects=False).status_code == 404
    assert cortos.clics("skill")[0]["clics"] == 1 and cortos.todos()[0]["clics"] == 1
    capsys.readouterr()
    cortos.main(["clics"])
    assert "/r/skill" in capsys.readouterr().out


def test_cuenta_de_la_instalacion(app_aislada, monkeypatch, capsys):
    import io
    enviados = _conectar(monkeypatch, instagram_dm.INSTALACION)
    monkeypatch.setattr("sys.stdin", io.StringIO("token-otro\nsecreto-de-prueba\n"))
    assert instagram_dm.main(["conectar", "0"]) == 0
    salida = capsys.readouterr().out
    assert "@cuenta_prueba" in salida and "token-otro" not in salida and "secreto-de-prueba" not in salida
    instagram_dm.main(["poner", "0", "SKILL", "https://orbyos.es/r/skill"])
    token = instagram_dm.token_aviso(instagram_dm.INSTALACION)
    r = app_aislada.get(f"/ig/{token}", params={"hub.mode": "subscribe", "hub.verify_token": token, "hub.challenge": "7"})
    assert r.text == "7"
    cuerpo = _aviso("c1", "skill porfa")
    assert app_aislada.post(f"/ig/{token}", content=cuerpo, headers={"x-hub-signature-256": _firmar(cuerpo)}).status_code == 200
    assert enviados[-1][:2] == ("privado", "c1") and "https://orbyos.es/r/skill" in enviados[-1][2]


def test_respuesta_publica_variada(app_aislada, monkeypatch):
    _registrar(app_aislada, "duena@ejemplo.com")
    nid = _dar_negocio("duena@ejemplo.com")
    enviados = _conectar(monkeypatch, nid)
    instagram_dm.poner_palabra(nid, "skill", "https://ejemplo.com", publica="*")
    neg = db.negocio(nid)
    for i in range(6):
        assert instagram_dm.atender(neg, instagram.comentarios(json.loads(_aviso(f"c{i}", "skill", f"5{i}")))[0]) == "enviado"
    publicas = [e[2] for e in enviados if e[0] == "publico"]
    assert len(publicas) == 6 and all(a != b for a, b in zip(publicas, publicas[1:]))
    assert all("{nombre}" not in p and " ," not in p for p in publicas)
    assert instagram_dm.respuesta_publica("Uno | Dos", "", "Uno") == "Dos"


def _dm(autor_id: str, texto: str, payload: str = "") -> bytes:
    m = {"mid": f"m-{autor_id}-{texto}", "text": texto, **({"quick_reply": {"payload": payload}} if payload else {})}
    return json.dumps({"object": "instagram", "entry": [{"id": "1784", "time": 1, "messaging": [
        {"sender": {"id": autor_id}, "recipient": {"id": "1784"}, "timestamp": 1, "message": m}]}]}).encode()


def test_conversacion_boton_enlace_y_pregunta(app_aislada, monkeypatch):
    from datetime import datetime, timedelta
    _registrar(app_aislada, "duena@ejemplo.com")
    nid = _dar_negocio("duena@ejemplo.com")
    enviados = _conectar(monkeypatch, instagram_dm.INSTALACION, modo="conversacion")
    instagram_dm.poner_palabra(0, "skill", "https://orbyos.es/r/skill", pregunta="¿Cuál has instalado primero?")
    token = instagram_dm.token_aviso(0)

    def avisar(cuerpo):
        assert app_aislada.post(f"/ig/{token}", content=cuerpo, headers={"x-hub-signature-256": _firmar(cuerpo)}).status_code == 200
    avisar(_aviso("c1", "SKILL"))
    primero = enviados[-1]
    assert primero[0] == "privado" and "orbyos.es" not in primero[2] and primero[3] == [("Mándamelo", "ENLACE:SKILL")]
    avisar(_dm("99", "hola"))  # alguien sin regalo pendiente: nada
    assert enviados[-1] == primero
    avisar(_dm("55", "Mándamelo", "ENLACE:SKILL"))
    assert enviados[-1][:2] == ("mensaje", "55") and "https://orbyos.es/r/skill" in enviados[-1][2]
    avisar(_dm("55", "gracias"))  # ya lo tiene: no se repite
    assert sum(1 for e in enviados if e[0] == "mensaje") == 1
    assert instagram_dm.preguntar_pendientes() == 0  # aún no ha pasado la hora
    assert instagram_dm.preguntar_pendientes(datetime.now() + timedelta(minutes=61)) == 1
    assert enviados[-1] == ("mensaje", "55", "¿Cuál has instalado primero?")
    assert instagram_dm.envios(0)[0]["fase"] == "preguntado"
    assert nid  # el negocio de la app no se toca


def test_conversacion_sin_boton_y_ventana(app_aislada, monkeypatch):
    from datetime import datetime, timedelta
    enviados = _conectar(monkeypatch, instagram_dm.INSTALACION, modo="conversacion")

    def sin_botones(t, cuenta, comentario, texto, botones=None):
        if botones:
            raise instagram.ErrorInstagram("no admite botones")
        enviados.append(("privado", comentario, texto))
    monkeypatch.setattr(instagram, "responder_en_privado", sin_botones)
    instagram_dm.poner_palabra(0, "orby", "https://orbyos.es/r/orby")
    neg = instagram_dm.negocio_de(0)
    assert instagram_dm.atender(neg, instagram.comentarios(json.loads(_aviso("c1", "orby")))[0]) == "enviado"
    assert "«sí»" in enviados[-1][2]
    assert instagram_dm.contestado(neg, instagram.mensajes(json.loads(_dm("55", "sí")))[0]) == "enlace"
    assert instagram_dm.preguntar_pendientes(datetime.now() + timedelta(hours=25)) == 0  # fuera de las 24 h
    assert instagram_dm.envios(0)[0]["fase"] == "caducado"


def test_palabra_exacta(app_aislada, monkeypatch):
    _registrar(app_aislada, "duena@ejemplo.com")
    nid = _dar_negocio("duena@ejemplo.com")
    _conectar(monkeypatch, nid)
    instagram_dm.main(["poner", str(nid), "ESTILO", "https://ejemplo.com/e", "--exacta"])
    assert instagram_dm.palabras(nid)[0]["exacta"] is True
    assert instagram_dm.regla_para(nid, "me encanta tu estilo", "1") is None
    assert instagram_dm.regla_para(nid, "Estilo", "1")["palabra"] == "ESTILO"
    assert instagram_dm.regla_para(nid, "quiero el ESTILO porfa", "1")["palabra"] == "ESTILO"
    assert instagram_dm.regla_para(instagram_dm.INSTALACION, "ESTILO", "1") is None  # cada cuenta, sus palabras


def test_conectar_con_el_boton(app_aislada, monkeypatch):
    from urllib.parse import parse_qs, urlparse
    from radar import config
    _registrar(app_aislada, "duena@ejemplo.com")
    nid = _dar_negocio("duena@ejemplo.com")
    assert app_aislada.get(f"/negocios/{nid}/conectores/instagram").json()["boton"] is False
    monkeypatch.setenv("RADAR_IG_APP_ID", "123")
    monkeypatch.setenv("RADAR_IG_APP_SECRETO", SECRETO)
    monkeypatch.setattr(config, "URL_PUBLICA", "https://orby.ejemplo")
    monkeypatch.setattr(instagram, "cuenta", lambda t: {"id": "1784", "usuario": "cuenta_prueba"})
    monkeypatch.setattr(instagram, "suscribir", lambda t: True)
    monkeypatch.setattr(instagram, "token_desde_codigo", lambda a, s, v, c: f"token-de-{c}")
    r = app_aislada.get(f"/negocios/{nid}/conectores/instagram/conectar", follow_redirects=False)
    destino = urlparse(r.headers["location"])
    q = parse_qs(destino.query)
    assert destino.netloc == "www.instagram.com" and q["redirect_uri"] == ["https://orby.ejemplo/instagram/volver"]
    assert app_aislada.get("/instagram/volver", params={"code": "x", "state": f"{nid}.falso"},
                           follow_redirects=False).headers["location"] == "/app"
    r = app_aislada.get(f"/negocios/{nid}/conectores/instagram/conectar", follow_redirects=False)
    estado = parse_qs(urlparse(r.headers["location"]).query)["state"][0]
    r = app_aislada.get("/instagram/volver", params={"code": "abc", "state": estado}, follow_redirects=False)
    assert "conectores" in r.headers["location"] and "cuenta_prueba" in r.headers["location"]
    datos = instagram_dm.conexion(nid)
    assert datos["token"] == "token-de-abc" and datos["secreto"] == SECRETO and "oauth" not in datos
    assert app_aislada.get("/instagram/volver", params={"code": "abc", "state": estado},  # el «state» no se reutiliza
                           follow_redirects=False).headers["location"] == "/app"
