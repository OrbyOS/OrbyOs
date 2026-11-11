"""Configuración: claves del proyecto (archivo .env), nombre de la app, planes y conectores."""
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent.parent
load_dotenv(APP_DIR / ".env")
# En un servidor, las claves pegadas desde la app se guardan en la carpeta de datos (RADAR_ENV_FILE) para no perderlas.
if os.getenv("RADAR_ENV_FILE"):
    load_dotenv(os.getenv("RADAR_ENV_FILE"), override=True)

DATA_DIR = Path(os.getenv("RADAR_DATA_DIR") or APP_DIR / "data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "radar.db"
EDICIONES_DIR = DATA_DIR / "ediciones"
EDICIONES_DIR.mkdir(exist_ok=True)
FUENTES_DIR = Path(__file__).resolve().parent / "static" / "fuentes"

# El nombre de la app: se cambia aquí (o con APP_NOMBRE) y sale en toda la app.
APP_NOMBRE = os.getenv("APP_NOMBRE", "Orby")
MODEL = os.getenv("RADAR_MODEL", "claude-opus-5-5")
PAIS = os.getenv("RADAR_PAIS", "ES")
IDIOMA = os.getenv("RADAR_IDIOMA", "es")
META_GRAPH_VERSION = os.getenv("META_GRAPH_VERSION", "v23.0")
# La app muestra e interpreta; de momento no propone ideas ni guiones (RADAR_IDEAS=1 los vuelve a activar).
MOSTRAR_IDEAS = os.getenv("RADAR_IDEAS", "0") == "1"
# El editor de reels que se vende aparte (sin negocio). De momento está apagado: la edición va dentro del SaaS completo.
EDITOR_PUBLICO = os.getenv("RADAR_EDITOR_PUBLICO", "0") == "1"
# Registro abierto: cualquiera se crea su cuenta (con sus propias claves). Si no, las cuentas las da de alta quien
# administra.
REGISTRO_ABIERTO = os.getenv("RADAR_REGISTRO_ABIERTO", "0") == "1"
# Correos que entran como administradores (separados por comas). El primer usuario también lo es.
ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "").split(",") if e.strip()}
# La dirección pública de la app (https://…): con ella, las guías de las palabras clave se pueden abrir desde un DM.
URL_PUBLICA = os.getenv("RADAR_URL_PUBLICA", "").strip().rstrip("/")
# Cookie de sesión con «Secure» cuando la app se sirve por https.
COOKIE_SEGURA = os.getenv("RADAR_COOKIE_SEGURA", "0") == "1"

WHISPER_MODELO = os.getenv("RADAR_WHISPER", "small")
FFMPEG = os.getenv("FFMPEG") or shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FFPROBE = os.getenv("FFPROBE") or shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"
MAX_SEGUNDOS_BRUTO = int(os.getenv("RADAR_MAX_SEGUNDOS", "420"))  # brutos de 4-5 min con varias tomas
MAX_SEGUNDOS_LARGO = int(os.getenv("RADAR_MAX_SEGUNDOS_LARGO", "3600"))  # modo «recortar un vídeo largo»
MAX_MB_BRUTO = int(os.getenv("RADAR_MAX_MB", "1500"))
MAX_MB_LARGO = int(os.getenv("RADAR_MAX_MB_LARGO", "6000"))
MARCAS_DIR = DATA_DIR / "marcas"
MARCAS_DIR.mkdir(exist_ok=True)


@dataclass(frozen=True)
class Plan:
    clave: str
    nombre: str
    negocios: int          # negocios propios o, en una agencia, clientes
    analisis_mes: int
    actualizaciones_mes: int
    ediciones_mes: int


# La cuota está por definir: estos límites sirven para controlar el gasto mientras tanto.
PLANES = {
    # Gratis: con su propia clave de Claude y sin lo que cuesta a la instalación (Apify, edición, publicación…):
    # ver radar/planes.py.
    "gratis": Plan("gratis", "Gratis", 1, 0, 0, 0),
    "prueba": Plan("prueba", "Prueba", 1, 2, 6, 3),
    "prueba_agencia": Plan("prueba_agencia", "Prueba agencia", 3, 4, 12, 6),
    "growth": Plan("growth", "Growth", 2, 8, 30, 20),
    "agencia": Plan("agencia", "Agencia", 15, 40, 120, 60),
    "interno": Plan("interno", "Interno", 999, 999, 999, 999),
    # El editor de reels se vende aparte: solo vídeos editados, sin análisis.
    "editor_prueba": Plan("editor_prueba", "Editor · prueba", 0, 0, 0, 2),
    "editor": Plan("editor", "Editor", 0, 0, 0, 20),
}
TIPOS_CUENTA = {"negocio": "Negocio", "agencia": "Agencia", "editor": "Editor de reels"}
# Si hay una URL de calendario (Calendly, Cal.com…), la landing ofrece reservar la llamada al enviar el formulario.
CALENDARIO_URL = os.getenv("RADAR_CALENDARIO_URL", "").strip()


def plan_inicial(tipo: str) -> str:
    if tipo == "editor":
        return os.getenv("RADAR_PLAN_INICIAL_EDITOR", "editor_prueba")
    return os.getenv("RADAR_PLAN_INICIAL_AGENCIA", "prueba_agencia") if tipo == "agencia" \
        else os.getenv("RADAR_PLAN_INICIAL", "prueba")


def plan(clave: str | None) -> Plan:
    return PLANES.get(clave or "", PLANES["prueba"])


@dataclass(frozen=True)
class Conector:
    clave: str
    nombre: str
    activo: bool
    para_que: str
    como_activarlo: str


def _hay(*variables: str) -> bool:
    return all(os.getenv(v, "").strip() for v in variables)


def claude_activo() -> bool:
    from . import claves
    if claves.propia("ANTHROPIC_API_KEY"):  # la clave de este negocio: siempre por la API
        return True
    if os.getenv("RADAR_MOTOR", "api").strip() == "claude_code" and (claves.compartidas() or not claves.actual()):
        return bool(os.getenv("CLAUDE_BIN", "").strip() or shutil.which("claude"))  # el plan de quien instala
    # El SDK también acepta ANTHROPIC_AUTH_TOKEN o un perfil de `ant auth login`.
    return bool(claves.clave("ANTHROPIC_API_KEY")) or (
        (claves.compartidas() or not claves.actual()) and _hay("ANTHROPIC_AUTH_TOKEN"))


def youtube_activo() -> bool:
    from . import claves
    return bool(claves.clave("YOUTUBE_API_KEY"))


def meta_ads_activo() -> bool:
    return _hay("META_AD_LIBRARY_TOKEN")


def apify_activo() -> bool:
    from . import claves
    return bool(claves.clave("APIFY_TOKEN"))


def instagram_activo() -> bool:
    return _hay("INSTAGRAM_TOKEN", "INSTAGRAM_USER_ID")


def ffmpeg_activo() -> bool:
    return Path(FFMPEG).exists() and Path(FFPROBE).exists()


MOTOR_REELS_DIR = Path(__file__).resolve().parent.parent / "motor_reels"


def cola_renders() -> Path | None:
    """La carpeta de la cola de renders (RADAR_COLA_RENDERS), si el servidor tiene un worker aparte que renderiza
    (motor_reels/cola.py). Sin ella, el motor renderiza en este mismo proceso, si puede."""
    c = os.environ.get("RADAR_COLA_RENDERS", "").strip()
    return Path(c) if c else None


def motor_reels_local() -> bool:
    """Este proceso puede renderizar: Node y las dependencias de Remotion instaladas."""
    return ffmpeg_activo() and shutil.which("npx") is not None and (MOTOR_REELS_DIR / "remotion" / "node_modules").exists()


def motor_reels_activo() -> bool:
    """El motor de reels (estilo «De editor») se puede usar: con el worker de renders o renderizando aquí."""
    return (ffmpeg_activo() and cola_renders() is not None) or motor_reels_local()


def conectores() -> list[Conector]:
    """Cuentas del proyecto. Solo las ve el administrador: el cliente no conecta nada."""
    return [
        Conector(
            "claude", "Claude (IA)", claude_activo(),
            "Piensa y escribe: kit de marca, desmontajes, planes, guiones, DMs, post-mortems e informes.",
            "Administración → Claves y ajustes: tu clave de la API o tu plan de Claude.",
        ),
        Conector(
            "youtube", "YouTube", youtube_activo(),
            "Los Shorts de tu canal y de los canales que sigue el analista.",
            "Google Cloud → «YouTube Data API v3» → Credenciales → Clave de API. Ponla en YOUTUBE_API_KEY.",
        ),
        Conector(
            "apify", "Apify", apify_activo(),
            "Los reels y TikToks de tus cuentas y de tu competencia.",
            "apify.com → Settings → API & Integrations. Ponlo en APIFY_TOKEN.",
        ),
        Conector(
            "ffmpeg", "Motor de edición (ffmpeg)", ffmpeg_activo(),
            "Corta, reencuadra a 9:16 y quema los subtítulos de las tomas que subes en Producción.",
            "Instala ffmpeg en el servidor (brew install ffmpeg o apt install ffmpeg).",
        ),
    ]
