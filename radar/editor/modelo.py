"""Lo que maneja el editor: modos de entrada, tipos de bloque, estilos y ajustes de marca."""
import copy
import re

MODOS = {
    "camara": {"nombre": "Hablando a cámara", "texto": "Sube el vídeo tal cual lo grabaste: quitamos silencios y tomas falsas y le ponemos los efectos."},
    "voz": {"nombre": "Solo tu voz", "texto": "Sube un audio (o un vídeo del que solo vale la voz): montamos el reel con texto en movimiento, tus capturas y tu color."},
    "largo": {"nombre": "Recortar un vídeo largo", "texto": "Sube un vídeo de YouTube, un directo o un podcast: elegimos el mejor trozo y lo convertimos en reel."},
}

TIPOS_BLOQUE = {
    "subtitulo": "Subtítulo",
    "gancho": "Gancho",
    "choque": "Palabra gigante",
    "lista": "Lista",
    "zoom": "Zoom",
    "pantalla": "Pantalla partida",
    "imagen": "Imagen a pantalla completa",
    "cinetico": "Texto en movimiento",
}
# Bloques que llaman mucho la atención: si hay demasiados, se pierde la sorpresa.
EFECTOS_FUERTES = {"choque", "lista", "pantalla", "imagen"}
TIPOS_POR_MODO = {
    "camara": ["subtitulo", "gancho", "choque", "lista", "zoom", "pantalla"],
    "largo": ["subtitulo", "gancho", "choque", "lista", "zoom", "pantalla"],
    "voz": ["cinetico", "gancho", "choque", "lista", "imagen"],
}

ESTILOS = {
    "impacto": {
        "nombre": "Impacto",
        "texto": "Ritmo rápido, subtítulos grandes con la palabra que suena resaltada, zooms y efectos con sonido.",
        "silencio_max": 0.25, "efectos_max": 4, "zoom_suave": True, "sonidos": True,
        "subtitulos": {"tamano_pct": 110, "posicion": "abajo", "mayusculas": True, "fuente": "condensada",
                       "resalta": True, "contorno": True, "palabras": 3},
    },
    "editorial": {
        "nombre": "Editorial",
        "texto": "Limpio y pausado: subtítulos discretos, pocos efectos y sonidos suaves.",
        "silencio_max": 0.45, "efectos_max": 2, "zoom_suave": True, "sonidos": True,
        "subtitulos": {"tamano_pct": 90, "posicion": "abajo", "mayusculas": False, "fuente": "clasica",
                       "resalta": False, "contorno": False, "palabras": 4},
    },
    "natural": {
        "nombre": "Natural",
        "texto": "Casi sin efectos: sin silencios, con subtítulos y algún zoom.",
        "silencio_max": 0.4, "efectos_max": 1, "zoom_suave": True, "sonidos": False,
        "subtitulos": {"tamano_pct": 100, "posicion": "abajo", "mayusculas": False, "fuente": "redonda",
                       "resalta": True, "contorno": True, "palabras": 3},
    },
    "competencia": {
        "nombre": "El de tu competencia",
        "texto": "El ritmo y los subtítulos medidos en los reels que más destacan en tu competencia.",
        "silencio_max": 0.4, "efectos_max": 3, "zoom_suave": True, "sonidos": True,
        "subtitulos": {"tamano_pct": 100, "posicion": "abajo", "mayusculas": False, "fuente": "redonda",
                       "resalta": True, "contorno": True, "palabras": 3},
    },
    # Lo monta el motor de reels (motor_reels, en Remotion) con el kit visual del negocio y las reglas de su
    # MANUAL_EDITOR.md. No usa los bloques ni los ajustes de subtítulos de los demás estilos.
    "editor": {
        "nombre": "De editor",
        "texto": "Como un editor profesional con tu kit visual: cambios de plano, titulares por detrás de ti, tarjetas y transiciones medidas.",
        "motor": True, "modos": ["camara", "largo"],
        "silencio_max": 0.3, "efectos_max": 0, "zoom_suave": False, "sonidos": True,
        "subtitulos": {"tamano_pct": 100, "posicion": "abajo", "mayusculas": False, "fuente": "clasica",
                       "resalta": True, "contorno": False, "palabras": 3},
    },
}

# El paquete de movimiento de cada marca: cómo entra y se mueve cada gráfico. Se elige en el onboarding (Kit de marca
# → Identidad visual) y Monti lo usa en todos los reels. El primero de cada lista es el de la casa.
MOVIMIENTOS = {
    "gancho": {
        "pop": "Palabra a palabra, con un pequeño rebote",
        "subida": "Cada línea sube y se enfoca",
        "fundido": "Aparece entero con un fundido lento",
    },
    "choque": {
        "golpe": "Cae desde muy grande y rebota",
        "foco": "Aparece desenfocada y se enfoca, sin rebote",
        "seco": "Entra de golpe, sin animación",
    },
    "lista": {
        "circulos": "Número dentro de un círculo de color",
        "numeros": "Número grande en color, sin círculo",
        "filete": "Una línea fina de color a la izquierda",
    },
    "subtitulos": {
        "corte": "Cambian de golpe",
        "pop": "Cada bloque entra con un pequeño salto",
    },
    "fondo_texto": {
        "sombra": "Sombra suave detrás de las letras",
        "velo": "Velo oscuro y difuso detrás del texto",
    },
    "zooms": {
        "suaves": "Acercamientos suaves",
        "marcados": "Acercamientos rápidos y marcados",
        "sin": "Sin acercamientos",
    },
}
MOVIMIENTO_BASE = {k: next(iter(v)) for k, v in MOVIMIENTOS.items()}
# Cuánto se acerca la cámara: (zoom de remarcar, zoom suave en los tramos quietos).
ZOOMS = {"suaves": (0.14, 0.08), "marcados": (0.22, 0.12), "sin": (0.0, 0.0)}


def movimiento(datos: dict | None) -> dict:
    """El paquete completo y válido: lo que no se haya elegido (o no exista) va con el de la casa."""
    datos = datos or {}
    return {k: datos.get(k) if datos.get(k) in MOVIMIENTOS[k] else MOVIMIENTO_BASE[k] for k in MOVIMIENTOS}


AJUSTES_BASE = {
    "estilo": "impacto",
    "color": "#2F6BFF",
    "color_texto": "#FFFFFF",
    "logo": "",               # archivo del logo del negocio (en la carpeta del negocio)
    "logo_esquina": False,    # logo pequeño arriba durante todo el reel
    "cierre": True,           # tarjeta final con el logo (si hay logo)
    "sonidos": True,
    "subtitulos": dict(ESTILOS["impacto"]["subtitulos"]),
    "movimiento": dict(MOVIMIENTO_BASE),
}

HEX = re.compile(r"#[0-9A-Fa-f]{6}")


def es_fuente_de_marca(valor) -> bool:
    """«marca:<ruta>»: una tipografía subida al Kit que existe en disco."""
    from pathlib import Path
    valor = str(valor or "")
    return valor.startswith("marca:") and Path(valor[6:]).suffix.lower() in (".ttf", ".otf") and Path(valor[6:]).exists()


def ajustes(datos: dict | None, *, estilo_competencia: dict | None = None) -> dict:
    """Ajustes completos: los del estilo elegido y, encima, lo que haya cambiado el usuario."""
    datos = copy.deepcopy(datos or {})
    estilo = datos.get("estilo") if datos.get("estilo") in ESTILOS else AJUSTES_BASE["estilo"]
    base = copy.deepcopy(ESTILOS[estilo])
    if estilo == "competencia" and estilo_competencia:
        sub = estilo_competencia.get("subtitulos") or {}
        base["subtitulos"].update({
            "posicion": sub.get("posicion", "abajo"), "mayusculas": bool(sub.get("mayusculas")),
            "fuente": sub.get("fuente", "redonda"), "resalta": bool(sub.get("resalta_palabra", True)),
            "contorno": bool(sub.get("contorno", True)), "palabras": int(sub.get("palabras_por_bloque") or 3),
        })
        base["silencio_max"] = {"rapido": 0.25, "medio": 0.4, "pausado": 0.6}.get(estilo_competencia.get("ritmo"), 0.4)
    salida = {**copy.deepcopy(AJUSTES_BASE), "estilo": estilo, "silencio_max": base["silencio_max"],
              "efectos_max": base["efectos_max"], "zoom_suave": base["zoom_suave"], "sonidos": base["sonidos"]}
    salida["subtitulos"] = {**base["subtitulos"], **(datos.get("subtitulos") or {})}
    salida["movimiento"] = movimiento(datos.get("movimiento"))
    for clave in ("color", "color_texto", "logo", "logo_esquina", "cierre", "sonidos"):
        if clave in datos and datos[clave] is not None:
            salida[clave] = datos[clave]
    for clave in ("color", "color_texto"):
        if not HEX.fullmatch(str(salida[clave] or "")):
            salida[clave] = AJUSTES_BASE[clave]
    s = salida["subtitulos"]
    s["tamano_pct"] = min(180, max(60, int(s.get("tamano_pct") or 100)))
    s["palabras"] = min(6, max(1, int(s.get("palabras") or 3)))
    if s.get("posicion") not in ("arriba", "centro", "abajo"):
        s["posicion"] = "abajo"
    if s.get("fuente") not in ("condensada", "redonda", "clasica") and not es_fuente_de_marca(s.get("fuente")):
        s["fuente"] = "redonda"
    return salida


ESTILO_SIN_MOTOR = "natural"  # el que se usa cuando un reel «De editor» no se puede montar con el motor


def es_de_monti(datos: dict | None) -> bool:
    """Ediciones de la cola de Monti (agentes/produccion.py): llevan «produccion» en sus datos."""
    return bool(datos) and (bool(datos.get("automatico")) or "produccion" in datos)


def usa_motor(ajustes_: dict, modo: str, datos: dict | None = None) -> bool:
    """Si este reel lo monta el motor de reels: estilo «De editor», en un modo que admite y con el motor instalado
    en este servidor. Monti solo lo usa con el worker de renders (config.cola_renders): renderizar con Remotion desde
    el proceso web ahogaría el servidor."""
    from .. import config
    e = ESTILOS.get(ajustes_.get("estilo"), {})
    return (bool(e.get("motor")) and modo in e.get("modos", [])
            and (not es_de_monti(datos) or config.cola_renders() is not None) and config.motor_reels_activo())


def cambios_de_ajustes(ajustes_: dict) -> dict:
    """Lo que se guarda: solo lo que el usuario puede cambiar (no lo que se deduce del estilo)."""
    return {k: ajustes_[k] for k in ("estilo", "color", "color_texto", "logo", "logo_esquina", "cierre", "sonidos",
                                     "subtitulos", "movimiento") if k in ajustes_}
