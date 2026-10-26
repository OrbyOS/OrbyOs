"""Paso 3: el plan del reel bloque a bloque (qué lleva cada frase) y los cambios que se piden con una frase."""
import json
import re

from .. import llm
from ..llm import B, N, S, lista, obj
from . import modelo

def _esquema_plan(modo: str) -> dict:
    return obj(
        bloques=lista(obj(frases=lista(S), tipo={"type": "string", "enum": modelo.TIPOS_POR_MODO[modo]},
                          texto=S, items=lista(S), captura=S, web=S, motivo=S)),
        avisos=lista(S),
    )


def _esquema_ajustes() -> dict:
    return obj(
        estilo={"type": "string", "enum": list(modelo.ESTILOS)},
        color=S, sonidos=B, logo_esquina=B, cierre=B,
        subtitulos=obj(tamano_pct=N, posicion={"type": "string", "enum": ["arriba", "centro", "abajo"]}, mayusculas=B,
                       fuente={"type": "string", "enum": ["condensada", "redonda", "clasica"]}, resalta=B, contorno=B,
                       palabras=N),
        movimiento=obj(**{k: {"type": "string", "enum": list(v)} for k, v in modelo.MOVIMIENTOS.items()}),
    )


REGLAS = """\
Eres el editor de un reel vertical. Te pasamos las frases que se quedan, en orden, y decides qué lleva cada bloque.
Un bloque agrupa una o varias frases seguidas. Todas las frases van en algún bloque, en el mismo orden.
Tipos de bloque:
- «gancho»: el primero del reel. Un título corto arriba (como mucho 7 palabras) con la promesa de lo que se dice.
- «subtitulo»: lo normal, subtítulos sobre la persona (en «voz», «cinetico»: texto grande en movimiento).
- «choque»: una palabra gigante a la altura de la cara que entra de golpe y suena, y la persona queda por delante.
  En «texto», una sola palabra clave que se dice en esa frase (como mucho 12 letras), en mayúsculas.
- «lista»: cuando se enumeran cosas. En «items», de 2 a 5 elementos cortos, tal y como se dicen.
- «zoom»: un acercamiento para remarcar una frase importante.
- «pantalla»: cuando se nombra una web, una herramienta o algo que se puede enseñar: arriba la captura y abajo la
  persona. En «captura», el nombre de una de las capturas adjuntas si encaja; si no, en «web», el dominio nombrado.
- «imagen» (solo «voz»): una captura a pantalla completa.
Reglas: los efectos fuertes (choque, lista, pantalla, imagen) no pueden pasar del máximo del estilo; con más se
pierde la sorpresa. Un «choque» nunca en el primer bloque ni dos seguidos. No cambies el orden ni el texto de las
frases. En «motivo», una frase corta con por qué ese bloque lleva eso. En «avisos», lo que el usuario debería saber
(por ejemplo, que nombra una web y no hay captura).
"""


def _material(frases: list[dict]) -> list[dict]:
    return [{"id": f["id"], "texto": f["texto"], "segundos": round(f["fin"] - f["inicio"], 1)}
            for f in frases if not f.get("quitada")]


def proponer(frases: list[dict], *, modo: str, ajustes: dict, capturas: list[str], preferencias: list[str]) -> dict:
    estilo = modelo.ESTILOS[ajustes["estilo"]]
    contexto = {
        "modo": modo,
        "estilo": {"nombre": estilo["nombre"], "como_es": estilo["texto"], "efectos_fuertes_maximo": ajustes["efectos_max"]},
        "capturas_adjuntas": capturas,
        "preferencias_del_usuario": preferencias,
    }
    datos = llm.json_con_esquema(
        REGLAS,
        f"Contexto:\n{json.dumps(contexto, ensure_ascii=False)}\n\n"
        f"Frases:\n{json.dumps(_material(frases), ensure_ascii=False)[:40000]}",
        _esquema_plan(modo),
    )
    return normalizar(datos, frases, modo=modo, capturas=capturas, efectos_max=ajustes["efectos_max"])


def basico(frases: list[dict], *, modo: str) -> dict:
    """Plan sin IA: gancho con la primera frase y subtítulos en el resto."""
    datos = {"bloques": [], "avisos": ["Plan automático sin IA: revisa los bloques."]}
    return normalizar(datos, frases, modo=modo, capturas=[], efectos_max=0)


def _palabra_clave(texto: str) -> str:
    palabras = [re.sub(r"[^\wáéíóúñü]", "", p, flags=re.I) for p in texto.split()]
    palabras = [p for p in palabras if len(p) >= 4] or [p for p in palabras if p] or ["¡OJO!"]
    return max(palabras, key=len)[:12].upper()


def normalizar(datos: dict, frases: list[dict], *, modo: str, capturas: list[str], efectos_max: int,
               forzar_gancho: bool = True) -> dict:
    """Deja el plan bien formado pase lo que pase: todas las frases, en orden, una vez cada una, con tipos válidos."""
    quedan = [f for f in frases if not f.get("quitada")]
    orden = {f["id"]: i for i, f in enumerate(quedan)}
    por_id = {f["id"]: f for f in quedan}
    normal = "cinetico" if modo == "voz" else "subtitulo"
    permitidos = set(modelo.TIPOS_POR_MODO[modo])
    usadas, bloques = set(), []
    for b in datos.get("bloques") or []:
        ids = sorted({i for i in b.get("frases") or [] if i in orden and i not in usadas}, key=orden.get)
        # Un bloque solo puede juntar frases seguidas.
        seguidas = [ids[0]] if ids else []
        for i in ids[1:]:
            if orden[i] == orden[seguidas[-1]] + 1:
                seguidas.append(i)
        if not seguidas:
            continue
        usadas.update(seguidas)
        tipo = b.get("tipo") if b.get("tipo") in permitidos else normal
        bloques.append({"frases": seguidas, "tipo": tipo, "texto": (b.get("texto") or "").strip(),
                        "items": [str(x).strip() for x in b.get("items") or [] if str(x).strip()][:5],
                        "captura": b.get("captura") or "", "web": (b.get("web") or "").strip(),
                        "motivo": (b.get("motivo") or "").strip()})
    # Las frases que no están en ningún bloque entran como bloques normales en su sitio.
    for f in quedan:
        if f["id"] not in usadas:
            bloques.append({"frases": [f["id"]], "tipo": normal, "texto": "", "items": [], "captura": "", "web": "",
                            "motivo": ""})
    bloques.sort(key=lambda b: orden[b["frases"][0]])
    # El reel abre siempre con un gancho, salvo que el usuario lo haya cambiado a mano.
    if bloques and forzar_gancho and bloques[0]["tipo"] != "gancho":
        bloques[0]["tipo"] = "gancho"

    avisos = [a for a in datos.get("avisos") or [] if a]
    fuertes = 0
    for n, b in enumerate(bloques):
        texto = " ".join(por_id[i]["texto"] for i in b["frases"])
        if b["tipo"] == "gancho":
            b["texto"] = (b["texto"] or texto)[:70]
        elif b["tipo"] == "choque":
            if n == 0 or (n and bloques[n - 1]["tipo"] == "choque"):
                b["tipo"] = normal
            else:
                b["texto"] = re.sub(r"\s+", " ", b["texto"]).upper()[:14] or _palabra_clave(texto)
        elif b["tipo"] == "lista" and len(b["items"]) < 2:
            b["tipo"] = normal
        elif b["tipo"] in ("pantalla", "imagen"):
            if b["captura"] not in capturas:
                b["captura"] = ""
            if not b["captura"] and not b["web"]:
                b["tipo"] = normal
        if b["tipo"] in modelo.EFECTOS_FUERTES:
            fuertes += 1
            if efectos_max and fuertes > efectos_max:
                avisos.append(f"Hay {fuertes} efectos fuertes en este reel y el estilo aconseja como mucho "
                              f"{efectos_max}: con más se pierde la sorpresa.")
        b["id"] = f"b{n + 1}"
    return {"bloques": bloques, "avisos": list(dict.fromkeys(avisos))}


CAMBIO_REGLAS = REGLAS + """
Ahora el usuario te pide un cambio con sus palabras. Aplícalo sobre el plan y los ajustes que te pasamos y deja todo
lo demás igual. Si pide algo de los subtítulos, del color, del estilo o de los sonidos, cámbialo en «ajustes»
(«tamano_pct» es el tamaño en % del normal: «un 30 % más grandes» es 130). Si pide cómo se mueven los gráficos
(«que la palabra gigante entre sin rebote», «sin zooms», «el gancho más suave»), cámbialo en «ajustes.movimiento»
con las opciones que te pasamos. Si pide cambiar lo que dice un gancho o
una palabra gigante, cámbialo en ese bloque. En «resumen», lo que has cambiado en una frase, en segunda persona del
usuario («Subtítulos un 30 % más grandes»).
"""


def pedir_cambio(instruccion: str, *, plan: dict, ajustes: dict, frases: list[dict], modo: str,
                 capturas: list[str]) -> tuple[dict, dict, str]:
    esquema = obj(plan=_esquema_plan(modo), ajustes=_esquema_ajustes(), resumen=S)
    actuales = {k: ajustes[k] for k in ("estilo", "color", "sonidos", "logo_esquina", "cierre", "subtitulos",
                                         "movimiento")}
    opciones = {k: {o: t for o, t in v.items()} for k, v in modelo.MOVIMIENTOS.items()}
    datos = llm.json_con_esquema(
        CAMBIO_REGLAS,
        f"Lo que pide el usuario: «{instruccion}»\n\n"
        f"Modo: {modo}. Capturas adjuntas: {capturas}\n\n"
        f"Ajustes actuales:\n{json.dumps(actuales, ensure_ascii=False)}\n\n"
        f"Opciones de movimiento:\n{json.dumps(opciones, ensure_ascii=False)}\n\n"
        f"Plan actual:\n{json.dumps(plan, ensure_ascii=False)[:30000]}\n\n"
        f"Frases:\n{json.dumps(_material(frases), ensure_ascii=False)[:30000]}",
        esquema,
        effort="low",
    )
    nuevo_plan = normalizar(datos["plan"], frases, modo=modo, capturas=capturas, efectos_max=ajustes["efectos_max"])
    nuevos = {**ajustes, **{k: v for k, v in datos["ajustes"].items() if k not in ("subtitulos", "movimiento")}}
    nuevos["subtitulos"] = {**ajustes["subtitulos"], **datos["ajustes"]["subtitulos"]}
    nuevos["movimiento"] = modelo.movimiento({**ajustes["movimiento"], **(datos["ajustes"].get("movimiento") or {})})
    return nuevo_plan, nuevos, datos.get("resumen") or "Hecho."
