"""Humanizador: deja un texto en español con cara de escrito por una persona antes de que salga. Vale para guiones,
estructuras, textos de posts, comentarios y mensajes (lo usan Escri, Chati y Publi).

- `limpiar(texto)` arregla lo mecánico: caracteres invisibles, rayas, comillas curvas y la palabrería de folleto (cada
  expresión por una palabra normal). Devuelve el texto limpio y la lista de cambios.
- `revisar(texto)` da una nota de 0 a 100 con cuatro señales y avisa de las construcciones de plantilla, que no se
  reescriben solas porque cambiar la forma de una frase necesita criterio.

Son comprobaciones hechas en local con el texto y nada más. Nunca se le promete al dueño que nadie notará la IA.
"""
import re
import statistics
import unicodedata

# ---------------------------------------------------------------- lo que se arregla solo

INVISIBLES = {
    "​": "espacio de ancho cero", "‌": "separador de ancho cero", "‍": "unión de ancho cero",
    "⁠": "unión de palabras", "﻿": "marca de orden de bytes", "­": "guion suave",
    "᠎": "separador mongol", "؜": "marca árabe", "‎": "marca de izquierda a derecha",
    "‏": "marca de derecha a izquierda", "‪": "incrustación", "‫": "incrustación", "‬": "fin de incrustación",
    "‭": "anulación", "‮": "anulación", "⁣": "separador invisible", "⁢": "multiplicación invisible",
}
ESPACIOS_RAROS = {" ": " ", " ": " ", " ": " ", " ": " ", " ": " "}
TIPOGRAFIA = [("—", ", ", "raya"), ("–", "-", "semirraya"), ("‘", "'", "comilla curva"), ("’", "'", "comilla curva"),
              ("“", "\"", "comilla curva"), ("”", "\"", "comilla curva"), ("…", "...", "puntos suspensivos de un carácter"),
              ("•", "-", "viñeta"), ("→", "->", "flecha")]

# Palabrería de IA en español: la expresión y su sustituta (vacía = se borra). De más larga a más corta.
PALABRERIA = [
    # arranques
    ("en el mundo de hoy en día", "hoy"), ("en el mundo actual", "hoy"), ("en el mundo de hoy", "hoy"),
    ("en la era digital", "hoy"), ("en el panorama actual", "hoy"), ("en un mundo cada vez más", "en un mundo más"),
    ("en el vertiginoso mundo de", "en"), ("en el cambiante mundo de", "en"), ("hoy en día", "hoy"),
    ("no es ningún secreto que", ""), ("seamos sinceros,", ""), ("seamos honestos,", ""), ("la realidad es que", ""),
    ("déjame contarte", ""), ("déjame explicarte", ""), ("te cuento un secreto:", ""), ("imagina un mundo en el que", "imagina que"),
    ("todos hemos estado ahí", ""), ("vamos al grano", ""), ("sin más dilación", ""), ("dicho esto,", ""),
    # cierres de redacción
    ("en definitiva,", ""), ("en conclusión,", ""), ("en resumen,", ""), ("para concluir,", ""), ("en pocas palabras,", ""),
    ("cabe destacar que", ""), ("es importante destacar que", ""), ("es importante señalar que", ""),
    ("vale la pena mencionar que", ""), ("sin lugar a dudas", ""), ("sin duda alguna", ""),
    # verbos de folleto
    ("sumergirnos en", "ver"), ("sumérgete en", "mira"), ("adentrarnos en", "entrar en"), ("adéntrate en", "entra en"),
    ("desbloquear", "conseguir"), ("desbloquea", "consigue"), ("potenciar", "mejorar"),
    ("catapultar", "subir"), ("catapulta", "sube"), ("revolucionar", "cambiar"), ("revoluciona", "cambia"),
    ("elevar tu", "mejorar tu"), ("eleva tu", "mejora tu"), ("brindar", "dar"), ("brinda", "da"), ("fomentar", "crear"),
    ("aprovechar al máximo", "aprovechar"), ("sacar el máximo partido a", "aprovechar"), ("optimizar al máximo", "mejorar"),
    ("llevar tu negocio al siguiente nivel", "hacer crecer tu negocio"), ("llevarlo al siguiente nivel", "mejorarlo"),
    ("al siguiente nivel", ""), ("navegar por", "moverte por"), ("es un testimonio de", "demuestra"),
    ("un testimonio de", "una prueba de"), ("aportar valor", "ayudar"), ("aporta valor", "ayuda"),
    # adjetivos y nombres de plantilla
    ("un sinfín de", "muchas"), ("una amplia gama de", "muchos"), ("un abanico de", "varias"),
    ("un mundo de posibilidades", "muchas opciones"), ("contenido de valor", "contenido útil"),
    ("de manera significativa", "mucho"), ("de forma significativa", "mucho"), ("significativamente", "mucho"),
    ("de manera eficaz", "bien"), ("de forma eficaz", "bien"), ("meticulosamente", "con cuidado"),
    ("revolucionario", "nuevo"), ("revolucionaria", "nueva"), ("disruptivo", "nuevo"), ("disruptiva", "nueva"),
    ("innovador", "nuevo"), ("innovadora", "nueva"), ("a la vanguardia", "por delante"), ("de vanguardia", "nuevo"),
    ("holístico", "completo"), ("holística", "completa"), ("sinergia", "colaboración"), ("sinergias", "colaboraciones"),
    ("robusto", "sólido"), ("robusta", "sólida"), ("sin fisuras", "sin cortes"), ("crucial", "clave"), ("vital", "clave"),
    ("fascinante", "curioso"), ("apasionante", "interesante"), ("intrincado", "complicado"), ("game changer", "un gran cambio"),
    ("next level", "mucho mejor"),
    # redes
    ("deja de hacer scroll", ""), ("no hagas scroll", ""), ("en el vídeo de hoy", ""), ("en este vídeo", ""),
    ("en este video", ""), ("quédate hasta el final", ""), ("sígueme para más", "sígueme"), ("sígueme para más contenido", "sígueme"),
    ("etiqueta a alguien que", ""), ("dale like si", ""), ("corre, no camines", ""), ("el algoritmo ama", ""),
    ("el algoritmo premia", ""),
]

# Construcciones de plantilla, por familias: se avisan, no se reescriben. (id, familia, patrón, nombre, arreglo)
ESTRUCTURAS = [
    # giros de redacción que se repiten en los textos generados
    ("no-es-x-es-y", "giro", r"\bno es (?:solo|s[oó]lo|solamente|simplemente) [^.!?\n]{2,60}[,.;] es\b",
     "«No es solo esto, es aquello»", "Di lo que quieres decir, sin la mitad que prepara el golpe."),
    ("no-solo-sino", "giro", r"\bno solo\b[^.!?\n]{2,80}\bsino (?:tambi[eé]n|que)\b",
     "«No solo…, sino también…»", "Parte la frase en dos o quédate con la mitad que importa."),
    ("no-va-de", "giro", r"\bno se trata de [^.!?\n]{2,60}[,.;] se trata de\b|\bno va de [^.!?\n]{2,60}[,.;] va de\b",
     "«No se trata de…, se trata de…»", "Empieza directamente por lo segundo."),
    ("pregunta-suelta", "giro", r"(?m)(?:^|[.!:]\s+)¿(?:el resultado|la clave|lo mejor|la trampa|el truco|el problema|"
                                r"la diferencia|la respuesta|el motivo|y sabes qu[eé]|y lo mejor)\?(?=\s|$)",
     "Pregunta que se responde sola en la línea siguiente", "Da la respuesta y quita la pregunta."),
    ("sabias-que", "giro", r"(?im)^\s*¿sab[ií]as que\b", "Arranque «¿Sabías que…?»", "Empieza por el dato."),
    ("spoiler", "giro", r"(?i)\b(?:spoiler|alerta de spoiler)\s*:", "«Spoiler:» de adorno", "Dilo sin anunciarlo."),
    ("anuncio-de-leccion", "giro", r"\besto es lo que (?:aprend[ií]|he aprendido)\b|\bte lo explico\b|\bte cuento por qu[eé]\b",
     "Anunciar lo que vas a contar", "Cuéntalo sin el anuncio."),
    ("tres-por-inercia", "giro", r"\b\w+, \w+ y \w+\.", "Enumeración de tres por inercia",
     "Usa las cosas que hay de verdad: si son dos, dos."),
    ("cierre-escolar", "giro", r"(?im)^\s*(?:en resumen|en conclusi[oó]n|para concluir|en definitiva)\b",
     "Cierre de redacción del colegio", "Acaba con la petición o volviendo a la primera frase."),
    ("soy-una-ia", "giro", r"\bcomo (?:modelo de lenguaje|inteligencia artificial|una ia)\b", "El texto dice que es una IA",
     "Bórralo."),
    # relleno de redes
    ("intro-de-video", "redes", r"\b(?:en (?:este|el) (?:v[ií]deo|reel|post)(?: de hoy)?|hoy (?:te|os) (?:voy a|traigo))\b",
     "Presentar el vídeo en vez de empezarlo", "Empieza por lo importante."),
    ("no-pases", "redes", r"(?im)^\s*(?:no hagas scroll|deja de hacer scroll|para de deslizar|no te vayas)\b",
     "Pedir que no pasen de largo", "Gánatelo con lo que prometes."),
    ("cebo-de-comentarios", "redes", r"¿(?:est[aá]s de acuerdo|qu[eé] opinas|qu[eé] pens[aá]is|me equivoco|a que s[ií])\?\s*$",
     "Pregunta para sacar comentarios", "Pide una cosa concreta o no pidas nada."),
    ("cebo-de-seguir", "redes", r"\b(?:s[ií]gueme para m[aá]s|etiqueta a (?:alguien|un amigo|una amiga)|dale (?:like|me gusta) si|"
                                r"comparte si|comenta si)\b", "Petición de reflejo (sígueme, etiqueta, dale like)",
     "Una sola petición, al final, y que tenga sentido."),
    # formato
    ("muro-de-hashtags", "formato", r"(?:#\w+[ \t]*){6,}", "Muchos hashtags seguidos", "Como mucho cinco, al final y del nicho."),
    ("emoji-de-adorno", "formato", r"[\U0001F680\U0001F525\U0001F4A1\u2728\U0001F3AF\U0001F447\U0001F449\U0001F64C]",
     "Emoji de adorno (cohete, fuego, bombilla, brillos, diana, manos)", "Quítalo."),
    ("lista-con-emojis", "formato", r"(?m)^\s*[\U0001F300-\U0001FAFF✅➡⬅✔✨]\s*\S", "Lista con emojis de viñeta",
     "Guiones normales o frases."),
    ("mayusculas", "formato", r"\b[A-ZÁÉÍÓÚÑ]{3,}\b(?:\s+\b[A-ZÁÉÍÓÚÑ]{3,}\b){2,}", "Varias palabras seguidas en mayúsculas",
     "Mayúsculas solo para la palabra clave."),
]
_ESTRUCTURAS = [(i, re.compile(p, re.IGNORECASE if i != "mayusculas" else 0), n, f) for i, _, p, n, f in ESTRUCTURAS]


def _palabreria(respetar: list[str]) -> list[tuple[re.Pattern, str, str]]:
    propias = {r.lower() for r in respetar or []}
    return [(re.compile(rf"(?<![\w]){re.escape(a)}(?![\w])", re.IGNORECASE), b, a)
            for a, b in sorted(PALABRERIA, key=lambda x: -len(x[0])) if a.lower() not in propias]


def _misma_mayuscula(original: str, nuevo: str) -> str:
    return nuevo[:1].upper() + nuevo[1:] if original[:1].isupper() and nuevo else nuevo


def limpiar(texto: str, *, respetar: list[str] | None = None) -> tuple[str, list[str]]:
    """Texto limpio y lista de cambios. `respetar`: expresiones que el dueño usa de verdad y no se tocan."""
    cambios, t = [], texto or ""
    invisibles = sum(t.count(c) for c in INVISIBLES) + sum(
        1 for ch in t if unicodedata.category(ch) == "Cf" and ch not in INVISIBLES and ch not in "‍")
    t = "".join(ch for ch in t if ch not in INVISIBLES and unicodedata.category(ch) != "Cf")
    if invisibles:
        cambios.append(f"{invisibles} carácter(es) invisible(s) borrado(s)")
    for raro, normal in ESPACIOS_RAROS.items():
        t = t.replace(raro, normal)
    for de, a, nombre in TIPOGRAFIA:
        if de in t:
            cambios.append(f"{t.count(de)} {nombre}(s)")
            t = t.replace(de, a)
    for patron, sustituta, original in _palabreria(respetar or []):
        def cambiar(m, s=sustituta):
            return _misma_mayuscula(m.group(0), s)
        t, n = patron.subn(cambiar, t)
        if n:
            cambios.append(f"«{original}» → «{sustituta}»" if sustituta else f"«{original}» borrado")
    # Lo que dejan los cambios: comas dobles, espacios antes de puntuación, frases que empiezan por coma.
    t = re.sub(r"\s+,", ",", t)
    t = re.sub(r",\s*,", ",", t)
    t = re.sub(r",\s*([.!?;:])", r"\1", t)
    t = re.sub(r"(^|[.!?¿¡]\s+|\n)\s*,\s*", r"\1", t)
    t = re.sub(r"[ \t]{2,}", " ", t)
    t = re.sub(r"(^|[.!?]\s+|\n)([a-záéíóúñ])", lambda m: m.group(1) + m.group(2).upper(), t)
    return t.strip(), cambios


# ---------------------------------------------------------------- la nota

PESOS = {"LIMPIEZA": 0.3, "PLANTILLAS": 0.3, "CADENCIA": 0.2, "CERCANÍA": 0.2}
FRASE_LARGA = 30             # palabras: más ya cuesta leerla o decirla de un tirón


def _tope(n: float) -> float:
    return max(0.0, min(100.0, n))


def _frases(texto: str) -> list[str]:
    return [f for f in re.split(r"(?<=[.!?…])\s+|\n+", texto or "") if len(f.split()) >= 2]


def _palabras(texto: str) -> list[str]:
    return re.findall(r"[\wáéíóúüñÁÉÍÓÚÜÑ]+", texto or "")


def estructuras(texto: str) -> list[dict]:
    """Las construcciones de plantilla que hay en el texto, con la frase y cómo arreglarla."""
    salida = []
    for ident, patron, nombre, arreglo in _ESTRUCTURAS:
        if m := patron.search(texto or ""):
            salida.append({"id": ident, "nombre": nombre, "frase": m.group(0).strip()[:80], "arreglo": arreglo})
    return salida


def revisar(texto: str, *, respetar: list[str] | None = None) -> dict:
    """Nota de 0 a 100 (más es más humano), con cuatro señales:
    - LIMPIEZA: palabrería de folleto, rayas y caracteres invisibles por cada 100 palabras;
    - PLANTILLAS: construcciones de plantilla (cada una resta 35);
    - CADENCIA: frases de largos distintos y ninguna eterna;
    - CERCANÍA: se habla a alguien o desde alguien (tú, yo, nosotros), no al aire.
    APROBADO desde 70 con ninguna señal por debajo de 50; SUENA A IA por debajo de 50."""
    w, frases = _palabras(texto), _frases(texto)
    n = max(1, len(w))

    expresiones = sum(len(p.findall(texto or "")) for p, _, _ in _palabreria(respetar or []))
    huellas = sum((texto or "").count(c) for c in INVISIBLES) + (texto or "").count("—") + (texto or "").count("–")
    por_cien = (expresiones + huellas) / n * 100
    limpieza = (_tope(100 - por_cien * 30), f"{expresiones} expresión(es) de folleto y {huellas} raya(s) o invisible(s)")

    trucos = estructuras(texto)
    plantillas = (_tope(100 - 35 * len(trucos)), f"{len(trucos)} construcción(es) de plantilla")

    largos = [len(_palabras(f)) for f in frases]
    if len(largos) >= 3 and statistics.mean(largos):
        cv = statistics.pstdev(largos) / statistics.mean(largos)
        cadencia_nota = _tope((cv - 0.15) / 0.45 * 100)
    else:
        cv, cadencia_nota = 0.0, 75.0          # con una o dos frases no hay ritmo que medir
    eternas = sum(1 for x in largos if x > FRASE_LARGA)
    cadencia = (_tope(cadencia_nota - 20 * eternas),
                f"variación {cv:.2f} entre {len(largos)} frases" + (f"; {eternas} de más de {FRASE_LARGA} palabras" if eternas else ""))

    personas = len(re.findall(r"\b(?:yo|me|mi|mis|t[uú]|te|ti|tus|os|vosotros|vuestro|nosotros|nos|usted)\b", texto or "",
                              re.IGNORECASE))
    cercania = (_tope(35 + personas / n * 100 * 20), f"{personas} marca(s) de persona")

    partes = {"LIMPIEZA": limpieza, "PLANTILLAS": plantillas, "CADENCIA": cadencia, "CERCANÍA": cercania}
    total = sum(PESOS[k] * v for k, (v, _) in partes.items())
    peor = min(v for v, _ in partes.values())
    return {"nota": round(total), "veredicto": "APROBADO" if total >= 70 and peor >= 50 else
            ("REVISAR" if total >= 50 else "SUENA A IA"),
            "comprobaciones": {k: {"nota": round(v), "detalle": d} for k, (v, d) in partes.items()},
            "estructuras": trucos}


def humanizar(texto: str, *, respetar: list[str] | None = None) -> dict:
    """Limpia y puntúa de una vez: lo que usan los agentes antes de enseñar un texto al dueño."""
    limpio, cambios = limpiar(texto, respetar=respetar)
    return {"texto": limpio, "cambios": cambios, **revisar(limpio, respetar=respetar)}
