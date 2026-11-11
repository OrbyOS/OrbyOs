"""Ritmo: cuánto se tarda en decir un guion y dónde se puede caer la atención, antes de grabarlo.

Parte el texto en frases y calcula el tiempo de cada una con las palabras por minuto del dueño (salen de su Kit).
Avisa de cuatro cosas: un gancho que tarda en decirse, una frase demasiado larga para decirla sin respirar, un tramo
largo sin nada concreto (ni un número, ni un nombre, ni un ejemplo) y un final que no vuelve a lo que prometía el
principio. Es una estimación por número de palabras: sirve para preparar, no sustituye a grabarlo. Solo se usa con
guion leído; con estructura libre, la duración sale de los bloques.
"""
import re

from .ganchos import palabras

PPM_INICIAL = 160            # palabras por minuto si el Kit no dice otra cosa
GANCHO_SEGUNDOS = 3.5        # la primera frase tiene que caber aquí
FRASE_SEGUNDOS = 5.0         # una frase más larga pide partirla o cambiar de plano dentro
TRAMO_PLANO_SEGUNDOS = 12.0  # tanto tiempo seguido sin nada concreto es donde se va la gente

_CONCRETO = re.compile(r"\d|(?<![.!?¿¡]\s)(?<!^)\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}\b|\b(?:euros?|mil|millones?|doble|triple|"
                       r"mitad|por ciento|por ejemplo|minutos?|horas?|d[ií]as?|semanas?|meses|años?)\b", re.IGNORECASE)
_RELLENO = set("""el la los las un una unos unas y o pero si de del a al en con por para que es son fue era ser lo le les
se su sus tu tus te mi mis me yo tú no ya muy más este esta esto eso esa ese como cuando porque hay está están""".split())


def frases(texto: str) -> list[str]:
    return [f.strip() for f in re.split(r"(?<=[.!?…])\s+|\n+", texto or "") if f.strip()]


def _claves(frase: str) -> set[str]:
    return {w.lower() for w in palabras(frase) if len(w) > 3 and w.lower() not in _RELLENO}


def medir(texto: str, *, ppm: float | None = None, objetivo: float | None = None) -> dict:
    """Las frases con su tiempo («golpes»), la duración total, los avisos y si el final vuelve al principio.
    `objetivo`: segundos que debería durar."""
    ppm = float(ppm or PPM_INICIAL)
    pps = ppm / 60
    golpes, reloj = [], 0.0
    for i, f in enumerate(frases(texto), 1):
        dura = len(palabras(f)) / pps
        golpes.append({"n": i, "empieza": round(reloj, 1), "dura": round(dura, 1), "texto": f,
                       "concreto": bool(_CONCRETO.search(f))})
        reloj += dura
    if not golpes:
        return {"ppm": ppm, "segundos": 0, "golpes": [], "avisos": [], "fallos": ["No hay nada que decir."], "bucle": False}
    fallos, avisos = [], []
    if golpes[0]["dura"] > GANCHO_SEGUNDOS:
        fallos.append(f"El gancho tarda {golpes[0]['dura']:.1f} s en decirse: que quepa en "
                      f"{int(GANCHO_SEGUNDOS * pps)} palabras.")
    largas = [g["n"] for g in golpes[1:] if g["dura"] > FRASE_SEGUNDOS]
    if largas:
        avisos.append(f"Frase(s) {', '.join(map(str, largas))}: más de {FRASE_SEGUNDOS:.0f} s seguidos. Pártela(s) o que "
                      "cambie el plano dentro.")
    plano, desde = 0.0, None
    for g in golpes:
        if g["concreto"]:
            plano, desde = 0.0, None
            continue
        desde = desde or g
        plano += g["dura"]
        if plano > TRAMO_PLANO_SEGUNDOS:
            avisos.append(f"Desde el segundo {desde['empieza']:.0f}, más de {TRAMO_PLANO_SEGUNDOS:.0f} s sin nada concreto: "
                          "mete un ejemplo, un nombre o un dato.")
            plano, desde = float("-inf"), None   # un aviso por tramo
    bucle = bool(_claves(golpes[0]["texto"]) & _claves(golpes[-1]["texto"]))
    if not bucle and len(golpes) > 2:
        avisos.append("La última frase no recoge nada de la primera: volver a una palabra del gancho cierra el vídeo y "
                      "anima a verlo otra vez.")
    if objetivo:
        sobra = reloj - objetivo
        if sobra > objetivo * 0.15:
            avisos.append(f"Dura {sobra:.0f} s más de lo previsto: sobran unas {int(sobra * pps)} palabras.")
        elif -sobra > objetivo * 0.3:
            avisos.append(f"Dura {-sobra:.0f} s menos de lo previsto. Si se entiende, corto está bien.")
    return {"ppm": ppm, "segundos": round(reloj), "golpes": golpes, "avisos": avisos, "fallos": fallos, "bucle": bucle}
