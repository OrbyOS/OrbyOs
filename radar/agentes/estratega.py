"""Plani: qué grabar hoy, en qué formato y para qué etapa del embudo.

- Las cuotas y los vídeos a la semana se cuentan en reels. Según el modo de grabación del Kit, una pieza es un guion
  (un reel) o una estructura: un vídeo de 3-5 minutos hablando libre del que Monti saca unos 3 reels.
- Cada pieza tiene un tipo (prueba, enseñar, opinión, historia u oferta), nunca dos del mismo tipo seguidas; una
  fórmula de gancho del catálogo común (ganchos.py), sin repetir en el plan; una hora límite para grabar e
  indicaciones de rodaje. Y un ángulo, no un tema.
- Reaprovecha una grabación larga en una semana de piezas que se sostienen solas.
- Si el Kit tiene activadas las historias, prepara las del día.
- Reparte las piezas entre tus carriles según lo que falta de su cuota semanal y del reparto por etapas.
- Remix primero: la mayoría de las piezas (70 %) rehacen un post que ya funcionó, de la competencia o tuyo. Ordena los
  candidatos por visualizaciones, por cuánto superaron lo normal de su cuenta, por lo recientes que son, por lo cerca que
  están de tu nicho y por el nivel de la cuenta. Un post que ya está cogido no se repite.
- Guarda un hueco para explorar (20 %): no siempre coge el primero de la lista.
- Enfría los temas: no propone lo mismo que en las dos últimas semanas ni lo que ya rechazaste.
- El código elige; Claude solo escribe el título, el ángulo y el esquema de cada pieza con tu Kit de marca.
"""
import json
import math
import random
import re
from datetime import datetime, timedelta

from .. import db, jobs, llm
from ..llm import ErrorIA
from . import analista, estado, ganchos
from . import aprobaciones as ap
from . import kit as kit_marca

AGENTE = "estratega"
REELS_POR_PIEZA = 3  # Monti saca 3-4 reels de cada estructura grabada: se cuenta por lo bajo
PIEZAS_DIA = 3
MAX_DIA_REELS = 12   # un «Graba hoy» nunca pasa de estos reels, aunque vaya muy atrasado (4 estructuras o 12 guiones)
MAX_LOTE_REELS = 30  # ni un día de grabación de estos (10 estructuras o 30 guiones)
TANDA = 7         # piezas por petición a Claude
REMIX_SHARE = 0.7
EXPLORAR = 0.2

# De dónde salen los remixes.
MIN_X = 2.0                 # veces su normal que tiene que haber hecho un post de la competencia
MAX_DIAS_AJENO = 30         # y no más antiguo que esto…
GRANDES_VISTAS = 500_000    # …salvo que pase de estas visualizaciones (probado sea cual sea su normal)
MAX_DIAS_PROBADO = 365
VIDA_MEDIA_DIAS = 14        # cada 14 días, un post de la competencia pierde la mitad de su tirón
PROPIO_MIN_X = 2.0
PROPIO_MIN_VISTAS = 10_000
MAX_DIAS_PROPIO = 365
ENFRIAR_DIAS = 14

TIPOS = {"remix": "Remix", "propio": "Repite tu éxito", "original": "Original",
         "reaprovechado": "De tu grabación larga"}
ESTADOS = {"propuesta": "Propuesta", "aprobada": "Lista para el guion", "rechazada": "Descartada", "guion": "Con guion",
           "grabada": "Grabada", "publicada": "Publicada"}
EN_MARCHA = ("aprobada", "guion", "grabada", "publicada")

_VACIAS = set("""para como pero porque cuando donde desde hasta sobre entre todos todas tiene tienen hacer hace esto
esta este estos estas aquí aqui solo sólo cada más mismo misma vida tienes puedes quieres nunca siempre""".split())


def _ahora() -> datetime:
    return datetime.now()


def _hoy() -> str:
    return _ahora().date().isoformat()


def palabras(texto: str) -> set[str]:
    texto = texto.lower()
    for a, b in zip("áéíóúü", "aeiouu"):
        texto = texto.replace(a, b)
    return {w for w in re.findall(r"[a-zñ]{5,}", texto) if w not in _VACIAS}


def _parecido(a: set[str], b: set[str]) -> float:
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


# ---------------------------------------------------------------- piezas

def _pieza_de_fila(f) -> dict:
    p = dict(f)
    p["esquema"] = json.loads(p["esquema"] or "[]")
    p["datos"] = json.loads(p["datos"] or "{}")
    p["tipo_nombre"] = TIPOS.get(p["tipo"], p["tipo"])
    p["estado_nombre"] = ESTADOS.get(p["estado"], p["estado"])
    return p


def piezas(negocio_id: int, *, dia: str | None = None, estados: tuple[str, ...] | None = None,
           desde: str | None = None) -> list[dict]:
    sql, args = "SELECT * FROM piezas WHERE negocio_id = ?", [negocio_id]
    if dia:
        sql += " AND dia = ?"
        args.append(dia)
    if desde:
        sql += " AND creado >= ?"
        args.append(desde)
    if estados:
        sql += f" AND estado IN ({','.join('?' * len(estados))})"
        args += list(estados)
    with db.conexion() as con:
        return [_pieza_de_fila(f) for f in con.execute(sql + " ORDER BY id", args)]


def pieza(negocio_id: int, pieza_id: int) -> dict | None:
    with db.conexion() as con:
        f = con.execute("SELECT * FROM piezas WHERE negocio_id = ? AND id = ?", (negocio_id, pieza_id)).fetchone()
    return _pieza_de_fila(f) if f else None


def cambiar_estado(negocio_id: int, ids: list[int], estado_: str, *, solo_desde: str | None = None):
    if not ids:
        return
    sql = f"UPDATE piezas SET estado = ? WHERE negocio_id = ? AND id IN ({','.join('?' * len(ids))})"
    args = [estado_, negocio_id, *ids]
    if solo_desde:
        sql += " AND estado = ?"
        args.append(solo_desde)
    with db.conexion() as con:
        con.execute(sql, args)


def descartar(negocio_id: int, pieza_id: int, motivo: str = ""):
    """Una pieza que no te convence: no se graba y su idea no se vuelve a proponer."""
    p = pieza(negocio_id, pieza_id)
    if p and p["estado"] in ("propuesta", "aprobada"):
        cambiar_estado(negocio_id, [pieza_id], "rechazada")
        kit_marca.anadir_rechazado(negocio_id, p["titulo"], motivo)


# ---------------------------------------------------------------- cómo va la semana

def inicio_de_semana(ahora: datetime | None = None) -> datetime:
    ahora = ahora or _ahora()
    return datetime.combine((ahora - timedelta(days=ahora.weekday())).date(), datetime.min.time())


def semana_de(p: dict) -> str:
    """El lunes de la semana en la que cuenta una pieza: la que se le puso al planificarla (un día de grabación en
    fin de semana prepara la siguiente) o, si no, la de cuando se creó."""
    return p["datos"].get("semana") or inicio_de_semana(datetime.fromisoformat(p["creado"][:19])).date().isoformat()


def reels_por_pieza(kit: dict) -> int:
    """Un guion leído da un reel; una estructura grabada hablando libre, unos 3."""
    return REELS_POR_PIEZA if kit.get("modo_grabacion", "estructura") == "estructura" else 1


def reels_de(p: dict, defecto: int = REELS_POR_PIEZA) -> int:
    """Los reels con los que cuenta una pieza."""
    r = p["datos"].get("reels")
    return defecto if r is None else int(r)


def estructuras(reels: int, por_pieza: int = REELS_POR_PIEZA) -> int:
    """Las piezas que hacen falta para esos reels."""
    return -(-max(0, reels) // por_pieza)


def semana(negocio_id: int, kit: dict | None = None, lunes: datetime | None = None) -> list[dict]:
    """Cada carril con su cuota y los reels que ya van esa semana (por defecto, esta)."""
    kit = kit or kit_marca.leer(negocio_id)
    lunes = lunes or inicio_de_semana()
    negocio = db.negocio(negocio_id) or {"ficha": {}}
    carriles = kit_marca.cuotas_que_caben(kit["carriles"], kit_marca.tope_semanal(negocio["ficha"]),
                                          exacto=bool(kit_marca.videos_pedidos(negocio["ficha"])))
    hechas: dict[str, int] = {}
    for p in piezas(negocio_id, estados=EN_MARCHA, desde=(lunes - timedelta(days=7)).isoformat()):
        if semana_de(p) == lunes.date().isoformat():
            hechas[p["carril"]] = hechas.get(p["carril"], 0) + reels_de(p, reels_por_pieza(kit))
    return [{**c, "hechas": hechas.get(c["id"], 0), "faltan": max(0, c["cuota"] - hechas.get(c["id"], 0))}
            for c in carriles]


def faltan_semana(negocio_id: int, kit: dict | None = None, lunes: datetime | None = None) -> int:
    """Cuántos reels faltan para cubrir las cuotas de la semana."""
    return sum(c["faltan"] for c in semana(negocio_id, kit, lunes) if c["cuota"] > 0)


def dias_de_plan(ahora: datetime | None = None) -> int:
    """Los días de lunes a viernes que quedan esta semana, hoy incluido (el piloto no prepara «Graba hoy» en fin de
    semana). En fin de semana, 1: lo que se pida a mano se hace hoy."""
    return max(1, 5 - (ahora or _ahora()).weekday())


def piezas_de_hoy(negocio_id: int, pedidos: int, kit: dict | None = None) -> int:
    """Con un número de reels pedido, las piezas que faltan de la semana repartidas entre los días que quedan:
    si un día no se planificó, los siguientes lo recuperan."""
    kit = kit or kit_marca.leer(negocio_id)
    por = reels_por_pieza(kit)
    faltan = estructuras(faltan_semana(negocio_id, kit), por)
    return min(max(1, MAX_DIA_REELS // por), -(-faltan // dias_de_plan()) if faltan else -(-estructuras(pedidos, por) // 5))


def reparto_reciente(negocio_id: int, dias: int = 30) -> dict[str, int]:
    """El % de piezas de cada etapa en el último mes, para compararlo con el objetivo."""
    desde = (_ahora() - timedelta(days=dias)).isoformat()
    cuenta = {e: 0 for e in kit_marca.ETAPAS}
    for p in piezas(negocio_id, estados=EN_MARCHA, desde=desde):
        if p["etapa"] in cuenta:
            cuenta[p["etapa"]] += 1
    total = sum(cuenta.values())
    return {e: round(100 * n / total) if total else 0 for e, n in cuenta.items()}


def huecos(negocio_id: int, n: int, kit: dict, lunes: datetime | None = None) -> list[dict]:
    """Los carriles de las `n` piezas: primero los que más cuota les falta; a igualdad, la etapa que va más por detrás
    de su objetivo. Si la semana ya está cubierta, sigue en proporción a las cuotas."""
    activos = [c for c in semana(negocio_id, kit, lunes) if c["cuota"] > 0]
    if not activos:
        return []
    reparto = reparto_reciente(negocio_id)
    retraso = {e: kit["mezcla"][e] - reparto[e] for e in kit_marca.ETAPAS}
    faltan = {c["id"]: c["faltan"] for c in activos}
    # Lo aprendido de tus resultados: cuánto rinde cada carril frente a lo normal (1 = como siempre).
    from . import aprendizaje
    peso = {c["id"]: 1.0 for c in activos} | {k: max(0.2, v) for k, v in aprendizaje.peso_de_carril(negocio_id).items()}
    elegidos = []
    for _ in range(n):
        orden = sorted(activos, key=lambda c: (-faltan[c["id"]], -retraso[c["etapa"]], -peso.get(c["id"], 1.0), -c["cuota"]))
        c = orden[0]
        if faltan[c["id"]] <= 0:  # semana cubierta: el que menos ha salido en este lote, en proporción a su cuota y su rendimiento
            c = min(activos, key=lambda c: (sum(1 for e in elegidos if e["id"] == c["id"]) / (c["cuota"] * peso.get(c["id"], 1.0)),
                                            -c["cuota"]))
        faltan[c["id"]] -= reels_por_pieza(kit)
        retraso[c["etapa"]] -= 100 / max(1, n)
        elegidos.append(c)
    return elegidos


# ---------------------------------------------------------------- tipo de pieza, gancho, hora y rodaje

CLASES = {"prueba": "Prueba", "ensenar": "Enseñar", "opinion": "Opinión", "historia": "Historia", "oferta": "Oferta"}
# Peso de cada tipo en la semana: una prueba, una o dos de enseñar, una opinión; historia y oferta, una cada dos semanas.
PESO_CLASE = {"prueba": 2, "ensenar": 3, "opinion": 2, "historia": 1, "oferta": 1}
CLASES_POR_ETAPA = {"tofu": ["opinion", "historia", "ensenar"], "mofu": ["ensenar", "prueba", "historia"],
                    "bofu": ["oferta", "prueba"]}
ENFRIAR_FORMULA_DIAS = 7
# Qué fórmulas de gancho van mejor a cada tipo de pieza y cuáles piden una cifra propia: las dice el catálogo de Escri
# (ganchos.para_clase y ganchos.CON_CIFRA); estas listas solo valen mientras el catálogo no las traiga.
_FORMULAS_POR_CLASE = {
    "prueba": [6, 13, 5, 1, 15, 25, 4, 17],
    "ensenar": [7, 9, 11, 16, 18, 10, 20, 26, 2, 3, 4, 5, 19, 23, 24],
    "opinion": [2, 3, 20, 22, 17, 23, 26, 8, 14],
    "historia": [21, 1, 15, 8, 25],
    "oferta": [12, 10, 14, 24, 19],
}
# Las que necesitan una cifra propia del dueño (dinero, tiempo, resultados): fuera si su Kit no permite cifras propias.
_CON_CIFRA_PROPIA = {1, 4, 5, 6, 13, 15}
if hasattr(ganchos, "para_clase"):
    FORMULAS_POR_CLASE = {c: list(ganchos.para_clase(c)) for c in _FORMULAS_POR_CLASE}
else:
    FORMULAS_POR_CLASE = _FORMULAS_POR_CLASE
CON_CIFRA_PROPIA = set(getattr(ganchos, "CON_CIFRA", _CON_CIFRA_PROPIA))

HORA_LIMITE = "20:00"        # sin plan de publicación, grabar hoy antes de esta hora
MARGEN_EDICION_HORAS = 3     # lo que necesita Monti entre que se graba y la primera publicación del día
# Indicaciones de rodaje de partida por formato; Claude añade lo que necesita cada pieza.
RODAJE = {
    "camara": ["Encuadre de pecho para arriba, a la altura de los ojos, con luz de frente (una ventana vale).",
               "Empieza ya diciendo el gancho: nada de saludar ni presentarte."],
    "voz": ["Graba la voz en un sitio sin eco, con el móvil a un palmo de la boca.",
            "Graba aparte la pantalla o las imágenes de lo que cuentas, en vertical."],
    "sin_cara": ["Graba manos, pantalla u objetos en vertical, con luz de frente.",
                 "La voz, aparte y en un sitio sin eco."],
}


def _ultima_clase(negocio_id: int) -> str:
    with db.conexion() as con:
        f = con.execute("SELECT datos FROM piezas WHERE negocio_id = ? AND estado != 'rechazada' ORDER BY id DESC LIMIT 1",
                        (negocio_id,)).fetchone()
    return json.loads(f["datos"] or "{}").get("clase", "") if f else ""


def clases_posibles(carril: dict, kit: dict) -> list[str]:
    """Los tipos que le van a un carril: los que diga el Kit o, si no, los de su etapa. Sin pruebas en el Kit, no hay
    piezas de prueba."""
    clases = [c for c in carril.get("clases") or [] if c in CLASES] or CLASES_POR_ETAPA.get(carril["etapa"], list(CLASES))
    if not kit.get("pruebas"):
        clases = [c for c in clases if c != "prueba"] or ["ensenar"]
    return clases


def ordenar_por_clase(negocio_id: int, lote: list[dict], kit: dict, lunes: datetime | None = None) -> list[dict]:
    """Pone a cada pieza su tipo y las ordena para que nunca vayan dos del mismo tipo seguidas (contando la última que
    ya se planificó). De entre los tipos que le van a cada carril, elige el que más se debe esta semana."""
    lunes = lunes or inicio_de_semana()
    cuenta = {c: 0 for c in CLASES}
    for p in piezas(negocio_id, desde=(lunes - timedelta(days=7)).isoformat()):
        if p["estado"] != "rechazada" and semana_de(p) == lunes.date().isoformat() and p["datos"].get("clase") in cuenta:
            cuenta[p["datos"]["clase"]] += 1
    total_peso = sum(PESO_CLASE.values())
    previa, quedan, salida = _ultima_clase(negocio_id), list(lote), []
    while quedan:
        total = sum(cuenta.values()) + 1
        deuda = lambda c: PESO_CLASE[c] * total / total_peso - cuenta[c]  # noqa: E731
        posibles = [clases_posibles(h["carril"], kit) for h in quedan]
        # Primero lo que solo admite un tipo (si se deja para el final, saldría repetido); luego, lo que más se debe.
        forzadas = {c: sum(1 for p in posibles if p == [c]) for c in CLASES}
        opciones = [(forzadas[c], deuda(c), -i, i, c) for i, p in enumerate(posibles) for c in p if c != previa]
        if not opciones:  # todas las que quedan solo admiten el tipo anterior: no hay otra
            opciones = [(forzadas[c], deuda(c), -i, i, c) for i, p in enumerate(posibles) for c in p]
        *_, i, clase = max(opciones)
        h = quedan.pop(i)
        salida.append({**h, "clase": clase})
        cuenta[clase] += 1
        previa = clase
    return salida


def _formula(id_) -> dict | None:
    return ganchos.POR_ID.get(int(id_)) if str(id_ or "").isdigit() else None


def _formula_en_texto(f: dict) -> str:
    return f"n.º {f['id']} «{f['nombre']}»: {f['plantilla']} Ejemplo: {f['ejemplo']} Ojo: {f['trampa']}"


def _formulas_recientes(negocio_id: int) -> list[int]:
    desde = (_ahora() - timedelta(days=ENFRIAR_FORMULA_DIAS)).isoformat()
    return [p["datos"]["formula"] for p in piezas(negocio_id, desde=desde)
            if p["estado"] != "rechazada" and p["datos"].get("formula")]


def poner_formulas(negocio_id: int, lote: list[dict], kit: dict, azar: random.Random) -> list[dict]:
    """Una fórmula de gancho por pieza, de las que le van a su tipo, sin repetir en el plan y dejando descansar las
    de la última semana. Un remix se queda con la de su original (la que diga Lupi o la que se reconozca en su gancho). Si el Kit no permite
    cifras propias, fuera las que las necesitan."""
    sin_cifras = not kit.get("limites", {}).get("cifras_propias", True)
    usadas = _formulas_recientes(negocio_id)
    for h in lote:
        plantilla = (h.get("fuente") or {}).get("plantilla") or {}
        original = plantilla.get("formula") or ganchos.clasificar(plantilla.get("gancho_literal") or "")
        if _formula(original):
            h["formula"] = int(original)
            usadas.append(h["formula"])
            continue
        posibles = [i for i in FORMULAS_POR_CLASE.get(h["clase"], []) if _formula(i)
                    and not (sin_cifras and i in CON_CIFRA_PROPIA)] or FORMULAS_POR_CLASE["ensenar"][:4]
        frescas = [i for i in posibles if i not in usadas] or posibles
        # Las que menos se han usado últimamente primero; entre ellas, al azar.
        menos = min(usadas.count(i) for i in frescas)
        h["formula"] = azar.choice([i for i in frescas if usadas.count(i) == menos])
        usadas.append(h["formula"])
    return lote


def hora_limite(kit: dict, ahora: datetime | None = None, *, lote: bool = False) -> str:
    """Hasta cuándo se puede grabar hoy: unas horas antes de la primera publicación de hoy (para que dé tiempo a
    montarlo) o, si hoy no se publica, a las 20:00. Un día de grabación, hasta las 20:00."""
    ahora = ahora or _ahora()
    hora = HORA_LIMITE
    if not lote:
        horas = sorted(h for red in (kit.get("publicacion") or {}).values() if red.get("activa")
                       and ahora.weekday() in (red.get("dias") or []) for h in red.get("horas") or [])
        for h in horas:
            try:
                limite = datetime.combine(ahora.date(), datetime.strptime(h, "%H:%M").time()) - timedelta(
                    hours=MARGEN_EDICION_HORAS)
            except ValueError:
                continue
            if limite >= ahora + timedelta(hours=1):
                hora = limite.strftime("%H:%M")
                break
    return f"{ahora.date().isoformat()}T{hora}"


def rodaje_de_partida(kit: dict) -> list[str]:
    return list(RODAJE.get((kit.get("voz") or {}).get("camara", "cara"), RODAJE["camara"]))


def es_tema(titulo: str) -> bool:
    """«Captación de clientes» es un tema; «Por qué dejé de hacer llamadas de diagnóstico gratis» es un ángulo."""
    return len(re.findall(r"\w+", titulo or "")) < 5


# ---------------------------------------------------------------- de dónde salen los remixes

def _edad_dias(p: dict, ahora: datetime) -> float:
    try:
        return max(0.0, (ahora - datetime.fromisoformat(p["publicado"][:19])).total_seconds() / 86400)
    except (ValueError, TypeError):
        return 9999.0


def _palabras_del_nicho(negocio: dict, kit: dict) -> set[str]:
    f = negocio["ficha"]
    texto = " ".join([str(f.get(k) or "") for k in ("que_vende", "a_quien", "dolores", "deseos", "palabras_clave", "temas")]
                     + [f"{c['nombre']} {c['descripcion']}" for c in kit["carriles"]])
    return palabras(texto)


def cogidos(negocio_id: int) -> set[int]:
    """Posts que ya tienen su remix: en marcha, o propuestos hoy."""
    with db.conexion() as con:
        filas = con.execute(
            "SELECT fuente_post_id FROM piezas WHERE negocio_id = ? AND fuente_post_id IS NOT NULL AND "
            f"(estado IN ({','.join('?' * len(EN_MARCHA))}) OR (estado = 'propuesta' AND dia = ?))",
            (negocio_id, *EN_MARCHA, _hoy())).fetchall()
    return {f[0] for f in filas}


def candidatos(negocio: dict, kit: dict | None = None, ahora: datetime | None = None) -> list[dict]:
    """Posts que se pueden rehacer, del más prometedor al menos."""
    ahora, kit = ahora or _ahora(), kit or kit_marca.leer(negocio["id"])
    nicho = _palabras_del_nicho(negocio, kit)
    temas_recientes = [palabras(p["titulo"] + " " + p["angulo"]) for p in
                       piezas(negocio["id"], desde=(ahora - timedelta(days=ENFRIAR_DIAS)).isoformat())
                       if p["estado"] != "rechazada"]
    rechazados = [palabras(r["concepto"]) for r in kit["rechazados"]]
    usados = cogidos(negocio["id"])
    revisa = llm.disponible()  # con Claude, solo vale lo que ya se ha comprobado que encaja
    with db.conexion() as con:
        filas = con.execute(
            "SELECT p.*, c.usuario AS cuenta, c.nivel AS nivel, c.propia AS propia FROM posts p "
            "JOIN cuentas c ON c.id = p.cuenta_id WHERE p.negocio_id = ? AND p.estado_plantilla != 'fallida'",
            (negocio["id"],)).fetchall()
    vistos_por_cuenta: dict[tuple, dict] = {}
    for f in filas:
        p = dict(f)
        p["plantilla"] = json.loads(p["plantilla"] or "{}")
        if p["id"] in usados or p["plantilla"].get("provisional") or p["plataforma"] in analista.SOLO_IDEAS:
            continue  # ya cogido, o su plantilla no sale del vídeo (solo del texto del post)
        if not p["propia"] and (p["encaje"] == "no" or (revisa and p["encaje"] != "si")):
            continue  # no encaja con el negocio (un meme, otro nicho…) o aún no se ha comprobado
        edad = _edad_dias(p, ahora)
        if p["propia"]:
            if not (p["x"] >= PROPIO_MIN_X and p["vistas"] >= PROPIO_MIN_VISTAS and edad <= MAX_DIAS_PROPIO):
                continue
            frescura = 0.5 ** (edad / 180)
        else:
            reciente = (p["x"] >= MIN_X or p["despega"]) and edad <= MAX_DIAS_AJENO  # lo que despega, ya
            probado = p["vistas"] >= GRANDES_VISTAS and edad <= MAX_DIAS_PROBADO
            if not (reciente or probado):
                continue
            frescura = max(0.5 ** (edad / VIDA_MEDIA_DIAS), 0.35 if probado else 0.0)
        tema = palabras(" ".join([p["texto"], p["plantilla"].get("tema", ""), p["gancho"]]))
        if any(_parecido(tema, t) >= 0.6 for t in temas_recientes + rechazados):
            continue
        cercania = min(1.0, len(tema & nicho) / 3)
        nivel = {1: 0.5, 2: 0.0, 3: -0.3}.get(p["nivel"], 0.0)
        p["puntuacion"] = round((math.log10(p["vistas"] + 10) + 0.6 * math.log2(max(p["x"], 1)) + 1.5 * cercania + nivel
                                 + (0.3 if p["estado_plantilla"] == "lista" else 0)
                                 + (0.8 + 0.3 * math.log2(max(p["ritmo"], 1)) if p["despega"] else 0))
                                * (0.5 + 0.5 * frescura), 3)
        # Si un creador subió el mismo vídeo dos veces, cuenta la mejor copia.
        clave = (p["cuenta_id"], " ".join(sorted(tema))[:80] or p["url"])
        if clave not in vistos_por_cuenta or vistos_por_cuenta[clave]["puntuacion"] < p["puntuacion"]:
            vistos_por_cuenta[clave] = p
    return sorted(vistos_por_cuenta.values(), key=lambda p: p["puntuacion"], reverse=True)


def anclas_recientes(negocio_id: int) -> list[str]:
    desde = (_ahora() - timedelta(days=ANCLA_DIAS)).isoformat()
    salida = []
    for p in piezas(negocio_id, desde=desde):
        a = p["datos"].get("ancla") or {}
        if p["estado"] != "rechazada" and a.get("tipo") not in (None, "", "plantilla", "ninguna") and a.get("texto"):
            salida.append(f"{TIPOS_ANCLA.get(a['tipo'], a['tipo'])}: {a['texto'][:160]}")
    return list(dict.fromkeys(salida))


def temas_largos(negocio_id: int, n: int = 8) -> list[str]:
    """Lo que está funcionando en vídeo largo (YouTube) en el nicho: ideas de tema para las piezas originales."""
    desde = (_ahora() - timedelta(days=90)).isoformat()
    with db.conexion() as con:
        filas = con.execute(
            "SELECT p.texto, p.x, p.vistas FROM posts p JOIN cuentas c ON c.id = p.cuenta_id WHERE p.negocio_id = ? AND "
            "p.plataforma = 'youtube' AND c.propia = 0 AND p.destaca = 1 AND p.encaje != 'no' AND p.publicado >= ? "
            "ORDER BY p.x DESC LIMIT ?", (negocio_id, desde, n)).fetchall()
    return [f"{f['texto'][:120]} (×{f['x']:g}, {f['vistas']} visualizaciones)" for f in filas]


def referencia(p: dict) -> str:
    """«Basado en el reel de @cuenta: 1,2 M visualizaciones, ×14 su normal»."""
    cuenta = p["cuenta"] if p["cuenta"].startswith("@") else "@" + p["cuenta"]
    vistas = p["vistas"]
    cifra = f"{vistas / 1e6:.1f} M".replace(".", ",") if vistas >= 1e6 else (
        f"{vistas / 1e3:.0f} mil" if vistas >= 1e3 else str(vistas))
    quien = "tu post" if p.get("propia") else f"el post de {cuenta}"
    veces = f"{p['x']:g}".replace(".", ",")
    return f"Basado en {quien}: {cifra} visualizaciones, ×{veces} su normal"


def elegir(negocio: dict, n: int, kit: dict, *, semilla: str = "", lunes: datetime | None = None) -> list[dict]:
    """Los huecos del lote, cada uno con su post de origen si es un remix."""
    slots = huecos(negocio["id"], n, kit, lunes)
    lista = candidatos(negocio, kit)
    azar = random.Random(semilla or f"{negocio['id']}-{_hoy()}")
    remixes = round(len(slots) * REMIX_SHARE)
    salida = []
    for i, carril in enumerate(slots):
        fuente = None
        if i < remixes and lista:
            # Explorar: de vez en cuando, uno de más abajo en la lista.
            j = azar.randrange(1, min(len(lista), 6)) if len(lista) > 1 and azar.random() < EXPLORAR else 0
            fuente = lista.pop(j)
        tipo = ("propio" if fuente["propia"] else "remix") if fuente else "original"
        salida.append({"carril": carril, "fuente": fuente, "tipo": tipo})
    return salida


# ---------------------------------------------------------------- escribir el lote

TIPOS_ANCLA = {"historia": "Una historia suya", "opinion": "Una opinión suya", "objecion": "Una objeción con su respuesta",
               "prueba": "Una prueba del inventario", "pregunta_publico": "Lo que pregunta el público",
               "frase_cliente": "Una frase de sus clientes", "tema_largo": "Un tema que funciona en vídeo largo",
               "plantilla": "La plantilla del post original", "ninguna": "Sin ancla"}
ANCLA_DIAS = 30  # la misma historia, opinión u objeción no se repite en un mes

ESQUEMA_LOTE = llm.obj(piezas=llm.lista(llm.obj(
    numero=llm.N, titulo=llm.S, angulo=llm.S, formato=llm.S, esquema=llm.lista(llm.S), rodaje=llm.lista(llm.S),
    ancla=llm.obj(tipo={"type": "string", "enum": list(TIPOS_ANCLA)}, texto=llm.S))))

SISTEMA_LOTE = """Eres Plani, quien planifica en un equipo de contenido en español. Te paso el Kit de marca del negocio y una lista
de piezas ya decididas: su carril, su etapa del embudo, su tipo (prueba, enseñar, opinión, historia u oferta), la
fórmula de gancho que le toca y, si es un remix, la plantilla del post original (su estructura, no sus palabras).
Para cada pieza escribe:
- titulo: un ÁNGULO, no un tema. «Captar clientes» es un tema; «Por qué dejé de hacer llamadas de diagnóstico
  gratis» es un ángulo: una situación, una postura o algo que pasó, que solo puede contar este negocio. Para el
  negocio, no el del creador original.
- angulo: en una frase, qué idea concreta defiende y para quién.
- formato: cómo se graba (hablando a cámara, pantalla partida, pantalla verde…). En un remix, el del original.
- esquema: {esquema}
  Con la fórmula de gancho que le toca en mente: el primer punto es lo que hace de gancho.
- rodaje: de 2 a 4 indicaciones cortas y prácticas para grabarla (dónde, qué enseñar, qué tener a mano). Parte de
  las de partida que te paso y añade lo que pide esta pieza.
Nunca uses el nombre, las marcas, las historias ni las cifras del creador original. Las cifras solo pueden salir del
inventario de pruebas del Kit, citando su id entre corchetes. No repitas las ideas rechazadas.
- ancla: cada pieza ORIGINAL se apoya en algo concreto y suyo del Kit o de lo que pregunta su público: una historia,
  una opinión, una objeción con su respuesta, una prueba, una frase de sus clientes, una pregunta del público o un tema
  que funciona en vídeo largo. Di cuál («tipo») y cópialo («texto»). Nunca una pieza genérica sin ancla. No uses un
  ancla de la lista de usadas en el último mes. En un remix, el ancla es «plantilla»."""


ESQUEMA_ESTRUCTURA = """de 3 a 6 temas que tocar. Cada pieza es un vídeo de 3-5 minutos hablando libre, sin guion, del
  que luego se sacan unos 3 reels: cada tema tiene que dar para un reel por sí solo. En un remix, los mismos pasos y
  en el mismo orden que el original, cada uno haciendo el mismo trabajo, pero con el tema, los ejemplos y la voz del
  negocio."""
ESQUEMA_GUION = """de 4 a 6 pasos de lo que se dice en un reel, empezando por el gancho y terminando con el cierre. En
  un remix, los mismos pasos y en el mismo orden que el original, cada uno haciendo el mismo trabajo, pero con el
  tema, los ejemplos y la voz del negocio."""


def _describir(i: int, hueco: dict) -> str:
    c, f = hueco["carril"], hueco["fuente"]
    linea = f"{i}. Carril «{c['nombre']}» ({c['etapa'].upper()}): {c['descripcion']}"
    if hueco.get("clase"):
        linea += f"\n   Tipo: {CLASES[hueco['clase']]}."
    if _formula(hueco.get("formula")):
        linea += f"\n   Fórmula de gancho {_formula_en_texto(_formula(hueco['formula']))}"
    if not f:
        return linea + "\n   Original: elige el tema que más sirva a este carril."
    t = f["plantilla"]
    if t.get("tema"):
        pasos = "; ".join(f"{p.get('desde', 0):g}-{p.get('hasta', 0):g} s {p.get('que_hace', '')}" for p in t.get("pasos") or [])
        return (linea + f"\n   Remix de {'su propio post' if f['propia'] else 'un post de la competencia'} "
                f"({f['x']:g} veces su normal). Tema original: {t['tema']}. Formato: {t.get('formato', '')}. "
                f"Pasos: {pasos}. Cierre: {t.get('cierre', '')}. Por qué funcionó: {t.get('por_que_funciona', '')}")
    return linea + "\n   Remix: el desmontaje de su post aún no está; propón el tema y un esquema provisional."


def redactar(negocio: dict, kit: dict, lote: list[dict], nota: str = "") -> list[dict]:
    """Título, ángulo, formato y esquema de cada pieza. Sin Claude, un borrador sacado de la plantilla."""
    if llm.disponible():
        sistema = SISTEMA_LOTE.replace("{esquema}", ESQUEMA_ESTRUCTURA if reels_por_pieza(kit) > 1 else ESQUEMA_GUION)
        peticion = kit_marca.contexto(negocio, kit) + "\n\n## Piezas\n" + "\n".join(
            _describir(i + 1, h) for i, h in enumerate(lote))
        peticion += "\n\n## Indicaciones de rodaje de partida\n" + "\n".join(f"- {r}" for r in rodaje_de_partida(kit))
        publico = analista.publico_en_texto(negocio["id"])
        if publico:
            peticion += "\n\n" + publico
        usadas = anclas_recientes(negocio["id"])
        if usadas:
            peticion += "\n\n## Anclas usadas en el último mes (no las repitas)\n" + "\n".join(f"- {a}" for a in usadas)
        largos = temas_largos(negocio["id"])
        if largos and any(not h["fuente"] for h in lote):
            peticion += ("\n\n## Temas que están funcionando en vídeo largo en tu nicho (para las piezas originales: "
                         "llévalos a vídeo corto con tu ángulo)\n" + "\n".join(f"- {t}" for t in largos))
        if nota:
            peticion += f"\n\n## Lo que ha pedido el dueño al revisar el plan anterior\n{nota}"
        for intento in range(2):
            try:
                datos = llm.json_con_esquema(sistema, peticion, ESQUEMA_LOTE, effort="medium")
            except ErrorIA:
                break
            por_numero = {int(p.get("numero") or 0): p for p in datos.get("piezas") or []}
            if not all(i + 1 in por_numero for i in range(len(lote))):
                continue
            textos = [por_numero[i + 1] for i in range(len(lote))]
            temas = [t["titulo"] for t in textos if es_tema(str(t.get("titulo") or ""))]
            if not temas or intento:
                return textos
            # Un título que es un tema y no un ángulo: se pide otra vez, una sola.
            peticion += ("\n\n## Corrige\nEstos títulos son temas, no ángulos: " + "; ".join(temas) +
                         ". Escríbelos como una situación, una postura o algo que pasó.")
    salida = []
    for h in lote:
        t = (h["fuente"] or {}).get("plantilla") or {}
        salida.append({"titulo": t.get("tema") or h["carril"]["nombre"], "angulo": h["carril"]["descripcion"],
                       "formato": t.get("formato") or "Hablando a cámara", "rodaje": rodaje_de_partida(kit),
                       "esquema": [p.get("que_hace", "") for p in t.get("pasos") or []] or ["Gancho", "Desarrollo", "Cierre"]})
    return salida


def planificar(negocio: dict, *, n: int = PIEZAS_DIA, lote: bool = False, nota: str = "") -> dict | None:
    """Prepara el «Graba hoy» (o un día de grabación con la semana entera) y lo manda a aprobar."""
    nid, kit = negocio["id"], kit_marca.leer(negocio["id"])
    # Un día de grabación en fin de semana prepara la semana que viene; el resto, la de hoy.
    lunes = inicio_de_semana() + timedelta(days=7 if lote and _ahora().weekday() >= 5 else 0)
    faltan = faltan_semana(nid, kit, lunes)
    pedidos = kit_marca.videos_pedidos(negocio["ficha"])
    por = reels_por_pieza(kit)
    if lote:
        n = min(max(1, MAX_LOTE_REELS // por), estructuras(faltan, por) or PIEZAS_DIA)
    elif pedidos:
        n = piezas_de_hoy(nid, pedidos, kit)  # 21 reels a la semana: 7 estructuras entre los días que quedan
    elif faltan:
        n = min(n, estructuras(faltan, por))  # no más de lo que falta para la semana: lo que sobra no se graba
    # Lo que quedó propuesto hoy sin aprobar se sustituye por el nuevo plan.
    viejas = [p["id"] for p in piezas(nid, dia=_hoy(), estados=("propuesta",))]
    cambiar_estado(nid, viejas, "rechazada")
    analista.revisar_encaje(negocio)  # lo que destaca y aún no se ha comprobado, antes de elegir
    semilla = f"{nid}-{_hoy()}-{len(viejas)}"
    elegido = elegir(negocio, n, kit, semilla=semilla, lunes=lunes)
    if not elegido:
        return None
    # Un remix nunca se escribe sin el desmontaje de su original: se pide ahora.
    for h in elegido:
        f = h["fuente"]
        if f and f["estado_plantilla"] != "lista":
            nuevo = analista.desmontar(nid, f["id"]) if llm.disponible() else {"estado_plantilla": ""}
            if nuevo["estado_plantilla"] == "lista" and not nuevo["plantilla"].get("provisional"):
                h["fuente"] = {**f, "plantilla": nuevo["plantilla"], "estado_plantilla": "lista"}
            else:
                h["fuente"], h["tipo"] = None, "original"
    elegido = poner_formulas(nid, ordenar_por_clase(nid, elegido, kit, lunes), kit, random.Random(semilla))
    ahora = _ahora()
    limite = hora_limite(kit, ahora, lote=lote)
    ids, vista = [], []
    nombres = {c["id"]: c["nombre"] for c in kit["carriles"]}
    # Por tandas: cada una ya ve las anclas que usó la anterior, y un día de 21 piezas no va en una sola petición.
    for i in range(0, len(elegido), TANDA):
        tanda = elegido[i:i + TANDA]
        _guardar(nid, tanda, redactar(negocio, kit, tanda, nota), ahora, lunes, nombres, ids, vista, por, limite)
    que_viene = " que viene" if lunes > inicio_de_semana() else ""
    if por > 1:
        cuantas = f"{len(ids)} estructura{'s' if len(ids) != 1 else ''} (unos {len(ids) * por} reels)"
    else:
        cuantas = f"{len(ids)} pieza{'s' if len(ids) != 1 else ''}"
    resumen = f"Día de grabación: {cuantas} para la semana{que_viene}" if lote else f"Graba hoy: {cuantas}"
    datos = {"piezas": ids, "lote": lote, "n": len(ids), "vista": vista, "grabar_antes": limite}
    if kit.get("formatos", {}).get("historias"):
        datos["historias"] = historias_del_dia(negocio, kit, vista)
    a = ap.pedir(nid, AGENTE, "brief", resumen, datos)
    with db.conexion() as con:
        con.execute(f"UPDATE piezas SET aprobacion_id = ? WHERE id IN ({','.join('?' * len(ids))})", (a["id"], *ids))
    return a


def _guardar(nid: int, elegido: list[dict], textos: list[dict], ahora: datetime, lunes: datetime, nombres: dict,
             ids: list[int], vista: list[dict], por: int = REELS_POR_PIEZA, limite: str = ""):
    with db.conexion() as con:
        for h, t in zip(elegido, textos):
            f = h["fuente"]
            datos = {"referencia": referencia(f), "url": f["url"], "plantilla": f["plantilla"]} if f else {}
            datos["semana"], datos["reels"] = lunes.date().isoformat(), por
            datos["clase"], datos["formula"] = h.get("clase", ""), h.get("formula")
            datos["rodaje"] = [str(x).strip()[:200] for x in t.get("rodaje") or [] if str(x).strip()][:4]
            ancla = t.get("ancla") or {}
            if ancla.get("tipo") in TIPOS_ANCLA and str(ancla.get("texto") or "").strip():
                datos["ancla"] = {"tipo": ancla["tipo"], "texto": str(ancla["texto"]).strip()[:400]}
            cur = con.execute(
                "INSERT INTO piezas (negocio_id, creado, dia, tipo, carril, etapa, fuente_post_id, titulo, angulo, "
                "formato, esquema, grabar_antes, datos) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (nid, ahora.isoformat(timespec="seconds"), _hoy(), h["tipo"], h["carril"]["id"], h["carril"]["etapa"],
                 f["id"] if f else None, str(t.get("titulo") or "")[:160], str(t.get("angulo") or "")[:400],
                 str(t.get("formato") or "")[:80], json.dumps([str(x)[:300] for x in t.get("esquema") or []][:8],
                                                             ensure_ascii=False),
                 limite or _hoy(), json.dumps(datos, ensure_ascii=False)))
            ids.append(cur.lastrowid)
            f_gancho = _formula(h.get("formula"))
            vista.append({"titulo": str(t.get("titulo") or "")[:160], "angulo": str(t.get("angulo") or "")[:400],
                          "tipo": TIPOS[h["tipo"]], "carril": nombres.get(h["carril"]["id"], ""),
                          "etapa": h["carril"]["etapa"], "referencia": datos.get("referencia", ""),
                          "clase": CLASES.get(h.get("clase"), ""),
                          "formula": f"n.º {f_gancho['id']} · {f_gancho['nombre']}" if f_gancho else "",
                          "grabar_antes": limite, "rodaje": datos["rodaje"]})


@ap.al_aprobar("brief")
def _brief_aprobado(a: dict):
    cambiar_estado(a["negocio_id"], a["datos"].get("piezas") or [], "aprobada", solo_desde="propuesta")


@ap.al_rechazar("brief")
def _brief_rechazado(a: dict):
    ids = a["datos"].get("piezas") or []
    if a["estado"] == "cambios":
        # Con «Pedir cambios», Plani rehace el plan con tu nota.
        negocio = db.negocio(a["negocio_id"])
        cambiar_estado(a["negocio_id"], ids, "rechazada", solo_desde="propuesta")
        r = a["datos"].get("reaprovechar")
        if negocio and r:
            jobs.en_segundo_plano(lambda: reaprovechar(negocio, r["texto"], r["titulo"],
                                                       video_propio=r["video_propio"], nota=a["nota"]))
        elif negocio:
            jobs.en_segundo_plano(trabajo_planificar, negocio, a["datos"].get("lote", False), a["nota"], None,
                                  a["datos"].get("n") or PIEZAS_DIA)
    else:
        cambiar_estado(a["negocio_id"], ids, "rechazada", solo_desde="propuesta")


def trabajo_planificar(negocio: dict, lote: bool, nota: str, usuario_id: int | None, n: int = PIEZAS_DIA):
    from .. import gasto
    gasto.empezar()
    gasto_id = db.abrir_gasto(usuario_id=usuario_id, negocio_id=negocio["id"], concepto="estratega")
    try:
        estado.cambiar(negocio["id"], AGENTE, trabajando=True, avisos=[])
        a = planificar(negocio, n=n, lote=lote, nota=nota)
        avisos = [] if a else ["No hay carriles con cuota: añade alguno en el Kit de marca."]
        cap = kit_marca.capacidad(negocio)
        if cap["ajustado"]:
            avisos.append(f"Tus temas fijos suman {cap['pedidos']} vídeos a la semana y pediste {cap['videos_semana']}: "
                          f"Plani reparte {cap['videos_semana']} entre ellos, en proporción.")
        if cap["recortado"]:
            avisos.append(f"Tus temas fijos piden {cap['pedidos']} vídeos a la semana, pero con «{cap['tiempo']}» para "
                          f"grabar caben {cap['tope']}: Plani planifica {cap['tope']}. Ajusta las cuotas en el Kit.")
        estado.cambiar(negocio["id"], AGENTE, trabajando=False, ultimo=_ahora().isoformat(timespec="seconds"),
                       avisos=avisos)
    except Exception as e:  # noqa: BLE001
        estado.cambiar(negocio["id"], AGENTE, trabajando=False, avisos=[f"El plan se ha parado: {e}"])
        raise
    finally:
        db.cerrar_gasto(gasto_id, gasto.uso())


# ---------------------------------------------------------------- historias del día (si el Kit las activa)

PEGATINAS = {"encuesta": "Encuesta", "preguntas": "Caja de preguntas", "quiz": "Quiz", "deslizador": "Deslizador",
             "enlace": "Enlace", "cuenta_atras": "Cuenta atrás", "anade_el_tuyo": "Añade el tuyo", "ninguna": "Ninguna"}
MAX_MARCOS = 7
MARCO_PREGUNTA = 4  # la pegatina, en el cuarto: más tarde ya no la ve casi nadie

ESQUEMA_HISTORIAS = llm.obj(marcos=llm.lista(llm.obj(
    imagen=llm.S, se_dice=llm.S, pegatina={"type": "string", "enum": list(PEGATINAS)})), despues=llm.S)

SISTEMA_HISTORIAS = """Eres Plani. Prepara las historias de Instagram de hoy para el negocio del Kit, de 3 a 7 marcos.
Las historias no buscan alcance: las ven quienes ya te siguen y deciden si eres alguien a quien comprarle.
- Marco 1: algo que pasa hoy, con la cara o las manos en imagen. Nunca texto sobre un fondo de color.
- Marcos 2-3: el contenido de verdad: el proceso, el resultado, el error. Una idea por marco.
- Marco 4: UNA pegatina. Encuesta (para que respondan muchos), caja de preguntas (para sacar sus palabras exactas),
  quiz (para enseñar dejando que fallen), enlace (si hay un sitio real al que ir), cuenta atrás (una fecha real).
- Marco 5: la respuesta, el resultado o lo que viene mañana.
Háblale a una persona («tú»). No repitas un post del feed sin decir nada. Si vendes, que sea aquí: tres marcos de
contexto, uno de oferta y uno de prueba. Sin cifras que no estén en el inventario de pruebas.
- imagen: qué se ve (selfie andando, pantalla, manos, foto…). se_dice: lo que se dice o se lee. pegatina: la del
  marco o «ninguna». despues: qué hacer con las respuestas (por ejemplo, contestar a cada uno que vote «sí»)."""


def _historias_validas(marcos: list[dict]) -> list[dict]:
    """De 3 a 7 marcos, una sola pegatina y, como tarde, en el cuarto."""
    marcos = [{"imagen": str(m.get("imagen") or "").strip()[:200], "se_dice": str(m.get("se_dice") or "").strip()[:300],
               "pegatina": m.get("pegatina") if m.get("pegatina") in PEGATINAS else "ninguna"}
              for m in marcos if str(m.get("se_dice") or "").strip()][:MAX_MARCOS]
    con = [i for i, m in enumerate(marcos) if m["pegatina"] != "ninguna"]
    for i in con[1:]:
        marcos[i]["pegatina"] = "ninguna"
    if con and con[0] >= MARCO_PREGUNTA and len(marcos) >= MARCO_PREGUNTA:
        marcos.insert(MARCO_PREGUNTA - 1, marcos.pop(con[0]))
    return marcos


def historias_del_dia(negocio: dict, kit: dict, vista: list[dict]) -> dict:
    """Las historias de hoy, atadas a lo que se graba hoy. Sin Claude, una plantilla de partida."""
    tema = vista[0]["titulo"] if vista else "lo que estás haciendo hoy"
    if llm.disponible():
        peticion = (kit_marca.contexto(negocio, kit) + "\n\n## Lo que se graba hoy\n"
                    + "\n".join(f"- {v['titulo']}: {v['angulo']}" for v in vista))
        try:
            d = llm.json_con_esquema(SISTEMA_HISTORIAS, peticion, ESQUEMA_HISTORIAS, effort="low")
            marcos = _historias_validas(d.get("marcos") or [])
            if len(marcos) >= 3:
                return {"marcos": marcos, "despues": str(d.get("despues") or "")[:300]}
        except ErrorIA:
            pass
    return {"marcos": [
        {"imagen": "Selfie, en movimiento", "se_dice": f"Hoy grabo sobre esto: {tema}.", "pegatina": "ninguna"},
        {"imagen": "Pantalla o manos", "se_dice": "Lo que más me preguntan de este tema, en una frase.", "pegatina": "ninguna"},
        {"imagen": "A cámara", "se_dice": "Mi postura, sin rodeos.", "pegatina": "ninguna"},
        {"imagen": "Fondo con la pregunta", "se_dice": "¿Qué te frena a ti con esto?", "pegatina": "preguntas"},
        {"imagen": "A cámara", "se_dice": "Mañana respondo las mejores.", "pegatina": "ninguna"}],
        "despues": "Contesta por mensaje a cada respuesta: sus palabras son ganchos y temas para los próximos vídeos.",
        "provisional": True}


# ---------------------------------------------------------------- reaprovechar una grabación larga

EXTRACTOS = {"afirmacion": "Afirmación que abre debate", "cifra": "Cifra", "historia": "Historia con un coste",
             "mecanismo": "Cómo funciona de verdad", "error": "Un error que admite", "frase": "Frase que se cita sola"}
CLASE_DE_EXTRACTO = {"afirmacion": "opinion", "cifra": "prueba", "historia": "historia", "mecanismo": "ensenar",
                     "error": "historia", "frase": "opinion"}
# Lo más fuerte primero, la historia a mitad de semana y el mecanismo al final.
ORDEN_EXTRACTO = {"afirmacion": 0, "error": 1, "cifra": 1, "historia": 2, "frase": 2, "mecanismo": 3}
MIN_EXTRACTOS = 4
MAX_REAPROVECHAR = 6

ESQUEMA_REAPROVECHAR = llm.obj(
    hallazgos=llm.obj(**{k: llm.N for k in EXTRACTOS}),
    piezas=llm.lista(llm.obj(extracto={"type": "string", "enum": list(EXTRACTOS)}, titulo=llm.S, fragmento=llm.S,
                             momento=llm.S, formula=llm.N)))

SISTEMA_REAPROVECHAR = """Eres Plani. Te paso una grabación larga del dueño del negocio (vídeo, pódcast, directo,
newsletter o llamada). Saca de ella las piezas que se sostienen SOLAS: quien las vea no ha visto el original y no lo
verá nunca. No resumas: extrae.
- hallazgos: cuántas hay de cada tipo en todo el texto: afirmacion (frases que abrirían una discusión), cifra,
  historia (una persona, una escena y un coste), mecanismo («así funciona de verdad…»), error (algo que salió mal)
  y frase (algo que ya se puede citar tal cual).
- piezas: las mejores, de 4 a 6, cada una de un extracto distinto. titulo: el ángulo de la pieza, no el tema.
  fragmento: la frase literal del original donde empieza (para cortarla de su vídeo). momento: el minuto si lo hay
  en el texto, o vacío. formula: el número de la fórmula de gancho que mejor le va, de la lista; varíalas.
Nunca escribas «como dije en mi último vídeo». Las cifras, solo si las dice él en el original."""


def reaprovechar(negocio: dict, texto: str, titulo: str = "", *, video_propio: bool = True,
                 nota: str = "") -> tuple[dict | None, str]:
    """Convierte una grabación larga en una semana de piezas: cada extracto, una pieza que se entiende sola. Si es un
    vídeo suyo, las piezas se cortan de él (no hace falta grabar). Devuelve (aprobación, aviso)."""
    nid, kit = negocio["id"], kit_marca.leer(negocio["id"])
    texto = (texto or "").strip()
    if len(texto.split()) < 150:
        return None, "El texto es muy corto para sacar una semana de piezas: pega la transcripción entera."
    if not llm.disponible():
        return None, "Para reaprovechar una grabación hace falta Claude: conéctalo en Conectores."
    formulas = "\n".join(f"- {f['id']}. {f['nombre']}: {f['plantilla']}" for f in ganchos.FORMULAS)
    peticion = (kit_marca.contexto(negocio, kit) + f"\n\n## Fórmulas de gancho\n{formulas}\n\n## La grabación"
                f"{': ' + titulo if titulo else ''}\n{texto[:60_000]}")
    if nota:
        peticion += f"\n\n## Lo que ha pedido el dueño al revisar el plan anterior\n{nota}"
    try:
        d = llm.json_con_esquema(SISTEMA_REAPROVECHAR, peticion, ESQUEMA_REAPROVECHAR, effort="medium")
    except ErrorIA as e:
        return None, f"No se ha podido leer la grabación: {e}"
    hallazgos = {k: int((d.get("hallazgos") or {}).get(k) or 0) for k in EXTRACTOS}
    sin_cifras = not kit["limites"].get("cifras_propias", True)
    elegidas = [p for p in d.get("piezas") or [] if p.get("extracto") in EXTRACTOS and str(p.get("titulo") or "").strip()
                and not (sin_cifras and p["extracto"] == "cifra")][:MAX_REAPROVECHAR]
    if not elegidas:
        return None, "No ha salido ninguna pieza que se sostenga sola de esta grabación."
    aviso = (f"La grabación da poco ({sum(hallazgos.values())} cosas que se sostienen solas): las piezas que salgan "
             "también serán flojas." if sum(hallazgos.values()) < MIN_EXTRACTOS else "")
    elegidas.sort(key=lambda p: ORDEN_EXTRACTO[p["extracto"]])
    formatos = kit.get("formatos") or {}
    activos = {c["id"]: c for c in semana(nid, kit) if c["cuota"] > 0} or {c["id"]: c for c in kit["carriles"]}
    usadas: list[int] = []
    ahora, ids, vista = _ahora(), [], []
    nombres = {c["id"]: c["nombre"] for c in kit["carriles"]}
    with db.conexion() as con:
        for i, p in enumerate(elegidas):
            clase = CLASE_DE_EXTRACTO[p["extracto"]]
            formato = ("carrusel" if p["extracto"] == "mecanismo" and formatos.get("carrusel") else
                       "historia" if p["extracto"] == "frase" and formatos.get("historias") else "reel")
            carril = max(activos.values(), key=lambda c: (clase in clases_posibles(c, kit), c.get("faltan", 0)))
            f_id = int(p.get("formula") or 0)
            if not _formula(f_id) or f_id in usadas or (sin_cifras and f_id in CON_CIFRA_PROPIA):
                f_id = next((i for i in FORMULAS_POR_CLASE[clase] if i not in usadas
                             and not (sin_cifras and i in CON_CIFRA_PROPIA)), FORMULAS_POR_CLASE["ensenar"][0])
            usadas.append(f_id)
            datos = {"semana": inicio_de_semana().date().isoformat(), "reels": 1 if formato == "reel" else 0,
                     "clase": clase, "formula": f_id, "reaprovechado": {
                         "origen": titulo[:160], "extracto": p["extracto"], "formato": formato,
                         "fragmento": str(p.get("fragmento") or "")[:400], "momento": str(p.get("momento") or "")[:20],
                         "sin_grabar": video_propio, "orden": i + 1}}
            cur = con.execute(
                "INSERT INTO piezas (negocio_id, creado, dia, tipo, carril, etapa, titulo, angulo, formato, esquema, "
                "grabar_antes, datos) VALUES (?, ?, ?, 'reaprovechado', ?, ?, ?, ?, ?, '[]', ?, ?)",
                (nid, ahora.isoformat(timespec="seconds"), _hoy(), carril["id"], carril["etapa"],
                 str(p["titulo"])[:160], EXTRACTOS[p["extracto"]], {"reel": "Corte de tu vídeo" if video_propio else
                                                                    "Hablando a cámara", "carrusel": "Carrusel",
                                                                    "historia": "Historia"}[formato],
                 "" if video_propio else hora_limite(kit, ahora, lote=True), json.dumps(datos, ensure_ascii=False)))
            ids.append(cur.lastrowid)
            f_gancho = _formula(f_id)
            vista.append({"titulo": str(p["titulo"])[:160], "angulo": EXTRACTOS[p["extracto"]], "tipo": TIPOS["reaprovechado"],
                          "carril": nombres.get(carril["id"], ""), "etapa": carril["etapa"], "referencia": titulo[:160],
                          "clase": CLASES[clase], "formula": f"n.º {f_gancho['id']} · {f_gancho['nombre']}",
                          "formato": formato, "fragmento": datos["reaprovechado"]["fragmento"]})
    a = ap.pedir(nid, AGENTE, "brief", f"Reaprovechar «{titulo or 'tu grabación'}»: {len(ids)} piezas",
                 {"piezas": ids, "lote": True, "n": len(ids), "vista": vista, "hallazgos": hallazgos,
                  "reaprovechar": {"titulo": titulo, "texto": texto[:60_000], "video_propio": video_propio},
                  "aviso": aviso})
    with db.conexion() as con:
        con.execute(f"UPDATE piezas SET aprobacion_id = ? WHERE id IN ({','.join('?' * len(ids))})", (a["id"], *ids))
    return a, aviso
