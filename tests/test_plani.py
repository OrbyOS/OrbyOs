"""Plani: tipos de pieza, fórmula de gancho, hora límite, rodaje, historias y reaprovechar."""
from datetime import datetime

from radar import db as _db
from radar import llm
from radar.agentes import aprobaciones as ap
from radar.agentes import estratega, kit

from .test_agentes import _negocio_con_cliente, db_negocio
from .test_radar import app_aislada, sin_claves_reales  # noqa: F401

LUNES = datetime(2026, 10, 19, 7, 0)
CARRILES = [{"id": "mito", "nombre": "Mitos", "cuota": 9, "etapa": "tofu", "descripcion": "x"},
            {"id": "metodo", "nombre": "Método", "cuota": 6, "etapa": "mofu", "descripcion": "x"},
            {"id": "oferta", "nombre": "Oferta", "cuota": 6, "etapa": "bofu", "descripcion": "x"}]


def _preparar(app_aislada, monkeypatch, **kit_):
    _, nid = _negocio_con_cliente(app_aislada)
    monkeypatch.setattr(estratega, "_ahora", lambda: LUNES)
    kit.cambiar(nid, carriles=CARRILES, **kit_)
    return nid


def _con_claude(monkeypatch, responder):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "prueba")
    monkeypatch.setattr(llm, "json_con_esquema", lambda sistema, peticion, esquema, **k: responder(sistema, peticion))


def test_nunca_dos_piezas_del_mismo_tipo_seguidas(app_aislada, monkeypatch):
    nid = _preparar(app_aislada, monkeypatch, modo_grabacion="guion")
    a = estratega.planificar(db_negocio(nid), lote=True)
    hoy = estratega.piezas(nid, dia=estratega._hoy())
    clases = [p["datos"]["clase"] for p in hoy]
    assert len(hoy) == 21 and all(c in estratega.CLASES for c in clases)
    assert all(x != y for x, y in zip(clases, clases[1:])), [(p["carril"], p["datos"]["clase"]) for p in hoy]
    assert "prueba" not in clases  # el Kit no tiene pruebas: no hay piezas de prueba
    assert {"opinion", "ensenar", "oferta"} <= set(clases)
    assert all(p["datos"]["reels"] == 1 for p in hoy)  # con guion, una pieza es un reel
    # Fórmula, hora límite y rodaje en cada pieza; la fórmula, sin repetir mientras quede alguna libre.
    formulas = [p["datos"]["formula"] for p in hoy]
    assert all(estratega._formula(f) for f in formulas) and len(set(formulas[:8])) == 8
    assert all(p["grabar_antes"] == "2026-10-19T20:00" and p["datos"]["rodaje"] for p in hoy)
    assert a["datos"]["vista"][0]["formula"].startswith("n.º ") and a["datos"]["vista"][0]["clase"]
    # El plan siguiente no empieza por el mismo tipo con el que acabó este.
    ap.decidir(a["id"], "aprobar")
    monkeypatch.setattr(estratega, "_ahora", lambda: datetime(2026, 10, 26, 7, 0))
    estratega.planificar(db_negocio(nid), n=1)
    siguiente = estratega.piezas(nid, dia="2026-10-26")[0]
    assert siguiente["datos"]["clase"] != clases[-1]


def test_con_estructuras_cada_pieza_cuenta_tres_reels(app_aislada, monkeypatch):
    nid = _preparar(app_aislada, monkeypatch)  # modo de partida: estructura
    _db.actualizar_negocio(nid, {**db_negocio(nid)["ficha"], "videos_semana": "21"})
    estratega.planificar(db_negocio(nid))
    hoy = estratega.piezas(nid, dia=estratega._hoy())
    assert len(hoy) == 2 and all(p["datos"]["reels"] == 3 for p in hoy)
    kit.cambiar(nid, modo_grabacion="guion")
    estratega.planificar(db_negocio(nid))
    assert len([p for p in estratega.piezas(nid, dia=estratega._hoy()) if p["estado"] == "propuesta"]) == 5


def test_sin_cifras_propias_no_hay_ganchos_que_las_pidan(app_aislada, monkeypatch):
    nid = _preparar(app_aislada, monkeypatch, modo_grabacion="guion",
                    pruebas=[{"id": "p1", "tipo": "resultado", "texto": "Un cliente", "cifra": "", "fuente": ""}])
    kit.cambiar(nid, limites={**kit.leer(nid)["limites"], "cifras_propias": False})
    estratega.planificar(db_negocio(nid), lote=True)
    formulas = {p["datos"]["formula"] for p in estratega.piezas(nid, dia=estratega._hoy())}
    assert formulas and not formulas & estratega.CON_CIFRA_PROPIA


def test_la_hora_limite_deja_tiempo_para_montarlo(app_aislada, monkeypatch):
    nid = _preparar(app_aislada, monkeypatch)
    k = kit.leer(nid)
    k["publicacion"] = {"instagram": {"activa": True, "dias": [0], "horas": ["13:30"], "autopublicar": False}}
    assert estratega.hora_limite(k, LUNES) == "2026-10-19T10:30"
    assert estratega.hora_limite(k, datetime(2026, 10, 19, 10, 0)) == "2026-10-19T20:00"  # ya no da tiempo
    assert estratega.hora_limite(k, datetime(2026, 10, 20, 7, 0)) == "2026-10-20T20:00"   # el martes no se publica
    assert estratega.hora_limite(k, LUNES, lote=True) == "2026-10-19T20:00"


def test_un_titulo_que_es_un_tema_se_pide_otra_vez(app_aislada, monkeypatch):
    nid = _preparar(app_aislada, monkeypatch, modo_grabacion="guion")
    pedidas = []

    def claude(sistema, peticion):
        pedidas.append(peticion)
        largo = len(pedidas) > 1
        return {"piezas": [{"numero": 1, "titulo": "Por qué dejé de hacer llamadas gratis" if largo else "Captación",
                            "angulo": "a", "formato": "A cámara", "esquema": ["Gancho"], "rodaje": ["Con luz de ventana"],
                            "ancla": {"tipo": "opinion", "texto": "Las llamadas gratis atraen curiosos"}}]}
    _con_claude(monkeypatch, claude)
    monkeypatch.setattr(estratega.analista, "revisar_encaje", lambda neg: 0)
    estratega.planificar(db_negocio(nid), n=1)
    p = estratega.piezas(nid, dia=estratega._hoy())[0]
    assert len(pedidas) == 2 and "son temas, no ángulos: Captación" in pedidas[1]
    assert p["titulo"].startswith("Por qué dejé") and p["datos"]["rodaje"] == ["Con luz de ventana"]
    assert "Fórmula de gancho n.º" in pedidas[0] and "Tipo: " in pedidas[0]


def test_historias_del_dia_si_el_kit_las_activa(app_aislada, monkeypatch):
    nid = _preparar(app_aislada, monkeypatch)
    a = estratega.planificar(db_negocio(nid), n=1)
    assert "historias" not in a["datos"]  # apagadas por defecto
    kit.cambiar(nid, formatos={**kit.leer(nid)["formatos"], "historias": True})
    a = estratega.planificar(db_negocio(nid), n=1)
    marcos = a["datos"]["historias"]["marcos"]
    con = [i for i, m in enumerate(marcos) if m["pegatina"] != "ninguna"]
    assert 3 <= len(marcos) <= 7 and len(con) == 1 and con[0] <= 3
    # Lo que llegue de Claude se arregla: una sola pegatina, y como tarde en el cuarto marco.
    malos = [{"imagen": "x", "se_dice": f"m{i}", "pegatina": "encuesta" if i in (5, 6) else "ninguna"} for i in range(9)]
    arreglados = estratega._historias_validas(malos)
    assert len(arreglados) == 7 and [m["pegatina"] for m in arreglados].index("encuesta") == 3
    assert sum(m["pegatina"] != "ninguna" for m in arreglados) == 1


TRANSCRIPCION = " ".join(["Hoy os cuento por qué dejé de hacer llamadas gratis y qué pasó después."] * 20)


def test_reaprovechar_una_grabacion_larga(app_aislada, monkeypatch):
    nid = _preparar(app_aislada, monkeypatch)
    assert estratega.reaprovechar(db_negocio(nid), "muy corto")[0] is None

    def claude(sistema, peticion):
        return {"hallazgos": {"afirmacion": 3, "cifra": 1, "historia": 2, "mecanismo": 2, "error": 1, "frase": 4},
                "piezas": [
                    {"extracto": "mecanismo", "titulo": "Así filtro a quien no va a comprar antes de la llamada",
                     "fragmento": "El formulario tiene cuatro preguntas", "momento": "12:40", "formula": 9},
                    {"extracto": "historia", "titulo": "El cliente que me pidió el dinero a los tres días",
                     "fragmento": "Y ahí fue cuando", "momento": "", "formula": 21},
                    {"extracto": "afirmacion", "titulo": "Las llamadas gratis te llenan la agenda de curiosos",
                     "fragmento": "Las llamadas gratis", "momento": "02:10", "formula": 21},
                    {"extracto": "error", "titulo": "Lo que perdí por no cobrar la primera sesión",
                     "fragmento": "Mi error fue", "momento": "", "formula": 99}]}
    _con_claude(monkeypatch, claude)
    antes = estratega.faltan_semana(nid)
    a, aviso = estratega.reaprovechar(db_negocio(nid), TRANSCRIPCION, "Por qué dejé las llamadas gratis")
    assert aviso == "" and a["resumen"] == "Reaprovechar «Por qué dejé las llamadas gratis»: 4 piezas"
    hechas = [estratega.pieza(nid, i) for i in a["datos"]["piezas"]]
    extractos = [p["datos"]["reaprovechado"]["extracto"] for p in hechas]
    assert extractos[0] == "afirmacion" and extractos[-1] == "mecanismo"  # lo fuerte primero, el mecanismo al final
    assert all(p["tipo"] == "reaprovechado" and p["grabar_antes"] == "" for p in hechas)  # se corta de su vídeo
    assert all(p["datos"]["reaprovechado"]["formato"] == "reel" for p in hechas)  # sin carruseles en el Kit
    formulas = [p["datos"]["formula"] for p in hechas]
    assert len(set(formulas)) == 4 and 99 not in formulas  # sin repetir y siempre una que existe
    ap.decidir(a["id"], "aprobar")
    assert estratega.faltan_semana(nid) == antes - 4
    # Con carruseles activos, el mecanismo va en carrusel y no cuenta como reel.
    kit.cambiar(nid, formatos={**kit.leer(nid)["formatos"], "carrusel": True})
    a, _ = estratega.reaprovechar(db_negocio(nid), TRANSCRIPCION, "Otra vez")
    mecanismo = next(estratega.pieza(nid, i) for i in a["datos"]["piezas"]
                     if estratega.pieza(nid, i)["datos"]["reaprovechado"]["extracto"] == "mecanismo")
    assert mecanismo["datos"]["reaprovechado"]["formato"] == "carrusel" and mecanismo["datos"]["reels"] == 0

