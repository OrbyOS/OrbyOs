"""Listas de correo de las landings (formularios de newsletter de otras webs servidas desde el mismo servidor).

POST /newsletter/<lista>/suscribir con nombre, email, acepto («si»), origen (la palabra del reel, opcional) y,
opcional, texto_consentimiento (lo que dice la casilla). Contra el spam: un campo trampa («web») y un máximo por IP y
hora. La IP no se guarda: solo su huella (hash con sal de la instalación). Un correo ya apuntado no se duplica.
Con Kit, de dos maneras. Con el formulario público de Kit (plan gratis, sin clave): «kit-formulario <lista> <número>»
y cada alta de esa lista se manda a ese formulario (Kit pide la confirmación por correo). Con la API (RADAR_KIT_API_KEY): cada alta se manda también a Kit, con la etiqueta de su origen y la secuencia de
bienvenida (RADAR_KIT_SECUENCIA, «Bienvenida» por defecto). RADAR_KIT_LISTAS dice qué listas van a Kit (todas, si no se
pone). Si Kit falla, el alta queda guardada aquí y se reintenta sola cada 10 minutos.
Para ver y exportar, desde el servidor:  python -m radar.newsletter --ayuda
"""
import csv
import hashlib
import os
import re
import secrets
import sys
import threading
import time
import traceback
from datetime import datetime, timedelta

from . import config, db

TRAMPA = "web"
POR_IP_HORA = 5
TEXTO_POR_DEFECTO = "Acepta recibir la newsletter y ha leído la política de privacidad."
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", re.I)
_recientes: dict[str, list[float]] = {}


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _sal() -> str:
    archivo = config.DATA_DIR / ".sal_newsletter"
    if not archivo.exists():
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(secrets.token_hex(16))
    return archivo.read_text().strip()


def huella(ip: str) -> str:
    return hashlib.sha256(f"{_sal()}:{ip}".encode()).hexdigest()[:24] if ip else ""


def lista_valida(lista: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9-]{1,40}", lista or ""))


def suscribir(lista: str, form, ip: str) -> str:
    """«ok», «repetido» (ya estaba: también es un ok para quien lo envía), «faltan» o «espera»."""
    if str(form.get(TRAMPA) or "").strip():
        return "ok"  # a un robot no se le dice que se le ha pillado
    nombre = " ".join(str(form.get("nombre") or "").split())[:120]
    email = str(form.get("email") or "").strip().lower()[:200]
    if not nombre or not _EMAIL.match(email) or str(form.get("acepto") or "").strip().lower() != "si":
        return "faltan"
    ahora = time.time()
    previas = [t for t in _recientes.get(ip, []) if ahora - t < 3600]
    if len(previas) >= POR_IP_HORA:
        return "espera"
    _recientes[ip] = previas + [ahora]
    texto = " ".join(str(form.get("texto_consentimiento") or "").split())[:500] or TEXTO_POR_DEFECTO
    origen = re.sub(r"[^A-Za-z0-9_-]", "", str(form.get("origen") or ""))[:40].upper()
    with db.conexion() as con:
        cur = con.execute("INSERT OR IGNORE INTO suscriptores (lista, email, nombre, creado, ip_huella, origen, "
                          "consentimiento, consentimiento_en) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                          (lista, email, nombre, _ahora(), huella(ip), origen, texto, _ahora()))
    if not cur.rowcount:
        return "repetido"
    from . import jobs
    jobs.en_segundo_plano(a_kit, cur.lastrowid)
    return "ok"


# ---------------------------------------------------------------- Kit

MAX_INTENTOS = 8


def _ajuste(var: str, defecto: str = "") -> str:
    """Del entorno o, si se guardó después de arrancar (con «clave-kit»), del .env de los ajustes."""
    valor = os.getenv(var, "").strip()
    if not valor:
        from dotenv import dotenv_values
        archivo = os.getenv("RADAR_ENV_FILE") or str(config.APP_DIR / ".env")
        valor = (dotenv_values(archivo).get(var) or "").strip() if os.path.exists(archivo) else ""
    return valor or defecto


def _listas_archivo():
    return config.DATA_DIR / "newsletter.json"


def ajustes_listas() -> dict:
    import json
    try:
        return json.loads(_listas_archivo().read_text())
    except (OSError, ValueError):
        return {}


def poner_formulario(lista: str, formulario_id: str):
    import json
    datos = ajustes_listas()
    datos.setdefault(lista, {})["kit_formulario"] = str(formulario_id).strip()
    _listas_archivo().parent.mkdir(parents=True, exist_ok=True)
    _listas_archivo().write_text(json.dumps(datos, ensure_ascii=False, indent=1))


def formulario_kit(lista: str) -> str:
    return (ajustes_listas().get(lista) or {}).get("kit_formulario", "")


def va_a_kit(lista: str) -> bool:
    listas = [x.strip() for x in _ajuste("RADAR_KIT_LISTAS").split(",") if x.strip()]
    return bool(_ajuste("RADAR_KIT_API_KEY")) and (not listas or lista in listas)


def a_kit(suscriptor_id: int) -> str:
    """Manda un alta a Kit. Devuelve «ok», «no» (esa lista no va a Kit) o el error (se reintentará)."""
    from .connectors import kit
    with db.conexion() as con:
        s = con.execute("SELECT * FROM suscriptores WHERE id = ?", (suscriptor_id,)).fetchone()
    if not s or s["kit"] in ("ok", "no", "navegador") or s["baja"]:
        return s["kit"] if s else "no"
    formulario = formulario_kit(s["lista"])
    if formulario:
        # Kit pone en cuarentena las altas que le llegan desde un servidor (IP de centro de datos): con su formulario
        # público, el alta la manda el navegador de la persona desde la landing. Aquí solo se apunta.
        with db.conexion() as con:
            con.execute("UPDATE suscriptores SET kit = 'navegador', kit_error = '' WHERE id = ?", (suscriptor_id,))
        return "navegador"
    if not _ajuste("RADAR_KIT_API_KEY"):
        return ""  # sin Kit todavía: queda pendiente y se manda cuando lo haya
    if not formulario and not va_a_kit(s["lista"]):
        with db.conexion() as con:
            con.execute("UPDATE suscriptores SET kit = 'no' WHERE id = ?", (suscriptor_id,))
        return "no"
    try:
        if formulario:
            kit.alta_por_formulario(formulario, s["email"], s["nombre"])
        else:
            kit.alta(_ajuste("RADAR_KIT_API_KEY"), s["email"], s["nombre"], etiqueta=s["origen"],
                     secuencia=_ajuste("RADAR_KIT_SECUENCIA", "Bienvenida"))
    except kit.ErrorKit as e:
        with db.conexion() as con:
            con.execute("UPDATE suscriptores SET kit_error = ?, kit_intentos = kit_intentos + 1 WHERE id = ?",
                        (str(e)[:300], suscriptor_id))
        return str(e)
    with db.conexion() as con:
        con.execute("UPDATE suscriptores SET kit = 'ok', kit_error = '' WHERE id = ?", (suscriptor_id,))
    return "ok"


def a_kit_pendientes() -> int:
    """Las altas que aún no han llegado a Kit (de los últimos 30 días y con menos de MAX_INTENTOS fallos)."""
    desde = (datetime.now() - timedelta(days=30)).isoformat(timespec="seconds")
    with db.conexion() as con:
        ids = [f["id"] for f in con.execute("SELECT id FROM suscriptores WHERE kit = '' AND baja = '' AND creado >= ? "
                                            "AND kit_intentos < ? ORDER BY id", (desde, MAX_INTENTOS))]
        for lista in ajustes_listas():  # las que quedaron pendientes o fallidas de una lista con formulario: ya no se mandan
            if formulario_kit(lista):
                con.execute("UPDATE suscriptores SET kit = 'navegador', kit_error = '' WHERE lista = ? AND kit = ''",
                            (lista,))
    return sum(a_kit(i) == "ok" for i in ids)


def arrancar():
    def vueltas():
        while True:
            time.sleep(600)
            try:
                a_kit_pendientes()
            except Exception:  # noqa: BLE001
                traceback.print_exc()
    threading.Thread(target=vueltas, daemon=True).start()


def suscriptores(lista: str) -> list[dict]:
    with db.conexion() as con:
        return [dict(f) for f in con.execute("SELECT nombre, email, creado, origen, consentimiento, consentimiento_en "
                                             "FROM suscriptores WHERE lista = ? AND baja = '' ORDER BY id", (lista,))]


def dar_de_baja(lista: str, email: str) -> bool:
    with db.conexion() as con:
        return con.execute("UPDATE suscriptores SET baja = ? WHERE lista = ? AND email = ? AND baja = ''",
                           (_ahora(), lista, email.strip().lower())).rowcount > 0


AYUDA = """Uso (dentro del contenedor: docker compose exec -T radar python -m radar.newsletter … </dev/null):
  listas                      cada lista con su número de suscriptores
  ver <lista>                 los suscriptores: fecha, origen, nombre y correo
  exportar <lista>            en CSV por la salida (… > suscriptores.csv)
  baja <lista> <correo>       lo quita de la lista (queda la fecha de baja)
  kit-formulario <lista> <n>  manda las altas de esa lista al formulario público de Kit con ese número
  clave-kit                   lee la clave de Kit de la entrada (no se ve), la comprueba y la guarda en los ajustes
  kit                         manda ya a Kit lo pendiente y dice cómo va cada lista"""


def main(args: list[str]) -> int:
    db.iniciar()
    orden = args[0] if args else ""
    if orden == "listas":
        with db.conexion() as con:
            for f in con.execute("SELECT lista, COUNT(*) n FROM suscriptores WHERE baja = '' GROUP BY lista"):
                print(f"{f['lista']:<20} {f['n']}")
    elif orden == "ver" and len(args) == 2:
        for s in suscriptores(args[1]):
            print(f"{s['creado']}  {s['origen'] or '-':<10} {s['nombre']:<24} {s['email']}")
    elif orden == "exportar" and len(args) == 2:
        filas = suscriptores(args[1])
        w = csv.DictWriter(sys.stdout, fieldnames=["nombre", "email", "creado", "origen", "consentimiento",
                                                   "consentimiento_en"])
        w.writeheader()
        w.writerows(filas)
    elif orden == "kit-formulario" and len(args) == 3 and args[2].isdigit():
        poner_formulario(args[1], args[2])
        print(f"Las altas de «{args[1]}» van al formulario {args[2]} de Kit. Enviadas ahora: {a_kit_pendientes()}")
    elif orden == "clave-kit":
        from dotenv import set_key
        from .connectors import kit
        clave = sys.stdin.readline().strip()
        try:
            cuenta = kit.comprobar(clave)
        except kit.ErrorKit as e:
            print(f"No se ha guardado: {e}")
            return 1
        archivo = os.getenv("RADAR_ENV_FILE") or str(config.APP_DIR / ".env")
        open(archivo, "a").close()
        set_key(archivo, "RADAR_KIT_API_KEY", clave, quote_mode="never")
        print(f"Clave de Kit guardada{f' (cuenta {cuenta})' if cuenta else ''}.")
    elif orden == "kit":
        print(f"Enviadas ahora: {a_kit_pendientes()}")
        with db.conexion() as con:
            for f in con.execute("SELECT lista, kit, COUNT(*) n, MAX(kit_error) e FROM suscriptores WHERE baja = '' "
                                 "GROUP BY lista, kit"):
                print(f"{f['lista']:<16} {f['kit'] or 'pendiente':<10} {f['n']:>5}  {f['e'] or ''}")
    elif orden == "baja" and len(args) == 3:
        print("dado de baja" if dar_de_baja(args[1], args[2]) else "no estaba")
    else:
        print(AYUDA)
        return 0 if orden in ("", "--ayuda", "-h") else 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
