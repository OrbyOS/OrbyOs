"""Base de datos (SQLite): usuarios, sesiones, negocios, análisis, ediciones y gasto."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta

from .config import DB_PATH

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creado TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL DEFAULT '',
    clave TEXT NOT NULL,            -- scrypt$sal$hash
    es_admin INTEGER NOT NULL DEFAULT 0,
    plan TEXT NOT NULL DEFAULT 'prueba',
    activo INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS sesiones (
    token TEXT PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    creado TEXT NOT NULL,
    caduca TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS negocios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creado TEXT NOT NULL,
    nombre TEXT NOT NULL,
    ficha TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS informes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    creado TEXT NOT NULL,
    estado TEXT NOT NULL,          -- en_curso | listo | error
    secciones TEXT NOT NULL,       -- JSON {modulo: {...}}
    registro TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS ediciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    creado TEXT NOT NULL,
    titulo TEXT NOT NULL DEFAULT '',
    estado TEXT NOT NULL,          -- en_cola | en_curso | listo | error
    paso TEXT NOT NULL DEFAULT '',
    estilo TEXT NOT NULL DEFAULT '{}',
    resultado TEXT NOT NULL DEFAULT '{}',
    registro TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS estilos (
    negocio_id INTEGER PRIMARY KEY REFERENCES negocios(id),
    actualizado TEXT NOT NULL,
    datos TEXT NOT NULL            -- JSON con la plantilla de edición
);
CREATE TABLE IF NOT EXISTS solicitudes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creado TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'nueva',   -- nueva | contactada | agendada | cliente | descartada
    datos TEXT NOT NULL,                    -- JSON con lo que rellenó en la landing
    notas TEXT NOT NULL DEFAULT '',
    usuario_id INTEGER,
    negocio_id INTEGER
);
CREATE TABLE IF NOT EXISTS invitaciones (
    token TEXT PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
    creado TEXT NOT NULL,
    usado INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS marcas (
    negocio_id INTEGER PRIMARY KEY REFERENCES negocios(id),
    actualizado TEXT NOT NULL,
    datos TEXT NOT NULL            -- JSON: color, logo, ajustes y preferencias recordadas del editor
);
CREATE TABLE IF NOT EXISTS enlaces (
    token TEXT PRIMARY KEY,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    creado TEXT NOT NULL,
    activo INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS gastos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creado TEXT NOT NULL,
    usuario_id INTEGER,
    negocio_id INTEGER,
    concepto TEXT NOT NULL,        -- analisis | actualizar:<vertical> | estilo | edicion
    referencia INTEGER,
    coste_claude REAL NOT NULL DEFAULT 0,
    coste_apify REAL NOT NULL DEFAULT 0,
    detalle TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS vega_mensajes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    usuario_id INTEGER,
    rol TEXT NOT NULL,             -- usuario | vega
    texto TEXT NOT NULL,
    creado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS kits (
    negocio_id INTEGER PRIMARY KEY REFERENCES negocios(id),
    actualizado TEXT NOT NULL,
    datos TEXT NOT NULL            -- JSON: voz, carriles, mezcla, pruebas, lecciones, prohibidas, autonomía
);
CREATE TABLE IF NOT EXISTS posts_fotos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    post_id INTEGER NOT NULL REFERENCES posts(id),
    capturado TEXT NOT NULL,
    horas REAL NOT NULL,                   -- la edad del post en ese momento
    vistas INTEGER NOT NULL DEFAULT 0,
    comentarios INTEGER NOT NULL DEFAULT 0,
    envios INTEGER NOT NULL DEFAULT 0      -- compartidos + guardados
);
CREATE INDEX IF NOT EXISTS posts_fotos_post ON posts_fotos (post_id);
CREATE TABLE IF NOT EXISTS onboarding (
    negocio_id INTEGER PRIMARY KEY REFERENCES negocios(id),
    actualizado TEXT NOT NULL,
    datos TEXT NOT NULL            -- JSON: los datos básicos, las llamadas (hasta 3) y la extracción
);
CREATE TABLE IF NOT EXISTS aprobaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    creado TEXT NOT NULL,
    agente TEXT NOT NULL,
    tipo TEXT NOT NULL,            -- qué se aprueba: voz, leccion, guion, video, publicacion, respuesta...
    resumen TEXT NOT NULL,
    datos TEXT NOT NULL DEFAULT '{}',
    clave INTEGER NOT NULL DEFAULT 0,       -- vende, afirma algo o responde a alguien: espera aunque haya autonomía
    estado TEXT NOT NULL DEFAULT 'pendiente',  -- pendiente | aprobada | rechazada | cambios
    nota TEXT NOT NULL DEFAULT '',
    decidido TEXT,
    decidido_por TEXT NOT NULL DEFAULT ''   -- correo de quien decide, o «piloto automático»
);
CREATE TABLE IF NOT EXISTS estado_agentes (
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    agente TEXT NOT NULL,
    actualizado TEXT NOT NULL,
    datos TEXT NOT NULL DEFAULT '{}',       -- JSON: si está trabajando, lo último que hizo y sus avisos
    PRIMARY KEY (negocio_id, agente)
);
CREATE TABLE IF NOT EXISTS cuentas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    plataforma TEXT NOT NULL,               -- instagram | tiktok | youtube
    usuario TEXT NOT NULL,
    propia INTEGER NOT NULL DEFAULT 0,
    nivel INTEGER NOT NULL DEFAULT 2,       -- 1 referente principal · 2 normal · 3 lejano
    ultimo_escaneo TEXT,
    aviso TEXT NOT NULL DEFAULT '',
    UNIQUE (negocio_id, plataforma, usuario)
);
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    cuenta_id INTEGER NOT NULL REFERENCES cuentas(id),
    plataforma TEXT NOT NULL,
    url TEXT NOT NULL,
    publicado TEXT NOT NULL DEFAULT '',
    segundos INTEGER NOT NULL DEFAULT 0,
    texto TEXT NOT NULL DEFAULT '',
    vistas INTEGER NOT NULL DEFAULT 0,
    likes INTEGER NOT NULL DEFAULT 0,
    comentarios INTEGER NOT NULL DEFAULT 0,
    compartidos INTEGER NOT NULL DEFAULT 0,
    imagen TEXT NOT NULL DEFAULT '',
    video_url TEXT NOT NULL DEFAULT '',
    actualizado TEXT NOT NULL,
    x REAL NOT NULL DEFAULT 0,              -- veces lo normal de su cuenta
    destaca INTEGER NOT NULL DEFAULT 0,
    transcripcion TEXT NOT NULL DEFAULT '',
    gancho TEXT NOT NULL DEFAULT '',        -- lo que se dice en los primeros segundos
    plantilla TEXT NOT NULL DEFAULT '{}',   -- el desmontaje para hacer el remix
    estado_plantilla TEXT NOT NULL DEFAULT '',  -- '' | lista | fallida
    intentos INTEGER NOT NULL DEFAULT 0,
    UNIQUE (negocio_id, url)
);
CREATE TABLE IF NOT EXISTS piezas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    creado TEXT NOT NULL,
    dia TEXT NOT NULL,                      -- el día del «Graba hoy» en el que se propuso
    estado TEXT NOT NULL DEFAULT 'propuesta',  -- propuesta | aprobada | rechazada | guion | grabada | publicada
    tipo TEXT NOT NULL,                     -- remix | propio | original | oferta
    carril TEXT NOT NULL DEFAULT '',
    etapa TEXT NOT NULL DEFAULT '',
    fuente_post_id INTEGER,                 -- el post que se rehace (remix)
    titulo TEXT NOT NULL,
    angulo TEXT NOT NULL DEFAULT '',
    formato TEXT NOT NULL DEFAULT '',
    esquema TEXT NOT NULL DEFAULT '[]',     -- JSON: los pasos del guion
    grabar_antes TEXT NOT NULL DEFAULT '',
    aprobacion_id INTEGER,
    datos TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS guiones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    pieza_id INTEGER NOT NULL REFERENCES piezas(id),
    creado TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    estado TEXT NOT NULL,                   -- bloqueado | pendiente | aprobado | rechazado | sustituido
    autor TEXT NOT NULL DEFAULT 'guionista',  -- guionista | tú
    texto TEXT NOT NULL DEFAULT '',
    gancho_fuente TEXT NOT NULL DEFAULT '',
    cta TEXT NOT NULL DEFAULT '',           -- comentar | seguir | enlace | mensaje | ninguna
    palabra_clave TEXT NOT NULL DEFAULT '',
    hashtags TEXT NOT NULL DEFAULT '[]',
    afirmaciones TEXT NOT NULL DEFAULT '[]',
    textos TEXT NOT NULL DEFAULT '{}',      -- el texto del post en cada plataforma
    validacion TEXT NOT NULL DEFAULT '{}',  -- fallos y avisos del validador
    aprobacion_id INTEGER,
    nota TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS conexiones (
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    servicio TEXT NOT NULL,                 -- zernio…
    actualizado TEXT NOT NULL,
    datos TEXT NOT NULL DEFAULT '{}',       -- JSON: clave (nunca se vuelve a enseñar), perfil, cuentas vistas
    PRIMARY KEY (negocio_id, servicio)
);
CREATE TABLE IF NOT EXISTS publicaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    edicion_id INTEGER NOT NULL REFERENCES ediciones(id),
    guion_id INTEGER,
    creado TEXT NOT NULL,
    plataforma TEXT NOT NULL,
    cuenta TEXT NOT NULL DEFAULT '',        -- id de la cuenta en Zernio
    texto TEXT NOT NULL DEFAULT '',
    programado TEXT NOT NULL,               -- fecha y hora local
    modo TEXT NOT NULL DEFAULT 'zernio',    -- zernio | tu (lo publicas tú: Instagram con audio en tendencia)
    estado TEXT NOT NULL DEFAULT 'programada',  -- programada | tu_publicas | publicada | fallida | cancelada
    clave_unica TEXT NOT NULL,              -- para no publicar nunca dos veces
    externo_id TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    utm TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    UNIQUE (negocio_id, clave_unica)
);
CREATE TABLE IF NOT EXISTS guias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    token TEXT NOT NULL UNIQUE,             -- la dirección pública /g/<token>
    palabra TEXT NOT NULL,
    guion_id INTEGER,
    creado TEXT NOT NULL,
    titulo TEXT NOT NULL,
    contenido TEXT NOT NULL DEFAULT '',     -- texto de la guía (párrafos y listas sencillas)
    enlace_externo TEXT NOT NULL DEFAULT '',-- si la guía vive en tu web, un Google Doc o Notion
    pedir_email INTEGER NOT NULL DEFAULT 1,
    visitas INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS automatizaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    palabra TEXT NOT NULL,
    plataforma TEXT NOT NULL,
    cuenta TEXT NOT NULL,
    externo_id TEXT NOT NULL DEFAULT '',
    creado TEXT NOT NULL,
    estado TEXT NOT NULL DEFAULT 'activa',  -- activa | fallida | apagada
    error TEXT NOT NULL DEFAULT '',
    UNIQUE (negocio_id, palabra, plataforma)
);
CREATE TABLE IF NOT EXISTS conversaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    externo_id TEXT NOT NULL,
    cuenta TEXT NOT NULL,
    plataforma TEXT NOT NULL,
    participante TEXT NOT NULL DEFAULT '',
    usuario TEXT NOT NULL DEFAULT '',
    ultima TEXT NOT NULL DEFAULT '',        -- fecha del último mensaje
    temperatura TEXT NOT NULL DEFAULT '',   -- caliente | templado | frio | spam
    intencion TEXT NOT NULL DEFAULT '',
    resumen TEXT NOT NULL DEFAULT '',
    huella TEXT NOT NULL DEFAULT '',        -- de los mensajes ya clasificados: no se paga dos veces
    contacto_id INTEGER,
    UNIQUE (negocio_id, externo_id)
);
CREATE TABLE IF NOT EXISTS mensajes_dm (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    conversacion_id INTEGER NOT NULL REFERENCES conversaciones(id),
    externo_id TEXT NOT NULL,
    direccion TEXT NOT NULL,                -- entrante | saliente
    texto TEXT NOT NULL DEFAULT '',
    creado TEXT NOT NULL,
    UNIQUE (negocio_id, externo_id)
);
CREATE TABLE IF NOT EXISTS contactos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    creado TEXT NOT NULL,
    nombre TEXT NOT NULL DEFAULT '',
    usuario TEXT NOT NULL DEFAULT '',
    plataforma TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    origen TEXT NOT NULL DEFAULT '',        -- guia | dm
    palabra TEXT NOT NULL DEFAULT '',
    utm TEXT NOT NULL DEFAULT '',
    temperatura TEXT NOT NULL DEFAULT 'templado',
    ultima TEXT NOT NULL DEFAULT '',
    crm TEXT NOT NULL DEFAULT ''            -- '' | enviado | error: …
);
CREATE TABLE IF NOT EXISTS metricas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    publicacion_id INTEGER NOT NULL REFERENCES publicaciones(id),
    momento TEXT NOT NULL,                  -- 1h | 24h | 72h | 7d | 30d
    capturado TEXT NOT NULL,
    datos TEXT NOT NULL DEFAULT '{}',       -- vistas, likes, comentarios, compartidos, guardados, seguidores, salto…
    UNIQUE (publicacion_id, momento)
);
CREATE TABLE IF NOT EXISTS postmortems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    publicacion_id INTEGER NOT NULL REFERENCES publicaciones(id),
    creado TEXT NOT NULL,
    tipo TEXT NOT NULL,                     -- despegue | flop | record
    x REAL NOT NULL DEFAULT 0,
    datos TEXT NOT NULL DEFAULT '{}',
    UNIQUE (publicacion_id, tipo)
);
CREATE TABLE IF NOT EXISTS eventos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    creado TEXT NOT NULL,
    tipo TEXT NOT NULL,                     -- clic | lead | llamada | venta
    utm_content TEXT NOT NULL DEFAULT '',
    visitante TEXT NOT NULL DEFAULT '',
    importe REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS informes_semanales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    semana TEXT NOT NULL,                   -- el lunes de la semana
    creado TEXT NOT NULL,
    datos TEXT NOT NULL DEFAULT '{}',
    UNIQUE (negocio_id, semana)
);
CREATE TABLE IF NOT EXISTS mensajes_salida (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    creado TEXT NOT NULL,
    texto TEXT NOT NULL,
    botones TEXT NOT NULL DEFAULT '[]',
    video TEXT NOT NULL DEFAULT '',         -- ruta de un vídeo que acompaña al mensaje
    prioridad TEXT NOT NULL DEFAULT 'normal',  -- alta | normal: las altas no esperan a que acabe el silencio
    clave TEXT NOT NULL DEFAULT '',         -- para no repetir el mismo aviso
    estado TEXT NOT NULL DEFAULT 'pendiente',  -- pendiente | enviado | fallido | agrupado
    intentos INTEGER NOT NULL DEFAULT 0,
    repeticiones INTEGER NOT NULL DEFAULT 0,
    enviado TEXT,
    mensaje_id INTEGER
);
CREATE TABLE IF NOT EXISTS palabras_clave (
    negocio_id INTEGER NOT NULL REFERENCES negocios(id),
    palabra TEXT NOT NULL,
    guion_id INTEGER,
    creado TEXT NOT NULL,
    PRIMARY KEY (negocio_id, palabra)
);
"""

# Columnas añadidas después de la primera versión (bases de datos ya creadas).
MIGRACIONES = [
    ("negocios", "usuario_id", "INTEGER REFERENCES usuarios(id)"),
    ("informes", "trabajo", "TEXT NOT NULL DEFAULT ''"),
    ("usuarios", "tipo", "TEXT NOT NULL DEFAULT 'negocio'"),
    ("ediciones", "modo", "TEXT NOT NULL DEFAULT ''"),       # camara | voz | largo ('' = edición automática antigua)
    ("ediciones", "fase", "TEXT NOT NULL DEFAULT ''"),       # procesando | revisar | plan | montando | listo | error
    ("ediciones", "datos", "TEXT NOT NULL DEFAULT '{}'"),    # frases, plan, ajustes y revisión del editor
    ("conversaciones", "palabra", "TEXT NOT NULL DEFAULT ''"),          # la última palabra clave que ha usado
    ("conversaciones", "ultima_entrante", "TEXT NOT NULL DEFAULT ''"),  # su último mensaje: Instagram da 24 h para contestar
    ("mensajes_dm", "origen", "TEXT NOT NULL DEFAULT 'dm'"),            # dm | comentario | guia
    ("posts", "guardados", "INTEGER NOT NULL DEFAULT 0"),
    ("posts", "encaje", "TEXT NOT NULL DEFAULT ''"),          # '' sin revisar | si | no: si encaja con el negocio
    ("posts", "encaje_tipo", "TEXT NOT NULL DEFAULT ''"),     # educativo, opinión, historia, meme…
    ("posts", "encaje_motivo", "TEXT NOT NULL DEFAULT ''"),
    ("posts", "ritmo", "REAL NOT NULL DEFAULT 0"),            # en sus primeras 72 h: veces lo normal a esa edad
    ("posts", "despega", "INTEGER NOT NULL DEFAULT 0"),
    ("posts", "comentarios_top", "TEXT NOT NULL DEFAULT ''"),
    ("guiones", "ganchos", "TEXT NOT NULL DEFAULT '[]'"),     # otros ganchos para el mismo guion, para elegir o probar  # JSON: los comentarios más relevantes, ya leídos
    ("cuentas", "tipo", "TEXT NOT NULL DEFAULT ''"),          # directa | adyacente | aspiracional | remix (de la competencia)
]


@contextmanager
def conexion():
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def iniciar():
    with conexion() as con:
        con.executescript(ESQUEMA)
        for tabla, columna, tipo in MIGRACIONES:
            columnas = {f["name"] for f in con.execute(f"PRAGMA table_info({tabla})")}
            if columna not in columnas:
                con.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
        # Lo que estaba en marcha cuando se cerró la app ya no va a terminar.
        con.execute(
            "UPDATE informes SET estado = 'error', trabajo = '', registro = registro || ? WHERE estado = 'en_curso'",
            ("Interrumpido: la app se cerró mientras se generaba.\n",),
        )
        con.execute(
            "UPDATE ediciones SET estado = 'error', registro = registro || ? WHERE estado IN ('en_cola', 'en_curso')",
            ("Interrumpido: la app se cerró mientras se editaba.\n",),
        )
        # En el editor por pasos, un trabajo cortado vuelve al paso anterior en lugar de perderse.
        con.execute("UPDATE ediciones SET fase = 'plan', estado = 'listo', paso = 'El montaje se cortó: vuelve a montarlo.' "
                    "WHERE modo != '' AND fase = 'montando'")


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _inicio_de_mes() -> str:
    return datetime.now().strftime("%Y-%m-01T00:00:00")


# ---------------------------------------------------------------- usuarios y sesiones

def crear_usuario(email: str, nombre: str, clave: str, *, es_admin: bool, plan: str, tipo: str = "negocio") -> int:
    with conexion() as con:
        cur = con.execute(
            "INSERT INTO usuarios (creado, email, nombre, clave, es_admin, plan, tipo) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (_ahora(), email.lower(), nombre, clave, int(es_admin), plan, tipo),
        )
        uid = cur.lastrowid
        if es_admin:
            # Los negocios de antes de las cuentas pasan al primer administrador.
            con.execute("UPDATE negocios SET usuario_id = ? WHERE usuario_id IS NULL", (uid,))
        return uid


def contar_usuarios() -> int:
    with conexion() as con:
        return con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]


def usuario_por_email(email: str) -> dict | None:
    with conexion() as con:
        f = con.execute("SELECT * FROM usuarios WHERE email = ?", (email.lower(),)).fetchone()
    return dict(f) if f else None


def usuario(usuario_id: int) -> dict | None:
    with conexion() as con:
        f = con.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
    return dict(f) if f else None


def actualizar_usuario(usuario_id: int, **campos):
    permitidos = {k: v for k, v in campos.items() if k in {"nombre", "plan", "es_admin", "activo", "clave", "tipo"}}
    if not permitidos:
        return
    with conexion() as con:
        con.execute(
            f"UPDATE usuarios SET {', '.join(f'{k} = ?' for k in permitidos)} WHERE id = ?",
            (*permitidos.values(), usuario_id),
        )


def crear_sesion(token: str, usuario_id: int, dias: int = 30):
    with conexion() as con:
        con.execute(
            "INSERT INTO sesiones (token, usuario_id, creado, caduca) VALUES (?, ?, ?, ?)",
            (token, usuario_id, _ahora(), (datetime.now() + timedelta(days=dias)).isoformat(timespec="seconds")),
        )


def usuario_de_sesion(token: str) -> dict | None:
    with conexion() as con:
        f = con.execute(
            "SELECT u.* FROM sesiones s JOIN usuarios u ON u.id = s.usuario_id "
            "WHERE s.token = ? AND s.caduca > ? AND u.activo = 1",
            (token, _ahora()),
        ).fetchone()
    return dict(f) if f else None


def borrar_sesion(token: str):
    with conexion() as con:
        con.execute("DELETE FROM sesiones WHERE token = ?", (token,))


def usuarios_con_uso() -> list[dict]:
    """Para el panel de administración: cada usuario con sus negocios, su uso del mes y su gasto."""
    mes = _inicio_de_mes()
    with conexion() as con:
        filas = con.execute(
            """
            SELECT u.*,
              (SELECT COUNT(*) FROM negocios n WHERE n.usuario_id = u.id) AS negocios,
              (SELECT COUNT(*) FROM gastos g WHERE g.usuario_id = u.id AND g.concepto = 'analisis' AND g.creado >= ?) AS analisis_mes,
              (SELECT COUNT(*) FROM gastos g WHERE g.usuario_id = u.id AND g.concepto = 'edicion' AND g.creado >= ?) AS ediciones_mes,
              (SELECT COALESCE(SUM(g.coste_claude + g.coste_apify), 0) FROM gastos g WHERE g.usuario_id = u.id AND g.creado >= ?) AS gasto_mes,
              (SELECT COALESCE(SUM(g.coste_claude + g.coste_apify), 0) FROM gastos g WHERE g.usuario_id = u.id) AS gasto_total
            FROM usuarios u ORDER BY u.id
            """,
            (mes, mes, mes),
        ).fetchall()
    return [dict(f) for f in filas]


# ---------------------------------------------------------------- negocios

def _negocio_de_fila(f) -> dict:
    return {"id": f["id"], "creado": f["creado"], "nombre": f["nombre"], "ficha": json.loads(f["ficha"]),
            "usuario_id": f["usuario_id"]}


def crear_negocio(ficha: dict, usuario_id: int | None = None) -> int:
    with conexion() as con:
        cur = con.execute(
            "INSERT INTO negocios (creado, nombre, ficha, usuario_id) VALUES (?, ?, ?, ?)",
            (_ahora(), ficha.get("nombre", "Sin nombre"), json.dumps(ficha, ensure_ascii=False), usuario_id),
        )
        return cur.lastrowid


def espacio_editor(usuario_id: int) -> int:
    """El espacio oculto donde van los reels del editor público (no es un negocio que se analice)."""
    with conexion() as con:
        for f in con.execute("SELECT id, ficha FROM negocios WHERE usuario_id = ?", (usuario_id,)):
            if json.loads(f["ficha"]).get("oculto"):
                return f["id"]
    return crear_negocio({"nombre": "Mis reels", "que_vende": "", "oculto": True}, usuario_id)


def negocios(usuario_id: int | None = None) -> list[dict]:
    """Los negocios de un usuario (o todos, para el administrador) con su último análisis."""
    filtro, params = ("WHERE n.usuario_id = ?", (usuario_id,)) if usuario_id is not None else ("", ())
    with conexion() as con:
        filas = con.execute(
            f"""
            SELECT n.*,
                   (SELECT COUNT(*) FROM informes i WHERE i.negocio_id = n.id) AS num_informes,
                   (SELECT i.estado FROM informes i WHERE i.negocio_id = n.id ORDER BY i.id DESC LIMIT 1) AS ultimo_estado,
                   (SELECT i.id FROM informes i WHERE i.negocio_id = n.id ORDER BY i.id DESC LIMIT 1) AS ultimo_id,
                   (SELECT i.creado FROM informes i WHERE i.negocio_id = n.id ORDER BY i.id DESC LIMIT 1) AS ultimo_creado
            FROM negocios n {filtro} ORDER BY n.id DESC
            """,
            params,
        ).fetchall()
    salida = [{
        **_negocio_de_fila(f),
        "num_informes": f["num_informes"], "ultimo_estado": f["ultimo_estado"],
        "ultimo_id": f["ultimo_id"], "ultimo_creado": f["ultimo_creado"],
    } for f in filas]
    return [n for n in salida if not n["ficha"].get("oculto")]


def contar_negocios(usuario_id: int) -> int:
    return len(negocios(usuario_id))


def actualizar_negocio(negocio_id: int, ficha: dict):
    with conexion() as con:
        con.execute(
            "UPDATE negocios SET nombre = ?, ficha = ? WHERE id = ?",
            (ficha.get("nombre", "Sin nombre"), json.dumps(ficha, ensure_ascii=False), negocio_id),
        )


def trabajo_en_marcha(negocio_id: int) -> bool:
    """Si hay un análisis o una edición de este negocio en marcha (no se puede borrar a medias)."""
    with conexion() as con:
        analisis = con.execute("SELECT 1 FROM informes WHERE negocio_id = ? AND estado = 'en_curso' LIMIT 1",
                               (negocio_id,)).fetchone()
        edicion = con.execute("SELECT 1 FROM ediciones WHERE negocio_id = ? AND estado IN ('en_cola', 'en_curso') LIMIT 1",
                              (negocio_id,)).fetchone()
    return bool(analisis or edicion)


def eliminar_negocio(negocio_id: int) -> list[int]:
    """Borra el negocio con sus análisis, ediciones, estilo y enlaces. Devuelve los ids de sus ediciones, para
    borrar también los vídeos del disco. El gasto se conserva, para que las cuentas del proyecto cuadren."""
    with conexion() as con:
        ediciones = [f["id"] for f in con.execute("SELECT id FROM ediciones WHERE negocio_id = ?", (negocio_id,))]
        for tabla in ("informes", "ediciones", "estilos", "enlaces", "marcas", "vega_mensajes", "kits", "aprobaciones",
                      "estado_agentes", "palabras_clave", "publicaciones", "conexiones", "guiones", "piezas", "posts",
                      "cuentas", "guias", "automatizaciones", "mensajes_dm", "conversaciones", "contactos", "metricas",
                      "postmortems", "eventos", "informes_semanales", "mensajes_salida", "onboarding", "posts_fotos"):
            con.execute(f"DELETE FROM {tabla} WHERE negocio_id = ?", (negocio_id,))
        con.execute("DELETE FROM negocios WHERE id = ?", (negocio_id,))
    return ediciones


def negocio(negocio_id: int) -> dict | None:
    with conexion() as con:
        f = con.execute("SELECT * FROM negocios WHERE id = ?", (negocio_id,)).fetchone()
    return _negocio_de_fila(f) if f else None


# ---------------------------------------------------------------- análisis (informes)

def contar_informes() -> int:
    with conexion() as con:
        return con.execute("SELECT COUNT(*) FROM informes").fetchone()[0]


def crear_informe(negocio_id: int, trabajo: str = "todo") -> int:
    with conexion() as con:
        cur = con.execute(
            "INSERT INTO informes (negocio_id, creado, estado, secciones, trabajo) VALUES (?, ?, 'en_curso', '{}', ?)",
            (negocio_id, _ahora(), trabajo),
        )
        return cur.lastrowid


def guardar_seccion(informe_id: int, modulo: str, contenido: dict):
    with conexion() as con:
        f = con.execute("SELECT secciones FROM informes WHERE id = ?", (informe_id,)).fetchone()
        secciones = json.loads(f["secciones"])
        secciones[modulo] = contenido
        con.execute(
            "UPDATE informes SET secciones = ? WHERE id = ?",
            (json.dumps(secciones, ensure_ascii=False), informe_id),
        )


def anotar(informe_id: int, linea: str):
    with conexion() as con:
        con.execute(
            "UPDATE informes SET registro = registro || ? WHERE id = ?",
            (f"[{datetime.now():%H:%M:%S}] {linea}\n", informe_id),
        )


def marcar_informe(informe_id: int, estado: str, trabajo: str = ""):
    with conexion() as con:
        con.execute("UPDATE informes SET estado = ?, trabajo = ? WHERE id = ?", (estado, trabajo, informe_id))


def cerrar_informe(informe_id: int, estado: str):
    marcar_informe(informe_id, estado, "")


def _informe_de_fila(f) -> dict:
    return {
        "id": f["id"], "negocio_id": f["negocio_id"], "creado": f["creado"], "estado": f["estado"],
        "trabajo": f["trabajo"], "secciones": json.loads(f["secciones"]), "registro": f["registro"],
    }


def informe(informe_id: int) -> dict | None:
    with conexion() as con:
        f = con.execute("SELECT * FROM informes WHERE id = ?", (informe_id,)).fetchone()
    return _informe_de_fila(f) if f else None


def ultimo_informe(negocio_id: int) -> dict | None:
    with conexion() as con:
        f = con.execute("SELECT * FROM informes WHERE negocio_id = ? ORDER BY id DESC LIMIT 1", (negocio_id,)).fetchone()
    return _informe_de_fila(f) if f else None


def informes_de(negocio_id: int) -> list[dict]:
    with conexion() as con:
        filas = con.execute(
            "SELECT id, creado, estado FROM informes WHERE negocio_id = ? ORDER BY id DESC", (negocio_id,)
        ).fetchall()
    return [dict(f) for f in filas]


# ---------------------------------------------------------------- enlaces de solo lectura

def crear_enlace(negocio_id: int, token: str):
    """Un enlace activo por negocio: el nuevo sustituye al anterior."""
    with conexion() as con:
        con.execute("UPDATE enlaces SET activo = 0 WHERE negocio_id = ?", (negocio_id,))
        con.execute("INSERT INTO enlaces (token, negocio_id, creado) VALUES (?, ?, ?)", (token, negocio_id, _ahora()))


def enlace_activo(negocio_id: int) -> str | None:
    with conexion() as con:
        f = con.execute("SELECT token FROM enlaces WHERE negocio_id = ? AND activo = 1 ORDER BY creado DESC LIMIT 1",
                        (negocio_id,)).fetchone()
    return f["token"] if f else None


def negocio_por_enlace(token: str) -> dict | None:
    with conexion() as con:
        f = con.execute("SELECT negocio_id FROM enlaces WHERE token = ? AND activo = 1", (token,)).fetchone()
    return negocio(f["negocio_id"]) if f else None


def desactivar_enlaces(negocio_id: int):
    with conexion() as con:
        con.execute("UPDATE enlaces SET activo = 0 WHERE negocio_id = ?", (negocio_id,))


# ---------------------------------------------------------------- edición

def crear_edicion(negocio_id: int, titulo: str, estilo: dict, *, modo: str = "", datos: dict | None = None) -> int:
    with conexion() as con:
        cur = con.execute(
            "INSERT INTO ediciones (negocio_id, creado, titulo, estado, estilo, modo, fase, datos) "
            "VALUES (?, ?, ?, 'en_cola', ?, ?, ?, ?)",
            (negocio_id, _ahora(), titulo, json.dumps(estilo, ensure_ascii=False), modo,
             "procesando" if modo else "", json.dumps(datos or {}, ensure_ascii=False)),
        )
        return cur.lastrowid


def guardar_datos_edicion(edicion_id: int, datos: dict, *, fase: str | None = None):
    with conexion() as con:
        con.execute("UPDATE ediciones SET datos = ? WHERE id = ?", (json.dumps(datos, ensure_ascii=False), edicion_id))
        if fase is not None:
            con.execute("UPDATE ediciones SET fase = ? WHERE id = ?", (fase, edicion_id))


def actualizar_edicion(edicion_id: int, *, estado: str | None = None, paso: str | None = None,
                       resultado: dict | None = None, linea: str | None = None):
    with conexion() as con:
        if estado is not None:
            con.execute("UPDATE ediciones SET estado = ? WHERE id = ?", (estado, edicion_id))
        if paso is not None:
            con.execute("UPDATE ediciones SET paso = ? WHERE id = ?", (paso, edicion_id))
        if resultado is not None:
            con.execute("UPDATE ediciones SET resultado = ? WHERE id = ?",
                        (json.dumps(resultado, ensure_ascii=False), edicion_id))
        if linea:
            con.execute("UPDATE ediciones SET registro = registro || ? WHERE id = ?",
                        (f"[{datetime.now():%H:%M:%S}] {linea}\n", edicion_id))


def _edicion_de_fila(f) -> dict:
    return {**dict(f), "estilo": json.loads(f["estilo"]), "resultado": json.loads(f["resultado"]),
            "datos": json.loads(f["datos"] or "{}")}


def edicion(edicion_id: int) -> dict | None:
    with conexion() as con:
        f = con.execute("SELECT * FROM ediciones WHERE id = ?", (edicion_id,)).fetchone()
    return _edicion_de_fila(f) if f else None


def ediciones_de(negocio_id: int) -> list[dict]:
    with conexion() as con:
        filas = con.execute("SELECT * FROM ediciones WHERE negocio_id = ? ORDER BY id DESC", (negocio_id,)).fetchall()
    return [_edicion_de_fila(f) for f in filas]


def estilo(negocio_id: int) -> dict | None:
    with conexion() as con:
        f = con.execute("SELECT * FROM estilos WHERE negocio_id = ?", (negocio_id,)).fetchone()
    return {**json.loads(f["datos"]), "actualizado": f["actualizado"]} if f else None


def guardar_estilo(negocio_id: int, datos: dict):
    datos = {k: v for k, v in datos.items() if k != "actualizado"}
    with conexion() as con:
        con.execute(
            "INSERT INTO estilos (negocio_id, actualizado, datos) VALUES (?, ?, ?) "
            "ON CONFLICT(negocio_id) DO UPDATE SET actualizado = excluded.actualizado, datos = excluded.datos",
            (negocio_id, _ahora(), json.dumps(datos, ensure_ascii=False)),
        )


def marca(negocio_id: int) -> dict:
    with conexion() as con:
        f = con.execute("SELECT datos FROM marcas WHERE negocio_id = ?", (negocio_id,)).fetchone()
    return json.loads(f["datos"]) if f else {}


def guardar_marca(negocio_id: int, datos: dict):
    with conexion() as con:
        con.execute(
            "INSERT INTO marcas (negocio_id, actualizado, datos) VALUES (?, ?, ?) "
            "ON CONFLICT(negocio_id) DO UPDATE SET actualizado = excluded.actualizado, datos = excluded.datos",
            (negocio_id, _ahora(), json.dumps(datos, ensure_ascii=False)),
        )


# ---------------------------------------------------------------- solicitudes de la landing e invitaciones

def crear_solicitud(datos: dict) -> int:
    with conexion() as con:
        cur = con.execute("INSERT INTO solicitudes (creado, datos) VALUES (?, ?)",
                          (_ahora(), json.dumps(datos, ensure_ascii=False)))
        return cur.lastrowid


def _solicitud_de_fila(f) -> dict:
    return {**dict(f), "datos": json.loads(f["datos"])}


def solicitudes() -> list[dict]:
    with conexion() as con:
        return [_solicitud_de_fila(f) for f in con.execute("SELECT * FROM solicitudes ORDER BY id DESC")]


def solicitud(solicitud_id: int) -> dict | None:
    with conexion() as con:
        f = con.execute("SELECT * FROM solicitudes WHERE id = ?", (solicitud_id,)).fetchone()
    return _solicitud_de_fila(f) if f else None


def actualizar_solicitud(solicitud_id: int, **campos):
    permitidos = {k: v for k, v in campos.items() if k in {"estado", "notas", "usuario_id", "negocio_id"}}
    if permitidos:
        with conexion() as con:
            con.execute(f"UPDATE solicitudes SET {', '.join(f'{k} = ?' for k in permitidos)} WHERE id = ?",
                        (*permitidos.values(), solicitud_id))


def crear_invitacion(token: str, usuario_id: int):
    with conexion() as con:
        con.execute("UPDATE invitaciones SET usado = 1 WHERE usuario_id = ?", (usuario_id,))
        con.execute("INSERT INTO invitaciones (token, usuario_id, creado) VALUES (?, ?, ?)", (token, usuario_id, _ahora()))


def invitacion(token: str) -> dict | None:
    with conexion() as con:
        f = con.execute("SELECT * FROM invitaciones WHERE token = ? AND usado = 0", (token,)).fetchone()
    return dict(f) if f else None


def invitacion_activa(usuario_id: int) -> str | None:
    with conexion() as con:
        f = con.execute("SELECT token FROM invitaciones WHERE usuario_id = ? AND usado = 0 ORDER BY creado DESC LIMIT 1",
                        (usuario_id,)).fetchone()
    return f["token"] if f else None


def usar_invitacion(token: str):
    with conexion() as con:
        con.execute("UPDATE invitaciones SET usado = 1 WHERE token = ?", (token,))


# ---------------------------------------------------------------- gasto

def abrir_gasto(*, usuario_id: int | None, negocio_id: int | None, concepto: str,
                referencia: int | None = None) -> int:
    """Se anota al lanzar el trabajo, para que cuente en el límite del plan aunque aún no haya terminado."""
    with conexion() as con:
        cur = con.execute(
            "INSERT INTO gastos (creado, usuario_id, negocio_id, concepto, referencia) VALUES (?, ?, ?, ?, ?)",
            (_ahora(), usuario_id, negocio_id, concepto, referencia),
        )
        return cur.lastrowid


def cerrar_gasto(gasto_id: int, uso: dict, *, referencia: int | None = None, concepto: str | None = None):
    with conexion() as con:
        con.execute(
            "UPDATE gastos SET coste_claude = ?, coste_apify = ?, detalle = ?, "
            "referencia = COALESCE(?, referencia), concepto = COALESCE(?, concepto) WHERE id = ?",
            (uso.get("coste_claude", 0), uso.get("apify_coste", 0), json.dumps(uso, ensure_ascii=False),
             referencia, concepto, gasto_id),
        )


# ---------------------------------------------------------------- la conversación con Vega

def guardar_mensaje_vega(negocio_id: int, usuario_id: int | None, rol: str, texto: str):
    with conexion() as con:
        con.execute("INSERT INTO vega_mensajes (negocio_id, usuario_id, rol, texto, creado) VALUES (?, ?, ?, ?, ?)",
                    (negocio_id, usuario_id, rol, texto, _ahora()))


def mensajes_vega(negocio_id: int, n: int = 40) -> list[dict]:
    """Los últimos mensajes de la conversación con Vega de un negocio, del más antiguo al más nuevo."""
    with conexion() as con:
        filas = con.execute("SELECT * FROM vega_mensajes WHERE negocio_id = ? ORDER BY id DESC LIMIT ?",
                            (negocio_id, n)).fetchall()
    return [dict(f) for f in reversed(filas)]


def borrar_mensajes_vega(negocio_id: int):
    with conexion() as con:
        con.execute("DELETE FROM vega_mensajes WHERE negocio_id = ?", (negocio_id,))


def mensajes_vega_hoy(usuario_id: int) -> int:
    """Cuántas preguntas le ha hecho hoy a Vega, para el límite diario."""
    with conexion() as con:
        f = con.execute("SELECT COUNT(*) AS n FROM vega_mensajes WHERE usuario_id = ? AND rol = 'usuario' AND creado >= ?",
                        (usuario_id, datetime.now().strftime("%Y-%m-%dT00:00:00"))).fetchone()
    return f["n"] or 0


def uso_del_mes(usuario_id: int) -> dict:
    mes = _inicio_de_mes()
    with conexion() as con:
        f = con.execute(
            "SELECT "
            " SUM(CASE WHEN concepto = 'analisis' THEN 1 ELSE 0 END) AS analisis,"
            " SUM(CASE WHEN concepto LIKE 'actualizar:%' THEN 1 ELSE 0 END) AS actualizaciones,"
            " SUM(CASE WHEN concepto = 'edicion' THEN 1 ELSE 0 END) AS ediciones "
            "FROM gastos WHERE usuario_id = ? AND creado >= ?",
            (usuario_id, mes),
        ).fetchone()
    return {"analisis": f["analisis"] or 0, "actualizaciones": f["actualizaciones"] or 0,
            "ediciones": f["ediciones"] or 0}


def gastos_recientes(limite: int = 40) -> list[dict]:
    with conexion() as con:
        filas = con.execute(
            "SELECT g.*, u.email, COALESCE(n.nombre, CASE WHEN g.negocio_id IS NOT NULL THEN 'Negocio eliminado' END) AS negocio "
            "FROM gastos g "
            "LEFT JOIN usuarios u ON u.id = g.usuario_id LEFT JOIN negocios n ON n.id = g.negocio_id "
            "ORDER BY g.id DESC LIMIT ?",
            (limite,),
        ).fetchall()
    return [dict(f) for f in filas]


def gasto_total() -> dict:
    mes = _inicio_de_mes()
    with conexion() as con:
        f = con.execute(
            "SELECT COALESCE(SUM(coste_claude), 0) AS claude, COALESCE(SUM(coste_apify), 0) AS apify, "
            "COALESCE(SUM(CASE WHEN creado >= ? THEN coste_claude + coste_apify ELSE 0 END), 0) AS mes "
            "FROM gastos",
            (mes,),
        ).fetchone()
    return dict(f)
