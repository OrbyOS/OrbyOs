"""Ganchos: el catálogo de fórmulas de gancho, la nota de un gancho y su revisión. Lo usan Escri (escribir), Plani
(elegir la fórmula de cada pieza), Monti (elegir el gancho de entre lo que dice el dueño) y Lupi (clasificar los
ganchos de otras cuentas para ver cuáles funcionan en el nicho).

Las fórmulas van por familias: chocar con una creencia, enseñar una prueba, dar algo útil, contar una historia,
hablarle a alguien concreto y reaccionar a la actualidad. Cada una dice a qué tipo de pieza le va mejor («clases») y
si necesita una cifra propia del negocio («cifra»): si el Kit no permite cifras propias, esas no se usan.

La nota solo lee el texto. Distingue bien un gancho trabajado de uno flojo (un saludo, una introducción, nada en
juego, demasiado largo para decirlo en un par de segundos), pero no adivina las visualizaciones: entre dos ganchos
decentes decide la retención real.
"""
import re

# ---------------------------------------------------------------- el catálogo

FAMILIAS = {
    "choque": "Chocar con una creencia", "prueba": "Enseñar una prueba", "utilidad": "Dar algo útil",
    "historia": "Contar una historia", "conversacion": "Hablarle a alguien concreto", "actualidad": "Reaccionar a la actualidad",
}

FORMULAS = [
    # -- choque
    {"id": 1, "familia": "choque", "nombre": "La creencia al revés",
     "plantilla": "Todo el mundo dice {lo de siempre}. {Lo que has visto tú}.",
     "ejemplo": "Todo el mundo dice que bajes el precio para vender más. A mí me pasó justo lo contrario.",
     "en_pantalla": "BAJAR PRECIO NO VENDE", "clases": ["opinion", "ensenar"], "cifra": False,
     "para": "Que se paren a comprobar si tienen razón ellos o tú.",
     "trampa": "Discutir una idea que nadie defiende: si nadie lo dice, no hay choque.",
     "match": r"\btodo el mundo (?:dice|te dice|cree|repite)\b|\bte han dicho (?:siempre )?que\b|\bsiempre se ha dicho\b"},
    {"id": 2, "familia": "choque", "nombre": "Lo que no se cuenta",
     "plantilla": "Hay una parte de {lo que quieren} de la que no se habla: {cuál}.",
     "ejemplo": "Nadie te cuenta que los primeros meses de una agencia se va más tiempo en vender que en hacer campañas.",
     "en_pantalla": "LO QUE NADIE CUENTA", "clases": ["opinion", "ensenar"], "cifra": False,
     "para": "Público que aún no te conoce: te pone del lado de quien habla claro.",
     "trampa": "Anunciar un secreto y contar lo que ya sabe todo el sector.",
     "match": r"\bnadie (?:te )?(?:cuenta|dice|explica|habla de)\b|\bno se habla de\b|\bde lo que nadie\b"},
    {"id": 3, "familia": "choque", "nombre": "Te sobra",
     "plantilla": "No necesitas {lo que todos piden}. Necesitas {lo que de verdad falta}.",
     "ejemplo": "No necesitas más seguidores para llenar la agenda. Necesitas diez conversaciones buenas al mes.",
     "en_pantalla": "NO TE HACEN FALTA SEGUIDORES", "clases": ["opinion", "ensenar", "oferta"], "cifra": False,
     "para": "Quitar un bloqueo: se guarda mucho porque alivia.",
     "trampa": "Quitar algo y no dar nada a cambio: la segunda frase es el vídeo.",
     "match": r"^\s*no (?:necesitas|hace falta|te hace falta|tienes que)\b"},
    {"id": 4, "familia": "choque", "nombre": "Para ya",
     "plantilla": "Si sigues {haciendo esto}, para. {Qué hacer en su lugar}.",
     "ejemplo": "Si sigues mandando la propuesta por correo después de la llamada, para. Mándala durante la llamada.",
     "en_pantalla": "NO MANDES LA PROPUESTA", "clases": ["ensenar", "opinion"], "cifra": False,
     "para": "Corregir un hábito que quien mira reconoce en sí mismo.",
     "trampa": "Prohibir algo que casi nadie hace.",
     "match": r"^\s*(?:deja de|dejad de|para de|no vuelvas a|no (?:mandes|publiques|uses|pongas|hagas|compres))\b|"
              r"\bsi sigues\b[^.!?]{0,60}[,.] para\b"},
    {"id": 5, "familia": "choque", "nombre": "El error de casi todos",
     "plantilla": "El error que cometen casi todos los {grupo} es {cuál}.",
     "ejemplo": "El error que cometen casi todos los coaches es explicar el programa antes de entender al cliente.",
     "en_pantalla": "EL ERROR DE CASI TODOS", "clases": ["ensenar", "opinion"], "cifra": False,
     "para": "Enseñar: quien mira quiere saber si es uno de ellos.",
     "trampa": "Hacer sentir torpe a quien mira: el error tiene que ser comprensible.",
     "match": r"\b(?:el|los|un|tu|tus) (?:mayor(?:es)? |gran |t[ií]pico )?error(?:es)?\b|\bhaciendo(?:lo)? mal\b|"
              r"\bno es culpa tuya\b"},
    # -- prueba
    {"id": 6, "familia": "prueba", "nombre": "Lo que me costó",
     "plantilla": "{Algo concreto} me costó {una decisión}.",
     "ejemplo": "No subir precios a tiempo me costó dos años de agencia sin margen.",
     "en_pantalla": "DOS AÑOS SIN MARGEN", "clases": ["prueba", "historia"], "cifra": True,
     "para": "Confianza: quien enseña sus errores parece de fiar.",
     "trampa": "Un coste vago. Tiene que poder medirse en dinero, tiempo o clientes.",
     "match": r"\b(?:me|nos) cost[oó]\b|\bperd[ií]\b[^.!?]{0,25}\d|\bes lo que (?:me|nos) cost[oó]\b"},
    {"id": 7, "familia": "prueba", "nombre": "Antes y ahora",
     "plantilla": "Antes {cómo era}. Ahora {cómo es}. Cambié {una sola cosa}.",
     "ejemplo": "Antes tardaba una tarde entera en preparar una propuesta. Ahora, quince minutos.",
     "en_pantalla": "UNA TARDE → 15 MINUTOS", "clases": ["prueba", "ensenar"], "cifra": True,
     "para": "Procesos: el salto se entiende de un vistazo.",
     "trampa": "Un salto increíble o tres cambios a la vez: una palanca y creíble.",
     "match": r"\bantes (?:tardaba|me llevaba|tard[aá]bamos|me costaba|era|ten[ií]a)\b|\bme llevaba[n]?\b[^.!?]{0,30}\d|"
              r"\bas[ií] (?:era|estaba)\b|\bantes y despu[eé]s\b"},
    {"id": 8, "familia": "prueba", "nombre": "Lo probé",
     "plantilla": "Probé {algo} durante {un tiempo}. Esto es lo que pasó.",
     "ejemplo": "Probé a no publicar en Instagram durante un mes. Esto es lo que pasó con mis llamadas.",
     "en_pantalla": "UN MES SIN PUBLICAR", "clases": ["prueba"], "cifra": True,
     "para": "Experimentos, mejor con la pantalla o el resultado a la vista.",
     "trampa": "Contar el resultado sin enseñarlo.",
     "match": r"\bprob[eé]\b[^.!?]{0,50}\bdurante\b|\bdurante \w+ (?:d[ií]as|semanas|meses)\b|\bn[uú]meros reales\b"},
    {"id": 9, "familia": "prueba", "nombre": "El caso de otro",
     "plantilla": "{Un negocio concreto} consiguió {un resultado} con {una palanca}.",
     "ejemplo": "Una academia de inglés de Valencia llenó su grupo de septiembre con un solo correo.",
     "en_pantalla": "UN CORREO, GRUPO LLENO", "clases": ["prueba", "historia", "oferta"], "cifra": False,
     "para": "Prueba cuando aún no tienes la tuya, siempre que el caso sea real y con permiso.",
     "trampa": "Un caso sin nombre ni fuente suena a inventado.",
     "match": r"^\s*(?:hay |una? )\w+[^.!?]{0,60}\b(?:consigui[oó]|llen[oó]|factur[oó]|pas[oó] de|cerr[oó]|dobl[oó])\b"},
    {"id": 10, "familia": "prueba", "nombre": "El dato con fuente",
     "plantilla": "Según {fuente}, {dato que sorprende}.",
     "ejemplo": "Según el INE, una de cada cinco empresas españolas ya usa inteligencia artificial.",
     "en_pantalla": "1 DE CADA 5 LA USA", "clases": ["opinion", "ensenar"], "cifra": False,
     "para": "Que lo repitan y lo manden: un dato con fuente se comparte.",
     "trampa": "Un dato sin fuente, o de los que circulan y son falsos.",
     "match": r"\d+(?:[.,]\d+)?\s?(?:%|por ciento)|\bseg[uú]n (?:el|la|los|las|un|una)\b|\buno? de cada \w+\b"},
    # -- utilidad
    {"id": 11, "familia": "utilidad", "nombre": "Si te pasa esto",
     "plantilla": "Si {síntoma concreto}, {dónde está el fallo}.",
     "ejemplo": "Si te escriben por privado y luego desaparecen, el fallo está en tu segundo mensaje.",
     "en_pantalla": "TE ESCRIBEN Y DESAPARECEN", "clases": ["ensenar", "oferta"], "cifra": False,
     "para": "Filtrar: se queda menos gente, pero la que tiene el problema.",
     "trampa": "Un síntoma tan amplio que le vale a cualquiera.",
     "match": r"^\s*si (?:tu|tus|te|tienes|est[aá]s|vendes|eres|llevas|cobras|trabajas)\b"},
    {"id": 12, "familia": "utilidad", "nombre": "Llévatelo",
     "plantilla": "Te dejo {la herramienta exacta} que uso para {una tarea}.",
     "ejemplo": "Te dejo las cuatro preguntas con las que abro cada llamada de venta.",
     "en_pantalla": "MIS 4 PREGUNTAS", "clases": ["ensenar", "oferta"], "cifra": False,
     "para": "Guardados y envíos: se queda con algo que puede usar mañana.",
     "trampa": "Que no se vea entero en pantalla: si no se puede copiar, no se lo lleva.",
     "match": r"\bte dejo\b|\bll[eé]vate\b|\bc[oó]piate\b|\br[oó]bame\b|\bqu[eé]date con (?:esta|este|estas|estos|mi|mis)\b"},
    {"id": 13, "familia": "utilidad", "nombre": "Mira cómo",
     "plantilla": "Mira lo que pasa cuando {acción}.",
     "ejemplo": "Mira lo que pasa cuando le pego a la IA las notas de una llamada de venta.",
     "en_pantalla": "MIRA ESTO", "clases": ["ensenar", "oferta"], "cifra": False,
     "para": "Demostraciones en pantalla con un resultado que se ve.",
     "trampa": "Un resultado que tarda en llegar: enseña primero el final.",
     "match": r"^\s*mira (?:lo que|esto|c[oó]mo|qu[eé])\b"},
    {"id": 14, "familia": "utilidad", "nombre": "La lista con favorita",
     "plantilla": "{N} {cosas} para {resultado}, y la {k} es la que casi nadie hace.",
     "ejemplo": "Tres cambios en tu página de ventas, y el tercero es el que casi nadie hace.",
     "en_pantalla": "3 CAMBIOS. EL 3.º, CLAVE", "clases": ["ensenar"], "cifra": False,
     "para": "Que se queden hasta el punto que has destacado.",
     "trampa": "Listas largas: más de cinco puntos ya no se recuerdan.",
     "match": r"\bes (?:la|el) que (?:casi )?nadie\b|^\s*(?:\d+|dos|tres|cuatro|cinco|seis|siete) "
              r"(?:cosas|errores|formas|pasos|claves|trucos|cambios|herramientas|preguntas|ideas)\b"},
    {"id": 15, "familia": "utilidad", "nombre": "El paso que falta",
     "plantilla": "Lo que separa {lo que tienen} de {lo que quieren} es {un paso}.",
     "ejemplo": "Lo que separa una buena llamada de una venta es lo que preguntas en el minuto cinco.",
     "en_pantalla": "EL MINUTO CINCO", "clases": ["ensenar", "oferta"], "cifra": False,
     "para": "Enseñar algo concreto que quien mira puede probar hoy.",
     "trampa": "Que el paso sea vago («ser constante»).",
     "match": r"\blo que separa\b|\bel paso que (?:falta|te falta)\b|\bte falta un paso\b"},
    {"id": 16, "familia": "utilidad", "nombre": "La vía rápida",
     "plantilla": "La manera más {rápida} de {resultado} es {algo concreto}.",
     "ejemplo": "La manera más rápida de ganar confianza en redes es enseñar cómo trabajas, no lo que consigues.",
     "en_pantalla": "LA VÍA RÁPIDA", "clases": ["ensenar", "opinion"], "cifra": False,
     "para": "Vídeos de una sola idea, sin historia.",
     "trampa": "Una respuesta blanda: si la segunda mitad es obvia, no hay vídeo.",
     "match": r"\b(?:la forma|la manera|el modo|el camino) m[aá]s\b|^\s*(?:el|la) (?:mejor|[uú]nic[oa]|m[aá]s r[aá]pid[oa])\b"},
    # -- historia
    {"id": 17, "familia": "historia", "nombre": "En mitad de la escena",
     "plantilla": "…y entonces {lo que cambió todo}.",
     "ejemplo": "…y entonces el cliente me pidió que paráramos la campaña. A los tres días de lanzarla.",
     "en_pantalla": "QUERÍA PARARLO TODO", "clases": ["historia"], "cifra": False,
     "para": "Historias: entrar tarde en la escena da ganas de saber cómo se llegó ahí.",
     "trampa": "No contar después cómo empezó.",
     "match": r"^\s*(?:\.\.\.|…)|^\s*y (?:ah[ií]|entonces) (?:fue cuando|es cuando|me)\b|^\s*y entonces\b"},
    {"id": 18, "familia": "historia", "nombre": "El día que",
     "plantilla": "El día que {un momento}, entendí {una lección}.",
     "ejemplo": "El día que un cliente me pidió la factura antes que el contrato, entendí cómo estaba vendiendo.",
     "en_pantalla": "EL DÍA QUE LO ENTENDÍ", "clases": ["historia", "opinion"], "cifra": False,
     "para": "Contar algo vivido y sacar una idea que sirve a quien mira.",
     "trampa": "Una historia sin lección, o una lección sin historia.",
     "match": r"^\s*el d[ií]a (?:que|en que)\b"},
    {"id": 19, "familia": "historia", "nombre": "Años en el oficio",
     "plantilla": "Llevo {tiempo} {haciendo esto} y hay algo que casi nunca cuento.",
     "ejemplo": "Llevo años montando lanzamientos y hay algo que casi nunca cuento en las llamadas.",
     "en_pantalla": "LO QUE NUNCA CUENTO", "clases": ["historia", "opinion"], "cifra": False,
     "para": "Autoridad sin enseñar credenciales ni resultados.",
     "trampa": "Prometer algo de dentro y contar algo de folleto.",
     "match": r"\bllevo \w+ (?:años|meses)\b|\b(?:casi )?nunca (?:cuento|digo|he contado)\b|\bpas[eé] \w+ años\b"},
    {"id": 20, "familia": "historia", "nombre": "Me salió mal",
     "plantilla": "Me salió mal {varias veces} antes de {lo que funcionó}.",
     "ejemplo": "Me salió mal el lanzamiento tres veces antes de entender qué fallaba.",
     "en_pantalla": "TRES INTENTOS FALLIDOS", "clases": ["historia", "prueba", "oferta"], "cifra": False,
     "para": "A quien empieza, que es casi todo el público: se ve en ti.",
     "trampa": "Que parezca suerte: tiene que haber un cambio concreto.",
     "match": r"\bme sali[oó] mal\b|\bfall[eé]\b[^.!?]{0,30}\bveces\b|\bmis primer[oa]s \w+\b[^.!?]{0,40}\bno\b"},
    # -- conversación
    {"id": 21, "familia": "conversacion", "nombre": "Va por vosotros",
     "plantilla": "{Un grupo concreto}: esto va por vosotros.",
     "ejemplo": "Consultores que cobráis por horas: esto va por vosotros.",
     "en_pantalla": "SI COBRAS POR HORAS", "clases": ["oferta", "opinion"], "cifra": False,
     "para": "Quedarse con la parte del público que compra y que se etiqueten entre ellos.",
     "trampa": "Un grupo tan grande que no es grupo («emprendedores»).",
     "match": r"^\s*[^,:.!?¿¡]{3,50}: (?:esto|este|esta|si|os|te)\b|\besto va por\b"},
    {"id": 22, "familia": "conversacion", "nombre": "La pregunta de siempre",
     "plantilla": "«{La pregunta tal cual}». Me la hacen cada semana.",
     "ejemplo": "«¿Cuánto tengo que cobrar por un lanzamiento?». Me lo preguntan cada semana.",
     "en_pantalla": "ME LO PREGUNTAN SIEMPRE", "clases": ["ensenar", "oferta"], "cifra": False,
     "para": "Búsqueda: la gente busca con esas mismas palabras.",
     "trampa": "Arreglar la pregunta: vale porque está dicha como la dicen ellos.",
     "match": r"\bme (?:la|lo) (?:preguntan|hacen|pregunt[aá]is)\b|\bme preguntan\b|^\s*[«\"“]\s*¿"},
    {"id": 23, "familia": "conversacion", "nombre": "La objeción",
     "plantilla": "«{La objeción tal cual}». Lo entiendo. {La respuesta}.",
     "ejemplo": "«No tengo tiempo para grabar». Lo entiendo. Por eso grabo una vez a la semana.",
     "en_pantalla": "«NO TENGO TIEMPO»", "clases": ["oferta"], "cifra": False,
     "para": "Vender a quien ya dijo que no una vez.",
     "trampa": "Inventarse la objeción: sácala de un mensaje o una llamada.",
     "match": r"^\s*[«\"“](?!\s*¿)"},
    # -- actualidad
    {"id": 24, "familia": "actualidad", "nombre": "Acaba de pasar",
     "plantilla": "{Algo del sector} acaba de cambiar. Esto es lo que te toca hacer.",
     "ejemplo": "Instagram acaba de cambiar cómo cuenta las visualizaciones. Esto es lo que te toca revisar.",
     "en_pantalla": "ACABA DE CAMBIAR", "clases": ["ensenar", "opinion"], "cifra": False,
     "para": "Noticias del nicho: llegar el primero con lo que cambia para quien mira.",
     "trampa": "Contar la noticia sin decir qué hacer con ella.",
     "match": r"\bacaba(?:n)? de (?:lanzar|sacar|presentar|anunciar|cambiar|salir)\b|^\s*(?:ha salido|ya est[aá] aqu[ií])\b|"
              r"\b(?:es|son) (?:el|la|los|las) (?:\w+ )?nuev[oa]s?\b|\bantes (?:del?|de que)\b[^.!?]{0,30}\b(?:\d|lunes|"
              r"martes|mi[eé]rcoles|jueves|viernes|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|"
              r"noviembre|diciembre)"},
    {"id": 25, "familia": "actualidad", "nombre": "Uno contra otro",
     "plantilla": "{A} o {B}. Los he probado y uno gana de lejos.",
     "ejemplo": "Carruseles o reels para vender un programa. Los he probado y uno gana de lejos.",
     "en_pantalla": "CARRUSEL VS REEL", "clases": ["opinion", "prueba"], "cifra": False,
     "para": "Comentarios: cada uno llega con su bando.",
     "trampa": "No mojarse: una comparación sin ganador no tiene final.",
     "match": r"^\s*[\w\s]{2,30}? (?:contra|vs\.?|versus) [\w\s]{2,30}?[.:]|\bvs\.?\b|\bversus\b|"
              r"\blos he probado\b|\bprob[eé] (?:los|las) dos\b"},
]
POR_ID = {f["id"]: f for f in FORMULAS}
CON_CIFRA = {f["id"] for f in FORMULAS if f["cifra"]}
# De la más concreta a la más general: así un gancho se queda con la fórmula que mejor lo describe.
ORDEN_CLASIFICAR = [6, 10, 2, 7, 8, 19, 20, 18, 9, 24, 3, 4, 5, 1, 12, 15, 16, 13, 25, 22, 23, 11, 17, 14, 21]
_MATCH = {f["id"]: re.compile(f["match"], re.IGNORECASE) for f in FORMULAS}

# Ganchos en inglés y variantes que los patrones de arriba no cogen, con el id de su fórmula. Sirven para clasificar
# ganchos de cuentas de otros países.
PATRONES_EXTRA = {
    6: r"\$\s?\d[\d,]*\s+(?:is|was) what\b|\bcost (?:me|us|him|her|them)\b|\blost\b[^.!?]{0,20}\$\s?\d",
    10: r"\b\d[\d,.]*\s?%\s+of\b",
    7: r"\bused to take\b|\bnow (?:it )?(?:only )?takes?\b|\btakes? (?:me )?\d+\s*(?:sec|second|min|minute|hour|hr)|"
       r"\breplaced?\b[^.!?]*\$\s?\d|\binstead of (?:paying|hiring)\b|\b(?:this|that) was\b[^.!?]*[.!?]\s*(?:this|that) is\b|"
       r"\bbefore\b[^.!?]*\bafter\b",
    2: r"\b(?:nobody|no one)\s+(?:ever\s+)?(?:tells|told|talks|says|said|mentions|teaches)\b",
    20: r"\bmy first\s+\d+\b|\bfirst\s+\d+\s+(?:reels?|videos?|posts?|clients?|months?)\b",
    3: r"\byou (?:do not|don'?t|dont) need\b|\bstop (?:trying to|worrying about)\b",
    5: r"\b(?:big(?:gest)?|common|the) mistake\b|\byou'?(?:re| are) doing\b[^.!?]*\bwrong\b",
    12: r"^\s*steal\b|\bsteal (?:this|these|my)\b",
    16: r"^\s*(?:the\s+)?(?:fastest|quickest|best|worst|biggest|easiest|only|most important)\s+\w+",
    24: r"^\s*(?:so,?\s+)?(?:this|these|here) (?:is|are)\s+(?:the\s+)?(?:new|my new)\b|^\s*\w+ just (?:launched|dropped|released)\b",
    13: r"^\s*watch (?:what|this|me)\b|^\s*(?:let me|lemme) show you\b",
    25: r"\bdifferences? between\b",
    19: r"\bi (?:spent|worked|ran|have been)\b[^.!?]*\b\d+\s*\+?\s*years?\b|\bwe never (?:told|said|showed)\b",
    8: r"\bi\s+\w+(?:ed)?\s+[^.!?]{0,30}\bfor\s+\d+\s+(?:days?|weeks?|months?|years?)\b|\bhere (?:are|is) (?:the|my)\b[^.!?]*\bnumbers\b",
    22: r"^\s*¿\s*(?:cómo|qué|por qué|cuándo|dónde|quién|cuál|cuánto|puedo|debo|se puede|hay|merece)\b[^?]{3,110}\?"
        r"|^\s*(?:how|what|why|when|where|who|which|can|should|do|does|is|are)\b[^?]{3,110}\?",
    11: r"^\s*if (?:you|your|i|we)\b",
    4: r"^\s*(?:stop|quit|never|don'?t)\b",
    17: r"^\s*(?:and (?:that'?s|that is|then) when|so (?:he|she|they) (?:said|asked))\b",
    14: r"^\s*(?:here are\s+)?\d+\s+\w+|\bnumber \d+\b",
    21: r"^\s*(?:attention|listen up)\b|^\s*for (?:anyone|everyone|those)\b",
}
_EXTRA = [(i, re.compile(PATRONES_EXTRA[i], re.IGNORECASE)) for i in ORDEN_CLASIFICAR if i in PATRONES_EXTRA]


def clasificar(gancho: str) -> int | None:
    """La fórmula de un gancho (su id) o None si no encaja en ninguna, que puede ser una fórmula nueva."""
    texto = " ".join((gancho or "").split())
    principal = next((i for i in ORDEN_CLASIFICAR if _MATCH[i].search(texto)), None)
    if principal or len(texto.split()) < 2:
        return principal
    return next((i for i, patron in _EXTRA if patron.search(texto)), None)


def nombre(formula_id: int | None) -> str:
    return POR_ID[formula_id]["nombre"] if formula_id in POR_ID else "Sin fórmula"


def para_clase(clase: str) -> list[int]:
    """Las fórmulas que le van a un tipo de pieza (prueba, ensenar, opinion, historia u oferta)."""
    return [f["id"] for f in FORMULAS if clase in f["clases"]]


def formulas_en_texto(ids: list[int] | None = None) -> str:
    """Las fórmulas para ponerlas en una petición a Claude."""
    return "\n".join(f"{f['id']}. {f['nombre']} ({FAMILIAS[f['familia']].lower()}): {f['plantilla']} "
                     f"(p. ej. «{f['ejemplo']}»). Cuidado: {f['trampa']}" for f in FORMULAS if not ids or f["id"] in ids)


# ---------------------------------------------------------------- la nota de un gancho

PPM_INICIAL = 160            # palabras por minuto si no llega el ritmo del dueño
PALABRAS_IDEAL = (4, 11)     # lo que cabe en los primeros segundos

_PALABRA = re.compile(r"[\wáéíóúüñÁÉÍÓÚÜÑ$€%'’-]+")
_NUMERO = re.compile(r"\d[\d.,]*\s?(?:%|€|\$|k\b|x\b)?")
_NOMBRE_PROPIO = re.compile(r"(?<![.!?¿¡]\s)(?<!^)\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,}\b")

CANTIDADES = {
    "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce", "quince", "veinte",
    "treinta", "cuarenta", "cincuenta", "cien", "mil", "millón", "millones", "docena", "mitad", "doble", "triple",
    "minuto", "minutos", "hora", "horas", "día", "días", "semana", "semanas", "mes", "meses", "año", "años",
    "euros", "euro", "dólares", "precio", "factura", "sueldo", "comisión", "gratis",
}
TENSION = {
    "no", "nunca", "nadie", "nada", "sin", "error", "errores", "mal", "falla", "fallo", "fallé", "pierdes", "perdí",
    "perder", "cuesta", "costó", "caro", "deja", "para", "basta", "peor", "problema", "riesgo", "cuidado", "ojo",
    "mentira", "verdad", "secreto", "pero", "aunque", "salvo", "solo", "todavía", "ya", "contra", "antes", "ahora",
    "nunca", "jamás", "quemado", "miedo", "vergüenza", "odio", "cambió", "cambia", "dejé", "tiras", "regalas", "sobra",
}
ARRANQUES_PROHIBIDOS = [
    (re.compile(r"^\s*(?:hola|buenas|muy buenas|qu[eé] tal|bienvenid)", re.IGNORECASE), "empieza saludando"),
    (re.compile(r"\b(?:en (?:este|el) (?:v[ií]deo|reel)(?: de hoy)?|hoy (?:te|os) (?:voy a|traigo)|te voy a (?:enseñar|"
                r"contar|explicar)|vengo a contaros)\b", re.IGNORECASE), "anuncia el vídeo en vez de empezarlo"),
    (re.compile(r"^\s*(?:deja de hacer scroll|no hagas scroll|para de deslizar|no deslices)", re.IGNORECASE),
     "pide que no pasen de largo"),
    (re.compile(r"(?:^|\s)#\w+"), "lleva un hashtag"),
    (re.compile(r"[\U0001F300-\U0001FAFF☀-➿]"), "lleva un emoji"),
]
ARRANQUES_FLOJOS = ("bueno", "vale", "pues", "o sea", "es que", "eh", "oye", "mira, ", "hoy", "básicamente",
                    "sinceramente", "quiero", "vamos a", "te has preguntado", "alguna vez", "en este", "lo que",
                    "hay muchas", "como", "cuando")
A_QUIEN_MIRA = {"tú", "tu", "tus", "te", "ti", "contigo", "vosotros", "vuestro", "vuestra", "vuestros", "os", "usted",
                "tienes", "eres", "estás", "haces", "quieres", "puedes", "necesitas", "vendes", "cobras", "llevas"}
ORDENES = {"deja", "para", "prueba", "mira", "guarda", "haz", "escribe", "empieza", "olvida", "cambia", "apunta",
           "fíjate", "copia", "llévate", "pregunta", "sube", "baja", "quita", "pon"}
PESOS = {"RAPIDEZ": 0.3, "TENSIÓN": 0.3, "CONCRECIÓN": 0.2, "DESTINATARIO": 0.2}


def _tope(n: float) -> float:
    return max(0.0, min(100.0, n))


def palabras(texto: str) -> list[str]:
    # «18.000» se dice como una palabra, así que cuenta como una.
    return _PALABRA.findall(re.sub(r"(?<=\d)[.,](?=\d)", "", texto or ""))


def _bajas(texto: str) -> list[str]:
    return [w.lower().strip("'’") for w in palabras(texto)]


def _rapidez(texto: str, pps: float) -> tuple[float, str]:
    """Se dice en un par de segundos y lo importante llega pronto."""
    w, bajas = palabras(texto), _bajas(texto)
    n = len(w)
    lo, hi = PALABRAS_IDEAL
    largo = 100.0 if lo <= n <= hi else _tope(100 - (lo - n) * 25) if n < lo else _tope(100 - (n - hi) * 9)
    donde = next((i for i, b in enumerate(bajas) if b in TENSION or b in CANTIDADES or b in A_QUIEN_MIRA
                  or _NUMERO.match(w[i])), None)
    pronto = 40.0 if donde is None else 100.0 if donde <= 2 else 75.0 if donde <= 5 else 45.0
    inicio = " ".join(bajas[:3])
    flojo = next((a for a in ARRANQUES_FLOJOS if (texto or "").lower().lstrip().startswith(a)), None)
    nota = (largo + pronto) / 2 - (25 if flojo else 0)
    detalle = f"{n} palabras, unos {n / pps:.1f} s; " + (
        "nada llama la atención" if donde is None else f"lo que engancha llega en la palabra {donde + 1}")
    return _tope(nota), detalle + (f"; arranque flojo «{flojo}»" if flojo else "") if inicio else "vacío"


def _tension(texto: str) -> tuple[float, str]:
    """Algo en juego: un error, un coste, un «no», un contraste."""
    marcas = sorted({b for b in _bajas(texto) if b in TENSION})
    nota = {0: 25.0, 1: 75.0}.get(len(marcas), 100.0)
    return nota, (f"en juego: {', '.join(marcas[:4])}" if marcas else "no hay nada en juego")


def _concrecion(texto: str) -> tuple[float, str]:
    """Algo que se puede imaginar o comprobar: una cantidad, un tiempo, un nombre."""
    hay = [x.strip() for x in _NUMERO.findall(texto) if x.strip()] + sorted(set(_NOMBRE_PROPIO.findall(texto))) + [
        b for b in _bajas(texto) if b in CANTIDADES]
    # Sin nada concreto no es un suspenso: hay negocios que no usan cifras propias. Pero concreto, mejor.
    return (45.0 if not hay else _tope(55 + len(hay) * 20)), (
        f"concreto: {', '.join(hay[:4])}" if hay else "nada concreto (ni cantidad, ni tiempo, ni nombre)")


def _destinatario(texto: str) -> tuple[float, str]:
    bajas = _bajas(texto)
    if set(bajas) & A_QUIEN_MIRA:
        return 100.0, "le habla a quien mira"
    if bajas and bajas[0] in ORDENES:
        return 85.0, f"empieza con una orden («{bajas[0]}»)"
    if set(bajas) & {"yo", "me", "mi", "mis", "nosotros", "nos", "nuestro", "nuestra"}:
        return 65.0, "habla de ti, sin nombrar a quien mira"
    return 30.0, "no le habla a nadie"


def puntuar(gancho: str, *, ppm: float | None = None) -> dict:
    """La nota de un gancho de 0 a 100: la media ponderada de cuatro aspectos, con un tope de 30 puntos por encima del
    peor (un aspecto muy flojo basta para que pasen de largo) y 20 menos por cada arranque prohibido.
    FUERTE desde 70 con ningún aspecto por debajo de 50; FLOJO por debajo de 50."""
    pps = (ppm or PPM_INICIAL) / 60
    partes = {"RAPIDEZ": _rapidez(gancho, pps), "TENSIÓN": _tension(gancho), "CONCRECIÓN": _concrecion(gancho),
              "DESTINATARIO": _destinatario(gancho)}
    prohibidos = [motivo for patron, motivo in ARRANQUES_PROHIBIDOS if patron.search(gancho or "")]
    media = sum(PESOS[k] * n for k, (n, _) in partes.items())
    peor = min(partes, key=lambda k: partes[k][0])
    total = _tope(min(media, partes[peor][0] + 30) - 20 * len(prohibidos))
    veredicto = ("FUERTE" if total >= 70 and partes[peor][0] >= 50 and not prohibidos else
                 "BIEN" if total >= 50 else "FLOJO")
    return {"gancho": (gancho or "").strip(), "nota": round(total), "veredicto": veredicto, "formula": clasificar(gancho),
            "peor": peor, "eliminatorios": [f"El gancho {m}." for m in prohibidos],
            "comprobaciones": {k: {"nota": round(n), "detalle": d} for k, (n, d) in partes.items()},
            "segundos": round(len(palabras(gancho)) / pps, 1)}


def ordenar(ganchos: list[str], *, ppm: float | None = None) -> list[dict]:
    """Varios ganchos, del mejor al peor."""
    return sorted((puntuar(g, ppm=ppm) for g in ganchos if (g or "").strip()), key=lambda r: -r["nota"])


# ---------------------------------------------------------------- la revisión

_DESTRIPA = re.compile(r"\b(?:porque|por eso|la clave (?:es|est[aá])|el secreto (?:es|est[aá])|la respuesta es|"
                       r"lo que (?:tienes|hay) que hacer es)\b", re.IGNORECASE)
_LISTA_ENTERA = re.compile(r"\baqu[ií] (?:tienes|van|os dejo) \w+ (?:consejos|trucos|claves|pasos|ideas)\b", re.IGNORECASE)


def auditar(gancho: str, *, ppm: float | None = None) -> dict:
    """Lo que le falla a un gancho, citando las palabras: llega tarde, es enrevesado, no va con nadie, no deja nada
    pendiente o destripa la respuesta. `pasa` si no le falla nada."""
    r = puntuar(gancho, ppm=ppm)
    w, c = palabras(gancho), r["comprobaciones"]
    fallos = {}
    if c["RAPIDEZ"]["nota"] < 60 or len(w) > PALABRAS_IDEAL[1] + 2:
        fallos["tarde"] = f"«{' '.join(w[:4])}…»: tarda en llegar a lo importante ({c['RAPIDEZ']['detalle']})."
    for e in r["eliminatorios"]:
        fallos.setdefault("tarde", e)
    incisos = len(re.findall(r"\b(?:que|cual|cuyo|donde|mientras|aunque)\b", gancho or "", re.IGNORECASE))
    if incisos > 2 or (gancho or "").count(",") > 2:
        fallos["enrevesado"] = "Hay que oírlo dos veces: demasiados incisos. Una idea y palabras sencillas."
    if c["DESTINATARIO"]["nota"] <= 30:
        fallos["no_va_con_nadie"] = "Quien mira no se ve dentro: dile a quién va o qué se juega."
    if c["TENSIÓN"]["nota"] <= 25 and c["CONCRECIÓN"]["nota"] <= 45:
        fallos["nada_pendiente"] = "No deja nada pendiente: falta algo en juego o algo concreto."
    if m := (_DESTRIPA.search(gancho or "") or _LISTA_ENTERA.search(gancho or "")):
        fallos["destripa"] = f"«{m.group(0)}» suelta la respuesta en el gancho: guárdala para después."
    return {**r, "fallos": fallos, "pasa": not fallos}
