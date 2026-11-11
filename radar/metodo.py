"""El criterio del producto, escrito como instrucciones para Claude y como datos para la interfaz.

El nicho: marcas personales, infoproductores, consultores, mentores y servicios online, y las agencias que
trabajan con ellos. Si una lectura sale genérica, lo primero que hay que revisar es este archivo.
"""

BASE = """\
Trabajas para una app de growth para marcas personales, infoproductores, consultores, mentores y servicios
online (y para las agencias que trabajan con ellos). La app muestra lo que está funcionando en su mercado y lo
interpreta. Escribe en español de España, con frases cortas y concretas. Nada de frases hechas ni de relleno.

Reglas que no se rompen:
- Muestras y traduces; no ordenas ni haces de consultor. Di «este tipo de contenido atrae mucho alcance, pero no
  filtra a quien puede pagar», no «haz esto» ni «deberías». La decisión es del negocio o de su marketer.
- Cada lectura se apoya en una prueba de los datos que te pasamos: un vídeo o una publicación que destaca, un
  anuncio que lleva semanas activo, una página o una oferta de la competencia. Di cuál.
- Lee siempre según la situación del negocio: la audiencia que ya tiene y el ticket de su oferta.
- No inventes cifras, clientes ni resultados. Si un dato no está, dilo.
- Si los datos son pocos o flojos, dilo en lugar de rellenar.
"""

# ------------------------------------------------------------------ El negocio

TIPOS_NEGOCIO = {
    "infoproducto": "Infoproducto (curso, membresía o comunidad)",
    "consultoria": "Consultoría o mentoría",
    "servicios": "Servicios online (lo hacemos por ti)",
    "marca_personal": "Marca personal o creador",
    "agencia": "Agencia del nicho",
}

MODELOS_VENTA = {
    "lanzamientos": "Lanzamientos por fechas",
    "evergreen": "Evergreen (siempre abierto)",
    "llamada": "Solicitud y llamada de venta",
    "mixto": "Una mezcla",
}

TICKETS = {
    "bajo": "Ticket bajo (menos de 300 €): en el nicho se suele vender sin llamada, con volumen.",
    "medio": "Ticket medio (300-2.000 €): en el nicho se suele vender con webinar, VSL o lanzamiento.",
    "alto": "Ticket alto (más de 2.000 €): en el nicho se suele vender con solicitud y llamada.",
}
# Desde aquí, el ticket se lee en la fila de «ticket alto» de la matriz.
TICKET_ALTO = {"alto"}

# ------------------------------------------------------------------ Contenido por etapas

ETAPAS = {
    "TOFU": {
        "nombre": "Atraer",
        "para_que": "Alcance y seguidores nuevos. Mucha gente y poco filtrado.",
        "senales": "Temas amplios, opinión, tendencia o polémica del sector; sin llamada a comprar; muchas visualizaciones por seguidor.",
        "ejemplo": "«El error que comete casi todo el que lanza su primer curso»",
    },
    "MOFU": {
        "nombre": "Generar confianza",
        "para_que": "Educa y demuestra el método. Filtra a quien encaja y puede pagar.",
        "senales": "Método, casos de clientes, resultados, el proceso por dentro; muchos guardados, compartidos y preguntas.",
        "ejemplo": "«Así llevamos a un cliente de 0 a 10.000 € al mes: el proceso»",
    },
    "BOFU": {
        "nombre": "Convertir",
        "para_que": "Hace que quien ya confía dé el paso: casos, objeciones y cómo es trabajar con el negocio.",
        "senales": "Casos y testimonios de clientes, objeciones resueltas, el servicio o el programa por dentro, dudas sobre el precio o el proceso.",
        "ejemplo": "«Lo que cambió en el negocio de un cliente en 90 días»",
    },
}

# Para qué le sirve cada pieza a la marca del negocio. Solo «marca» es contenido que podría hacer; la promoción es
# parte del funnel de quien la publica (se enseña en Funnel y oferta) y lo de fuera no habla a su cliente.
USOS = {
    "marca": "Contenido que la marca de este negocio podría hacer para su cliente: enseña, opina, cuenta o demuestra.",
    "promocion": "Pieza de venta o de lanzamiento: anuncio, plazas, cuenta atrás, inscripciones, invitación al webinar u oferta con precio.",
    "fuera": "No habla al cliente de este negocio: otro público, entretenimiento, estilo de vida o herramientas para el público general.",
}

CLASIFICAR = """\
Clasifica cada vídeo o publicación en la etapa del funnel que trabaja:
""" + "\n".join(f"- {k} ({v['nombre']}): {v['para_que']} Señales: {v['senales']}" for k, v in ETAPAS.items()) + """
Usa el texto, el formato y las cifras: un ratio alto con pocas señales de compra suele ser TOFU. En LinkedIn no hay
visualizaciones: se mide por interacciones. En «motivo», una frase con la señal que te ha hecho decidir.
Además, en «uso», para qué le sirve la pieza a la marca de ESTE negocio:
""" + "\n".join(f"- {k}: {v}" for k, v in USOS.items()) + """
Las piezas de venta directa (plazas, precios, cuenta atrás, inscripciones, anuncios de un lanzamiento) son
«promocion», no BOFU de marca. «Comenta X y te lo envío» es «marca» si el vídeo enseña algo y solo regala un recurso;
es «promocion» si solo anuncia la oferta. Ponle a todas la etapa más cercana.
"""

# Matriz audiencia del negocio × ticket de su oferta. Describe lo habitual en el nicho para cada situación;
# no es una recomendación.
CUADRANTES = {
    ("pequena", "alto"): {
        "nombre": "Poca audiencia y ticket alto",
        "texto": "Lo habitual en el nicho: contenido que demuestra criterio (MOFU) y venta por solicitud y llamada.",
        "ejemplo": "Ej.: consultor que empieza con un programa de 3.000 €",
    },
    ("grande", "alto"): {
        "nombre": "Audiencia hecha y ticket alto",
        "texto": "El alcance ya está; lo que más pesa en el mercado es filtrar y cualificar (MOFU y BOFU).",
        "ejemplo": "Ej.: mentor con 100.000 seguidores y una mentoría de 5.000 €",
    },
    ("pequena", "bajo"): {
        "nombre": "Poca audiencia y ticket bajo",
        "texto": "Con ticket bajo hace falta volumen: el mercado se apoya en alcance (TOFU) y venta directa.",
        "ejemplo": "Ej.: creador que lanza su primer curso de 97 €",
    },
    ("grande", "bajo"): {
        "nombre": "Audiencia hecha y ticket bajo",
        "texto": "Con audiencia y ticket bajo, el mercado vive de lanzamientos y ofertas a su lista (BOFU).",
        "ejemplo": "Ej.: infoproductor con 300.000 seguidores y un curso de 197 €",
    },
}
# A partir de aquí se lee como «audiencia hecha» (el TOFU ya está trabajado).
UMBRAL_AUDIENCIA = 10_000
# Por debajo, el negocio empieza de cero.
UMBRAL_CERO = 100

# Cuando la ficha no marca el ticket ni el precio de una oferta, el negocio no cae en ninguna fila de la matriz.
# Se dice tal cual, sin recomendar.
TICKET_SIN_OFERTA = "Sin oferta con precio todavía: la ficha no marca el ticket ni el precio de la oferta principal."
FUERA_DE_LA_MATRIZ = {
    "sin_oferta": {
        "nombre": "Sin oferta todavía",
        "texto": "Sin una oferta con precio, el negocio no cae en ninguna fila de la matriz. En el nicho, el ticket es "
                 "lo que separa vender con volumen de vender con solicitud y llamada.",
    },
    "cero_sin_oferta": {
        "nombre": "Empiezas de cero, sin oferta todavía",
        "texto": "Sin audiencia y sin una oferta con precio, el negocio todavía no cae en ningún cuadrante: es el "
                 "punto de partida de casi todas las marcas personales del nicho.",
    },
}

CONTENIDO_CORTO = """\
Método para el contenido corto (reels hablando a cámara y publicaciones de LinkedIn):
- Gancho sin saludo: una situación que vive la audiencia o una postura que choca.
- Conflicto: por qué esa situación duele o por qué la gente se equivoca.
- Giro: el ángulo nuevo con el que se queda quien lo ve.
- Cierre con una puerta al siguiente contenido o a la oferta, según la etapa.
- Una sola idea por pieza.
- Cada guion lleva un apartado «Tu ejemplo», planteado como pregunta al dueño del negocio, para que lo cuente con su experiencia. No le inventes vivencias.
- Agrupa las ideas en series por tema.
"""

CONTENIDO_LARGO = """\
Método para el contenido largo (YouTube):
- Es donde el negocio demuestra lo que sabe y genera confianza.
- Título con una promesa clara y concreta. Inspírate en los vídeos que destacan en el nicho, sin copiarlos.
- Primeros 30 segundos: sin saludo; la promesa, una prueba si la hay y una agenda numerada de lo que se va a ver.
- Estructura por bloques, cada uno con su remate. Cierre con un paso concreto hacia la oferta.
"""

# ------------------------------------------------------------------ Lo que promete el contenido

# Cada vídeo del nicho se compara con la mediana de su canal o cuenta y se agrupa por lo que promete.
PROMESAS = {
    "herramientas": {
        "nombre": "Herramientas",
        "que": "Una herramienta, una app, un prompt o una automatización.",
        "ejemplo": "«5 herramientas de IA que hacen el trabajo de un equipo»",
    },
    "negocio_real": {
        "nombre": "Un negocio real",
        "que": "Un negocio de verdad por dentro: facturación, clientes, un caso real o cómo se ha montado.",
        "ejemplo": "«Así facturo 20.000 € al mes con mi agencia»",
    },
    "otras": {
        "nombre": "Otras promesas",
        "que": "Opinión, tendencias, motivación o consejos generales, sin herramienta ni negocio concreto.",
        "ejemplo": "«Lo que nadie te cuenta de emprender»",
    },
}

CLASIFICAR_PROMESA = """\
Clasifica cada vídeo por lo que promete en su título o su texto (no por el tema del canal):
""" + "\n".join(f"- {k}: {v['que']} Ej.: {v['ejemplo']}" for k, v in PROMESAS.items()) + """
Si mezcla las dos (por ejemplo, «cómo facturo 10.000 € con esta herramienta»), manda lo que se lleva quien lo ve:
si es el resultado de un negocio, negocio_real; si es la herramienta, herramientas. En «motivo», una frase con la
señal del título que te ha hecho decidir.
"""

# Sin la clave de Claude, se agrupa por palabras del título (sin tildes). Las «fuertes» de un negocio real pesan más
# que las de una herramienta, y las de una herramienta más que las «suaves» de un negocio.
PALABRAS_PROMESA = {
    "negocio_fuerte": (r"\d[\d.,]*\s?(k|mil|m|€|\$|euros?|dolares|usd|reais)(?![a-z])", r"[€$]\s?\d", r"\bfactur",
                       r"\bfature?i", r"\bfaturamento", r"caso real", r"casos reales", r"\bmi (negocio|agencia|empresa)",
                       r"\bmeu negocio", r"\bminha agencia", r"\bmy (business|agency)", r"\brevenue", r"\bingresos"),
    "herramientas": (r"\bherramientas?\b", r"\bferramentas?\b", r"\btools?\b", r"\bapps?\b", r"\baplicacion",
                     r"\bchat ?gpt", r"\bgpt", r"\bclaude\b", r"\bgemini\b", r"\bmidjourney", r"\bprompts?\b",
                     r"\bautomatiza", r"\bautomat(e|ion)", r"\bn8n\b", r"\bzapier\b", r"\bmake\.com\b", r"\bnotion\b",
                     r"\bcanva\b", r"\bcapcut\b", r"\bplantillas?\b", r"\btemplates?\b", r"\bsoftware\b",
                     r"\bagentes? de ia\b", r"\bai agents?\b", r"\bia\b", r"inteligencia artificial"),
    "negocio_suave": (r"\bclientes?\b", r"\bclients?\b", r"\bventas?\b", r"\bvender\b", r"\bvendi\b",
                      r"\bnegocios?\b", r"\bbusiness\b", r"\bagencias?\b", r"\bganar dinero\b",
                      r"\bmake money\b"),
}

# ------------------------------------------------------------------ Funnel y oferta

TIPOS_FUNNEL = {
    "lead_magnet": "Lead magnet",
    "webinar": "Masterclass o webinar",
    "vsl": "Vídeo de ventas (VSL)",
    "reto": "Reto",
    "lanzamiento": "Lanzamiento o lista de espera",
    "llamada": "Solicitud y llamada",
    "low_ticket": "Low ticket",
    "venta_directa": "Venta directa",
    "comunidad": "Comunidad",
    "mensaje_directo": "Mensaje directo (comenta, DM o WhatsApp)",
    "formulario_meta": "Formulario de Meta",
    "otro": "Otro",
}

# Qué exige cada funnel en la oferta, con un ejemplo del nicho.
EXIGE = {
    "lead_magnet": ("Una oferta de atracción gratis y un paso siguiente claro hacia la venta",
                    "Guía, plantilla o mini curso gratis a cambio del email"),
    "webinar": ("La oferta principal al final, con bonus y fecha límite", "Masterclass gratuita en directo o grabada"),
    "vsl": ("Una promesa fuerte, pruebas y la oferta completa en el mismo vídeo", "Vídeo de 20 minutos y botón de compra o de aplicar"),
    "reto": ("Varios días de valor gratis y una oferta abierta al terminar el reto", "Reto de 5 días en grupo"),
    "lanzamiento": ("Una apertura por fechas, con escasez real y una lista calentada antes", "Lista de espera y carrito abierto 7 días"),
    "llamada": ("Oferta de ticket alto, con cualificación previa y alguien que cierre", "Formulario de aplicación y sesión estratégica"),
    "low_ticket": ("Un producto barato que se compra sin pensar y lleva a la oferta principal", "Plantilla o taller de 27 € con upsell"),
    "venta_directa": ("Precio visible, garantía y bonus", "Página de venta del curso con checkout"),
    "comunidad": ("Valor continuo y una oferta superior para los miembros que quieren más", "Comunidad en Skool gratis o de pago"),
    "mensaje_directo": ("Respuesta rápida y una oferta que se cierra en la conversación", "«Comenta GUÍA» y un setter que sigue por DM"),
    "formulario_meta": ("Un gancho claro y una llamada rápida al contacto", "Formulario instantáneo de Meta"),
}

FUNNELS = """\
Método para leer los funnels de la competencia:
- Un anuncio que lleva muchas semanas activo, o del que la marca tiene varias versiones, probablemente le funciona.
- Tipos de funnel: """ + ", ".join(f"{k} ({v})" for k, v in TIPOS_FUNNEL.items() if k != "otro") + """.
- Cada funnel exige algo de la oferta:
""" + "\n".join(f"  - {TIPOS_FUNNEL[k]}: {v[0]}." for k, v in EXIGE.items()) + """
- La oferta de entrada es lo que se da o se vende primero (gratis o barato); la principal, lo que se vende después.
"""

NIVELES_ESCALERA = {
    "entrada": "Gratis",
    "low_ticket": "Low ticket",
    "principal": "Programa o curso",
    "alto_ticket": "Alto ticket",
    "hecho_por_ti": "Hecho por ti",
}

ESCALERA = """\
Método para la escalera de ofertas del mercado:
- Ordena lo que vende la competencia de lo más barato a lo más caro, con estos peldaños: entrada (gratis: lead
  magnet, masterclass, comunidad gratuita), low_ticket, principal (curso o programa), alto_ticket (mentoría,
  consultoría, mastermind) y hecho_por_ti (servicio). Solo los peldaños que hayas visto.
- Para cada peldaño: qué es, el precio habitual (con el rango que has visto), quién lo hace y la URL de la prueba.
- No propongas la oferta del negocio. Si la ficha dice lo que vende hoy, di en qué peldaño queda frente al mercado.
"""
