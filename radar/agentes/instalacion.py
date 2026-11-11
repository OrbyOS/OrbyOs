"""Las claves y ajustes de la instalación, pegados desde la propia app (Administración → Claves y ajustes).

Se guardan en el archivo .env de la instalación y se aplican al momento. Las claves secretas no se vuelven a enseñar:
solo se ve si están puestas. Así, quien instala Radar no tiene que tocar ningún archivo.
"""
import os

from dotenv import set_key

from .. import config

# (variable, etiqueta, ayuda, secreta)
CLAVES = [
    ("RADAR_MOTOR", "Cómo usa Claude la app",
     "«api»: con una clave de console.anthropic.com (pagas por uso). «claude_code»: con tu plan Pro o Max a través de "
     "Claude Code instalado en este ordenador.", False),
    ("ANTHROPIC_API_KEY", "Clave de la API de Claude", "console.anthropic.com → API Keys. Solo con el motor «api».", True),
    ("CLAUDE_CODE_OAUTH_TOKEN", "Token de tu plan de Claude",
     "En una terminal: `claude setup-token`, y pega aquí lo que salga. Solo con el motor «claude_code».", True),
    ("APIFY_TOKEN", "Token de Apify", "apify.com → Settings → API & Integrations. Para leer reels, TikToks y anuncios.", True),
    ("YOUTUBE_API_KEY", "Clave de YouTube", "Google Cloud → YouTube Data API v3 → Credenciales.", True),
    ("ZERNIO_API_KEY", "Clave de Zernio (para todos los negocios)",
     "Opcional: cada negocio puede poner la suya en Publicación.", True),
    ("MANYCHAT_API_KEY", "Clave de ManyChat", "ManyChat → Settings → API (necesita el plan Pro). Para los DMs y las "
     "palabras clave de Instagram.", True),
    ("RADAR_IG_APP_ID", "Identificador de la app de Instagram",
     "developers.facebook.com → tu app → Instagram → Configuración de la API con el inicio de sesión de Instagram. "
     "Con él, cada negocio conecta su Instagram con un botón.", False),
    ("RADAR_IG_APP_SECRETO", "Clave secreta de la app de Instagram", "En la misma página, «Mostrar».", True),
    ("RADAR_URL_PUBLICA", "Dirección pública de la app",
     "Si la app está en un servidor (https://…): con ella las guías se abren desde un DM y ManyChat le pasa los mensajes.", False),
    ("RADAR_PRESUPUESTO_APIFY", "Presupuesto de Apify al mes por negocio ($)", "15 por defecto.", False),
    ("RADAR_PRESUPUESTO_CLAUDE", "Presupuesto de Claude al mes por negocio ($)",
     "40 por defecto. El piloto automático se para al llegar.", False),
]
MOTORES = {"api": "Clave de la API", "claude_code": "Mi plan de Claude (Claude Code)"}
ARCHIVO = config.Path(os.getenv("RADAR_ENV_FILE") or config.APP_DIR / ".env")


def estado() -> list[dict]:
    salida = []
    for var, etiqueta, ayuda, secreta in CLAVES:
        valor = os.getenv(var, "").strip()
        salida.append({"var": var, "etiqueta": etiqueta, "ayuda": ayuda, "secreta": secreta, "puesta": bool(valor),
                       "valor": "" if secreta else valor})
    return salida


def guardar(cambios: dict[str, str]) -> list[str]:
    """Guarda lo que llega (lo vacío no toca lo que había) y lo aplica sin reiniciar. Devuelve qué se ha cambiado."""
    validas = {c[0]: c for c in CLAVES}
    hechos = []
    ARCHIVO.touch(exist_ok=True)
    for var, valor in cambios.items():
        if var not in validas:
            continue
        valor = (valor or "").strip()
        if not valor:
            continue
        if var == "RADAR_MOTOR" and valor not in MOTORES:
            continue
        if var.startswith("RADAR_PRESUPUESTO"):
            try:
                valor = str(max(0.0, float(valor.replace(",", "."))))
            except ValueError:
                continue
        if var == "RADAR_URL_PUBLICA" and not valor.startswith("https://"):
            continue
        set_key(str(ARCHIVO), var, valor, quote_mode="never")
        os.environ[var] = valor
        hechos.append(validas[var][1])
    _aplicar()
    return hechos


def _aplicar():
    """Los valores que algunos módulos leen al arrancar."""
    from . import analista, piloto
    config.URL_PUBLICA = os.getenv("RADAR_URL_PUBLICA", "").strip().rstrip("/")
    for modulo, atributo, var in ((analista, "PRESUPUESTO_APIFY_MES", "RADAR_PRESUPUESTO_APIFY"),
                                  (piloto, "PRESUPUESTO_CLAUDE_MES", "RADAR_PRESUPUESTO_CLAUDE")):
        if os.getenv(var):
            setattr(modulo, atributo, float(os.getenv(var)))
