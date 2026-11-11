"""Kit (antes ConvertKit): las altas de las newsletters de las landings, con la etiqueta de su origen y su secuencia.

Comprobado el 28/10/2026 contra la documentación de la API v4 (developers.kit.com/v4):
- Base `https://api.kit.com/v4`; la clave va en la cabecera `X-Kit-Api-Key`.
- `POST /subscribers` {email_address, first_name, state}: crea el suscriptor o actualiza el que ya existe.
- `GET /tags` → {tags: [{id, name}]}; `POST /tags` {name}; `POST /tags/{id}/subscribers` {email_address}.
- `GET /sequences` → {sequences: [{id, name}]}; `POST /sequences/{id}/subscribers` {email_address}.
- Las listas paginan (`pagination.has_next_page`, `end_cursor`, `after`).
"""
import httpx

BASE = "https://api.kit.com/v4"


class ErrorKit(Exception):
    pass


def _llamar(metodo: str, ruta: str, clave: str, **kwargs) -> dict:
    if not clave:
        raise ErrorKit("Falta la clave de Kit.")
    try:
        r = httpx.request(metodo, BASE + ruta, headers={"X-Kit-Api-Key": clave, "Accept": "application/json"},
                          timeout=30, **kwargs)
    except httpx.HTTPError as e:
        raise ErrorKit(f"No hay conexión con Kit: {e.__class__.__name__}") from e
    if r.status_code in (401, 403):
        raise ErrorKit("La clave de Kit no es válida.")
    try:
        datos = r.json()
    except ValueError:
        datos = {}
    if r.status_code >= 400:
        errores = datos.get("errors") if isinstance(datos, dict) else None
        raise ErrorKit(f"Kit ha respondido {r.status_code}: {'; '.join(errores or [])[:200]}")
    return datos if isinstance(datos, dict) else {}


def _todos(ruta: str, clave_lista: str, clave: str) -> list[dict]:
    salida, despues = [], None
    for _ in range(20):
        d = _llamar("GET", ruta, clave, params={"per_page": 500, **({"after": despues} if despues else {})})
        salida += d.get(clave_lista) or []
        pag = d.get("pagination") or {}
        if not pag.get("has_next_page"):
            break
        despues = pag.get("end_cursor")
    return salida


def etiqueta_id(clave: str, nombre: str) -> int:
    """El id de la etiqueta con ese nombre; si no existe, la crea."""
    for t in _todos("/tags", "tags", clave):
        if (t.get("name") or "").strip().lower() == nombre.strip().lower():
            return int(t["id"])
    d = _llamar("POST", "/tags", clave, json={"name": nombre})
    return int((d.get("tag") or d).get("id"))


def secuencia_id(clave: str, nombre: str) -> int | None:
    for s in _todos("/sequences", "sequences", clave):
        if (s.get("name") or "").strip().lower() == nombre.strip().lower():
            return int(s["id"])
    return None


def alta(clave: str, email: str, nombre: str, *, etiqueta: str = "", secuencia: str = "") -> dict:
    """Crea (o actualiza) el suscriptor, le pone la etiqueta y lo mete en la secuencia. Lanza ErrorKit."""
    _llamar("POST", "/subscribers", clave, json={"email_address": email, "first_name": nombre, "state": "active"})
    hecho = {"etiqueta": "", "secuencia": ""}
    if etiqueta:
        _llamar("POST", f"/tags/{etiqueta_id(clave, etiqueta)}/subscribers", clave, json={"email_address": email})
        hecho["etiqueta"] = etiqueta
    if secuencia:
        sid = secuencia_id(clave, secuencia)
        if sid is None:
            raise ErrorKit(f"No encuentro la secuencia «{secuencia}» en Kit.")
        _llamar("POST", f"/sequences/{sid}/subscribers", clave, json={"email_address": email})
        hecho["secuencia"] = secuencia
    return hecho


def alta_por_formulario(formulario_id: str, email: str, nombre: str) -> None:
    """Sin clave (plan gratis): el mismo envío que hace el formulario público de Kit incrustado en una web. Kit manda
    su correo de confirmación y, al confirmar, la persona queda suscrita. Lanza ErrorKit."""
    if not str(formulario_id).isdigit():
        raise ErrorKit("El formulario de Kit tiene que ser su número.")
    try:
        r = httpx.post(f"https://app.kit.com/forms/{formulario_id}/subscriptions", timeout=30, follow_redirects=True,
                       headers={"Accept": "application/json", "User-Agent": "Mozilla/5.0 (compatible; Orby)"},
                       data={"email_address": email, "fields[first_name]": nombre})
    except httpx.HTTPError as e:
        raise ErrorKit(f"No hay conexión con Kit: {e.__class__.__name__}") from e
    if r.status_code >= 400:
        raise ErrorKit(f"El formulario de Kit ha respondido {r.status_code}: {r.text[:120]}")
    try:
        datos = r.json()
    except ValueError:
        return
    if isinstance(datos, dict) and str(datos.get("status", "success")).lower() not in ("success", "ok"):
        raise ErrorKit(f"Kit no ha aceptado el alta: {str(datos)[:200]}")


def comprobar(clave: str) -> str:
    """El nombre de la cuenta, si la clave vale."""
    d = _llamar("GET", "/account", clave)
    return ((d.get("account") or {}).get("name") or (d.get("user") or {}).get("email") or "").strip()
