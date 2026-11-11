"""Los regalos de un negocio: una palabra clave que la gente comenta, un enlace corto que cuenta los clics y el sitio
al que lleva (una guía, una skill, una landing con su newsletter…). Todo junto, con sus números:
comentarios con la palabra, privados enviados, clics y correos que dejaron (los que llegan con esa palabra de origen).

La palabra la atiende la respuesta automática de Instagram (instagram_dm) con el enlace corto; el enlace corto
(radar.cortos) lleva al destino y cuenta cada clic.
"""
import re
from datetime import datetime

from .. import config, cortos, db


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _palabra(texto: str) -> str:
    import unicodedata
    sin_tildes = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", sin_tildes.upper())[:30]


def _de_fila(f) -> dict:
    r = dict(f)
    r["activa"] = bool(r["activa"])
    r["exacta"] = bool(r["exacta"])
    base = r.get("dominio") or config.URL_PUBLICA  # con su dominio, el enlace se ve suyo (su web manda /r/ a la app)
    r["enlace_corto"] = f"{base}/r/{r['corto']}" if base else f"/r/{r['corto']}"
    return r


def regalo(negocio_id: int, regalo_id: int) -> dict | None:
    with db.conexion() as con:
        f = con.execute("SELECT * FROM regalos WHERE negocio_id = ? AND id = ?", (negocio_id, regalo_id)).fetchone()
    return _de_fila(f) if f else None


def _corto_libre(nombre: str, negocio_id: int, salvo: str = "") -> str:
    """El nombre del enlace corto: el de la palabra, salvo que ya lo use otro (entonces, con el número del negocio)."""
    base = re.sub(r"[^a-z0-9-]", "", nombre.lower())[:30] or "regalo"
    for candidato in (base, f"{base}-{negocio_id}"):
        if candidato == salvo or not cortos.destino(candidato):
            return candidato
    n = 2
    while cortos.destino(f"{base}-{negocio_id}-{n}"):
        n += 1
    return f"{base}-{negocio_id}-{n}"


def guardar(negocio_id: int, *, palabra: str, destino: str = "", guia_id: int | None = None, regalo_id: int | None = None,
            activa: bool = True, exacta: bool = False, mensaje: str = "", pregunta: str = "", media_id: str = "",
            dominio: str | None = None, apertura: str | None = None) -> dict:
    """Crea o cambia un regalo. El destino es una dirección (https://…) o una guía de Comunidad. Lanza ValueError."""
    palabra = _palabra(palabra)
    if not palabra:
        raise ValueError("Pon la palabra que la gente tiene que comentar.")
    destino = (destino or "").strip()
    if guia_id and not destino:
        from . import comunidad
        g = next((g for g in comunidad.guias(negocio_id) if g["id"] == guia_id), None)
        destino = comunidad.enlace_guia(g) if g else ""
    if not destino.startswith(("https://", "http://")):
        raise ValueError("Pon adónde lleva el regalo: una dirección que empiece por https:// o una de tus guías.")
    antes = regalo(negocio_id, regalo_id) if regalo_id else None
    if dominio is None:
        dominio = (antes or {}).get("dominio", "")
    if apertura is None:
        apertura = (antes or {}).get("apertura", "")
    dominio = dominio.strip().rstrip("/")
    if dominio and not re.fullmatch(r"https://[a-z0-9.-]+\.[a-z]{2,}", dominio):
        raise ValueError("El dominio del enlace corto tiene que ser como https://tu-web.es (sin nada detrás).")
    with db.conexion() as con:
        otra = con.execute("SELECT id FROM regalos WHERE negocio_id = ? AND palabra = ? AND media_id = ? AND id != ?",
                           (negocio_id, palabra, media_id.strip(), regalo_id or 0)).fetchone()
    if otra:
        raise ValueError(f"Ya tienes un regalo con la palabra {palabra}.")
    corto = _corto_libre(palabra, negocio_id, salvo=(antes or {}).get("corto", ""))
    cortos.poner(corto, destino, negocio_id=negocio_id)
    valores = (palabra, destino, guia_id, int(activa), int(exacta), mensaje.strip()[:900], pregunta.strip()[:600],
               media_id.strip(), corto, dominio, apertura.strip()[:600])
    with db.conexion() as con:
        if antes:
            con.execute("UPDATE regalos SET palabra = ?, destino = ?, guia_id = ?, activa = ?, exacta = ?, mensaje = ?, "
                        "pregunta = ?, media_id = ?, corto = ?, dominio = ?, apertura = ? WHERE id = ?", valores + (antes["id"],))
            rid = antes["id"]
        else:
            rid = con.execute("INSERT INTO regalos (palabra, destino, guia_id, activa, exacta, mensaje, pregunta, media_id, "
                              "corto, dominio, apertura, negocio_id, creado) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                              valores + (negocio_id, _ahora())).lastrowid
    if antes and antes["corto"] != corto:
        cortos.quitar(antes["corto"])
    return regalo(negocio_id, rid)


def quitar(negocio_id: int, regalo_id: int) -> bool:
    r = regalo(negocio_id, regalo_id)
    if not r:
        return False
    with db.conexion() as con:
        con.execute("DELETE FROM regalos WHERE id = ?", (regalo_id,))
    cortos.quitar(r["corto"])
    return True


def lista(negocio_id: int) -> list[dict]:
    """Los regalos del negocio con sus números, del más nuevo al más antiguo."""
    with db.conexion() as con:
        filas = [_de_fila(f) for f in con.execute("SELECT * FROM regalos WHERE negocio_id = ? ORDER BY id DESC",
                                                  (negocio_id,))]
        for r in filas:
            e = con.execute("SELECT COUNT(*) AS n, SUM(estado = 'enviado') AS enviados, MAX(creado) AS ultimo "
                            "FROM envios_ig WHERE negocio_id = ? AND palabra = ?", (negocio_id, r["palabra"])).fetchone()
            r["comentarios"], r["privados"], r["ultimo"] = e["n"] or 0, e["enviados"] or 0, e["ultimo"] or ""
            r["clics"] = con.execute("SELECT COALESCE(SUM(clics), 0) FROM clics_cortos WHERE nombre = ?",
                                     (r["corto"],)).fetchone()[0]
            r["correos"] = con.execute("SELECT COUNT(*) FROM suscriptores WHERE origen = ? AND baja = ''",
                                       (r["palabra"],)).fetchone()[0]
    return filas


def para_instagram(negocio_id: int) -> list[dict]:
    """Los regalos activos como palabras de la respuesta automática de Instagram (con el enlace corto)."""
    salida = []
    for r in lista(negocio_id):
        if r["activa"]:
            mensaje = r["mensaje"] if not r["mensaje"] or "{enlace}" in r["mensaje"] else f"{r['mensaje']} {{enlace}}"
            regla = {"palabra": r["palabra"], "enlace": r["enlace_corto"] if (config.URL_PUBLICA or r["dominio"]) else r["destino"],
                     "mensaje": mensaje, "media_id": r["media_id"], "regalo_id": r["id"]}
            if r["exacta"]:
                regla["exacta"] = True
            if r["pregunta"]:
                regla["pregunta"] = r["pregunta"]
            if r["apertura"]:
                regla["apertura"] = r["apertura"]
            salida.append(regla)
    return salida


# ---------------------------------------------------------------- desde el servidor, sin pantalla

AYUDA = """Uso (dentro del contenedor: docker compose exec -T radar python -m radar.agentes.regalos … </dev/null):
  lista <negocio>
  poner <negocio> <PALABRA> <destino> [--exacta] [--mensaje "texto con {enlace}"] [--pregunta "…"] [--reel <media_id>]
        [--apertura "…"] [--dominio https://su-web.es]   el enlace corto con su dominio (su web tiene que mandar /r/ a la app)
  quitar <negocio> <PALABRA>"""


def main(args: list[str]) -> int:
    import sys
    db.iniciar()
    if len(args) < 2 or not args[1].isdigit():
        print(AYUDA)
        return 0 if not args or args[0] in ("--ayuda", "-h") else 1
    orden, nid, resto = args[0], int(args[1]), args[2:]

    def opcion(nombre: str) -> str:
        if nombre in resto:
            i = resto.index(nombre)
            valor = resto[i + 1] if i + 1 < len(resto) else ""
            del resto[i:i + 2]
            return valor
        return ""
    exacta = "--exacta" in resto
    resto[:] = [a for a in resto if a != "--exacta"]
    mensaje, pregunta, reel = (opcion(n).replace("\\n", "\n") for n in ("--mensaje", "--pregunta", "--reel"))
    apertura = opcion("--apertura").replace("\\n", "\n") or None
    dominio = opcion("--dominio") or None
    if orden == "lista":
        for r in lista(nid):
            print(f"{r['palabra']:<12} {'activa' if r['activa'] else 'pausa':<7} {r['enlace_corto']:<36} "
                  f"com {r['comentarios']} · priv {r['privados']} · clics {r['clics']} · correos {r['correos']}")
    elif orden == "poner" and len(resto) >= 2:
        actual = next((r for r in lista(nid) if r["palabra"] == _palabra(resto[0]) and r["media_id"] == reel), None)
        try:
            r = guardar(nid, palabra=resto[0], destino=resto[1], regalo_id=(actual or {}).get("id"), exacta=exacta,
                        mensaje=mensaje, pregunta=pregunta, media_id=reel, dominio=dominio, apertura=apertura)
        except ValueError as e:
            print(e)
            return 1
        print(f"{r['palabra']} → {r['enlace_corto']} → {r['destino']}")
    elif orden == "quitar" and resto:
        r = next((r for r in lista(nid) if r["palabra"] == _palabra(resto[0])), None)
        print("quitado" if r and quitar(nid, r["id"]) else "no estaba")
    else:
        print(AYUDA)
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))
