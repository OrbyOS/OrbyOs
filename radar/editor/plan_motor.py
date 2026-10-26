"""Paso 3 con el estilo «De editor»: Claude decide los planos del reel siguiendo el MANUAL_EDITOR.md del motor.

Claude señala palabras (por su número), no segundos. motor_reels convierte eso a segundos con los tiempos reales,
corta los silencios, valida las reglas del manual y, si algo no cumple, se lo devuelve a Claude una vez; lo que
siga sin cumplir se arregla solo (`sanear`). El resultado es un montaje que cumple `esquema_montaje.json`.
"""
import json

from motor_reels.motor import desde_palabras, validar

from .. import config, llm
from ..llm import B, N, S, lista, obj
from . import frases as fr

MANUAL = (config.MOTOR_REELS_DIR / "MANUAL_EDITOR.md").read_text(encoding="utf-8")


def _esquema() -> dict:
    grafico = obj(
        tipo={"type": "string", "enum": ["ninguno", "efecto", "titular", "icono", "chat", "ficha", "fondo", "imagen"]},
        icono={"type": "string", "enum": sorted(validar.ICONOS)}, lado={"type": "string", "enum": ["izquierda", "derecha"]},
        clase={"type": "string", "enum": ["lista", "cifra", "comparacion", "proceso", "grafica"]},
        lugar={"type": "string", "enum": ["encima", "partida", "completa"]},
        titulo=S, sufijo=S, elementos=lista(obj(texto=S, valor=S, en=N)),
        palabra=S, kicker=N, en=N, envio=N, etiqueta=S, texto=S, titular=S,
        wikipedia=S, web=S, propia=S, pie=S, forma={"type": "string", "enum": ["tarjeta", "pantalla"]},
        filas=lista(obj(etiqueta=S, valor=S, cifra=B, sufijo=S, en=N)),
    )
    plano = obj(desde=N, hasta=N, gancho=B, modo={"type": "string", "enum": ["real", "recorte"]}, zoom=N,
                fondo={"type": "string", "enum": ["luz", "rejilla"]}, fondo_foto=S,
                entrada={"type": "string", "enum": ["corte", "latigo", "tiras"]}, sacudida=N, golpe=N, grafico=grafico,
                motivo=S)
    return obj(planos=lista(plano), avisos=lista(S))


REGLAS = f"""\
Eres el editor de un reel vertical y trabajas con el manual de abajo, que manda sobre tu gusto. Te pasamos lo que
dice la persona, palabra a palabra y numerado, ya sin las tomas falsas que se han quitado. El bruto puede durar
varios minutos: tú decides qué se queda, el gancho y los planos.

Cómo responder:
- «planos», en orden: cada uno va de la palabra «desde» a la palabra «hasta» (ambas incluidas). No se reordena nada.
- **Qué se queda**: la mejor versión de cada parte. Lo que se repite, se va por las ramas o no suma se corta dejando
  fuera frases ENTERAS (no pongas ningún plano sobre ellas). Nunca cortes una frase por la mitad. La duración es la
  que pida la idea bien contada: reels de valor, no tienen por qué ser cortos.
- **El gancho**: el primer plano. Normalmente es lo primero que se dice; si hay una frase mejor para abrir (más
  concreta, más sorprendente, con una cifra), pon ese tramo como PRIMER plano con «gancho»: true. Esa frase no se
  repite después: deja fuera de los demás planos sus palabras.
- Un plano nuevo en cada cambio de encuadre: cada 1,5-3 s, sobre la palabra fuerte o en una pausa (‖ en el texto).
  Los silencios dentro de un plano se cortan solos con un punch-in; no hace falta que los marques.
- «modo»: «real» (el vídeo tal cual) o «recorte» (la persona sobre un fondo animado). En recortes, «fondo»: «luz» o
  «rejilla», o «fondo_foto» con el nombre de una foto propia del cliente. «zoom»: 1 abierto, 1.2-1.35 cerrado, 1.5
  muy cerrado. Alterna real/recorte y abierto/cerrado.
- «entrada»: «corte» casi siempre; «latigo» o «tiras» solo al cambiar de bloque de ideas.
- «sacudida»: número de palabra donde la cámara da un golpe, o -1.
- «golpe»: número de la palabra más fuerte de la frase para un golpe de zoom (acercamiento rápido), o -1. Es lo que
  quita la monotonía sin sobreeditar: unos 4-6 por minuto, en las palabras que de verdad pesan.
- «grafico.tipo»: el apoyo de ese plano. Los campos que no se usan, vacíos o 0.
  · «efecto» (el apoyo principal, tipo After Effects) cuando hay pasos, números, un antes y un después, un proceso o
    una tendencia. «clase»: «lista» (pasos o puntos), «cifra» (un número grande; en «sufijo» la unidad), «comparacion»
    (2 elementos: antes y después), «proceso» (2-4 pasos encadenados), «grafica» (2-4 barras con su «valor»).
    «titulo»: antetítulo corto. «elementos» (1-5): «texto» (≤ 3 palabras), «valor» si lleva número, y «en» = número
    de la palabra en que aparece cada uno (cuando se dice). «lugar»: «encima» (la cara entera y el efecto a la altura
    del pecho; lo normal), «partida» (arriba el efecto y abajo la persona; cuando necesita más explicación gráfica) o
    «completa» (el efecto ocupa toda la pantalla; para el momento más gráfico, como mucho uno por minuto). Alterna los
    tres lugares a lo largo del reel.
  · «icono»: un icono de línea junto a la cabeza para una idea concreta (un plazo, una herramienta, un resultado).
    «icono» (de la lista), «texto» opcional (≤ 2 palabras), «en» = número de palabra y «lado».
  · «titular»: «palabra» (como mucho 12 letras: la idea, no la frase) y «kicker» = cuántas de las primeras palabras
    del plano van de antetítulo (0-7). En un «recorte», el titular sale desde el primer fotograma. El primer plano del
    reel es un recorte con titular: es la portada.
  · «chat»: un mensaje que la persona describe. «etiqueta» (a quién va), «texto» (≤ 40 letras), «en» y «envio» =
    números de palabra en que aparece y en que se envía.
  · «ficha»: datos de la persona o de un caso (nombre, cifra, plazo). «filas» (1-3): etiqueta corta, valor, «cifra»
    si el valor es un número que cuenta desde 0, «sufijo» opcional, y «en» = número de palabra.
  · «fondo»: el fondo desaparece en la palabra «en» y aparece «titular» (opcional) detrás de la persona.
  · «imagen», SOLO en momentos puntuales: cuando enseñar la cosa nombrada convence más que un efecto. «en» = número de
    la palabra que la nombra. De dónde sale, por este orden: «propia» (el nombre exacto de una foto o captura del
    cliente, de la lista que te pasamos), «wikipedia» (el título EXACTO del artículo en inglés, nunca un nombre
    ambiguo) y/o «web» (el dominio). «pie»: lo que se ve (≤ 32 letras). «forma»: «tarjeta» o «pantalla» (capturas
    que hay que leer). Nunca para ideas abstractas.
- Emoticonos: los que diga la voz del cliente (te lo pasamos); sin dato, ninguno.
- Cada rótulo, seis palabras como mucho. El primer plano abre con un titular: es la portada.
- «motivo»: por qué ese plano es así, en una frase corta. «avisos»: lo que el usuario debería saber.

MANUAL_EDITOR.md
================
{MANUAL}
"""

CAMBIO = """
Ahora el usuario pide un cambio con sus palabras. Aplícalo sobre los planos actuales y deja lo demás igual, salvo que
el cambio choque con el manual: entonces haz lo más parecido que lo cumpla y explícalo en «resumen». En «resumen», lo
que has cambiado en una frase, en segunda persona del usuario.
"""


def _con_gancho(frases: list[dict], gancho: str | None) -> list[dict]:
    """Si este reel sale de un bruto con varios (manual, 0 bis) y su gancho está fuera de su tramo, esa frase vuelve
    solo para abrir este reel."""
    if not gancho:
        return frases
    return [{**f, "quitada": False, "fuera": False} if f["id"] == gancho else f for f in frases]


def _forzar_gancho(por_palabras: dict, quedan: list[dict], gancho: str | None) -> dict:
    """El gancho elegido para el reel va como primer plano con «gancho»: true (salvo que ya sea lo primero)."""
    indices = [i for i, w in enumerate(quedan) if w.get("frase") == gancho]
    if not indices or indices[0] == 0:
        return por_palabras
    planos = [p for p in por_palabras.get("planos", []) if not p.get("gancho")]
    previo = next((p for p in por_palabras.get("planos", []) if p.get("gancho")), {})
    primero = {"modo": "recorte", "zoom": 1.0, "fondo": "luz", "motivo": "Gancho elegido para este reel",
               **{k: v for k, v in previo.items() if k in ("modo", "zoom", "fondo", "fondo_foto", "grafico", "motivo")},
               "desde": indices[0], "hasta": indices[-1], "gancho": True}
    return {**por_palabras, "planos": [primero, *planos]}


def material(frases: list[dict], palabras: list[dict]) -> tuple[list[dict], list[dict]]:
    """(las que se quedan, todas) en el orden del bruto. Cada palabra que se queda lleva `orden`, su posición entre
    todas: sirve para no cortar encima de una palabra quitada."""
    todas, quedan = [], []
    for f in frases:
        for w in fr.palabras_de(f, palabras):
            todas.append(w)
            if not f.get("quitada"):
                quedan.append({**w, "orden": len(todas) - 1, "frase": f["id"]})
    return quedan, todas


def texto_numerado(quedan: list[dict]) -> str:
    lineas, actual, frase = [], [], None
    for i, w in enumerate(quedan):
        if w["frase"] != frase and actual:
            lineas.append(" ".join(actual))
            actual = []
        if not actual:
            actual.append(f"({w['start']:.1f} s)")
        elif w["start"] - quedan[i - 1]["end"] > desde_palabras.SILENCIO:
            actual.append("‖")
        actual.append(f"[{i}] {w['word']}")
        frase = w["frase"]
    if actual:
        lineas.append(" ".join(actual))
    return "\n".join(lineas)


def _limpiar(datos: dict) -> dict:
    """Números a enteros, «ninguno» y -1 fuera: lo que entiende desde_palabras."""
    planos = []
    for p in datos.get("planos") or []:
        q = {"desde": int(p.get("desde") or 0), "hasta": int(p.get("hasta") or 0), "modo": p.get("modo", "real"),
             "zoom": min(1.6, max(1.0, float(p.get("zoom") or 1.0))), "entrada": p.get("entrada", "corte"),
             "motivo": p.get("motivo", "")}
        if (p.get("sacudida") or -1) >= 0:
            q["sacudida"] = int(p["sacudida"])
        if (p.get("golpe") or -1) >= 0:
            q["golpe"] = int(p["golpe"])
        if p.get("gancho"):
            q["gancho"] = True
        if p.get("modo") == "recorte":
            if p.get("fondo_foto"):
                q["fondo_foto"] = p["fondo_foto"]
            elif p.get("fondo") in ("luz", "rejilla"):
                q["fondo"] = p["fondo"]
        g = p.get("grafico") or {}
        if g.get("tipo") and g["tipo"] != "ninguno":
            g = {k: v for k, v in g.items() if v not in ("", None, [])}
            for clave in ("en", "envio", "kicker"):
                if clave in g:
                    g[clave] = int(g[clave])
            for f in g.get("filas", []) + g.get("elementos", []):
                f["en"] = int(f.get("en") or 0)
            q["grafico"] = g
        planos.append(q)
    return {"planos": planos, "avisos": [a for a in datos.get("avisos") or [] if a]}


def _a_montaje(por_palabras: dict, quedan: list[dict], todas: list[dict], *, bruto: str, kit: str,
               emojis: str = "nunca") -> dict:
    """`emojis`: los de la voz del cliente (kit «voz.emojis»: nunca, pocos o libre); viaja en el montaje para validar."""
    m = desde_palabras.convertir(por_palabras, quedan, todas, bruto=bruto, kit=kit)
    m["reglas"] = {"emojis": emojis if emojis in ("nunca", "pocos", "libre") else "nunca"}
    return m


def _errores_para_claude(errores: list[str]) -> str:
    return "El montaje no cumple estas reglas; corrígelo:\n" + "\n".join(f"- {e}" for e in errores)


def proponer(frases: list[dict], palabras: list[dict], *, preferencias: list[str], bruto: str, kit: str,
             instruccion: str = "", actual: dict | None = None, propias: list[str] | None = None,
             gancho: str | None = None, nunca: list[str] | None = None, emojis: str = "nunca") -> dict:
    """Devuelve {"por_palabras", "segundos", "avisos", "resumen"}. Con `instruccion`, cambia el plan `actual`.
    `nunca`: lo que el cliente no quiere ver en su edición (su identidad visual)."""
    frases = _con_gancho(frases, gancho)
    quedan, todas = material(frases, palabras)
    if not quedan:
        raise llm.ErrorIA("No queda ninguna frase.")
    esquema = _esquema()
    system = REGLAS
    peticion = (f"Preferencias del usuario: {json.dumps(preferencias, ensure_ascii=False)}\n"
                f"Lo que este cliente no quiere nunca en su edición (dato del cliente; manda sobre tu gusto, nunca "
                f"sobre el manual): {json.dumps(nunca or [], ensure_ascii=False)}\n"
                f"Emoticonos según su voz: {emojis} (pocos = {validar.POCOS_EMOJIS} por reel como mucho).\n"
                f"Fotos y capturas propias del cliente: {json.dumps(propias or [], ensure_ascii=False)}\n"
                + (f"El gancho de este reel es la frase que empieza en la palabra "
                   f"[{next((i for i, w in enumerate(quedan) if w.get('frase') == gancho), 0)}]: va como primer plano "
                   f"con «gancho»: true.\n" if gancho else "")
                + f"Dura {quedan[-1]['end'] - quedan[0]['start']:.0f} s y tiene {len(quedan)} palabras.\n\n"
                f"Lo que dice, frase a frase (entre paréntesis, el segundo del bruto):\n{texto_numerado(quedan)[:60000]}")
    if instruccion:
        esquema = obj(planos=esquema["properties"]["planos"], avisos=esquema["properties"]["avisos"], resumen=S)
        system = REGLAS + CAMBIO
        peticion = (f"Lo que pide el usuario: «{instruccion}»\n\nPlanos actuales:\n"
                    f"{json.dumps((actual or {}).get('planos', []), ensure_ascii=False)}\n\n{peticion}")
    datos = llm.json_con_esquema(system, peticion, esquema, effort="low" if instruccion else "medium")
    resumen = datos.get("resumen") or ""
    por_palabras = _forzar_gancho(_limpiar(datos), quedan, gancho)
    montaje = _a_montaje(por_palabras, quedan, todas, bruto=bruto, kit=kit, emojis=emojis)
    errores, _ = validar.validar(montaje)
    if errores:
        segunda = llm.json_con_esquema(
            system, f"{peticion}\n\nTu propuesta anterior:\n{json.dumps(por_palabras, ensure_ascii=False)}\n\n"
                    f"{_errores_para_claude(errores)}", esquema, effort="low")
        por_palabras = _forzar_gancho(_limpiar(segunda), quedan, gancho)
        resumen = segunda.get("resumen") or resumen
        montaje = _a_montaje(por_palabras, quedan, todas, bruto=bruto, kit=kit, emojis=emojis)
    montaje, arreglos = desde_palabras.sanear(montaje)
    _, avisos = validar.validar(montaje)
    return {"por_palabras": por_palabras, "segundos": montaje, "avisos": por_palabras["avisos"] + avisos + arreglos,
            "resumen": resumen}


def basico(frases: list[dict], palabras: list[dict], *, bruto: str, kit: str, gancho: str | None = None,
           emojis: str = "nunca") -> dict:
    """Sin IA: recorte con titular de portada y, después, planos que alternan abierto y cerrado cada ~2,5 s."""
    quedan, todas = material(_con_gancho(frases, gancho), palabras)
    planos, desde = [], 0
    while desde < len(quedan):
        hasta = desde
        while hasta + 1 < len(quedan) and quedan[hasta + 1]["end"] - quedan[desde]["start"] < 2.5:
            hasta += 1
        n = len(planos)
        planos.append({"desde": desde, "hasta": hasta, "modo": "recorte" if n == 0 else "real",
                       "zoom": 1.0 if n % 2 else 1.25, "entrada": "corte"})
        desde = hasta + 1
    por_palabras = _forzar_gancho({"planos": planos, "avisos": ["Plan automático sin IA: revísalo."]}, quedan, gancho)
    planos = por_palabras["planos"]
    if planos:
        primero = planos[0]
        clave = max((w["word"].strip(" ,.;:¿?¡!") for w in quedan[primero["desde"]:primero["hasta"] + 1]), key=len)[:12]
        primero.update(modo="recorte", grafico={"tipo": "titular", "palabra": clave.capitalize(), "kicker": 0})
    montaje, arreglos = desde_palabras.sanear(_a_montaje(por_palabras, quedan, todas, bruto=bruto, kit=kit, emojis=emojis))
    return {"por_palabras": por_palabras, "segundos": montaje, "avisos": por_palabras["avisos"] + arreglos,
            "resumen": ""}


ENCUADRES = [(1.15, "abierto"), (1.4, "cerrado"), (9, "muy cerrado")]


def para_ver(datos: dict, palabras: list[dict]) -> list[dict]:
    """Los planos de un reel «De editor» contados para el cliente («Así queda cada plano»): qué dice, cómo se ve y qué
    lleva. Lo pinta la interfaz; si el reel no se montó con el motor, la lista está vacía."""
    montaje = datos.get("montaje") or {}
    planos = (montaje.get("segundos") or {}).get("planos") or []
    pedidos = (montaje.get("por_palabras") or {}).get("planos") or []
    quedan, _ = material(datos.get("frases") or [], palabras)
    salida = []
    for p in planos:
        a, b = p["src"]
        g = p.get("grafico") or {}
        grafico = {"titular": lambda: f"Titular «{g['palabra']}»", "chat": lambda: f"Mensaje «{g['texto']}»",
                   "ficha": lambda: "Ficha: " + ", ".join(f"{x['etiqueta']} {x['valor']}" for x in g["filas"]),
                   "fondo": lambda: "Se va el fondo" + (f" y aparece «{g['titular']}»" if g.get("titular") else ""),
                   "imagen": lambda: f"Imagen real: {g.get('pie') or g.get('wikipedia') or g.get('web') or ''}",
                   "efecto": lambda: "Efecto: " + {"lista": "lista", "cifra": "cifra", "comparacion": "antes y después",
                                                   "proceso": "proceso", "grafica": "gráfica"}.get(g.get("clase"), "")
                                     + {"partida": " (pantalla partida)", "completa": " (pantalla completa)"}.get(
                                         g.get("lugar"), ""),
                   }.get(g.get("tipo"), lambda: "")()
        base = p["id"][1:].split("-")[0]
        num = int(base) - 1 if base.isdigit() else -1
        salida.append({
            "inicio": round(a, 2),
            "dice": " ".join(w["word"] for w in quedan if a <= (w["start"] + w["end"]) / 2 < b),
            "como": "Recortado sobre tu color" if p["modo"] == "recorte" else "Tu vídeo",
            "encuadre": next(n for z, n in ENCUADRES if p.get("zoom", 1) < z),
            "entrada": {"latigo": "Entra con látigo", "tiras": "Entra en tiras"}.get(p.get("entrada"), ""),
            "sacudida": "sacudida" in p,
            "corte_silencio": "-" in p["id"],
            "gancho": bool(p.get("gancho")),  # gancho traído de más adelante en el bruto
            "grafico": grafico,
            "motivo": pedidos[num].get("motivo", "") if 0 <= num < len(pedidos) and "-" not in p["id"] else "",
        })
    return salida


# ---------------------------------------------------------------- varios reels de un bruto (manual, 0 bis)

REGLAS_SERIE = f"""\
Eres el editor de una marca personal. Te pasamos la transcripción de un bruto de varios minutos, frase a frase, ya sin
las tomas falsas. Dentro suele haber más de un reel. Decide cuáles salen siguiendo la sección «Más de un reel de un
bruto» del manual de abajo: cada reel se sostiene solo (su gancho, una idea completa y su cierre), dura al menos 25 s
(objetivo 30 o más) y no repite más del 30 % de otro (salvo el completo y los de un punto, que pueden compartir texto
pero no el gancho). Si solo da para uno, devuelve uno: calidad antes que cantidad.
Para cada reel: «tipo» (completo, punto o idea), «titulo» (de qué va, ≤ 8 palabras), «desde» y «hasta» (ids de la
primera y la última frase de su tramo), «gancho» (id de la frase que lo abre; puede estar fuera del tramo),
«candidatos» (ids de hasta tres frases más que también podrían abrirlo, de su tramo o de fuera) y «motivo» (por qué se
sostiene solo, una frase). El gancho final se elige puntuando tu propuesta y los candidatos.

MANUAL_EDITOR.md
================
{MANUAL}
"""


GANCHO_PALABRAS = (4, 20)  # una frase más corta o más larga no abre un reel


def mejor_gancho(propuesto: str, candidatos: list[str], tramo: list[dict], quedan: list[dict], usados: set[str],
                 ppm: float | None = None) -> tuple[str, dict]:
    """El gancho del reel, puntuado con el catálogo de ganchos (agentes/ganchos.py): la propuesta de Claude, sus
    candidatos y las frases del tramo que tienen largo de gancho. Gana la que pasa la auditoría con más nota; a
    igualdad, la de Claude. Devuelve (id de la frase, su auditoría con «formula»)."""
    from ..agentes import ganchos
    por_id = {f["id"]: f for f in quedan}
    ids = [i for i in dict.fromkeys([propuesto, *candidatos, *(f["id"] for f in tramo)])
           if i in por_id and i not in usados]
    largo = lambda i: GANCHO_PALABRAS[0] <= len(ganchos.palabras(por_id[i]["texto"])) <= GANCHO_PALABRAS[1]  # noqa: E731
    ids = [i for i in ids if i == propuesto or largo(i)]
    if not ids:
        return propuesto, {}
    notas = {i: ganchos.auditar(por_id[i]["texto"], ppm=ppm) for i in ids}
    mejor = max(ids, key=lambda i: (notas[i]["pasa"], notas[i]["nota"], i == propuesto, i in candidatos))
    a = notas[mejor]
    return mejor, {"nota": a["nota"], "veredicto": a["veredicto"], "formula": a["formula"],
                   "formula_nombre": ganchos.nombre(a["formula"]), "fallos": list(a["fallos"])}


def mapa_de_reels(frases: list[dict], estructura: str = "", ppm: float | None = None) -> list[dict]:
    """Los reels que salen de un bruto: [{tipo, titulo, desde, hasta, gancho, gancho_nota, motivo}], ya comprobados
    (ids que existen, al menos 25 s y sin repetir gancho). El gancho sale puntuado (`mejor_gancho`) y guarda su fórmula
    para que Lupi y Orby midan cuáles funcionan. Cada uno se monta después como una edición con solo su tramo.
    `ppm`: palabras por minuto del dueño (voz del Kit), para medir cuánto tarda en decirse el gancho."""
    from motor_reels.motor import validar
    quedan = [f for f in frases if not f.get("quitada")]
    if not quedan:
        return []
    material = [{"id": f["id"], "t": round(f["inicio"]), "texto": f["texto"]} for f in quedan]
    esquema = obj(reels=lista(obj(tipo={"type": "string", "enum": ["completo", "punto", "idea"]}, titulo=S,
                                  desde=S, hasta=S, gancho=S, candidatos=lista(S), motivo=S)))
    peticion = json.dumps(material, ensure_ascii=False)[:150000]
    if estructura.strip():
        # La estructura que se pensó grabar (Escri): cada bloque suele ser un reel. Es una pista, no una orden: manda
        # lo que se dice de verdad en el bruto.
        peticion = (f"Estructura que se pensó grabar (DATOS, solo como pista de dónde empieza y acaba cada tema; "
                    f"si el bruto no la sigue, manda el bruto):\n{estructura.strip()[:6000]}\n\n"
                    f"Transcripción:\n{peticion}")
    datos = llm.json_con_esquema(REGLAS_SERIE, peticion, esquema)
    posicion = {f["id"]: i for i, f in enumerate(quedan)}
    reels, ganchos = [], set()
    for r in datos.get("reels") or []:
        if r.get("desde") not in posicion or r.get("hasta") not in posicion:
            continue
        a, b = sorted((posicion[r["desde"]], posicion[r["hasta"]]))
        propuesto = r.get("gancho") if r.get("gancho") in posicion else quedan[a]["id"]
        gancho, nota = mejor_gancho(propuesto, [c for c in (r.get("candidatos") or [])[:3] if c in posicion],
                                    quedan[a:b + 1], quedan, ganchos, ppm)
        dura = sum(f["fin"] - f["inicio"] for f in quedan[a:b + 1])
        if not a <= posicion[gancho] <= b:  # el gancho viene de fuera del tramo: también suma
            dura += quedan[posicion[gancho]]["fin"] - quedan[posicion[gancho]]["inicio"]
        if dura < validar.DURACION_MIN_REEL or gancho in ganchos:
            continue
        ganchos.add(gancho)
        reels.append({"tipo": r.get("tipo", "idea"), "titulo": r.get("titulo", ""), "desde": quedan[a]["id"],
                      "hasta": quedan[b]["id"], "gancho": gancho, "gancho_nota": nota, "motivo": r.get("motivo", "")})
    # Sin ninguno válido, el bruto entero es un reel.
    return reels or [{"tipo": "completo", "titulo": "", "desde": quedan[0]["id"], "hasta": quedan[-1]["id"],
                      "gancho": quedan[0]["id"], "motivo": "El bruto entero."}]
