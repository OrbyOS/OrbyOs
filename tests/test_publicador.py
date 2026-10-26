"""Publi: ensayo, enlace con seguimiento, la palabra clave fuera de Instagram, hashtags y reels de prueba."""
from datetime import datetime, timedelta

import httpx

from radar import db as _db
from radar.agentes import aprobaciones as ap
from radar.agentes import kit, publicador
from radar.modules import edicion as motor
from tests.test_agentes import _negocio_con_cliente, _video_aprobado, _Zernio  # noqa: F401
from tests.test_radar import app_aislada  # noqa: F401


def _con_zernio(monkeypatch, nid):
    falso = _Zernio()
    monkeypatch.setattr(httpx, "request", falso.request)
    monkeypatch.setattr(httpx, "put", falso.put)
    publicador.conectar(nid, "sk_buena")
    return falso


def _creados(falso):
    return [p[3]["json"] for p in falso.peticiones if p[0] == "POST" and p[1].endswith("/posts")]


def test_el_ensayo_no_manda_nada(app_aislada, monkeypatch):
    _, nid = _negocio_con_cliente(app_aislada)
    falso = _con_zernio(monkeypatch, nid)
    eid = _video_aprobado(nid)
    kit.cambiar(nid, cta={**kit.leer(nid)["cta"], "web": "mentora.es", "prefijo_utm": "rd"})
    r = publicador.programar(nid, eid, ["tiktok", "youtube", "instagram"], ensayo=True)
    assert not _creados(falso) and not publicador.publicaciones(nid)
    plan = {p["red"]: p for p in r["plan"]}
    assert "reconectarla" in " ".join(plan["youtube"]["problemas"])
    assert plan["tiktok"]["problemas"] == [] and plan["tiktok"]["cuando"]
    assert plan["tiktok"]["utm"].endswith("utm_content=rdcierre_1")
    # La misma hora pasada se ve en el ensayo.
    r = publicador.programar(nid, eid, ["tiktok"], cuando=datetime(2020, 1, 1, 10, 0), ensayo=True)
    assert "Esa hora ya ha pasado." in r["plan"][0]["problemas"]


def test_enlace_por_pieza_y_palabra_clave_solo_en_instagram(app_aislada, monkeypatch):
    _, nid = _negocio_con_cliente(app_aislada)
    falso = _con_zernio(monkeypatch, nid)
    kit.cambiar(nid, cta={**kit.leer(nid)["cta"], "web": "mentora.es"},
                hashtags=["#ventas", "#negocio", "#mentoria", "#emprender", "#clientes", "#marca"],
                publicacion={"linkedin": {"activa": True, "dias": list(range(7)), "horas": ["09:00"]}})
    eid = _video_aprobado(nid)
    datos = publicador.conexion(nid)
    datos["cuentas"].append({"id": "acc_li", "plataforma": "linkedin", "perfil": "", "usuario": "mentora",
                             "nombre": "", "activa": True, "reconectar": False, "seguidores": 0})
    publicador._guardar_conexion(nid, datos)
    r = publicador.programar(nid, eid, ["tiktok", "linkedin", "instagram"])
    assert {p["red"] for p in r["programadas"]} == {"tiktok", "linkedin", "instagram"}, r["fallos"]
    pubs = {p["plataforma"]: p for p in publicador.publicaciones(nid)}
    # Un número por pieza, el mismo en todas sus redes.
    assert {p["utm"].rsplit("_", 1)[1] for p in pubs.values()} == {"1"}
    li = pubs["linkedin"]["texto"]
    assert "CIERRE" not in li and "Más aquí: https://mentora.es?utm_source=linkedin" in li and "#" not in li
    tt = pubs["tiktok"]["texto"]
    assert "CIERRE" not in tt and "Enlace en la bio." in tt
    ig = pubs["instagram"]["texto"]
    assert "Comenta CIERRE" in ig and "utm_" not in ig
    # De 3 a 5 hashtags: los del tema primero, luego los del Kit, sin repetir.
    etiquetas = ig.split("\n")[-1].split()
    assert etiquetas[:3] == ["#coaching", "#ventas", "#marca"] and len(etiquetas) == 5 and len(set(etiquetas)) == 5
    # La pieza siguiente lleva el número 2.
    otra = _video_aprobado(nid, palabra="PRECIO")
    assert publicador.numero_de_pieza(nid, otra) == 2 and publicador.numero_de_pieza(nid, eid) == 1


def test_texto_final_se_puede_pasar_dos_veces():
    t = publicador.texto_final("Gancho.\n\nEscríbeme CIERRE por privado.\n\n#uno", "youtube", palabra="CIERRE",
                               utm="https://x.es?utm_content=cierre_1", etiquetas=["#a", "#b", "#c"])
    assert t == "Gancho.\n\nMás aquí: https://x.es?utm_content=cierre_1"
    assert publicador.texto_final(t, "youtube", palabra="CIERRE", utm="https://x.es?utm_content=cierre_1") == t
    ig = publicador.texto_final("Hola\n#a #b #c #d", "instagram", etiquetas=["#x", "#y", "#z"])
    assert ig.endswith("#a #b #c #d")  # ya trae de 3 a 5: se respetan


def test_el_humanizador_de_escri_limpia_los_textos():
    t = publicador.texto_final("Esto\u200b lo cambia todo — de verdad.\n\nComenta CIERRE", "instagram", palabra="CIERRE")
    assert "\u200b" not in t and "—" not in t and "Comenta CIERRE" in t


def test_reels_de_prueba_solo_si_se_activan_y_con_tu_ok(app_aislada, monkeypatch):
    _, nid = _negocio_con_cliente(app_aislada)
    falso = _con_zernio(monkeypatch, nid)
    eid = _video_aprobado(nid)
    assert "no están activados" in publicador.proponer_reels_prueba(nid, eid)["fallos"][0]
    kit.cambiar(nid, reels_prueba={"activa": True, "al_dia": 3})
    assert "Monti tiene que hacerlas" in publicador.proponer_reels_prueba(nid, eid)["fallos"][0]
    carpeta = motor.carpeta(eid) / publicador.CARPETA_VARIANTES
    carpeta.mkdir()
    for i in range(4):
        (carpeta / f"v{i}.mp4").write_bytes(b"v")
    # La primera vez, una sola: hay que comprobar que no sale en el perfil.
    r = publicador.proponer_reels_prueba(nid, eid)
    a = r["aprobacion"]
    assert a["estado"] == "pendiente" and len(a["datos"]["variantes"]) == 1 and not _creados(falso)
    ap.decidir(a["id"], "aprobar")
    cuerpos = _creados(falso)
    assert len(cuerpos) == 1
    datos_ig = cuerpos[0]["platforms"][0]["platformSpecificData"]
    assert datos_ig == {"trialParams": {"graduationStrategy": "MANUAL"}} and "shareToFeed" not in datos_ig
    prueba = publicador.publicaciones(nid)[0]
    assert prueba["modo"] == "prueba"
    # Un reel de prueba no ocupa el hueco ni cuenta como publicado en Instagram.
    assert prueba["programado"][:16] not in publicador.ocupados(nid, "instagram")
    # Confirmado por el dueño: ya va el lote, repartido en la ventana del día y sin repetir lo ya programado.
    publicador.confirmar_fuera_del_perfil(nid)
    plan = publicador.plan_de_prueba(nid, eid, datetime.now() + timedelta(days=2))
    horas = [v["cuando"] for v in plan["variantes"]]
    assert len(horas) == 3 and horas == sorted(horas) and "08:00" <= f"{horas[0]:%H:%M}" and f"{horas[-1]:%H:%M}" <= "21:00"
    assert plan["variantes"][0]["hashtags"] != plan["variantes"][1]["hashtags"]
    a2 = publicador.proponer_reels_prueba(nid, eid, datetime.now() + timedelta(days=2))["aprobacion"]
    ap.decidir(a2["id"], "aprobar")
    assert [v["archivo"] for v in a2["datos"]["variantes"]] == ["v1.mp4", "v2.mp4", "v3.mp4"]  # v0 ya salió
    assert len(_creados(falso)) == 4
    with _db.conexion() as con:
        assert con.execute("SELECT COUNT(*) FROM publicaciones WHERE modo = 'prueba'").fetchone()[0] == 4
    ap.decidir(a2["id"], "aprobar")  # aprobar otra vez no repite nada
    assert len(_creados(falso)) == 4
