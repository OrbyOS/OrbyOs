"""Las solicitudes de implementación que llegan desde la landing («Solicitar implementación»): se guardan, se ven en
Administración y avisan por Telegram a quien administra (si tiene el bot conectado en alguno de sus negocios).

Contra el spam: un campo trampa que una persona no ve (si viene relleno, se da las gracias y no se guarda nada) y un
máximo de solicitudes por IP y hora."""
import re
import time

from . import db

CAMPOS = {"nombre": 120, "email": 200, "negocio": 200, "web": 300, "redes": 400, "mensaje": 2000}
TRAMPA = "sitio"            # el campo oculto: los robots lo rellenan
POR_IP_HORA = 5
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
_recientes: dict[str, list[float]] = {}


def recibir(form, ip: str) -> str:
    """Devuelve el resultado para la landing: «gracias», «faltan» o «espera»."""
    if str(form.get(TRAMPA) or "").strip():
        return "gracias"  # a un robot no se le dice que se le ha pillado
    datos = {k: " ".join(str(form.get(k) or "").split())[:n] if k != "mensaje" else str(form.get(k) or "").strip()[:n]
             for k, n in CAMPOS.items()}
    if not datos["nombre"] or not _EMAIL.match(datos["email"]):
        return "faltan"
    ahora = time.time()
    previas = [t for t in _recientes.get(ip, []) if ahora - t < 3600]
    if len(previas) >= POR_IP_HORA:
        return "espera"
    _recientes[ip] = previas + [ahora]
    sid = db.crear_solicitud({**datos, "origen": "landing"})
    avisar(sid, datos)
    return "gracias"


def avisar(solicitud_id: int, datos: dict):
    """Un mensaje por Telegram al primer negocio con el bot conectado de quien administra. Si no hay, nada."""
    from .agentes import jefa
    admins = [u for u in db.usuarios_con_uso() if u.get("es_admin")]
    for u in admins:
        for neg in db.negocios(u["id"]):
            if jefa.conectado(neg["id"]):
                texto = (f"Nueva solicitud de implementación: {datos['nombre']} ({datos['email']})"
                         + (f"\nNegocio: {datos['negocio']}" if datos["negocio"] else "")
                         + (f"\nWeb: {datos['web']}" if datos["web"] else "")
                         + (f"\nRedes: {datos['redes']}" if datos["redes"] else "")
                         + (f"\n\n{datos['mensaje'][:600]}" if datos["mensaje"] else "")
                         + "\n\nLa tienes en Administración.")
                jefa.encolar(neg["id"], texto, clave=f"solicitud-{solicitud_id}", prioridad="alta")
                return
