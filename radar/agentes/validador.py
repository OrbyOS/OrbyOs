"""El validador de Escri: reglas en código que Claude no puede cambiar. Un texto solo llega a tus aprobaciones si las
cumple todas. Devuelve fallos (bloquean) y avisos (se enseñan, pero no bloquean).

Escri trabaja en uno de los dos modos de grabación del Kit:
- «estructura» (por defecto): el dueño habla libre 3-5 minutos siguiendo la idea, los bloques con sus puntos y el
  cierre, y Monti saca los reels con ganchos de lo que dice. Aquí no se escriben ni se miden ganchos.
- «guion»: el dueño lee lo que dice. Se mide el gancho (sus fórmulas y su nota), el ritmo con sus palabras por
  minuto y que no suene a IA.

En los dos: frases prohibidas y límites del Kit, llamada a la acción y palabra clave, hashtags, cifras con fuente (o
ninguna, si el negocio no usa cifras propias), clientes sin permiso, datos falsos de siempre y remix sin copiar.
"""
import re

from . import ganchos, humanizador, ritmo

MODOS = {"guion": "Guion para leer", "estructura": "Estructura para hablar libre"}
MODO_INICIAL = "estructura"   # el flujo principal: grabar suelto y que Monti saque varios reels
PALABRAS_POR_SEGUNDO = ritmo.PPM_INICIAL / 60
SEGUNDOS_MIN, SEGUNDOS_MAX = 20, 75      # un guion leído: de 20 a 75 s
GANCHO_NOTA_MIN = 50                     # por debajo, todavía no hay gancho
BLOQUES_MIN, BLOQUES_MAX = 3, 6          # un bloque por tema, de 40 a 70 s cada uno: 3-5 minutos en total
SEGUNDOS_POR_BLOQUE = 60
PUNTOS_MIN, PUNTOS_MAX = 2, 5
PUNTO_MAX_PALABRAS = 25                  # más largo ya es una frase para leer, no una idea
HASHTAGS_MIN, HASHTAGS_MAX = 3, 5

CTAS = {
    "comentar": "Comentar una palabra",
    "mensaje": "Escribir por mensaje",
    "enlace": "Enlace en la bio",
    "seguir": "Seguir la cuenta",
    "ninguna": "Sin llamada a la acción",
}
_CTA_PATRON = {
    "comentar": r"\bcomenta",
    "mensaje": r"\b(escr[ií]beme|m[aá]ndame|env[ií]ame|por (dm|privado|mensaje))",
    "enlace": r"\b(enlace|link|bio)\b",
    "seguir": r"\bs[ií]gueme\b",
}

# Frases de relleno que delatan un texto escrito por una IA o de plantilla.
GENERICAS = [
    "en el mundo de hoy", "en el mundo actual", "hoy en día", "sin más dilación", "déjame contarte", "en este vídeo",
    "en este video", "no es solo", "no se trata solo de", "sumérgete", "desbloquea", "revoluciona", "lleva tu negocio al",
    "al siguiente nivel", "cabe destacar", "en definitiva", "es importante destacar", "un mundo de posibilidades",
    "el secreto mejor guardado", "game changer", "te lo cuento todo", "quédate hasta el final",
]

_CAMPO = re.compile(r"^(idea|cierre|tu ejemplo)\s*:\s*(.*)$", re.IGNORECASE)
_BLOQUE = re.compile(r"^\d+[.)]\s+(.+)$")
_PUNTO = re.compile(r"^[-*•]\s+(.+)$")
_ACOTACION = re.compile(r"\[[^\]]*\]|\((?:[^)]*\b(?:pausa|plano|corte|escena|m[uú]sica|texto en pantalla|zoom)\b[^)]*)\)",
                        re.IGNORECASE)
_ETIQUETA = re.compile(r"^\s*(?:[-*#>•]|\d+[.)]\s|(?:gancho|hook|paso \d+|cierre|cta|desarrollo|giro|prueba|reenganche|idea)\s*:)",
                       re.IGNORECASE | re.MULTILINE)
# Datos que circulan por internet y son falsos: no se usan nunca, digan lo que digan las afirmaciones.
DATOS_FALSOS = re.compile(
    r"\b8 segundos de atenci[oó]n|\batenci[oó]n de un pez|\bpez de colores\b|\b10 ?% (?:de nuestro|del) cerebro|"
    r"\b93 ?% de la comunicaci[oó]n|\b21 d[ií]as (?:para|en) (?:crear|formar|cambiar) un h[aá]bito|"
    r"\b(?:regla|ley) de las 10[.,]?000 horas", re.IGNORECASE)
_CIFRA_EN_LETRAS = re.compile(
    r"\b(?:dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|quince|veinte|treinta|cuarenta|cincuenta|"
    r"sesenta|setenta|ochenta|noventa|cien|ciento|doscientos|trescientos|quinientos|mil|un mill[oó]n|millones|"
    r"el doble|el triple|la mitad)(?:\s+(?:mil|millones|de))*\s+(?:euros|d[oó]lares|por ciento|clientes|alumnos|"
    r"seguidores|ventas|leads|veces m[aá]s|facturados)\b", re.IGNORECASE)
_URL = re.compile(r"https?://|www\.", re.IGNORECASE)
VISIBLE_INSTAGRAM = 125                  # lo que se ve antes de «… más»
_NUMERO = re.compile(r"(\d+(?:[.,]\d+)*)\s*(%|por ciento|€|euros|\$|d[oó]lares|k\b|mil\b|millones)?", re.IGNORECASE)


def normal(texto: str) -> str:
    texto = texto.lower()
    for a, b in zip("áéíóúüàèìòù", "aeiouuaeiou"):
        texto = texto.replace(a, b)
    return " ".join(re.sub(r"[^\w\s%€$]", " ", texto).split())


def contar_palabras(texto: str) -> int:
    return len(re.findall(r"\w+", texto))


def frases(texto: str) -> list[str]:
    return [f for f in re.split(r"(?<=[.!?…])\s+|\n+", texto) if f.strip()]


# ---------------------------------------------------------------- palabra clave

def error_palabra_clave(palabra: str, usadas: set[str], texto: str = "") -> str | None:
    """4 a 9 letras, nunca usada, sin solaparse con otra y sin salir en el guion fuera de la llamada a la acción."""
    p = (palabra or "").strip().upper()
    if not re.fullmatch(r"[A-ZÑ]{4,9}", p):
        return "La palabra clave tiene que tener de 4 a 9 letras, sin números ni espacios."
    usadas = {u.upper() for u in usadas}
    if p in usadas:
        return f"La palabra clave {p} ya se usó en otro post."
    pegada = next((u for u in usadas if u in p or p in u), None)
    if pegada:
        return f"La palabra clave {p} se confunde con {pegada}, que ya se usó."
    resto = " ".join(f for f in frases(texto) if not re.search(_CTA_PATRON["comentar"] + "|" + _CTA_PATRON["mensaje"],
                                                               f, re.IGNORECASE))
    if re.search(rf"\b{re.escape(normal(p))}\b", normal(resto)):
        return f"La palabra clave {p} sale en el guion: tiene que ser una palabra que nadie escriba sin querer."
    return None


# ---------------------------------------------------------------- cifras

def _digitos(token: str) -> str:
    return re.sub(r"[.,\s]", "", token)


def cifras_sin_respaldo(texto: str, permitidas: list[str]) -> list[str]:
    """Cifras del guion que no salen del inventario de pruebas ni de la oferta. Los números pequeños sin unidad
    («3 pasos») no cuentan como cifra."""
    respaldo = {_digitos(m.group(1)) for c in permitidas for m in _NUMERO.finditer(c)}
    salida = []
    for m in _NUMERO.finditer(texto):
        numero, unidad = m.group(1), m.group(2)
        valor = float(_digitos(numero) or 0)
        if not unidad and valor <= 10:
            continue
        if not unidad and re.fullmatch(r"(19|20)\d\d", numero):  # años
            continue
        if _digitos(numero) not in respaldo:
            salida.append(m.group(0).strip())
    return salida


# ---------------------------------------------------------------- el guion entero

def ngramas(texto: str, n: int = 8) -> set[tuple]:
    w = normal(texto).split()
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def leer_estructura(texto: str) -> dict:
    """La estructura escrita en texto: «Idea: …», bloques numerados («1. tema») con sus puntos («- …») y «Tu ejemplo: …»,
    y «Cierre: …». Es el mismo formato que se ve y se edita en la app."""
    salida = {"idea": "", "bloques": [], "cierre": ""}
    for linea in (x.strip() for x in (texto or "").splitlines()):
        if not linea:
            continue
        if m := _CAMPO.match(linea):
            campo, valor = normal(m.group(1)), m.group(2).strip()
            if campo == "idea":
                salida["idea"] = valor
            elif campo == "cierre":
                salida["cierre"] = valor
            elif salida["bloques"]:
                salida["bloques"][-1]["ejemplo"] = valor
        elif m := _BLOQUE.match(linea):
            salida["bloques"].append({"tema": m.group(1).strip(), "puntos": [], "ejemplo": ""})
        elif m := _PUNTO.match(linea):
            if salida["bloques"]:
                salida["bloques"][-1]["puntos"].append(m.group(1).strip())
    return salida


def escribir_estructura(idea: str, bloques: list[dict], cierre: str) -> str:
    """Lo contrario de `leer_estructura`."""
    partes = [f"Idea: {idea.strip()}"] if idea.strip() else []
    for i, b in enumerate(bloques, 1):
        lineas = [f"{i}. {b['tema'].strip()}"] + [f"- {x.strip()}" for x in b.get("puntos") or [] if x.strip()]
        if (b.get("ejemplo") or "").strip():
            lineas.append(f"Tu ejemplo: {b['ejemplo'].strip()}")
        partes.append("\n".join(lineas))
    if cierre.strip():
        partes.append(f"Cierre: {cierre.strip()}")
    return "\n\n".join(partes)


def _clientes_sin_permiso(texto_n: str, pruebas: list[dict]) -> list[str]:
    """Nombres de clientes que salen en el texto sin permiso para nombrarlos."""
    salida = []
    for p in pruebas or []:
        permiso = p.get("permiso_nombre", p.get("consentimiento"))
        nombre = normal(str(p.get("cliente") or p.get("titulo") or ""))
        if p.get("tipo") == "caso" and not permiso and len(nombre) >= 3 and re.search(rf"\b{re.escape(nombre)}\b", texto_n):
            salida.append(str(p.get("cliente") or p.get("titulo")))
    return salida


def _comun(g: dict, texto: str, *, prohibidas, permitidas, usadas, etapa, remix, cifras_propias, pruebas, cierre: str,
           sin_cierre: str, fallos: list, avisos: list):
    """Lo que se comprueba igual en un guion y en una estructura."""
    texto_n = normal(texto)
    for frase in [*GENERICAS, *prohibidas]:
        if frase.strip() and normal(frase) and re.search(rf"\b{re.escape(normal(frase))}\b", texto_n):
            fallos.append(f"Usa una frase prohibida: «{frase}».")

    cta = g.get("cta") or ""
    if cta not in CTAS:
        fallos.append("Falta el tipo de llamada a la acción.")
    elif cta == "ninguna" and etapa == "bofu":
        avisos.append("Es una pieza para vender y no pide nada al final.")
    palabra = (g.get("palabra_clave") or "").strip().upper()
    if cta in ("comentar", "mensaje"):
        error = error_palabra_clave(palabra, usadas, sin_cierre)
        if error:
            fallos.append(error)
        elif not re.search(rf"\b{re.escape(normal(palabra))}\b", normal(cierre)):
            fallos.append(f"El cierre no dice la palabra clave {palabra}.")

    etiquetas = g.get("hashtags") or []
    if not HASHTAGS_MIN <= len(etiquetas) <= HASHTAGS_MAX:
        fallos.append(f"Lleva {len(etiquetas)} hashtags: tienen que ser de {HASHTAGS_MIN} a {HASHTAGS_MAX}, del nicho.")
    elif any(not re.fullmatch(r"#[a-z0-9áéíóúñü_]{2,40}", h) for h in etiquetas):
        fallos.append("Cada hashtag empieza por # y va en minúsculas, sin espacios.")
    if not (g.get("gancho_fuente") or "").strip():
        fallos.append("No dice de dónde sale el tema.")

    # Cifras: solo del inventario de pruebas o de la oferta, y ninguna si el negocio no usa cifras propias.
    sueltas = cifras_sin_respaldo(texto, permitidas if cifras_propias else [])
    letras = [m.group(0) for m in _CIFRA_EN_LETRAS.finditer(texto)]
    if sueltas and cifras_propias:
        fallos.append("Cifras sin fuente en el inventario de pruebas: " + ", ".join(sueltas[:5]) + ".")
    elif (sueltas or letras) and not cifras_propias:
        fallos.append("Este negocio no usa cifras propias y aquí hay: " + ", ".join((sueltas + letras)[:5]) + ".")
    elif letras:
        avisos.append("Cifra dicha con letras: «" + "», «".join(letras[:3]) + "». Comprueba que sale de una prueba.")
    if m := DATOS_FALSOS.search(texto):
        fallos.append(f"«{m.group(0)}» es un dato falso que circula por internet: quítalo.")
    for nombre in _clientes_sin_permiso(texto_n, pruebas):
        fallos.append(f"Nombra a un cliente sin permiso para hacerlo: «{nombre}». Descríbelo por su tipo.")

    ids = {str(p.get("id")) for p in pruebas or []}
    for a in g.get("afirmaciones") or []:
        veredicto = (a.get("veredicto") or "").upper()
        citadas = re.findall(r"\[([^\]]+)\]", a.get("fuente") or "")
        if veredicto == "CUT" and a.get("texto") and normal(a["texto"]) in texto_n:
            fallos.append(f"Sigue en el texto una afirmación que había que quitar: «{a['texto']}».")
        elif veredicto == "FIX":
            avisos.append(f"Revisa esta afirmación: «{a.get('texto', '')}» ({a.get('fuente') or 'sin fuente'}).")
        if veredicto in ("PASS", "FIX") and pruebas is not None and any(c not in ids for c in citadas):
            fallos.append(f"La afirmación «{a.get('texto', '')}» cita una prueba que no está en el inventario.")

    if remix:
        suyos = [str(x) for x in remix.get("del_creador") or []] + ([remix["cuenta"].lstrip("@")] if remix.get("cuenta") else [])
        for cosa in suyos:
            cosa_n = normal(cosa)
            if len(cosa_n) >= 4 and re.search(rf"\b{re.escape(cosa_n)}\b", texto_n):
                fallos.append(f"Lleva algo que es del creador original: «{cosa}».")


def validar(g: dict, *, prohibidas: list[str], permitidas: list[str], usadas: set[str], etapa: str = "",
            remix: dict | None = None, modo: str = MODO_INICIAL, ppm: float | None = None, cifras_propias: bool = True,
            pruebas: list[dict] | None = None) -> dict:
    """`g`: texto, cta, palabra_clave, hashtags, gancho_fuente, afirmaciones. `remix`: plantilla del original con
    `del_creador`, `cuenta`, `transcripcion` y `segundos`. `modo`: «guion» o «estructura» (del Kit). `ppm`: palabras
    por minuto del dueño. `pruebas`: el inventario, para comprobar las fuentes citadas y los clientes sin permiso."""
    if modo == "estructura":
        return _validar_estructura(g, prohibidas=prohibidas, permitidas=permitidas, usadas=usadas, etapa=etapa,
                                   remix=remix, cifras_propias=cifras_propias, pruebas=pruebas)
    fallos, avisos = [], []
    texto = (g.get("texto") or "").strip()
    n = contar_palabras(texto)
    pps = (ppm or ritmo.PPM_INICIAL) / 60
    minimo, maximo = round(SEGUNDOS_MIN * pps), round(SEGUNDOS_MAX * pps)
    if remix and remix.get("segundos"):
        # Un remix puede durar lo que duraba el original.
        maximo = max(maximo, round(remix["segundos"] * pps * 1.25))
        minimo = min(minimo, max(25, round(remix["segundos"] * pps * 0.6)))
    if n < minimo:
        fallos.append(f"Es demasiado corto: {n} palabras (mínimo {minimo}).")
    elif n > maximo:
        fallos.append(f"Es demasiado largo: {n} palabras (máximo {maximo}, unos {round(maximo / pps)} s).")
    if _ACOTACION.search(texto) or _ETIQUETA.search(texto):
        fallos.append("Solo puede llevar lo que se dice: nada de acotaciones, títulos de paso, viñetas ni almohadillas.")

    # El gancho: la primera frase. Por debajo de 50 todavía no hay gancho; la auditoría avisa de lo que falla.
    primera = (frases(texto) or [""])[0]
    nota = ganchos.auditar(primera, ppm=ppm)
    if texto and nota["nota"] < GANCHO_NOTA_MIN:
        fallos.append(f"El gancho saca un {nota['nota']} sobre 100: todavía no hay gancho. Lo más flojo: "
                      f"{nota['peor'].lower()} ({nota['comprobaciones'][nota['peor']]['detalle']}).")
    avisos += [f"Gancho: {f}" for f in nota["fallos"].values()]

    medida = ritmo.medir(texto, ppm=ppm)
    avisos += medida["fallos"] + medida["avisos"]
    humano = humanizador.revisar(texto)
    avisos += [f"Suena a plantilla ({e['nombre']}): «{e['frase']}». {e['arreglo']}" for e in humano["estructuras"]]
    if any(c in texto for c in humanizador.INVISIBLES) or "—" in texto:
        fallos.append("Lleva rayas o caracteres invisibles: pásalo por el humanizador.")

    cta = g.get("cta") or ""
    cierre = " ".join(frases(texto)[-3:])
    if cta in _CTA_PATRON and not re.search(_CTA_PATRON[cta], cierre, re.IGNORECASE):
        fallos.append(f"La llamada a la acción del final no pide lo que dice su tipo ({CTAS[cta].lower()}).")
    _comun(g, texto, prohibidas=prohibidas, permitidas=permitidas, usadas=usadas, etapa=etapa, remix=remix,
           cifras_propias=cifras_propias, pruebas=pruebas, cierre=cierre, sin_cierre=texto, fallos=fallos, avisos=avisos)
    original = (remix or {}).get("transcripcion") or ""
    if original:
        gancho_original = " ".join(normal(frases(original)[0] if frases(original) else "").split())
        copiados = {c for c in ngramas(texto) & ngramas(original) if " ".join(c) not in gancho_original}
        if copiados:
            fallos.append("Copia un trozo largo de lo que dice el original después del gancho: cuéntalo con tus palabras.")
    return {"fallos": list(dict.fromkeys(fallos)), "avisos": list(dict.fromkeys(avisos)), "palabras": n, "modo": "guion",
            "segundos": round(n / pps), "gancho": {k: nota[k] for k in ("nota", "veredicto", "formula", "peor")},
            "humano": humano["nota"]}


def _validar_estructura(g: dict, *, prohibidas, permitidas, usadas, etapa, remix, cifras_propias, pruebas) -> dict:
    fallos, avisos = [], []
    texto = (g.get("texto") or "").strip()
    e = leer_estructura(texto)
    if not e["idea"]:
        fallos.append("Falta la idea del vídeo en una frase («Idea: …»).")
    if not BLOQUES_MIN <= len(e["bloques"]) <= BLOQUES_MAX:
        fallos.append(f"Tiene {len(e['bloques'])} bloques: tienen que ser de {BLOQUES_MIN} a {BLOQUES_MAX}, uno por "
                      "tema, para unos 3-5 minutos.")
    for i, b in enumerate(e["bloques"], 1):
        if not PUNTOS_MIN <= len(b["puntos"]) <= PUNTOS_MAX:
            fallos.append(f"El bloque {i} tiene {len(b['puntos'])} puntos: tienen que ser de {PUNTOS_MIN} a {PUNTOS_MAX}.")
        if any(contar_palabras(x) > PUNTO_MAX_PALABRAS for x in [b["tema"], *b["puntos"]]):
            fallos.append(f"El bloque {i} tiene frases para leer: cada punto es una idea corta (como mucho "
                          f"{PUNTO_MAX_PALABRAS} palabras), no un guion.")
    cta = g.get("cta") or ""
    if cta in _CTA_PATRON and not e["cierre"]:
        fallos.append(f"Falta el cierre («Cierre: …») con la llamada a la acción ({CTAS[cta].lower()}).")
    _comun(g, texto, prohibidas=prohibidas, permitidas=permitidas, usadas=usadas, etapa=etapa, remix=remix,
           cifras_propias=cifras_propias, pruebas=pruebas, cierre=e["cierre"],
           sin_cierre=escribir_estructura(e["idea"], e["bloques"], ""), fallos=fallos, avisos=avisos)
    if (remix or {}).get("transcripcion") and ngramas(texto) & ngramas(remix["transcripcion"]):
        fallos.append("Copia un trozo largo de lo que dice el original: cuéntalo con tus palabras.")
    return {"fallos": list(dict.fromkeys(fallos)), "avisos": list(dict.fromkeys(avisos)), "palabras": contar_palabras(texto),
            "modo": "estructura", "bloques": len(e["bloques"]), "segundos": len(e["bloques"]) * SEGUNDOS_POR_BLOQUE}


# ---------------------------------------------------------------- los textos de cada red

def visible(texto: str, corte: int = VISIBLE_INSTAGRAM) -> str:
    """Lo que se ve del texto de Instagram antes de «… más»."""
    t = " ".join((texto or "").split())
    return t if len(t) <= corte else t[:corte].rsplit(" ", 1)[0] + "…"


def revisar_textos(textos: dict, *, cta: str, palabra: str, redes: list[str] | None = None) -> list[str]:
    """Avisos sobre el texto del post de cada red: la palabra clave donde funciona (y solo ahí), lo que se ve antes de
    «… más», nada de enlaces en Instagram y como mucho cinco hashtags."""
    avisos, palabra = [], (palabra or "").upper()
    for red, texto in (textos or {}).items():
        if not isinstance(texto, str) or not texto.strip() or (redes is not None and red not in redes):
            continue
        nombre = red.capitalize() if red != "youtube" else "YouTube"
        etiquetas = re.findall(r"(?:^|\s)#\w+", texto)
        if len(etiquetas) > HASHTAGS_MAX:
            avisos.append(f"{nombre}: {len(etiquetas)} hashtags; como mucho {HASHTAGS_MAX}.")
        pide_comentar = palabra and re.search(rf"\bcomenta\w*\b[^.!?\n]{{0,20}}\b{re.escape(palabra)}\b", texto, re.IGNORECASE)
        if red == "instagram":
            primera = visible(texto)
            if _URL.search(texto):
                avisos.append("Instagram: los enlaces del texto no se pueden pulsar; manda a la bio o al mensaje.")
            if cta == "comentar" and palabra and palabra not in texto.upper():
                avisos.append("Instagram: el texto no pide comentar la palabra clave.")
            if re.match(r"\s*(?:hola|buenas|#|[\U0001F300-\U0001FAFF])", primera, re.IGNORECASE):
                avisos.append("Instagram: lo que se ve antes de «… más» empieza con un saludo, un hashtag o un emoji.")
        elif pide_comentar:
            avisos.append(f"{nombre}: allí comentar la palabra no manda nada; usa «escríbeme {palabra}» o el enlace.")
    return avisos
