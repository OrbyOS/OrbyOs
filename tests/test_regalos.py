"""Regalos: palabra + enlace corto + destino, con sus números, y la respuesta automática de Instagram los usa."""
import json

from radar import config, cortos, db, newsletter
from radar.agentes import instagram_dm, regalos
from radar.connectors import instagram

from .test_instagram_dm import _aviso, _conectar
from .test_radar import _dar_negocio, _registrar, app_aislada, sin_claves_reales  # noqa: F401


def test_regalo_completo(app_aislada, monkeypatch):
    monkeypatch.setattr(config, "URL_PUBLICA", "https://orby.ejemplo")
    cliente = _registrar(app_aislada, "duena@ejemplo.com")
    nid = _dar_negocio("duena@ejemplo.com")
    r = cliente.post(f"/negocios/{nid}/regalos", data={"palabra": "guía", "destino": "https://ejemplo.com/guia",
                                                        "activa": "si", "exacta": "si", "mensaje": "Aquí la tienes:",
                                                        "pregunta": "¿Para qué la usarás?"}, follow_redirects=False)
    assert r.status_code == 303 and "#regalos" in r.headers["location"]
    g = cliente.get(f"/negocios/{nid}/regalos").json()[0]
    assert g["palabra"] == "GUIA" and g["enlace_corto"] == "https://orby.ejemplo/r/guia" and g["exacta"]
    assert cortos.destino("guia") == "https://ejemplo.com/guia"
    # Instagram lo usa: comentario → botón → enlace corto en el privado, con su pregunta
    enviados = _conectar(monkeypatch, nid, modo="directo")
    neg = db.negocio(nid)
    assert instagram_dm.atender(neg, instagram.comentarios(json.loads(_aviso("c1", "GUIA")))[0]) == "enviado"
    privados = [e for e in enviados if e[0] == "privado"]
    assert privados[-1][2] == "Aquí la tienes: https://orby.ejemplo/r/guia"
    assert enviados[-1][0] == "publico" and enviados[-1][2] in instagram_dm.VARIADAS_PERSONA
    assert instagram_dm.regla_para(nid, "me encanta la guia", "1") is None  # exacta
    cortos.contar("guia", "Mozilla iPhone")
    newsletter.suscribir("landing", {"nombre": "Ana", "email": "ana@ejemplo.com", "acepto": "si", "origen": "guia"}, "9")
    g = regalos.lista(nid)[0]
    assert (g["comentarios"], g["privados"], g["clics"], g["correos"]) == (1, 1, 1, 1) and g["ultimo"]
    # Otro negocio con la misma palabra: su propio enlace corto
    _registrar(app_aislada, "otra@ejemplo.com")
    otro = _dar_negocio("otra@ejemplo.com")
    assert regalos.guardar(otro, palabra="GUIA", destino="https://otra.com")["corto"] == f"guia-{otro}"
    # Editar, pausar y quitar
    cliente.post(f"/negocios/{nid}/regalos", data={"regalo_id": g["id"], "palabra": "GUIA", "destino": "https://nuevo.com"})
    assert cortos.destino("guia") == "https://nuevo.com" and not regalos.lista(nid)[0]["activa"]
    assert instagram_dm.regla_para(nid, "GUIA", "1") is None  # en pausa
    assert cliente.post(f"/negocios/{nid}/regalos", data={"palabra": "GUIA", "destino": "https://x.com"},
                        follow_redirects=False).headers["location"].endswith("#regalos")  # repetida: aviso
    cliente.post(f"/negocios/{nid}/regalos/{g['id']}/quitar")
    assert not regalos.lista(nid) and not cortos.destino("guia")
    assert cliente.post(f"/negocios/{nid}/regalos", data={"palabra": "X", "destino": "nada"}).status_code == 200


def test_regalos_desde_el_servidor(app_aislada, capsys):
    _registrar(app_aislada, "duena@ejemplo.com")
    nid = _dar_negocio("duena@ejemplo.com")
    assert regalos.main(["poner", str(nid), "skill", "https://gravity.ejemplo/?r=SKILL", "--exacta",
                         "--mensaje", "Te lo dejo aquí: {enlace}\\n\\nLo que pediste está arriba."]) == 0
    r = regalos.lista(nid)[0]
    assert r["palabra"] == "SKILL" and r["exacta"] and r["activa"] and "\n\nLo que pediste" in r["mensaje"]
    assert regalos.main(["poner", str(nid), "SKILL", "https://otra.ejemplo"]) == 0 and len(regalos.lista(nid)) == 1
    assert regalos.main(["quitar", str(nid), "skill"]) == 0 and not regalos.lista(nid)


def test_regalo_skill_en_la_cuenta_de_una_persona(app_aislada, monkeypatch):
    """El ensayo del primer reel con «Comenta SKILL»: privado (botón → enlace corto), respuesta pública variada en
    primera persona y palabra exacta. Todo con avisos simulados."""
    monkeypatch.setattr(config, "URL_PUBLICA", "https://orby.ejemplo")
    _registrar(app_aislada, "duena@ejemplo.com")
    nid = _dar_negocio("duena@ejemplo.com")
    regalos.main(["poner", str(nid), "SKILL", "https://gravity.ejemplo/?r=SKILL", "--exacta",
                  "--mensaje", "Te lo dejo aquí: {enlace}"])
    enviados = _conectar(monkeypatch, nid, modo="conversacion")
    neg = db.negocio(nid)
    for i, texto in enumerate(["skills", "me encanta tu skill", "SKILLAZO", "#skillset"]):
        c = instagram.comentarios(json.loads(_aviso(f"n{i}", texto, autor_id=f"9{i}")))[0]
        assert instagram_dm.atender(neg, c) == "sin_palabra", texto
    assert not enviados
    publicas = []
    for i, texto in enumerate(["SKILL", "skill", "Quiero la SKILL!!", "SKILL porfa"]):
        assert instagram_dm.atender(neg, instagram.comentarios(json.loads(_aviso(f"c{i}", texto, autor_id=f"5{i}")))[0]) == "enviado"
        publicas.append(enviados[-1][2])
        assert enviados[-2][3] == [("Mándamelo", "ENLACE:SKILL")]  # el privado con el botón
    assert all(p in instagram_dm.VARIADAS_PERSONA for p in publicas)
    assert all(a != b for a, b in zip(publicas, publicas[1:]))
    m = instagram.mensajes(json.loads(json.dumps({"object": "instagram", "entry": [{"id": "1784", "messaging": [
        {"sender": {"id": "50"}, "recipient": {"id": "1784"}, "message": {"mid": "m1", "text": "Mándamelo",
                                                                        "quick_reply": {"payload": "ENLACE:SKILL"}}}]}]})))[0]
    assert instagram_dm.contestado(neg, m) == "enlace"
    assert enviados[-1][2] == f"Te lo dejo aquí: https://orby.ejemplo/r/skill"


def test_enlace_corto_con_el_dominio_del_negocio(app_aislada, monkeypatch):
    monkeypatch.setattr(config, "URL_PUBLICA", "https://orby.ejemplo")
    _registrar(app_aislada, "duena@ejemplo.com")
    nid = _dar_negocio("duena@ejemplo.com")
    regalos.main(["poner", str(nid), "SKILL", "https://gravity.ejemplo/?r=SKILL", "--exacta", "--dominio",
                  "https://gravity.ejemplo", "--mensaje", "Te lo dejo aquí: {enlace}\\n\\nLa skill de guiones es la primera."])
    r = regalos.lista(nid)[0]
    assert r["enlace_corto"] == "https://gravity.ejemplo/r/skill" and "\n\nLa skill" in r["mensaje"]
    assert instagram_dm.regla_para(nid, "SKILL", "1")["enlace"] == "https://gravity.ejemplo/r/skill"
    regalos.main(["poner", str(nid), "SKILL", "https://gravity.ejemplo/?r=SKILL", "--exacta"])  # sin --dominio: lo mantiene
    assert regalos.lista(nid)[0]["enlace_corto"] == "https://gravity.ejemplo/r/skill"
    # Llega por la web del negocio (otro Host): redirige y cuenta el clic
    resp = app_aislada.get("/r/skill", headers={"host": "gravity.ejemplo", "user-agent": "Mozilla iPhone"},
                           follow_redirects=False)
    assert resp.status_code == 302 and resp.headers["location"] == "https://gravity.ejemplo/?r=SKILL"
    assert regalos.lista(nid)[0]["clics"] == 1
    assert regalos.main(["poner", str(nid), "SKILL", "https://x.es", "--dominio", "gravity.ejemplo"]) == 1


def test_apertura_con_el_nombre(app_aislada, monkeypatch):
    _registrar(app_aislada, "duena@ejemplo.com")
    nid = _dar_negocio("duena@ejemplo.com")
    regalos.main(["poner", str(nid), "SKILL", "https://gravity.ejemplo/?r=SKILL", "--exacta", "--apertura",
                  "Hola, {nombre}. Tengo la skill preparada. ¿Te la mando?"])
    enviados = _conectar(monkeypatch, nid, modo="conversacion")
    neg = db.negocio(nid)
    nombres = {"51": "Julia 🌸 Pérez", "52": ""}
    monkeypatch.setattr(instagram, "nombre_de", lambda t, uid: nombres.get(uid, ""))
    casos = [("51", "alguien", "Hola, Julia."), ("52", "alguien", "Hola, @alguien."), ("53", "", "Hola. Tengo")]
    for autor_id, usuario, empieza in casos:
        aviso = json.loads(_aviso(f"c{autor_id}", "SKILL", autor_id=autor_id))
        aviso["entry"][0]["changes"][0]["value"]["from"]["username"] = usuario
        assert instagram_dm.atender(neg, instagram.comentarios(aviso)[0]) == "enviado"
        privado = [e for e in enviados if e[0] == "privado"][-1][2]
        assert privado.startswith(empieza) and "{nombre}" not in privado, privado
