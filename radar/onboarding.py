"""El onboarding: el formulario corto de la landing de venta y la llamada de onboarding a fondo.

De la llamada sale la ficha del negocio, y de la ficha sale todo lo demás (los análisis se apoyan en estas
respuestas). Cada campo es (clave, etiqueta, tipo, ayuda). Los tipos: text, textarea, select:<opciones> y
competidores (una fila por competidor, con un campo para cada dato).
"""
from itertools import zip_longest

from . import metodo

FACTURACION = ["Aún no facturo", "Menos de 3.000 € al mes", "De 3.000 a 10.000 € al mes", "De 10.000 a 30.000 € al mes",
               "De 30.000 a 100.000 € al mes", "Más de 100.000 € al mes"]

# ---------------------------------------------------------------- 1. Formulario de la landing (para cualificar)

SOLICITUD = [
    ("nombre", "Tu nombre", "text", ""),
    ("email", "Correo", "email", ""),
    ("telefono", "WhatsApp", "tel", "Para escribirte y agendar la llamada."),
    ("tipo", "¿Qué eres?", "select:negocio=Tengo un negocio|agencia=Soy una agencia", ""),
    ("negocio", "Nombre del negocio o de la agencia", "text", ""),
    ("web", "Web o Instagram", "text", ""),
    ("que_vende", "Qué vendes y a quién", "textarea", "En dos líneas."),
    ("precio", "Precio de tu oferta principal", "text", "Por ejemplo: mentoría de 3 meses, 3.000 €."),
    ("facturacion", "Facturación mensual aproximada", "select:" + "|".join(f"{x}={x}" for x in FACTURACION), ""),
    ("objetivo", "¿Qué quieres conseguir en los próximos 3 meses?", "textarea", ""),
    ("origen", "¿Cómo nos has conocido?", "text", ""),
]
OBLIGATORIOS_SOLICITUD = {"nombre", "email", "telefono", "tipo", "negocio", "que_vende", "facturacion", "objetivo"}

ESTADOS_SOLICITUD = {
    "nueva": "Nueva",
    "contactada": "Contactada",
    "agendada": "Llamada agendada",
    "cliente": "Onboarding hecho",
    "descartada": "Descartada",
}


def _opciones(dic: dict) -> str:
    return "select:" + "|".join(f"{k}={v}" for k, v in dic.items())


# ---------------------------------------------------------------- 2. La llamada de onboarding (a fondo)

SECCIONES = [
    {
        "clave": "negocio",
        "titulo": "El negocio hoy",
        "guion": "Que te cuente el negocio con sus palabras. Escucha cómo lo explica: es el punto de partida de los textos.",
        "preguntas": ["¿Qué vendes y a quién, en una frase?", "¿Cuánto llevas y cómo has llegado hasta aquí?",
                      "¿Cuánto facturas al mes y cuántos clientes nuevos entran?", "¿Quién hay en el equipo y qué hace cada uno?",
                      "¿Dónde quieres estar en 3, 6 y 12 meses, con cifras?", "¿Qué crees que te frena hoy?",
                      "¿Hay algún país o idioma que vaya por delante en tu tema y del que quieras ver contenido?"],
        "campos": [
            ("nombre", "Nombre del negocio", "text", ""),
            ("web", "Web", "text", ""),
            ("tipo_negocio", "Tipo de negocio", _opciones(metodo.TIPOS_NEGOCIO), ""),
            ("mercado", "Dónde vende", "text", "País o países, idioma."),
            ("mercados_referencia", "Mercados de referencia", "text",
             "Países e idiomas de los que mirar contenido aunque no venda allí. Ej.: Brasil en portugués, Estados Unidos en inglés."),
            ("que_vende", "Qué vende, en una frase", "textarea", ""),
            ("trayectoria", "Años y trayectoria", "textarea", ""),
            ("facturacion", "Facturación mensual", "select:" + "|".join(f"{x}={x}" for x in FACTURACION), ""),
            ("clientes_mes", "Clientes nuevos al mes", "text", ""),
            ("equipo", "Equipo y quién hace qué", "textarea", "Marketing, ventas, contenido, entrega."),
            ("objetivo", "Objetivos a 3, 6 y 12 meses", "textarea", "Con cifras."),
            ("freno", "Lo que cree que le frena", "textarea", ""),
        ],
    },
    {
        "clave": "cliente",
        "titulo": "Cliente ideal",
        "guion": "Pide ejemplos de clientes reales, no un avatar inventado. Apunta las frases literales: son oro para el contenido.",
        "preguntas": ["Piensa en tus 3 mejores clientes: ¿quiénes son y qué tienen en común?", "¿Qué problema tenían cuando llegaron?",
                      "¿Qué quieren conseguir de verdad?", "¿Qué habían probado antes y por qué no les funcionó?",
                      "¿Qué objeciones te ponen antes de comprar?", "¿Por qué te acaban eligiendo?",
                      "¿Cómo te buscan o con qué palabras describen su problema?"],
        "campos": [
            ("a_quien", "Quién es su cliente ideal", "textarea", "Perfil, situación, momento."),
            ("mejores_clientes", "Sus mejores clientes (ejemplos reales)", "textarea", ""),
            ("dolores", "Problemas y dolores", "textarea", "Con sus palabras."),
            ("deseos", "Lo que quieren conseguir", "textarea", ""),
            ("ha_probado", "Lo que ya han probado", "textarea", ""),
            ("objeciones", "Objeciones antes de comprar", "textarea", ""),
            ("por_que_compran", "Por qué le eligen", "textarea", ""),
            ("palabras_clave", "Cómo le buscan", "text", "Separado por comas."),
        ],
    },
    {
        "clave": "oferta",
        "titulo": "La oferta",
        "guion": "Recorre toda la escalera de ofertas, de la más barata a la más cara. Pide cifras de resultados y testimonios con enlace.",
        "preguntas": ["¿Cuál es tu oferta principal? ¿Qué incluye, cómo se entrega y cuánto cuesta?",
                      "¿Qué otras ofertas tienes, de la más barata a la más cara?", "¿Das garantía? ¿Hay bonus?",
                      "¿Qué resultados han conseguido tus clientes, con cifras?", "¿Tienes testimonios o casos grabados?",
                      "¿Tienes algún regalo de entrada (guía, clase, plantilla)?", "¿Por qué tú y no otro?"],
        "campos": [
            ("precio_principal", "Oferta principal y precio", "textarea", "Qué incluye, formato, duración y precio."),
            ("ticket", "Ticket de la oferta principal", "select:bajo=Bajo (menos de 300 €)|medio=Medio (300-2.000 €)|alto=Alto (más de 2.000 €)", ""),
            ("escalera", "El resto de ofertas", "textarea", "De la más barata a la más cara, con precio."),
            ("garantia", "Garantía y bonus", "textarea", ""),
            ("resultados", "Resultados de clientes", "textarea", "Con cifras y nombres si se pueden usar."),
            ("testimonios", "Testimonios y casos disponibles", "textarea", "Enlaces."),
            ("lead_magnet", "Regalo de entrada", "textarea", ""),
            ("diferencia", "Por qué él y no la competencia", "textarea", ""),
        ],
    },
    {
        "clave": "captacion",
        "titulo": "Captación y ventas",
        "guion": "Dibuja con él el camino del cliente, del primer contacto al pago. Pide números aunque sean aproximados.",
        "preguntas": ["¿De dónde te llegan hoy los clientes (y en qué porcentaje)?", "¿Cuál es el camino desde que te descubren hasta que pagan?",
                      "¿Vendes por lanzamientos, en evergreen o con llamada?", "¿Quién hace las llamadas, cuántas al mes y cuántas cierras?",
                      "¿Tienes lista de correo o comunidad? ¿Cuánta gente?", "¿Qué herramientas usas (web, CRM, correo, pagos, calendario)?",
                      "¿Conoces tus números: coste por lead, conversión, coste por cliente?"],
        "campos": [
            ("canales", "De dónde vienen los clientes", "textarea", "Canales y porcentaje."),
            ("modelo_venta", "Cómo vende", _opciones(metodo.MODELOS_VENTA), ""),
            ("funnel_actual", "Su funnel paso a paso", "textarea", ""),
            ("proceso_venta", "Proceso de venta", "textarea", "Setter, closer, llamadas al mes, tasa de cierre."),
            ("lanzamientos", "Lanzamientos", "textarea", "Fechas y resultados de los últimos."),
            ("lista", "Lista de correo o comunidad", "text", "Tamaño y frecuencia."),
            ("herramientas", "Herramientas", "textarea", ""),
            ("metricas", "Métricas que conoce", "textarea", ""),
        ],
    },
    {
        "clave": "anuncios",
        "titulo": "Publicidad",
        "guion": "Si invierte, entiende qué le funciona y quién lo lleva. Si no, por qué no.",
        "preguntas": ["¿Inviertes en anuncios? ¿Cuánto al mes y dónde?", "¿Qué anuncios te han funcionado mejor?",
                      "¿Quién los gestiona?", "¿Con qué nombre de página o anunciante salen?"],
        "campos": [
            ("invierte", "¿Invierte en anuncios?", "select:si=Sí|probado=Lo ha probado|no=No", ""),
            ("presupuesto", "Presupuesto mensual y plataformas", "text", ""),
            ("anuncios_funcionan", "Lo que le ha funcionado", "textarea", ""),
            ("gestion_anuncios", "Quién los gestiona", "text", ""),
            ("anunciante", "Nombre de la página o del anunciante", "text", "Para buscarle en la biblioteca de anuncios."),
        ],
    },
    {
        "clave": "contenido",
        "titulo": "Contenido",
        "guion": "Pide los enlaces de lo que mejor le ha funcionado y de lo que no quiere hacer nunca. Cuánto tiempo real tiene.",
        "preguntas": ["¿En qué redes estás y con qué usuario?", "¿Cuántos seguidores tienes en cada una?",
                      "¿Qué publicas, cada cuánto y quién lo graba y lo edita?", "¿Qué contenido te ha funcionado mejor? (enlaces)",
                      "¿De qué temas podrías hablar horas?", "¿Qué no quieres hacer nunca?", "¿Cuánto tiempo a la semana tienes para contenido?"],
        "campos": [
            ("instagram", "Instagram", "text", "@usuario"),
            ("linkedin", "LinkedIn", "text", "Perfil o página de empresa."),
            ("youtube", "YouTube", "text", ""),
            ("tiktok", "TikTok", "text", ""),
            ("otros_canales", "Otros canales", "text", "Podcast, newsletter, X…"),
            ("seguidores", "Seguidores en total", "text", ""),
            ("frecuencia", "Qué publica y cada cuánto", "textarea", ""),
            ("produccion", "Quién graba y edita", "text", ""),
            ("mejor_contenido", "Lo que mejor le ha funcionado", "textarea", "Enlaces."),
            ("temas", "Temas que domina", "textarea", ""),
            ("no_quiere", "Lo que no quiere hacer", "textarea", ""),
            ("tiempo", "Tiempo a la semana para contenido", "text", ""),
        ],
    },
    {
        "clave": "competencia",
        "titulo": "Competencia y referentes",
        "guion": "Los competidores que nombre él valen más que los que encontremos. Pide también referentes de fuera de su mercado.",
        "preguntas": ["¿Con quién te comparan tus clientes?", "Si no te compran a ti, ¿a quién le compran?",
                      "¿A quién admiras de tu sector o de fuera (aunque no compita contigo)?", "¿Qué hacen mejor que tú? ¿Y peor?"],
        "campos": [
            ("competidores", "Competidores", "competidores", "Uno por fila. Basta con el nombre; el resto ayuda a encontrar su contenido."),
            ("referentes", "Referentes que admira", "textarea", ""),
            ("alternativas", "A quién compran si no a él", "textarea", ""),
            ("comparacion", "Qué hacen mejor y peor", "textarea", ""),
        ],
    },
    {
        "clave": "marca",
        "titulo": "Marca",
        "guion": "Cómo habla y cómo se ve. El logo se sube luego en Edición.",
        "preguntas": ["¿Cómo describirías tu forma de hablar?", "¿Tienes colores y tipografías de marca?",
                      "¿Qué estilo de edición de reels te gusta? (ejemplos)"],
        "campos": [
            ("tono", "Tono de la marca", "text", ""),
            ("colores", "Colores y tipografías", "text", ""),
            ("estilo_edicion", "Estilo de edición que le gusta", "textarea", "Ejemplos."),
        ],
    },
    {
        "clave": "cierre",
        "titulo": "Expectativas y cierre",
        "guion": "Acordad cómo se medirá el éxito y la próxima revisión. Explícale qué verá en la app y cuándo.",
        "preguntas": ["¿Qué esperas conseguir con nosotros?", "¿Cómo sabremos dentro de 90 días que ha funcionado?",
                      "¿Cuándo hacemos la próxima revisión?"],
        "campos": [
            ("expectativas", "Lo que espera", "textarea", ""),
            ("exito", "Cómo se medirá el éxito", "textarea", ""),
            ("proxima_revision", "Próxima revisión", "text", "Fecha."),
            ("notas", "Notas de la llamada", "textarea", "Solo para vosotros."),
        ],
    },
]

CAMPOS = [c for s in SECCIONES for c in s["campos"]]
CAMPOS_COMPETIDOR = ("nombre", "web", "instagram", "tiktok", "linkedin", "youtube")
CLAVES = [c[0] for c in CAMPOS]
ETIQUETAS = {c[0]: c[1] for c in CAMPOS}
PRIVADOS = {"notas"}  # no van a los análisis


def opciones(tipo: str) -> list[tuple[str, str]]:
    if not tipo.startswith("select:"):
        return []
    return [tuple(x.split("=", 1)) for x in tipo[7:].split("|")]


def competidores_del_formulario(form) -> list[dict] | None:
    """Las filas de competidores que envía el formulario (comp_nombre, comp_web…, repetidos una vez por fila), sin
    las vacías. None si el formulario no trae filas (entonces vale el campo de texto «competidores»)."""
    if not form.get("competidores_filas"):
        return None
    columnas = [form.getlist(f"comp_{k}") for k in CAMPOS_COMPETIDOR]
    filas = []
    for valores in zip_longest(*columnas, fillvalue=""):
        fila = {k: str(v or "").strip()[:300] for k, v in zip(CAMPOS_COMPETIDOR, valores)}
        if any(fila.values()):
            filas.append(fila)
    return filas


def _relleno(valor) -> bool:
    return bool(valor.strip()) if isinstance(valor, str) else bool(valor)


def de_solicitud(datos: dict) -> dict:
    """Lo que ya se sabe por el formulario de la landing, colocado en los campos del onboarding."""
    precio = datos.get("precio", "")
    return {
        "nombre": datos.get("negocio", ""), "web": datos.get("web", "") if "instagram" not in datos.get("web", "") else "",
        "instagram": datos.get("web", "") if "instagram" in datos.get("web", "") or datos.get("web", "").startswith("@") else "",
        "que_vende": datos.get("que_vende", ""), "precio_principal": precio, "facturacion": datos.get("facturacion", ""),
        "objetivo": datos.get("objetivo", ""),
        "tipo_negocio": "agencia" if datos.get("tipo") == "agencia" else "",
    }


def resumen(ficha: dict) -> dict:
    """Lo que se sabe del negocio, con nombres legibles, para dárselo a Claude en los análisis."""
    return {ETIQUETAS[k]: v for k, v in ficha.items() if k in ETIQUETAS and k not in PRIVADOS and v}


def completitud(ficha: dict) -> int:
    """Porcentaje de campos del onboarding rellenos."""
    rellenos = sum(1 for k in CLAVES if k not in PRIVADOS and _relleno(ficha.get(k)))
    return round(100 * rellenos / max(1, len([k for k in CLAVES if k not in PRIVADOS])))


def para_ia(ficha: dict) -> dict:
    """La ficha sin las notas privadas de la llamada ni los campos vacíos: lo que se le pasa a Claude."""
    return {k: v for k, v in ficha.items() if v and k not in PRIVADOS and k != "oculto"}
