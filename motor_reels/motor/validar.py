"""Las reglas duras del MANUAL_EDITOR.md, comprobadas sobre un montaje antes de renderizar.

Lo que sale como «error» no se renderiza; lo que sale como «aviso» se renderiza pero hay que mirarlo.
Las reglas de criterio (nada literal, la palabra fuerte...) no se pueden medir: las aplica quien escribe el montaje.
"""
import json
import math
import re
from collections import Counter
from pathlib import Path

# Máximos por minuto de reel (tabla de la sección 1 del manual). Un reel de menos de un minuto cuenta como uno.
MAXIMOS = {"efecto": 4, "titular": 2, "tarjeta": 2, "imagen": 2, "transicion": 2, "fondo": 2, "sacudida": 1,
           "completa": 1, "icono": 4, "golpe": 6}
# Iconos de línea que sabe dibujar el motor (remotion/src/iconos.tsx).
ICONOS = {"idea", "rayo", "check", "dinero", "reloj", "subida", "persona", "equipo", "chat", "codigo", "ia", "cohete",
          "objetivo", "mundo", "candado", "flecha", "negocio", "chispa"}
HUECO_MIN = 1.0      # segundos de cara limpia entre el final de un gráfico y el siguiente
PLANO_MIN = 0.4      # un plano más corto no se llega a leer
ZOOM_DISTINTO = 0.1  # dos planos seguidos deben diferenciarse al menos en esto (o en el modo)
# Emoticonos y pictogramas: prohibidos en cualquier texto del reel.
EMOJI = re.compile("[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF️‍⌀-⏿]")
TEXTOS = ("palabra", "texto", "etiqueta", "titular", "pie", "valor", "sufijo", "titulo")
# Un rótulo se lee de un vistazo: seis palabras como mucho. El mensaje de un chat y el pie de una foto no son rótulos.
PALABRAS_ROTULO = 6
NO_ROTULOS = {"chat": {"texto"}, "imagen": {"pie"}}
# Emoticonos según la voz del cliente (kit «voz.emojis»): nunca, pocos (hasta POCOS_EMOJIS por reel) o libre.
POCOS_EMOJIS = 2
# Zona segura de Instagram (1080x1920): ningún texto fuera. La misma que pinta remotion/src/zona.ts.
ZONA_SEGURA = json.loads((Path(__file__).resolve().parents[1] / "zona_segura.json").read_text(encoding="utf-8"))


def cajas_fuera_de_zona() -> list[str]:
    """Las cajas de texto de las piezas que se salen de la zona segura (debe ser ninguna)."""
    z = ZONA_SEGURA["zona"]
    return [n for n, c in ZONA_SEGURA["cajas"].items()
            if c["x0"] < z["x0"] or c["x1"] > z["x1"] or c["y0"] < z["y0"] or c["y1"] > z["y1"]]


def rotulos_de(g: dict) -> list[str]:
    """Los textos del gráfico que son rótulos (lo que se lee en pantalla de un golpe)."""
    fuera = NO_ROTULOS.get(g.get("tipo"), set())
    salida = [str(g[k]) for k in TEXTOS if g.get(k) and k not in fuera]
    if g.get("kicker"):
        salida.append(" ".join(str(k) for k in g["kicker"]))
    for f in g.get("filas", []) + g.get("elementos", []):
        salida += [str(f[k]) for k in TEXTOS if f.get(k)]
    return salida


def palabras_de(texto: str) -> int:
    return len([w for w in re.split(r"\s+", texto.strip()) if w])


def maximo(clave: str, minutos: float) -> int:
    return math.ceil(MAXIMOS[clave] * max(1.0, minutos))


def textos_de(g: dict) -> list[str]:
    """Todo el texto que un gráfico pone en pantalla."""
    salida = [str(g[k]) for k in TEXTOS if g.get(k)] + [str(k) for k in g.get("kicker", [])]
    for f in g.get("filas", []) + g.get("elementos", []):
        salida += [str(f[k]) for k in TEXTOS if f.get(k)]
    return salida


def momentos_de(g: dict) -> list[float]:
    """Los segundos del bruto en que entra cada parte del gráfico."""
    salida = [g["en"]] if "en" in g else []
    salida += [x["en"] for x in g.get("filas", []) + g.get("elementos", []) if "en" in x]
    if g.get("tipo") == "chat":
        salida.append(g["envio"])
    return salida


def validar(m: dict) -> tuple[list[str], list[str]]:
    """`m["reglas"]["emojis"]` (de la voz del cliente) decide los emoticonos; sin dato, ninguno."""
    errores, avisos = [], []
    emojis = (m.get("reglas") or {}).get("emojis", "nunca")
    n_emojis = 0
    planos = m.get("planos", [])
    if not planos:
        return ["El montaje no tiene planos."], []

    usos = Counter()
    graficos = []  # (inicio, fin) en segundos del reel
    at = 0.0
    previo = None
    gancho = planos[0] if planos[0].get("gancho") else None
    # Planos tapados por un efecto a pantalla partida o completa que abarca varios: entre ellos no hay «salto».
    tapados = set()
    for i, p in enumerate(planos):
        g = p.get("grafico") or {}
        if g.get("lugar") in ("partida", "completa"):
            tapados.update(range(i, i + p.get("abarca", 1)))
    for i, p in enumerate(planos):
        nombre = f"plano «{p.get('id', i)}»"
        a, b = p["src"]
        dur = b - a
        if dur < PLANO_MIN:
            errores.append(f"{nombre}: dura {dur:.2f} s; el mínimo es {PLANO_MIN} s.")
        if p.get("gancho") and i > 0:
            errores.append(f"{nombre}: solo el primer plano puede ser el gancho traído de otra parte del bruto.")
        # El orden del discurso no se toca; el gancho es la única excepción (sección 0 del manual).
        if previo and previo is not gancho and a < previo["src"][1] - 0.01:
            errores.append(f"{nombre}: empieza antes de que acabe el anterior. El discurso no se reordena ni se repite.")
        if gancho and p is not gancho and a < gancho["src"][1] - 0.01 and b > gancho["src"][0] + 0.01:
            errores.append(f"{nombre}: repite el tramo del gancho; lo que abre el reel no se vuelve a decir.")
        zoom = p.get("zoom", 1.0)
        if previo and previo["modo"] == p["modo"] and abs(previo.get("zoom", 1.0) - zoom) < ZOOM_DISTINTO \
                and p.get("entrada", "corte") == "corte" and i not in tapados:
            errores.append(f"{nombre}: mismo modo y casi el mismo zoom que el anterior; eso es un salto, no un corte.")
        if p.get("entrada") in ("latigo", "tiras"):
            usos["transicion"] += 1
        if "golpe" in p:
            usos["golpe"] += 1
            if not a <= p["golpe"] <= b:
                errores.append(f"{nombre}: el golpe de zoom cae fuera del plano.")
        if "sacudida" in p:
            usos["sacudida"] += 1
            if not a <= p["sacudida"] <= b:
                errores.append(f"{nombre}: la sacudida cae fuera del plano.")

        g = p.get("grafico")
        if g:
            t = g["tipo"]
            usos[{"chat": "tarjeta", "ficha": "tarjeta"}.get(t, t)] += 1
            if t == "efecto" and g.get("lugar") == "completa":
                usos["completa"] += 1
            if t == "icono" and g.get("icono") not in ICONOS:
                errores.append(f"{nombre}: el icono «{g.get('icono')}» no existe (hay: {', '.join(sorted(ICONOS))}).")
            if t == "efecto" and not g.get("elementos"):
                errores.append(f"{nombre}: el efecto no tiene elementos.")
            n = sum(len(EMOJI.findall(x)) for x in textos_de(g))
            n_emojis += n
            if n and emojis == "nunca":
                errores.append(f"{nombre}: lleva emoticonos y la voz de este cliente no los usa.")
            for x in rotulos_de(g):
                if palabras_de(x) > PALABRAS_ROTULO:
                    errores.append(f"{nombre}: «{x}» tiene {palabras_de(x)} palabras; un rótulo lleva "
                                   f"{PALABRAS_ROTULO} como mucho.")
            momentos = momentos_de(g)
            grupo = planos[i:i + p.get("abarca", 1)]
            for x in momentos:
                if not any(q["src"][0] - 0.05 <= x <= q["src"][1] for q in grupo):
                    errores.append(f"{nombre}: el gráfico entra en {x} s, fuera de su plano o de los que abarca.")
            inicio = at + max(0.0, min(momentos or [a]) - a)
            graficos.append((inicio, at + sum(q["src"][1] - q["src"][0] for q in grupo), nombre))
            if t == "titular" and p["modo"] == "recorte" and g["en"] - a > 0.1:
                avisos.append(f"{nombre}: en un recorte el titular debería verse desde el primer fotograma del plano.")
        at += dur
        previo = p

    minutos = at / 60
    for clave in MAXIMOS:
        if usos[clave] > maximo(clave, minutos):
            errores.append(f"Demasiados recursos de tipo «{clave}»: {usos[clave]} "
                           f"(máximo {maximo(clave, minutos)} en {at:.0f} s).")

    for (_, fin, n1), (ini, _, n2) in zip(graficos, graficos[1:]):
        if ini - fin < HUECO_MIN:
            avisos.append(f"Entre {n1} y {n2} solo hay {max(0, ini - fin):.1f} s de cara limpia (mínimo {HUECO_MIN} s).")

    if emojis == "pocos" and n_emojis > POCOS_EMOJIS:
        errores.append(f"Lleva {n_emojis} emoticonos; con la voz de este cliente, {POCOS_EMOJIS} como mucho por reel.")
    # El gancho se lee desde el primer fotograma (es la portada en el feed): el primer plano abre con su titular,
    # que el render pone entero en el fotograma 0.
    primero = planos[0].get("grafico")
    if not (primero and primero["tipo"] == "titular"):
        errores.append("El primer fotograma no enseña el gancho: el primer plano tiene que abrir con un titular.")
    for n in cajas_fuera_de_zona():
        errores.append(f"La caja de texto «{n}» se sale de la zona segura.")
    return errores, avisos


# ---------------------------------------------------------------- varios reels de un bruto (sección 0 bis)

DURACION_MIN_REEL = 25.0  # segundos: un trozo que no llega no es un reel
SOLAPE_MAX = 0.30         # parte de lo que se dice que pueden compartir dos reels del mismo bruto


def _tramos(m: dict) -> list[tuple[float, float]]:
    return [tuple(p["src"]) for p in m.get("planos", [])]


def _comun(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    return sum(max(0.0, min(x2, y2) - max(x1, y1)) for x1, x2 in a for y1, y2 in b)


def validar_serie(montajes: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Los reels sacados de un mismo bruto: {nombre: montaje}. Cada montaje puede llevar
    "serie": {"tipo": "completo" | "punto" | "idea"}. El completo y los de un solo punto pueden compartir texto
    (es la misma idea a dos escalas), pero no el gancho."""
    errores, avisos = [], []
    duracion = {n: sum(b - a for a, b in _tramos(m)) for n, m in montajes.items()}
    for n, d in duracion.items():
        if d < DURACION_MIN_REEL:
            errores.append(f"«{n}» dura {d:.0f} s; un reel de la serie dura al menos {DURACION_MIN_REEL:.0f} s.")
    nombres = list(montajes)
    for i, n1 in enumerate(nombres):
        for n2 in nombres[i + 1:]:
            m1, m2 = montajes[n1], montajes[n2]
            tipos = {(m1.get("serie") or {}).get("tipo"), (m2.get("serie") or {}).get("tipo")}
            comun = _comun(_tramos(m1), _tramos(m2))
            parte = comun / max(1e-6, min(duracion[n1], duracion[n2]))
            g1, g2 = m1["planos"][0]["src"], m2["planos"][0]["src"]
            if _comun([tuple(g1)], [tuple(g2)]) > 0.5 * min(g1[1] - g1[0], g2[1] - g2[0]):
                errores.append(f"«{n1}» y «{n2}» abren con el mismo gancho; cada reel necesita el suyo.")
            if parte > SOLAPE_MAX and tipos != {"completo", "punto"}:
                errores.append(f"«{n1}» y «{n2}» comparten el {parte:.0%} de lo que se dice (máximo "
                               f"{SOLAPE_MAX:.0%}): se publicaría lo mismo dos veces.")
            elif parte > SOLAPE_MAX:
                avisos.append(f"«{n2}» repite el {parte:.0%} de «{n1}» (completo y de un punto: permitido).")
    return errores, avisos
