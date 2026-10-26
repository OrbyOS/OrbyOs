"""Paso 2: la transcripción partida en frases, la limpieza con IA (tomas falsas, repeticiones, frases cortadas) y,
en el modo «vídeo largo», la elección del mejor trozo. Nunca se cambia el orden de lo que se dice."""
import json
import re

from .. import llm
from ..llm import B, N, S, lista, obj

FIN_DE_FRASE = re.compile(r"[.?!…]$")
PAUSA_DE_FRASE = 0.6
MAX_PALABRAS = 16


def partir(palabras: list[dict]) -> list[dict]:
    """Agrupa las palabras en frases por la puntuación, las pausas largas y un máximo de palabras."""
    frases, actual = [], []
    for i, w in enumerate(palabras):
        actual.append(i)
        siguiente = palabras[i + 1] if i + 1 < len(palabras) else None
        pausa = (siguiente["start"] - w["end"]) if siguiente else 999
        if FIN_DE_FRASE.search(w["word"]) or pausa > PAUSA_DE_FRASE or len(actual) >= MAX_PALABRAS:
            frases.append(actual)
            actual = []
    if actual:
        frases.append(actual)
    salida = []
    for n, indices in enumerate(frases, 1):
        texto = " ".join(palabras[i]["word"].strip() for i in indices)
        salida.append({"id": f"f{n}", "inicio": palabras[indices[0]]["start"], "fin": palabras[indices[-1]]["end"],
                       "palabras": [indices[0], indices[-1]], "texto": texto, "original": texto,
                       "quitada": False, "motivo": ""})
    return salida


def palabras_de(frase: dict, palabras: list[dict]) -> list[dict]:
    """Las palabras de una frase. Si se ha corregido el texto, se reparten sus tiempos entre las palabras nuevas."""
    a, b = frase["palabras"]
    originales = palabras[a:b + 1]
    if frase.get("texto", "").strip() == frase.get("original", "").strip() or not originales:
        return originales
    nuevas = frase["texto"].split()
    if not nuevas:
        return []
    inicio, fin = originales[0]["start"], originales[-1]["end"]
    total = sum(len(p) + 1 for p in nuevas)
    salida, t = [], inicio
    for p in nuevas:
        d = (fin - inicio) * (len(p) + 1) / total
        salida.append({"start": round(t, 3), "end": round(t + d * 0.92, 3), "word": p})
        t += d
    return salida


def palabras_que_quedan(frases: list[dict], palabras: list[dict]) -> list[dict]:
    salida = []
    for f in frases:
        if not f.get("quitada"):
            salida += [{**w, "frase": f["id"]} for w in palabras_de(f, palabras)]
    return salida


# ---------------------------------------------------------------- limpieza con IA

LIMPIEZA = obj(frases=lista(obj(id=S, parte=S, quitar=B, motivo=S)))
TOMAS_LARGAS = 120  # a partir de aquí el bruto suele traer varias tomas de cada parte

REGLAS_LIMPIEZA = """\
Eres un editor de vídeo. Te pasamos la transcripción de un vídeo hablando a cámara, frase a frase y en orden. Puede
ser un bruto de varios minutos en el que la persona graba varias veces cada parte hasta que le sale bien.

1. Agrupa primero las frases por PARTE del guion: frases seguidas que dicen lo mismo con otras palabras o se vuelven
   a grabar son tomas de la misma parte. En «parte», pon la misma etiqueta («P1», «P2»…) a todas las frases de las
   tomas de una parte. Una toma puede ser un bloque de varias frases seguidas.
2. De cada parte grabada varias veces, deja la toma más completa y fluida: sin tropiezos, sin frases a medias y con
   la idea entera. A igualdad, la última. Quita ENTERAS las demás tomas (todas sus frases), no frases sueltas.
   Si te pasamos datos medidos de la voz, úsalos: «tropiezos» (palabras repetidas pegadas; mejor 0), «energia»
   (frente al resto del vídeo; mejor alta) y «pausa_antes».
3. Quita también:
   - frases que se cortan a medias o se corrigen («no, espera», «vuelvo a empezar»);
   - muletillas y frases dirigidas a alguien fuera de cámara («¿así está bien?», «corta», «¿se oye?»);
   - repeticiones de una idea que ya se ha dicho igual justo antes.
No quites contenido solo porque sea largo, ni ideas que aportan algo. Nunca cambies el orden.
En «motivo», una frase corta y concreta («toma 1 de P3: se traba; vale la toma 3», «frase cortada»). Devuelve
todas las frases.
"""


def limpiar(frases: list[dict]) -> list[dict]:
    """Marca las frases que sobran (y de cada parte grabada varias veces, deja la mejor toma). Si la IA falla, se
    deja todo y se avisa en el paso de revisión."""
    material = [{"id": f["id"], "t": round(f["inicio"], 1), "texto": f["texto"],
                 "segundos": round(f["fin"] - f["inicio"], 1),
                 **{k: f[k] for k in ("tropiezos", "energia", "pausa_antes") if k in f}} for f in frases]
    largo = bool(frases) and frases[-1]["fin"] - frases[0]["inicio"] > TOMAS_LARGAS
    datos = llm.json_con_esquema(REGLAS_LIMPIEZA, json.dumps(material, ensure_ascii=False)[:150000], LIMPIEZA,
                                 effort="medium" if largo else "low")
    marcas = {m["id"]: m for m in datos.get("frases", [])}
    for f in frases:
        m = marcas.get(f["id"])
        if not m:
            continue
        if m.get("parte"):
            f["parte"] = m["parte"]
        if m.get("quitar"):
            f["quitada"] = True
            f["motivo"] = m.get("motivo") or "Sobra"
    return frases


# ---------------------------------------------------------------- vídeo largo: el mejor trozo

RECORTE = obj(desde=S, hasta=S, titulo=S, motivo=S, duracion_aproximada=N)

REGLAS_RECORTE = """\
Eres un editor de reels. De la transcripción de un vídeo largo, elige el trozo seguido que mejor funcionaría como
reel de 30 a 75 segundos: que empiece con un gancho (una afirmación fuerte, una pregunta o una situación concreta),
que se entienda sin el resto del vídeo y que cierre una idea. No juntes trozos separados ni cambies el orden.
Devuelve el id de la primera frase («desde») y de la última («hasta»), un título corto para el reel y el motivo.
Algunas frases traen cómo suenan: «energia» (cuánto más fuerte o más flojo que lo normal de este vídeo, de -3 a 3),
«pausa_antes» (segundos callado justo antes: una pausa antes de un remate suele ser un buen momento) y «tropiezos»
(palabras repetidas por un fallo). A igualdad de contenido, prefiere los trozos con energía y sin tropiezos, y nunca
uno que empiece o acabe a media idea.
"""


def medir_voz(wav, frases: list[dict], palabras: list[dict]):
    """Cómo suena cada frase (idea de ai-video-editor, MIT): su energía frente al resto del vídeo, la pausa que hay
    antes y los tropiezos (una palabra repetida casi pegada). Se guarda en cada frase para elegir el trozo."""
    import wave

    import numpy as np
    with wave.open(str(wav), "rb") as w:
        tasa = w.getframerate()
        audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    niveles = []
    for f in frases:
        trozo = audio[int(f["inicio"] * tasa):int(f["fin"] * tasa)]
        niveles.append(20 * np.log10(float(np.sqrt(np.mean(trozo ** 2))) + 1e-6) if len(trozo) else None)
    validos = [n for n in niveles if n is not None]
    media = float(np.mean(validos)) if validos else 0.0
    desviacion = float(np.std(validos)) or 1.0 if validos else 1.0
    for n, (f, nivel) in enumerate(zip(frases, niveles)):
        f["energia"] = round(max(-3.0, min(3.0, (nivel - media) / desviacion)), 1) if nivel is not None else 0.0
        f["pausa_antes"] = round(max(0.0, f["inicio"] - frases[n - 1]["fin"]), 1) if n else 0.0
        a, b = f["palabras"]
        ws = [re.sub(r"[^\wáéíóúñü]", "", w["word"].lower()) for w in palabras[a:b + 1]]
        f["tropiezos"] = sum(1 for x, y in zip(ws, ws[1:]) if x and x == y)


def elegir_trozo(frases: list[dict], *, minimo: float = 25, maximo: float = 80) -> dict:
    """Devuelve {desde, hasta, titulo, motivo} con un trozo seguido de entre `minimo` y `maximo` segundos."""
    material = [{"id": f["id"], "t": round(f["inicio"]), "texto": f["texto"],
                 **{k: f[k] for k in ("energia", "pausa_antes", "tropiezos") if f.get(k)}} for f in frases]
    datos = llm.json_con_esquema(REGLAS_RECORTE, json.dumps(material, ensure_ascii=False)[:150000], RECORTE)
    ids = [f["id"] for f in frases]
    a = ids.index(datos["desde"]) if datos.get("desde") in ids else 0
    b = ids.index(datos["hasta"]) if datos.get("hasta") in ids else len(ids) - 1
    a, b = min(a, b), max(a, b)
    # Se ajusta a la duración: se alarga o se recorta por el final, sin tocar el principio que eligió.
    while b + 1 < len(frases) and frases[b]["fin"] - frases[a]["inicio"] < minimo:
        b += 1
    while b > a and frases[b]["fin"] - frases[a]["inicio"] > maximo:
        b -= 1
    return {"desde": frases[a]["id"], "hasta": frases[b]["id"], "titulo": datos.get("titulo", ""),
            "motivo": datos.get("motivo", "")}


def aplicar_trozo(frases: list[dict], trozo: dict) -> list[dict]:
    """Deja solo las frases del trozo; las de fuera se marcan para poder recuperarlas si hace falta."""
    ids = [f["id"] for f in frases]
    a, b = ids.index(trozo["desde"]), ids.index(trozo["hasta"])
    for i, f in enumerate(frases):
        if i < a or i > b:
            f.update(quitada=True, motivo="Fuera del trozo elegido", fuera=True)
    return frases
