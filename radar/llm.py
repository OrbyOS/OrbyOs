"""Llamadas a Claude: investigación con búsqueda web y respuestas en JSON con esquema."""
import base64
import json
import os
import threading
import time

import anthropic

from . import gasto
from .config import MODEL, claude_activo

# Si un clasificador de seguridad rechaza la petición, la API la repite en el modelo
# que Anthropic recomienda para ese caso, dentro de la misma llamada.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
WEB_SEARCH = {"type": "web_search_20260209", "name": "web_search", "max_uses": 6}
MAX_REANUDACIONES = 5


class ErrorIA(Exception):
    """Error de la IA con un mensaje que se puede enseñar en el informe."""

    def __init__(self, *args):
        super().__init__(*args)
        _fallos.ultimo = str(self)  # para saber si un paso ha perdido la parte de IA aunque siga adelante


_fallos = threading.local()


def empezar_paso():
    _fallos.ultimo = None


def fallo_del_paso() -> str | None:
    return getattr(_fallos, "ultimo", None)


_clientes: dict[str, anthropic.Anthropic] = {}


def _cli() -> anthropic.Anthropic:
    """Un cliente por clave: cada negocio usa (y paga) la suya."""
    from . import claves
    clave = claves.clave("ANTHROPIC_API_KEY")
    if clave not in _clientes:
        # Las claves que no pertenecen a un workspace necesitan decir en cuál trabajar.
        workspace = os.getenv("ANTHROPIC_WORKSPACE_ID", "").strip() if not claves.propia("ANTHROPIC_API_KEY") else ""
        cabeceras = {"anthropic-workspace-id": workspace} if workspace else None
        _clientes[clave] = anthropic.Anthropic(api_key=clave or None, default_headers=cabeceras)
    return _clientes[clave]


# ---------------------------------------------------------------- motor: la API o tu plan de Claude (Claude Code)

def motor() -> str:
    """«api» (clave de console.anthropic.com) o «claude_code» (el plan Pro/Max de quien instala Radar, a través de la
    línea de comandos de Claude Code ya iniciada o con CLAUDE_CODE_OAUTH_TOKEN de `claude setup-token`)."""
    from . import claves
    if claves.propia("ANTHROPIC_API_KEY") or (claves.actual() and not claves.compartidas()):
        return "api"  # con la clave de cada negocio, siempre la API (el plan de Claude es de quien instala)
    return "claude_code" if os.getenv("RADAR_MOTOR", "api").strip() == "claude_code" else "api"


def claude_bin() -> str:
    import shutil
    return os.getenv("CLAUDE_BIN", "").strip() or shutil.which("claude") or ""


def disponible() -> bool:
    return bool(claude_bin()) if motor() == "claude_code" else claude_activo()


def _claude_code(system: str, peticion: str, *, esquema: dict | None = None, herramientas: str = "",
                 turnos: int = 6, timeout: int = 900) -> dict:
    """Una llamada a `claude -p` sin herramientas (o solo con las que se digan) y sin sesión guardada."""
    import subprocess
    orden = [claude_bin(), "-p", "--output-format", "json", "--system-prompt", system, "--tools", herramientas,
             "--disallowedTools", "mcp__*", "--no-session-persistence", "--max-turns", str(turnos),
             "--permission-mode", "dontAsk"]
    if herramientas:
        orden += ["--allowedTools", herramientas]
    if esquema:
        orden += ["--json-schema", json.dumps(esquema)]
    if os.getenv("RADAR_MODELO_CLAUDE_CODE", "").strip():
        orden += ["--model", os.getenv("RADAR_MODELO_CLAUDE_CODE").strip()]
    try:
        r = subprocess.run(orden, input=peticion, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as e:
        raise ErrorIA("No encuentro Claude Code en este ordenador. Instálalo o pon la clave de la API.") from e
    except subprocess.TimeoutExpired as e:
        raise ErrorIA("Claude ha tardado demasiado en responder.") from e
    try:
        datos = json.loads(r.stdout or "{}")
    except json.JSONDecodeError as e:
        raise ErrorIA(f"Claude Code no ha devuelto una respuesta que se pueda leer: {(r.stderr or r.stdout)[:200]}") from e
    if datos.get("is_error") or datos.get("subtype") not in (None, "success"):
        motivo = datos.get("result") or datos.get("subtype") or r.stderr[:200]
        if "login" in str(motivo).lower() or "auth" in str(motivo).lower():
            raise ErrorIA("Claude Code no tiene la sesión iniciada: ejecuta `claude setup-token` y pega el token en Ajustes.")
        raise ErrorIA(f"Claude Code no ha podido responder: {str(motivo)[:200]}")
    gasto.sumar_llamada()
    return datos


# --- Ayudas para escribir esquemas JSON compatibles con salidas estructuradas ---
S = {"type": "string"}
N = {"type": "number"}
B = {"type": "boolean"}


def obj(**props) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def lista(items: dict) -> dict:
    return {"type": "array", "items": items}


REINTENTOS = (4, 12)  # segundos de espera antes de cada reintento


def _llamar(**kwargs):
    for espera in (*REINTENTOS, None):
        try:
            return _llamar_una_vez(**kwargs)
        except _Reintentable:
            if espera is None:
                raise ErrorIA("El servicio de Claude está saturado ahora mismo. Prueba de nuevo en unos minutos.")
            time.sleep(espera)


class _Reintentable(Exception):
    """Un corte del servicio (sobrecarga, error a mitad de la respuesta): se vuelve a intentar."""


def _llamar_una_vez(**kwargs):
    try:
        with _cli().beta.messages.stream(
            model=MODEL,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            **kwargs,
        ) as stream:
            resp = stream.get_final_message()
        gasto.sumar_claude(resp.usage)
        return resp
    except anthropic.APIStatusError as e:
        # Un error con estado 200 llega dentro del stream (por ejemplo, «overloaded_error»).
        if e.status_code in (200, 429, 500, 502, 503, 504, 529):
            raise _Reintentable() from e
        return _traducir(e)
    except anthropic.APIConnectionError as e:
        raise _Reintentable() from e


def _traducir(e: Exception):
    try:
        raise e
    except anthropic.AuthenticationError as e:
        raise ErrorIA("La clave de Claude no es válida. Revisa ANTHROPIC_API_KEY en el archivo .env.") from e
    except anthropic.PermissionDeniedError as e:
        raise ErrorIA("La clave de Claude no tiene permiso para este modelo o función.") from e
    except anthropic.RateLimitError as e:
        raise ErrorIA("Claude ha llegado al límite de uso. Prueba de nuevo en unos minutos.") from e
    except anthropic.BadRequestError as e:
        if "credit balance" in str(e.message):
            raise ErrorIA(
                "Tu cuenta de Anthropic no tiene saldo. Añade créditos en console.anthropic.com → Settings → Billing."
            ) from e
        if "anthropic-workspace-id" in str(e.message):
            raise ErrorIA(
                "La clave de Claude no pertenece a ningún workspace. Crea la clave dentro de un workspace en la "
                "consola de Anthropic, o pon el ID del workspace en ANTHROPIC_WORKSPACE_ID en el archivo .env."
            ) from e
        raise ErrorIA(f"Claude ha rechazado la petición: {e.message}") from e
    except anthropic.APIStatusError as e:
        raise ErrorIA(f"Error del servicio de Claude ({e.status_code}). Prueba de nuevo más tarde.") from e
    except anthropic.APIConnectionError as e:
        raise ErrorIA("No hay conexión con Claude. Revisa la conexión a internet.") from e


def _comprobar(resp):
    if resp.stop_reason == "refusal":
        raise ErrorIA("Claude ha rechazado esta petición por sus normas de seguridad.")
    if resp.stop_reason == "max_tokens":
        raise ErrorIA("La respuesta de Claude se ha cortado por longitud.")


def _texto(resp) -> str:
    return "\n".join(b.text for b in resp.content if b.type == "text").strip()


def investigar(system: str, peticion: str, *, effort: str = "medium") -> str:
    """Investiga en la web y devuelve un texto con lo encontrado, citando las URL."""
    if not disponible():
        raise ErrorIA("Falta la clave de Claude.")
    if motor() == "claude_code":
        return str(_claude_code(system, peticion, herramientas="WebSearch,WebFetch", turnos=30).get("result") or "").strip()
    mensajes = [{"role": "user", "content": peticion}]
    for _ in range(MAX_REANUDACIONES + 1):
        resp = _llamar(
            max_tokens=32000,
            system=system,
            messages=mensajes,
            tools=[WEB_SEARCH],
            output_config={"effort": effort},
        )
        if resp.stop_reason != "pause_turn":
            break
        # La búsqueda en el servidor se ha pausado: se reenvía el turno tal cual y continúa.
        mensajes = mensajes + [{"role": "assistant", "content": resp.content}]
    else:
        raise ErrorIA("La investigación web no ha terminado tras varios intentos.")
    _comprobar(resp)
    return _texto(resp)


def conversar(system: list[dict], mensajes: list[dict], *, effort: str = "low", max_tokens: int = 4000,
              al_terminar=None):
    """Habla con Claude y devuelve el texto según llega. `al_terminar(usage)` recibe el consumo al acabar (el texto
    se va generando en varios hilos, así que el gasto no se puede anotar por hilo)."""
    if not disponible():
        raise ErrorIA("Falta la clave de Claude.")
    if motor() == "claude_code":
        sistema = "\n\n".join(b.get("text", "") for b in system)
        conversacion = "\n\n".join(f"{'DUEÑO' if m['role'] == 'user' else 'VEGA'}: {m['content']}" for m in mensajes)
        yield str(_claude_code(sistema, conversacion + "\n\nResponde al último mensaje del DUEÑO.").get("result") or "")
        return
    try:
        with _cli().beta.messages.stream(model=MODEL, betas=[FALLBACK_BETA], fallbacks="default", max_tokens=max_tokens,
                                         system=system, messages=mensajes,
                                         output_config={"effort": effort}) as stream:
            for trozo in stream.text_stream:
                yield trozo
            resp = stream.get_final_message()
        if al_terminar:
            al_terminar(resp.usage)
        _comprobar(resp)
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
        if isinstance(e, anthropic.APIStatusError) and e.status_code in (429, 500, 502, 503, 504, 529):
            raise ErrorIA("El servicio de Claude está saturado ahora mismo. Prueba de nuevo en unos segundos.") from e
        _traducir(e)


def json_con_esquema(system: str, peticion: str, esquema: dict, *, effort: str = "medium",
                     imagenes: list[bytes] | None = None) -> dict:
    """Pide a Claude una respuesta que cumple el esquema JSON y la devuelve como dict.
    `imagenes` son JPEG que van delante del texto (por ejemplo, fotogramas de un vídeo)."""
    if not disponible():
        raise ErrorIA("Falta la clave de Claude.")
    if motor() == "claude_code":
        if imagenes:
            raise ErrorIA("Mirar fotogramas necesita la clave de la API de Claude.")
        datos = _claude_code(system, peticion, esquema=esquema)
        if not isinstance(datos.get("structured_output"), dict):
            raise ErrorIA("Claude Code no ha devuelto la respuesta con el formato pedido.")
        return datos["structured_output"]
    contenido = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                               "data": base64.b64encode(img).decode()}}
                 for img in imagenes or []]
    contenido.append({"type": "text", "text": peticion})
    resp = _llamar(
        max_tokens=64000,
        system=system,
        messages=[{"role": "user", "content": contenido}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": esquema}},
    )
    _comprobar(resp)
    texto = _texto(resp)
    try:
        return json.loads(texto)
    except json.JSONDecodeError as e:
        raise ErrorIA("Claude ha devuelto un JSON que no se puede leer.") from e
