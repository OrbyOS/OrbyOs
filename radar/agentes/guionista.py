"""Escri: convierte cada pieza aprobada en lo que va a grabar el dueño, según el modo de grabación de su Kit.

- «estructura» (por defecto): la idea, de 3 a 6 bloques con los puntos que tocar y una pregunta para su ejemplo, y
  el cierre. El dueño habla libre 3-5 minutos y Monti saca de ahí los reels, con ganchos de lo que ha dicho.
- «guion»: el texto que se dice, con 3 ganchos de las fórmulas del catálogo puntuados en código, medido con las palabras por
  minuto del dueño y pasado por el humanizador.
- Remix: si la pieza rehace un post probado, conserva su estructura y cambia el tema, las pruebas y las palabras. Solo
  lee la plantilla del original, nunca su transcripción.
- Con tu voz: el Kit de marca, tus lecciones y tus mejores posts van en cada petición.
- Registro de afirmaciones: cada cifra o hecho se marca PASS, FIX o CUT con su fuente. Si el negocio no usa cifras
  propias (límite del Kit), no lleva ninguna.
- Textos de cada red activa y, si el Kit los activa, carrusel y post de texto.
- El validador en código decide: si falla, Escri lo corrige con la lista de fallos; si sigue fallando, se queda
  bloqueado y no llega a tus aprobaciones.
"""
import json
import re
from datetime import datetime

from .. import db, gasto, jobs, llm
from ..llm import ErrorIA
from . import analista, estado, estratega, ganchos, humanizador, ritmo, validador
from . import aprobaciones as ap
from . import kit as kit_marca

AGENTE = "guionista"
REVISIONES = 2
ESTADOS = {"bloqueado": "No pasa el validador", "pendiente": "Esperando tu aprobación", "aprobado": "Listo para grabar",
           "rechazado": "Descartado", "sustituido": "Versión anterior"}
PLATAFORMAS_TEXTO = {"instagram": "Instagram", "tiktok": "TikTok", "youtube": "YouTube", "linkedin": "LinkedIn"}


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------- guiones y palabras clave

def _guion_de_fila(f) -> dict:
    g = dict(f)
    for k, vacio in (("hashtags", "[]"), ("afirmaciones", "[]"), ("textos", "{}"), ("validacion", "{}"), ("ganchos", "[]")):
        g[k] = json.loads(g[k] or vacio)
    g["estado_nombre"] = ESTADOS.get(g["estado"], g["estado"])
    return g


def guion(negocio_id: int, guion_id: int) -> dict | None:
    with db.conexion() as con:
        f = con.execute("SELECT * FROM guiones WHERE negocio_id = ? AND id = ?", (negocio_id, guion_id)).fetchone()
    return _guion_de_fila(f) if f else None


def guiones(negocio_id: int, *, estados: tuple[str, ...] | None = None) -> list[dict]:
    sql, args = "SELECT * FROM guiones WHERE negocio_id = ?", [negocio_id]
    if estados:
        sql += f" AND estado IN ({','.join('?' * len(estados))})"
        args += list(estados)
    with db.conexion() as con:
        return [_guion_de_fila(f) for f in con.execute(sql + " ORDER BY id DESC", args)]


def guion_de_pieza(negocio_id: int, pieza_id: int) -> dict | None:
    with db.conexion() as con:
        f = con.execute("SELECT * FROM guiones WHERE negocio_id = ? AND pieza_id = ? AND estado != 'sustituido' "
                        "ORDER BY id DESC LIMIT 1", (negocio_id, pieza_id)).fetchone()
    return _guion_de_fila(f) if f else None


def palabras_usadas(negocio_id: int, salvo_guion: int | None = None) -> set[str]:
    with db.conexion() as con:
        filas = con.execute("SELECT palabra, guion_id FROM palabras_clave WHERE negocio_id = ?", (negocio_id,)).fetchall()
    return {f["palabra"] for f in filas if salvo_guion is None or f["guion_id"] != salvo_guion}


def registrar_palabra(negocio_id: int, palabra: str, guion_id: int):
    if palabra:
        with db.conexion() as con:
            con.execute("DELETE FROM palabras_clave WHERE negocio_id = ? AND guion_id = ?", (negocio_id, guion_id))
            con.execute("INSERT OR IGNORE INTO palabras_clave (negocio_id, palabra, guion_id, creado) VALUES (?, ?, ?, ?)",
                        (negocio_id, palabra.upper(), guion_id, _ahora()))


def liberar_palabra(negocio_id: int, guion_id: int):
    with db.conexion() as con:
        con.execute("DELETE FROM palabras_clave WHERE negocio_id = ? AND guion_id = ?", (negocio_id, guion_id))


# ---------------------------------------------------------------- lo que necesita Escri

def bancos_de_ganchos(negocio_id: int) -> dict[str, list[str]]:
    """Tus ganchos que hicieron ×3 o más, y los de la competencia que destacaron."""
    with db.conexion() as con:
        filas = con.execute(
            "SELECT p.gancho, p.texto, p.x, c.propia, p.plantilla FROM posts p JOIN cuentas c ON c.id = p.cuenta_id "
            "WHERE p.negocio_id = ? AND (p.x >= 3 OR p.destaca = 1) ORDER BY p.x DESC LIMIT 60", (negocio_id,)).fetchall()
    propios, ajenos = [], []
    for f in filas:
        gancho = f["gancho"] or json.loads(f["plantilla"] or "{}").get("gancho_literal") or ""
        if not gancho:
            continue
        (propios if f["propia"] else ajenos).append(f"{gancho} (×{f['x']:g})")
    return {"propios": propios[:12], "competencia": ajenos[:15]}


def tus_mejores(negocio_id: int, n: int = 5) -> list[str]:
    """Tus posts que más superaron tu normal y tus guiones aprobados: así suenas tú."""
    salida = []
    with db.conexion() as con:
        for f in con.execute("SELECT p.texto, p.gancho, p.transcripcion, p.x FROM posts p JOIN cuentas c ON "
                             "c.id = p.cuenta_id WHERE p.negocio_id = ? AND c.propia = 1 ORDER BY p.x DESC LIMIT ?",
                             (negocio_id, n)):
            texto = analista.texto_de(f["transcripcion"]) or f["texto"]
            if texto:
                salida.append(f"(×{f['x']:g}) {texto[:700]}")
        for f in con.execute("SELECT texto FROM guiones WHERE negocio_id = ? AND estado = 'aprobado' ORDER BY id DESC "
                             "LIMIT 3", (negocio_id,)):
            salida.append(f"(guion aprobado) {f['texto'][:700]}")
    return salida


def _remix_de(negocio_id: int, pieza: dict) -> dict | None:
    """Lo que el validador necesita del original de un remix (su transcripción no llega nunca a Claude)."""
    if not pieza.get("fuente_post_id"):
        return None
    p = analista.post(negocio_id, pieza["fuente_post_id"])
    if not p:
        return None
    plantilla = p["plantilla"] if p["estado_plantilla"] == "lista" else pieza["datos"].get("plantilla") or {}
    segundos = max([float(x.get("hasta") or 0) for x in plantilla.get("pasos") or []] or [p["segundos"] or 0])
    return {"plantilla": plantilla, "del_creador": plantilla.get("del_creador") or [], "cuenta": p["cuenta"],
            "transcripcion": analista.texto_de(p["transcripcion"]), "segundos": segundos or p["segundos"]}


# ---------------------------------------------------------------- los ajustes del Kit que cambian cómo escribe Escri

FORMATOS_EXTRA = {"carrusel": "Carrusel", "texto": "Post de texto"}


def ajustes(kit: dict) -> dict:
    """Lo que Escri lee del Kit del negocio. Si un campo aún no existe, usa un punto de partida neutro."""
    voz, limites = kit.get("voz") or {}, kit.get("limites") or {}
    vetadas = [str(x).strip() for x in kit.get("nunca_prometer") or [] if str(x).strip()]
    for clave, valor in limites.items():
        if clave == "cifras_propias":
            continue
        vetadas += [str(x).strip() for x in (valor if isinstance(valor, list) else str(valor or "").splitlines())
                    if str(x).strip()]
    formatos = kit.get("formatos") or []
    if isinstance(formatos, dict):
        formatos = [k for k, v in formatos.items() if v]
    try:
        ppm = float(voz.get("ppm") or 0) or ritmo.PPM_INICIAL
    except (TypeError, ValueError):
        ppm = ritmo.PPM_INICIAL
    publicacion = kit.get("publicacion") or {}
    return {"modo": kit.get("modo_grabacion") if kit.get("modo_grabacion") in validador.MODOS else validador.MODO_INICIAL,
            "ppm": ppm, "cifras_propias": limites.get("cifras_propias", True) is not False, "vetadas": vetadas,
            "redes": [r for r in PLATAFORMAS_TEXTO if (publicacion.get(r) or {}).get("activa")] or ["instagram"],
            "formatos": [f for f in formatos if f in FORMATOS_EXTRA]}


def cifras_permitidas(negocio: dict, kit: dict) -> list[str]:
    """Las cifras del inventario de pruebas con fuente, y los precios de tu propia oferta. Ninguna si el negocio no
    usa cifras propias."""
    if not ajustes(kit)["cifras_propias"]:
        return []
    f = negocio["ficha"]
    return kit_marca.cifras_permitidas(kit) + [str(f.get(k) or "") for k in ("precio_principal", "escalera", "garantia")
                                               if f.get(k)]


# ---------------------------------------------------------------- escribir

_AFIRMACIONES = llm.lista(llm.obj(texto=llm.S, veredicto={"type": "string", "enum": ["PASS", "FIX", "CUT"]}, fuente=llm.S))


def esquema(aj: dict) -> dict:
    """La forma de la respuesta: depende del modo de grabación, de las redes activas y de los formatos extra."""
    campos = dict(gancho_fuente=llm.S, cta={"type": "string", "enum": list(validador.CTAS)},
                  palabras_clave=llm.lista(llm.S), hashtags=llm.lista(llm.S), afirmaciones=_AFIRMACIONES,
                  textos=llm.obj(**{r: llm.S for r in aj["redes"]}))
    if aj["modo"] == "estructura":
        campos.update(idea=llm.S, bloques=llm.lista(llm.obj(tema=llm.S, puntos=llm.lista(llm.S), ejemplo=llm.S)),
                      cierre=llm.S)
    else:
        campos.update(texto=llm.S, ganchos=llm.lista(llm.obj(formula={"type": "integer"}, dicho=llm.S, en_pantalla=llm.S)))
    if "carrusel" in aj["formatos"]:
        campos["carrusel"] = llm.lista(llm.obj(titular=llm.S, texto=llm.S))
    if "texto" in aj["formatos"]:
        campos["post_texto"] = llm.S
    return llm.obj(**campos)


_REGLAS_COMUNES = """- Cumple la voz, las lecciones y lo que nunca dice el Kit de marca. No uses sus frases prohibidas, sus límites ni frases
  hechas de plantilla («en el mundo de hoy», «no es solo…, es…», «no se trata de…, se trata de…», «al siguiente nivel»,
  preguntas retóricas sueltas como «¿El resultado?»). Nada de rayas largas ni emojis de adorno.
- Concreción: cada idea que sostiene el vídeo, en lo más concreto que permitan las fuentes (un caso, un momento, un
  nombre, una cifra). Nunca inventes el detalle: si no está en el Kit, déjalo general.
{cifras}
- «afirmaciones»: cada dato o hecho, con PASS si tiene fuente, FIX si hay que matizarlo, CUT si hay que quitarlo (y
  entonces no lo pongas). Lo que diga una sola fuente de fuera se atribuye («según…»).
- Clientes: solo se nombran si la prueba tiene permiso; si no, se describen por su tipo.
- Si es un remix: copia la ESTRUCTURA del original y cambia el tema, los ejemplos y las pruebas por los del negocio.
  Nunca uses el nombre, las marcas, los productos, las muletillas, las historias ni las cifras del creador original.
- «cta»: la llamada a la acción del final. «comentar» pide comentar la palabra clave; «mensaje», escribirla por
  privado; «enlace», el enlace de la bio; «seguir», seguir la cuenta.
- «palabras_clave»: 3 candidatas de 4 a 9 letras, en mayúsculas, que no salgan en el resto del texto y que no estén en
  la lista de usadas.
- «gancho_fuente»: de dónde sale («remix de la plantilla», «banco propio: …», «banco de la competencia: …» o «nuevo»).
- «hashtags»: de 3 a 5, del nicho, en minúsculas. Nada de #viral, #fyp ni parecidos.
- «textos»: el texto del post en cada red activa ({redes}). Lo primero que se lee (unos 125 caracteres en Instagram,
  antes de «… más») lleva la petición o el gancho en palabras sencillas, nunca un saludo, un hashtag ni un emoji.
  Después, de dos a cuatro párrafos cortos con las palabras que la gente buscaría y una sola petición. Instagram pide
  comentar la palabra clave si la llamada es comentar; en TikTok y YouTube comentar no manda nada: «escríbeme
  PALABRA» o «enlace en la bio»; en LinkedIn, un texto algo más largo, con el gancho en la primera línea y sin pedir
  comentar la palabra. Sin enlaces dentro del texto de Instagram.{extras}"""

_CARRUSEL = """
- «carrusel»: la misma idea en diapositivas, de 6 a 10. La 1 es la portada (seis palabras como mucho en «titular» y una
  línea de promesa en «texto»); la 2 dice por qué importa; luego una idea por diapositiva (titular de 3 a 7 palabras y
  como mucho 25 palabras debajo); la penúltima resume todo en una lista; la última es la única petición."""
_POST_TEXTO = """
- «post_texto»: un post de texto que se sostiene solo (para X, Threads o LinkedIn): una idea, la primera línea es todo
  el punto y el resto lo gana. Sin pedir comentar la palabra clave."""

SISTEMA_GUION = """Eres Escri, quien escribe los guiones de una marca personal en español de España. Escribes guiones de vídeos
cortos (de 20 a 75 segundos) que el dueño dice a cámara con sus palabras, a unas {ppm:.0f} palabras por minuto.

Reglas:
- «texto» es SOLO lo que se dice, en frases cortas y un párrafo por golpe (una idea cada 2-4 segundos). Sin
  acotaciones, sin títulos de paso, sin viñetas, sin emojis. Mayúsculas solo para la palabra clave.
- Ganchos: antes de escribir, elige 3 fórmulas distintas de la lista que encajen de verdad con la idea y escribe un
  gancho con cada una en «ganchos» (su número en «formula», lo que se dice en «dicho», de 5 a 12 palabras, y lo que
  se lee en pantalla en «en_pantalla», seis palabras como mucho). Sin saludo ni introducción: empieza en la frase a la
  que normalmente llegarías en el segundo seis. El «texto» empieza con el mejor de los tres, tal cual.
- Si el Kit trae frases literales de sus clientes, parte de una de ellas: su cliente se reconoce en sus palabras.
- El gancho abre una intriga concreta que el cuerpo cierra antes de la llamada a la acción; no da la respuesta.
- Si es original, sigue este esqueleto: gancho, por qué importa (una frase), el cuerpo con una idea por golpe, lo que
  prometía el gancho y una sola petición. La última frase repite una palabra del gancho para que el vídeo vuelva a
  empezar con sentido.
- Suena hablado: frases de largo distinto (una de cuatro palabras junto a otra de dieciocho), las muletillas que el
  Kit dice que usa, nada que tenga que ensayar.
""" + _REGLAS_COMUNES + """

Las fórmulas de gancho del catálogo:
{formulas}"""

SISTEMA_ESTRUCTURA = """Eres Escri, quien prepara lo que va a grabar el dueño de una marca personal en español de España. No escribes
guiones: escribes ESTRUCTURAS. El dueño graba un vídeo de 3 a 5 minutos hablando a cámara, libre y con sus palabras,
siguiendo tu estructura. Después, quien edita saca de esa grabación 3 o 4 reels, con ganchos que salen de lo que él ha
dicho.

Reglas:
- «idea»: la idea del vídeo en una frase. Es lo que defiende, no un título ni un gancho.
- «bloques»: de 3 a 6 (lo normal, 4 o 5), uno por tema, en el orden en que tiene sentido contarlos. Cada bloque tiene
  que entenderse solo, porque puede acabar siendo un reel por sí mismo.
  - «tema»: de qué va el bloque, en pocas palabras.
  - «puntos»: de 2 a 5 ideas que tocar, cortas (como mucho 25 palabras), escritas como notas, no como frases para
    leer. Puede haber un conflicto (lo que la gente cree), una explicación y un giro (cómo lo ve él).
  - «ejemplo»: una pregunta para que lo cuente con algo que le ha pasado de verdad («¿Cuándo te diste cuenta de…?»).
    Nunca le inventes vivencias, clientes ni resultados.
- No escribas ganchos ni frases hechas para decir tal cual: eso sale de la grabación.
- «cierre»: una nota de qué pedir al final; lleva la palabra clave tal cual si la hay.
""" + _REGLAS_COMUNES


def sistema(aj: dict) -> str:
    cifras = ("- Cifras: SOLO del inventario de pruebas (cítalas en «afirmaciones» con su id entre corchetes como fuente) o "
              "de la oferta del negocio (fuente «oferta»). Nunca inventes una cifra. Si no hay prueba con cifra, no pongas "
              "números." if aj["cifras_propias"] else
              "- Este negocio NO usa cifras propias: ni facturación, ni número de clientes, ni resultados con números, ni "
              "precios. No pongas ningún número (tampoco escrito con letras); la autoridad sale del criterio y los ejemplos.")
    extras = (_CARRUSEL if "carrusel" in aj["formatos"] else "") + (_POST_TEXTO if "texto" in aj["formatos"] else "")
    comunes = {"cifras": cifras, "redes": ", ".join(PLATAFORMAS_TEXTO[r] for r in aj["redes"]), "extras": extras}
    if aj["modo"] == "estructura":
        return SISTEMA_ESTRUCTURA.format(**comunes)
    return SISTEMA_GUION.format(ppm=aj["ppm"], formulas=ganchos.formulas_en_texto(), **comunes)


def _peticion(negocio: dict, kit: dict, pieza: dict, remix: dict | None, nota: str) -> str:
    carriles = {c["id"]: c for c in kit["carriles"]}
    c = carriles.get(pieza["carril"], {})
    partes = [kit_marca.contexto(negocio, kit), "## La pieza",
              f"Título: {pieza['titulo']}\nÁngulo: {pieza['angulo']}\nCarril: {c.get('nombre', pieza['carril'])} — "
              f"{c.get('descripcion', '')}\nEtapa: {pieza['etapa'].upper()}\nFormato: {pieza['formato']}\n"
              "Esquema propuesto por Plani:\n" + "\n".join(f"- {x}" for x in pieza["esquema"])
              + (f"\nSe apoya en ({pieza['datos']['ancla']['tipo']}): {pieza['datos']['ancla']['texto']}\nLa estructura "
                 "tiene que contar ESTO, con sus detalles concretos." if (pieza["datos"].get("ancla") or {}).get("texto") else "")]
    if remix:
        t = remix["plantilla"]
        partes.append("## Plantilla del original (remix)\n" + json.dumps(
            {k: t.get(k) for k in ("tema", "gancho_literal", "pasos", "formato", "aspecto", "cierre", "por_que_funciona")},
            ensure_ascii=False, indent=1) + f"\nDuración del original: {remix['segundos']:.0f} s.\nEs del creador y NO se "
            "usa: " + ", ".join(remix["del_creador"]))
    bancos = bancos_de_ganchos(negocio["id"])
    if bancos["propios"]:
        partes.append("## Tus temas que mejor funcionaron (por su gancho)\n" + "\n".join(f"- {x}" for x in bancos["propios"]))
    if bancos["competencia"]:
        partes.append("## Temas de la competencia que destacaron (por su gancho; solo como idea)\n" +
                      "\n".join(f"- {x}" for x in bancos["competencia"]))
    publico = analista.publico_en_texto(negocio["id"])
    if publico:
        partes.append(publico + "\nÚsalo para que responda a lo que de verdad pregunta la gente.")
    mejores = tus_mejores(negocio["id"])
    if mejores:
        partes.append("## Así suena el dueño (sus mejores posts)\n" + "\n---\n".join(mejores))
    if kit.get("hashtags"):
        partes.append("## Hashtags del negocio (elige de aquí)\n" + " ".join(kit["hashtags"]))
    usadas = sorted(palabras_usadas(negocio["id"]))
    partes.append("## Palabras clave ya usadas\n" + (", ".join(usadas) or "Ninguna."))
    if nota:
        partes.append(f"## Lo que ha pedido el dueño\n{nota}")
    return "\n\n".join(partes)


def _una_linea(x) -> str:
    return " ".join(str(x or "").split())


def _limpiar(datos: dict, usadas: set[str], aj: dict) -> dict:
    if aj["modo"] == "estructura":
        bloques = [{"tema": _una_linea(b.get("tema")), "puntos": [_una_linea(x) for x in b.get("puntos") or [] if _una_linea(x)],
                    "ejemplo": _una_linea(b.get("ejemplo"))} for b in datos.get("bloques") or [] if _una_linea(b.get("tema"))]
        texto = validador.escribir_estructura(_una_linea(datos.get("idea")), bloques, _una_linea(datos.get("cierre")))
        opciones = []
    else:
        texto = "\n\n".join(p.strip() for p in str(datos.get("texto") or "").split("\n") if p.strip())
        opciones = [{**ganchos.puntuar(humanizador.limpiar(_una_linea(x.get("dicho")))[0], ppm=aj["ppm"]),
                     "formula_pedida": x.get("formula"), "en_pantalla": _una_linea(x.get("en_pantalla"))[:60]}
                    for x in datos.get("ganchos") or [] if _una_linea(x.get("dicho"))][:3]
        opciones = sorted(opciones, key=lambda r: -r["nota"])
    texto = humanizador.limpiar(texto)[0]
    hashtags = []
    for h in datos.get("hashtags") or []:
        h = "#" + re.sub(r"[^\wáéíóúñü]", "", str(h).lower().lstrip("#"))
        if len(h) > 2 and h not in hashtags:
            hashtags.append(h)
    candidatas = [str(p).strip().upper() for p in datos.get("palabras_clave") or []]
    palabra = next((p for p in candidatas if not validador.error_palabra_clave(p, usadas, texto)),
                   candidatas[0] if candidatas else "")
    textos = {k: humanizador.limpiar(str((datos.get("textos") or {}).get(k) or ""))[0][:2200] for k in aj["redes"]}
    if datos.get("carrusel"):
        textos["carrusel"] = [{"titular": humanizador.limpiar(_una_linea(d.get("titular")))[0][:80],
                               "texto": humanizador.limpiar(_una_linea(d.get("texto")))[0][:300]}
                              for d in datos["carrusel"] if _una_linea(d.get("titular"))][:20]
    if datos.get("post_texto"):
        textos["post_texto"] = humanizador.limpiar(str(datos["post_texto"]))[0][:3000]
    return {"texto": texto, "gancho_fuente": str(datos.get("gancho_fuente") or "")[:200], "cta": datos.get("cta") or "",
            "ganchos": [{k: o[k] for k in ("gancho", "nota", "veredicto", "formula", "peor", "en_pantalla")} for o in opciones],
            "palabra_clave": palabra if datos.get("cta") in ("comentar", "mensaje") else "",
            "hashtags": hashtags[:8], "afirmaciones": datos.get("afirmaciones") or [], "textos": textos}


def comprobar(negocio: dict, kit: dict, pieza: dict, g: dict, *, salvo_guion: int | None = None) -> dict:
    aj = ajustes(kit)
    v = validador.validar(g, prohibidas=kit["prohibidas"] + kit["voz"]["nunca"] + aj["vetadas"],
                          permitidas=cifras_permitidas(negocio, kit), usadas=palabras_usadas(negocio["id"], salvo_guion),
                          etapa=pieza["etapa"], remix=_remix_de(negocio["id"], pieza), modo=aj["modo"], ppm=aj["ppm"],
                          cifras_propias=aj["cifras_propias"], pruebas=kit.get("pruebas") or [])
    v["avisos"] += validador.revisar_textos(g.get("textos") or {}, cta=g.get("cta") or "", palabra=g.get("palabra_clave") or "",
                                            redes=aj["redes"])
    return v


def escribir(negocio: dict, pieza_id: int, *, nota: str = "") -> dict:
    """Escribe (o reescribe) la estructura de una pieza. Si pasa el validador, la manda a aprobar."""
    nid = negocio["id"]
    kit, pieza = kit_marca.leer(nid), estratega.pieza(nid, pieza_id)
    if not pieza:
        raise ValueError("Esa pieza no existe.")
    anterior = guion_de_pieza(nid, pieza_id)
    remix = _remix_de(nid, pieza)
    peticion = _peticion(negocio, kit, pieza, remix, nota or (anterior or {}).get("nota", ""))
    usadas = palabras_usadas(nid, anterior["id"] if anterior else None)
    aj = ajustes(kit)
    g, v = {}, {"fallos": ["No se ha podido escribir."], "avisos": []}
    for intento in range(REVISIONES + 1):
        if intento:
            peticion += ("\n\n## Tu versión anterior no pasa el validador\n" + json.dumps(g, ensure_ascii=False) +
                         "\nFallos que hay que corregir (devuélvelo entero, corregido):\n" +
                         "\n".join(f"- {f}" for f in v["fallos"]))
        try:
            g = _limpiar(llm.json_con_esquema(sistema(aj), peticion, esquema(aj), effort="medium"), usadas, aj)
        except ErrorIA as e:
            v = {"fallos": [str(e)], "avisos": []}
            break
        v = comprobar(negocio, kit, pieza, g, salvo_guion=anterior["id"] if anterior else None)
        if not v["fallos"]:
            break
    return guardar(negocio, pieza, g, v, anterior=anterior, autor="guionista")


def guardar(negocio: dict, pieza: dict, g: dict, v: dict, *, anterior: dict | None, autor: str) -> dict:
    nid = negocio["id"]
    bloqueado = bool(v["fallos"]) and autor == "guionista"
    with db.conexion() as con:
        if anterior:
            con.execute("UPDATE guiones SET estado = 'sustituido' WHERE id = ?", (anterior["id"],))
        cur = con.execute(
            "INSERT INTO guiones (negocio_id, pieza_id, creado, version, estado, autor, texto, gancho_fuente, cta, "
            "palabra_clave, hashtags, afirmaciones, textos, validacion, ganchos) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "?, ?)",
            (nid, pieza["id"], _ahora(), (anterior or {}).get("version", 0) + 1,
             "bloqueado" if bloqueado else ("aprobado" if autor == "tú" else "pendiente"), autor, g.get("texto", ""),
             g.get("gancho_fuente", ""), g.get("cta", ""), g.get("palabra_clave", ""),
             json.dumps(g.get("hashtags") or [], ensure_ascii=False), json.dumps(g.get("afirmaciones") or [], ensure_ascii=False),
             json.dumps(g.get("textos") or {}, ensure_ascii=False), json.dumps(v, ensure_ascii=False),
             json.dumps(g.get("ganchos") or [], ensure_ascii=False)))
        guion_id = cur.lastrowid
    if anterior:
        liberar_palabra(nid, anterior["id"])
    if bloqueado:
        return guion(nid, guion_id)
    registrar_palabra(nid, g.get("palabra_clave", ""), guion_id)
    estratega.cambiar_estado(nid, [pieza["id"]], "guion")
    if autor == "guionista":
        # Lo que vende o afirma una cifra es «importante»: espera aunque Escri revise solo lo importante.
        clave = pieza["etapa"] == "bofu" or any((a.get("veredicto") or "").upper() == "PASS" for a in g.get("afirmaciones") or [])
        que = "Estructura" if (v.get("modo") or "") == "estructura" else "Guion"
        a = ap.pedir(nid, AGENTE, "guion", f"{que}: {pieza['titulo']}",
                     {"guion_id": guion_id, "texto": g.get("texto", ""), "palabra_clave": g.get("palabra_clave", ""),
                      "avisos": v["avisos"], "referencia": pieza["datos"].get("referencia", "")}, clave=clave)
        with db.conexion() as con:
            con.execute("UPDATE guiones SET aprobacion_id = ? WHERE id = ?", (a["id"], guion_id))
    return guion(nid, guion_id)


def editar(negocio: dict, guion_id: int, texto: str, palabra_clave: str = "") -> dict:
    """Tu propia versión: se guarda aprobada (el validador avisa, no bloquea) y, si cambia mucho, Escri
    propone la regla que ha aprendido."""
    nid = negocio["id"]
    g = guion(nid, guion_id)
    pieza = estratega.pieza(nid, g["pieza_id"])
    kit = kit_marca.leer(nid)
    nuevo = {**g, "texto": texto.strip(), "palabra_clave": (palabra_clave or g["palabra_clave"]).strip().upper()}
    v = comprobar(negocio, kit, pieza, nuevo, salvo_guion=guion_id)
    v = {**v, "fallos": [], "avisos": v["fallos"] + v["avisos"]}
    if g.get("aprobacion_id"):
        ap.decidir(g["aprobacion_id"], "aprobar", por="tú", nota="Editado a mano")
    resultado = guardar(negocio, pieza, nuevo, v, anterior=guion(nid, guion_id), autor="tú")
    if g["autor"] == "guionista" and llm.disponible() and _cambio_grande(g["texto"], texto):
        jobs.en_segundo_plano(aprender_de_la_edicion, nid, g["texto"], texto)
    return resultado


def _cambio_grande(antes: str, despues: str) -> bool:
    a, b = set(validador.normal(antes).split()), set(validador.normal(despues).split())
    return bool(a) and len(a ^ b) / len(a | b) > 0.15


ESQUEMA_LECCION = llm.obj(hay_regla=llm.B, regla=llm.S, por_que=llm.S)


def aprender_de_la_edicion(negocio_id: int, antes: str, despues: str):
    """El dueño ha corregido un guion: si la corrección es una regla general, se propone como lección."""
    try:
        r = llm.json_con_esquema(
            "Comparas un guion o la estructura de un vídeo escritos por la IA con la versión que ha corregido su dueño. Si "
            "la corrección refleja una regla general que debería cumplir cualquier texto futuro (temas, enfoque, tono, "
            "palabras, longitud…), escríbela en una frase imperativa y corta. Si solo son cambios de este texto, "
            "hay_regla = false.",
            f"<antes>\n{antes}\n</antes>\n<despues>\n{despues}\n</despues>", ESQUEMA_LECCION, effort="low")
    except ErrorIA:
        return
    if r.get("hay_regla") and r.get("regla"):
        ap.proponer_leccion(negocio_id, AGENTE, r["regla"], r.get("por_que") or "Lo has corregido en un guion")


# ---------------------------------------------------------------- aprobaciones

@ap.al_aprobar("guion")
def _guion_aprobado(a: dict):
    with db.conexion() as con:
        con.execute("UPDATE guiones SET estado = 'aprobado' WHERE id = ? AND estado = 'pendiente'",
                    (a["datos"].get("guion_id"),))


@ap.al_rechazar("guion")
def _guion_rechazado(a: dict):
    nid, guion_id = a["negocio_id"], a["datos"].get("guion_id")
    g = guion(nid, guion_id)
    if not g:
        return
    if a["estado"] == "cambios":
        with db.conexion() as con:
            con.execute("UPDATE guiones SET nota = ? WHERE id = ?", (a["nota"], guion_id))
        negocio = db.negocio(nid)
        if negocio:
            jobs.en_segundo_plano(trabajo_escribir, negocio, [g["pieza_id"]], a["nota"], None)
    else:
        with db.conexion() as con:
            con.execute("UPDATE guiones SET estado = 'rechazado' WHERE id = ?", (guion_id,))
        liberar_palabra(nid, guion_id)
        estratega.cambiar_estado(nid, [g["pieza_id"]], "aprobada")


@ap.al_aprobar("brief")
def _escribir_al_aprobar_el_plan(a: dict):
    """En cuanto apruebas el «Graba hoy», Escri se pone con los guiones."""
    negocio = db.negocio(a["negocio_id"])
    ids = a["datos"].get("piezas") or []
    if negocio and ids and llm.disponible():
        jobs.en_segundo_plano(trabajo_escribir, negocio, ids, "", None)


def trabajo_escribir(negocio: dict, pieza_ids: list[int], nota: str, usuario_id: int | None):
    gasto.empezar()
    gasto_id = db.abrir_gasto(usuario_id=usuario_id, negocio_id=negocio["id"], concepto="guionista")
    estado.cambiar(negocio["id"], AGENTE, trabajando=True, avisos=[])
    avisos = []
    try:
        for pid in pieza_ids:
            p = estratega.pieza(negocio["id"], pid)
            if not p or p["estado"] not in ("aprobada", "guion"):
                continue
            g = escribir(negocio, pid, nota=nota)
            if g["estado"] == "bloqueado":
                avisos.append(f"«{p['titulo']}» no pasa el validador: " + " ".join(g["validacion"]["fallos"][:2]))
    finally:
        estado.cambiar(negocio["id"], AGENTE, trabajando=False, ultimo=_ahora(), avisos=avisos)
        db.cerrar_gasto(gasto_id, gasto.uso())


def marcar_grabado(negocio_id: int, guion_id: int):
    g = guion(negocio_id, guion_id)
    if g and g["estado"] == "aprobado":
        estratega.cambiar_estado(negocio_id, [g["pieza_id"]], "grabada")


def pedir_sobre(negocio: dict, tema: str) -> int:
    """«Pídeselo a la IA»: primero busca un post probado sobre ese tema para rehacerlo; si no hay, una pieza original
    en el carril que más falta. Devuelve el id de la pieza (aprobada: la has pedido tú)."""
    nid, kit = negocio["id"], kit_marca.leer(negocio["id"])
    tema_p = estratega.palabras(tema)
    fuente = next((p for p in estratega.candidatos(negocio, kit) if estratega._parecido(
        tema_p, estratega.palabras(" ".join([p["texto"], p["plantilla"].get("tema", ""), p["gancho"]]))) >= 0.34
        and p["estado_plantilla"] == "lista"), None)
    hueco = (estratega.huecos(nid, 1, kit) or kit["carriles"] or [{"id": "", "etapa": "tofu", "nombre": ""}])[0]
    datos = {"referencia": estratega.referencia(fuente), "url": fuente["url"], "plantilla": fuente["plantilla"]} if fuente else {}
    with db.conexion() as con:
        cur = con.execute(
            "INSERT INTO piezas (negocio_id, creado, dia, estado, tipo, carril, etapa, fuente_post_id, titulo, angulo, "
            "formato, esquema, grabar_antes, datos) VALUES (?, ?, ?, 'aprobada', ?, ?, ?, ?, ?, '', ?, '[]', '', ?)",
            (nid, _ahora(), _ahora()[:10], ("propio" if fuente["propia"] else "remix") if fuente else "original",
             hueco["id"], hueco["etapa"], fuente["id"] if fuente else None, tema.strip()[:160],
             (fuente or {}).get("plantilla", {}).get("formato") or "Hablando a cámara", json.dumps(datos, ensure_ascii=False)))
        return cur.lastrowid


def escribir_a_mano(negocio: dict, titulo: str, texto: str, *, cta: str = "ninguna", palabra_clave: str = "",
                    hashtags: str = "") -> dict:
    """«Lo escribo yo»: una pieza original con tu guion, aprobado desde el principio."""
    pieza_id = pedir_sobre(negocio, titulo)
    with db.conexion() as con:  # lo has escrito tú: no es un remix aunque haya un post parecido
        con.execute("UPDATE piezas SET tipo = 'original', fuente_post_id = NULL, datos = '{}' WHERE id = ?", (pieza_id,))
    pieza = estratega.pieza(negocio["id"], pieza_id)
    etiquetas = ["#" + re.sub(r"[^\wáéíóúñü]", "", h.lower().lstrip("#")) for h in re.split(r"[\s,]+", hashtags) if h.strip("# ")]
    g = {"texto": texto.strip(), "gancho_fuente": "tuyo", "cta": cta if cta in validador.CTAS else "ninguna",
         "palabra_clave": palabra_clave.strip().upper(), "hashtags": etiquetas, "afirmaciones": [], "textos": {}}
    v = comprobar(negocio, kit_marca.leer(negocio["id"]), pieza, g)
    return guardar(negocio, pieza, g, {**v, "fallos": [], "avisos": v["fallos"] + v["avisos"]}, anterior=None, autor="tú")
