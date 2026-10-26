"""Una sola cola de aprobaciones para todo el equipo. Cada agente pide permiso aquí antes de que algo cambie el kit o
salga en público; según la autonomía que le hayas dado, espera a que decidas o sigue solo. Lo que vende, afirma algo o
responde a una persona («clave») espera siempre, salvo en piloto automático."""
import json
from datetime import datetime

from .. import db
from . import AGENTES
from . import kit as kit_marca

TIPOS = {
    "kit": "Kit de marca",
    "leccion": "Lección",
    "brief": "Graba hoy",
    "guion": "Guion",
    "video": "Vídeo",
    "publicacion": "Publicación",
    "respuesta": "Respuesta",
    "cuentas": "Cuentas nuevas",
    "reels_prueba": "Reels de prueba",
    "dm": "Mensaje directo",
    "comentarios": "Respuestas a comentarios",
    "ronda": "Ronda de interacción",
}
ESTADOS = {"pendiente": "Esperando", "aprobada": "Aprobada", "rechazada": "Rechazada", "cambios": "Con cambios pedidos"}
PILOTO = "piloto automático"

# Lo que pasa al decidir cada tipo: fn(aprobacion). Cada módulo registra los suyos y se ejecutan en orden.
_AL_PEDIR: list = []   # fn(aprobacion) cuando algo se queda esperando a una persona (avisos al móvil)
_AL_APROBAR: dict[str, list] = {}
_AL_RECHAZAR: dict[str, list] = {}


def al_aprobar(tipo: str):
    def registrar(fn):
        _AL_APROBAR.setdefault(tipo, []).append(fn)
        return fn
    return registrar


def al_pedir(fn):
    _AL_PEDIR.append(fn)
    return fn


def al_rechazar(tipo: str):
    """También se ejecuta con «Pedir cambios»: la aprobación llega con estado «cambios» y la nota."""
    def registrar(fn):
        _AL_RECHAZAR.setdefault(tipo, []).append(fn)
        return fn
    return registrar


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _de_fila(f) -> dict:
    a = dict(f)
    a["datos"] = json.loads(a["datos"] or "{}")
    a["clave"] = bool(a["clave"])
    a["ref"] = f"ap-{a['id']}"
    a["agente_nombre"] = AGENTES.get(a["agente"], {}).get("nombre", a["agente"])
    a["tipo_nombre"] = TIPOS.get(a["tipo"], a["tipo"])
    return a


def espera(autonomia: str, clave: bool) -> bool:
    """¿Tiene que esperar a una persona?"""
    if autonomia == "piloto":
        return False
    if autonomia == "revisar_clave":
        return clave
    return True


def pedir(negocio_id: int, agente: str, tipo: str, resumen: str, datos: dict | None = None, *,
          clave: bool = False, siempre: bool = False) -> dict:
    """Crea la petición. Si la autonomía del agente lo permite, se aprueba sola y se ejecuta lo que toque.
    `siempre` la hace esperar a una persona aunque el agente vaya en piloto automático."""
    with db.conexion() as con:
        cur = con.execute("INSERT INTO aprobaciones (negocio_id, creado, agente, tipo, resumen, datos, clave) "
                          "VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (negocio_id, _ahora(), agente, tipo, resumen[:300], json.dumps(datos or {}, ensure_ascii=False),
                           int(clave)))
        ap_id = cur.lastrowid
    if not siempre and not espera(kit_marca.autonomia(negocio_id, agente), clave):
        return decidir(ap_id, "aprobar", por=PILOTO)
    a = aprobacion(ap_id)
    for aviso in _AL_PEDIR:
        aviso(a)
    return a


def aprobacion(ap_id: int) -> dict | None:
    with db.conexion() as con:
        f = con.execute("SELECT * FROM aprobaciones WHERE id = ?", (ap_id,)).fetchone()
    return _de_fila(f) if f else None


def por_ref(negocio_id: int, ref: str) -> dict | None:
    """«ap-7» o «7» → la aprobación, si es de este negocio."""
    ref = ref.strip().lower().removeprefix("ap-")
    if not ref.isdigit():
        return None
    a = aprobacion(int(ref))
    return a if a and a["negocio_id"] == negocio_id else None


def de_negocio(negocio_id: int, *, estado: str | None = None, limite: int = 100) -> list[dict]:
    sql, args = "SELECT * FROM aprobaciones WHERE negocio_id = ?", [negocio_id]
    if estado:
        sql += " AND estado = ?"
        args.append(estado)
    sql += " ORDER BY id " + ("ASC" if estado == "pendiente" else "DESC") + " LIMIT ?"
    with db.conexion() as con:
        return [_de_fila(f) for f in con.execute(sql, (*args, limite))]


def pendientes(negocio_id: int) -> list[dict]:
    """Lo que espera tu decisión, lo más antiguo primero."""
    return de_negocio(negocio_id, estado="pendiente")


def contar_pendientes(negocio_id: int) -> int:
    with db.conexion() as con:
        return con.execute("SELECT COUNT(*) FROM aprobaciones WHERE negocio_id = ? AND estado = 'pendiente'",
                           (negocio_id,)).fetchone()[0]


PARTES_KIT = ("pruebas", "carriles", "prohibidas", "competencia", "voz.frases", "voz.muestras", "voz.como_habla",
              "voz.movimientos", "voz.nunca", "contexto.historias", "contexto.opiniones", "contexto.objeciones",
              "contexto.frases_cliente", "contexto.preguntas_frecuentes", "ficha", "ortografia")


def quitar_parte(ap_id: int, parte: str, indice: int | None = None, clave: str = "") -> bool:
    """Antes de aprobar, quita lo que no quieres de un borrador del Kit o de las cuentas que propone Lupi."""
    a = aprobacion(ap_id)
    if a and a["tipo"] == "cuentas" and parte == "cuentas":
        return _quitar_de_lista(a, a["datos"].get("cuentas"), indice)
    return _quitar_parte_kit(ap_id, parte, indice, clave)


def _quitar_de_lista(a: dict, lista, indice: int | None) -> bool:
    if a["estado"] != "pendiente" or not isinstance(lista, list) or indice is None or not 0 <= indice < len(lista):
        return False
    lista.pop(indice)
    with db.conexion() as con:
        con.execute("UPDATE aprobaciones SET datos = ? WHERE id = ? AND estado = 'pendiente'",
                    (json.dumps(a["datos"], ensure_ascii=False), a["id"]))
    return True


def _quitar_parte_kit(ap_id: int, parte: str, indice: int | None = None, clave: str = "") -> bool:
    """Antes de aprobar un borrador del Kit, quita lo que no quieres: una prueba, una historia, una frase, un campo de
    la ficha… (`parte` con su `indice` en la lista o, en la ficha, la `clave` del campo). Lo demás sigue esperando."""
    a = aprobacion(ap_id)
    if not a or a["estado"] != "pendiente" or a["tipo"] != "kit" or parte not in PARTES_KIT:
        return False
    sitio, _, campo = parte.partition(".")
    contenedor = a["datos"].get(sitio)
    if campo:
        contenedor = (contenedor or {}).get(campo) if isinstance(contenedor, dict) else None
    if parte == "ficha":
        if not isinstance(contenedor, dict) or clave not in contenedor:
            return False
        contenedor.pop(clave)
    else:
        if not isinstance(contenedor, list) or indice is None or not 0 <= indice < len(contenedor):
            return False
        contenedor.pop(indice)
    with db.conexion() as con:
        con.execute("UPDATE aprobaciones SET datos = ? WHERE id = ? AND estado = 'pendiente'",
                    (json.dumps(a["datos"], ensure_ascii=False), ap_id))
    return True


def decidir(ap_id: int, decision: str, *, nota: str = "", por: str = "", datos: dict | None = None) -> dict:
    """aprobar | rechazar | cambios. `datos` sustituye a lo propuesto (lo que editas antes de aprobar).
    Una decisión ya tomada no se repite: devuelve la aprobación tal cual."""
    estado = {"aprobar": "aprobada", "rechazar": "rechazada", "cambios": "cambios"}.get(decision)
    if not estado:
        raise ValueError(f"Decisión desconocida: {decision}")
    with db.conexion() as con:
        cambio = con.execute(
            "UPDATE aprobaciones SET estado = ?, nota = ?, decidido = ?, decidido_por = ?"
            + (", datos = ?" if datos is not None else "") + " WHERE id = ? AND estado = 'pendiente'",
            (estado, nota.strip()[:1000], _ahora(), por[:120],
             *([json.dumps(datos, ensure_ascii=False)] if datos is not None else []), ap_id),
        ).rowcount
    a = aprobacion(ap_id)
    if cambio and a:
        for accion in (_AL_APROBAR if estado == "aprobada" else _AL_RECHAZAR).get(a["tipo"], []):
            accion(a)
    return a


# ---------------------------------------------------------------- lo que hace cada aprobación del kit

@al_aprobar("kit")
def _aplicar_kit(a: dict):
    """Un borrador del kit aprobado: entran las partes que trae (voz, carriles, pruebas)."""
    d, actual = a["datos"], kit_marca.leer(a["negocio_id"])
    cambios = {}
    if d.get("voz"):
        cambios["voz"] = kit_marca.limpiar_voz(d["voz"])
    if d.get("carriles"):
        cambios["carriles"] = kit_marca.limpiar_carriles(d["carriles"])
    if d.get("pruebas"):
        nuevas = [p for p in (kit_marca.limpiar_prueba(x) for x in d["pruebas"]) if p]
        titulos = {p["titulo"].lower() for p in actual["pruebas"]}
        cambios["pruebas"] = actual["pruebas"] + [p for p in nuevas if p["titulo"].lower() not in titulos]
    if d.get("prohibidas"):
        cambios["prohibidas"] = kit_marca.lineas("\n".join(actual["prohibidas"] + list(d["prohibidas"])), 60)
    if d.get("contexto"):
        cambios["contexto"] = kit_marca.limpiar_contexto(d["contexto"])
    if d.get("objetivo") and d["objetivo"].get("metrica") in ("leads", "llamadas", "ventas", "seguidores"):
        cambios["objetivo"] = {"metrica": d["objetivo"]["metrica"], "valor": d["objetivo"].get("valor") or 0}
    est = d.get("estrategia") or {}
    if est:  # límites, ángulos, llamada a la acción, formatos…: se suman a lo que ya hay, sin borrar lo que no trae
        if est.get("voz"):
            cambios["voz"] = kit_marca.limpiar_voz({**(cambios.get("voz") or actual["voz"]), **est["voz"]})
        partes = dict(est)
        for clave in ("limites", "cta", "formatos"):
            if clave in partes:
                partes[clave] = {**actual[clave], **partes[clave]}
        cambios.update(kit_marca.limpiar_estrategia(partes))
    kit_marca.cambiar(a["negocio_id"], **cambios)
    if d.get("ortografia"):  # los nombres que Monti tiene que escribir bien en los subtítulos
        from . import identidad
        identidad.anadir_palabras(a["negocio_id"], d["ortografia"])
    if d.get("ficha") or d.get("competencia"):
        _aplicar_a_la_ficha(a["negocio_id"], d.get("ficha") or {}, d.get("competencia") or [])


def _aplicar_a_la_ficha(negocio_id: int, campos: dict, competencia: list[dict]):
    """Lo que sale de las llamadas sustituye a lo que había en la ficha; la competencia se suma (sin repetir) y Lupi
    empieza a seguirla."""
    neg = db.negocio(negocio_id)
    if not neg:
        return
    ficha = dict(neg["ficha"])
    for k, v in campos.items():
        if str(v or "").strip():
            ficha[k] = str(v).strip()
    if competencia:
        filas = ficha.get("competidores") if isinstance(ficha.get("competidores"), list) else []
        vistos = {(r, str(f.get(r) or "").lower().lstrip("@")) for f in filas for r in ("instagram", "tiktok", "youtube")}
        for c in competencia:
            fila = {"nombre": str(c.get("nombre") or "")[:120], "web": "", "linkedin": "",
                    **{r: str(c.get(r) or "").strip().lstrip("@")[:120] for r in ("instagram", "tiktok", "youtube")}}
            if not any((r, fila[r].lower()) in vistos for r in ("instagram", "tiktok", "youtube") if fila[r]):
                filas.append(fila)
        ficha["competidores"] = filas
    db.actualizar_negocio(negocio_id, ficha)
    from . import analista
    analista.desde_la_ficha(db.negocio(negocio_id))
    tipos = {"directa", "adyacente", "aspiracional", "remix"}
    with db.conexion() as con:  # el tipo de cada cuenta de la competencia (Lupi compara distinto según el tipo)
        for c in competencia:
            for red in ("instagram", "tiktok", "youtube"):
                usuario = analista.usuario_de(red, str(c.get(red) or "")) if c.get(red) else ""
                if usuario and c.get("tipo") in tipos:
                    con.execute("UPDATE cuentas SET tipo = ? WHERE negocio_id = ? AND plataforma = ? AND usuario = ? "
                                "AND propia = 0", (c["tipo"], negocio_id, red, usuario))


@al_aprobar("cuentas")
def _seguir_cuentas(a: dict):
    """Las cuentas que propone Lupi y apruebas: empieza a seguirlas."""
    from . import analista
    for c in a["datos"].get("cuentas") or []:
        analista.anadir_cuenta(a["negocio_id"], c.get("plataforma", ""), c.get("usuario", ""), tipo=c.get("tipo", ""))


@al_rechazar("cuentas")
def _no_proponer_mas(a: dict):
    """Las que rechazas no se vuelven a proponer."""
    from . import analista, estado
    viejas = estado.leer(a["negocio_id"], analista.AGENTE).get("descartadas") or []
    nuevas = [f"{c.get('plataforma')}:{str(c.get('usuario', '')).lower()}" for c in a["datos"].get("cuentas") or []]
    estado.cambiar(a["negocio_id"], analista.AGENTE, descartadas=list(dict.fromkeys(viejas + nuevas))[-500:])


@al_aprobar("leccion")
def _activar_leccion(a: dict):
    kit_marca.activar_leccion(a["negocio_id"], a["datos"].get("leccion_id", ""))


@al_rechazar("leccion")
def _quitar_leccion(a: dict):
    kit_marca.borrar_leccion(a["negocio_id"], a["datos"].get("leccion_id", ""))


def proponer_leccion(negocio_id: int, agente: str, regla: str, evidencia: str = "") -> dict | None:
    """Un agente cree que ha aprendido algo: la regla queda pendiente hasta que la apruebes, siempre."""
    leccion = kit_marca.anadir_leccion(negocio_id, regla, origen=AGENTES.get(agente, {}).get("nombre", agente),
                                       evidencia=evidencia, activa=False)
    if not leccion:
        return None
    return pedir(negocio_id, agente, "leccion", f"Nueva regla: {leccion['regla']}",
                 {"leccion_id": leccion["id"], "regla": leccion["regla"], "evidencia": evidencia}, siempre=True)
