"""Montaje por palabras → montaje en segundos (esquema_montaje.json), y saneado automático.

Quien decide (Claude en el SaaS) señala palabras, no segundos: «del plano 12 al 19, cerrado, titular "Prueba"».
Calcular tiempos es donde una IA se equivoca; aquí se hace con los tiempos reales de la transcripción:
- cada plano se parte en los silencios largos y en las frases quitadas: el silencio se corta y el corte se tapa con
  un punch-in (regla del manual: un silencio cortado dentro de un plano cambia el encuadre);
- los bordes de cada tramo se ajustan para no comerse la palabra de al lado (también las quitadas);
- `sanear` arregla lo que el validador marque, para que el SaaS nunca se quede sin reel.
"""
import copy

from . import validar as val

SILENCIO = 0.3     # un hueco más largo entre palabras se corta
ANTES = 0.06       # aire antes de la primera palabra de un tramo
DESPUES = 0.14     # aire después de la última
SALTO_ZOOM = 0.15  # cambio de encuadre que tapa un corte de silencio
ESPERA_MAX = 0.8   # segundos que una pantalla partida o completa puede esperar a su primer elemento


def _tramos(indices: list[int], palabras: list[dict]) -> list[list[int]]:
    """Parte una lista de índices de palabras en tramos sin silencios largos ni saltos en el bruto."""
    tramos = []
    for i in indices:
        if tramos:
            j = tramos[-1][-1]
            seguidas = palabras[i].get("orden", i) == palabras[j].get("orden", j) + 1
            if seguidas and palabras[i]["start"] - palabras[j]["end"] <= SILENCIO:
                tramos[-1].append(i)
                continue
        tramos.append([i])
    return tramos


def _limites(tramo: list[int], palabras: list[dict], todas: list[dict]) -> tuple[float, float]:
    """Inicio y fin del tramo en el bruto, sin pisar ninguna palabra de fuera (tampoco las quitadas)."""
    primera, ultima = palabras[tramo[0]], palabras[tramo[-1]]
    a, b = primera["start"], ultima["end"]
    io, uo = primera.get("orden"), ultima.get("orden")
    antes = todas[io - 1]["end"] if io else 0.0
    despues = todas[uo + 1]["start"] if uo is not None and uo + 1 < len(todas) else b + 1.0
    # Nunca más allá de la mitad del hueco con la palabra vecina.
    ini = max(0.0, a - ANTES, (antes + a) / 2)
    fin = min(b + DESPUES, (b + despues) / 2)
    if fin - ini < val.PLANO_MIN:  # una palabra suelta: se alarga hacia el silencio de después si lo hay
        fin = max(fin, min(ini + val.PLANO_MIN, despues - 0.02))
    return round(ini, 3), round(fin, 3)


def convertir(por_palabras: dict, palabras: list[dict], todas: list[dict], *, bruto: str, kit: str) -> dict:
    """`palabras`: las que se quedan, en orden (start, end, word y, si se conoce, `orden` = su índice en el bruto).
    `todas`: todas las palabras del bruto, para no cortar encima de una quitada."""
    n = len(palabras)
    validos = [p for p in por_palabras.get("planos") or [] if isinstance(p.get("desde"), int)]
    # El gancho puede venir de cualquier parte del bruto (sección 0 del manual): va primero, entero y sin repetirse.
    gancho = next((p for p in validos if p.get("gancho")), None)
    gancho_idx = set()
    if gancho:
        gancho_idx = set(range(max(0, gancho["desde"]), min(gancho.get("hasta", gancho["desde"]), n - 1) + 1))
        validos = [p for p in validos if p is not gancho]
    pedidos = []
    for p in sorted(validos, key=lambda p: p["desde"]):
        # Una pantalla partida o completa empieza cuando entra su primer elemento (manual, sección 1): lo que se dice
        # antes va con la cara entera, no con medio panel vacío.
        g = p.get("grafico") or {}
        primero = min([e.get("en") for e in g.get("elementos", []) if isinstance(e.get("en"), int)] or [None],
                      key=lambda x: x if x is not None else 10**9)
        if (g.get("tipo") == "efecto" and g.get("lugar") in ("partida", "completa") and isinstance(primero, int)
                and p["desde"] < primero <= p.get("hasta", p["desde"]) and 0 <= p["desde"] < n and primero < n
                and palabras[primero]["start"] - palabras[p["desde"]]["start"] > ESPERA_MAX):
            antes = {k: v for k, v in p.items() if k not in ("grafico", "hasta")}
            antes["hasta"] = primero - 1
            pedidos += [antes, {**p, "desde": primero}]
        else:
            pedidos.append(p)
    frase_de = [w.get("frase") for w in palabras]

    def es_corte(hueco: list[int]) -> bool:
        """Un hueco entre planos es un corte decidido si son frases enteras (lo que no suma); si deja frases a
        medias, es un descuido y esas palabras vuelven a su plano."""
        if not hueco or None in (frase_de[i] for i in hueco):
            return False
        frases = {frase_de[i] for i in hueco}
        return all(i in hueco for i in range(n) if frase_de[i] in frases)

    # Cobertura sin solapes: ninguna palabra se pierde salvo los cortes de frases enteras y el tramo del gancho.
    planos_idx, siguiente = [], 0
    for p in pedidos:
        desde, hasta = max(p["desde"], siguiente), min(p.get("hasta", p["desde"]), n - 1)
        if hasta < desde:
            continue
        hueco = [i for i in range(siguiente, desde) if i not in gancho_idx]
        if hueco and not es_corte(hueco):
            if planos_idx:
                planos_idx[-1]["indices"] += hueco
            else:
                desde = min(hueco)
        indices = [i for i in range(desde, hasta + 1) if i not in gancho_idx]
        if indices:
            planos_idx.append({**p, "indices": indices})
        siguiente = hasta + 1
    resto = [i for i in range(siguiente, n) if i not in gancho_idx]
    if resto and not es_corte(resto):
        if planos_idx:
            planos_idx[-1]["indices"] += resto
        else:
            planos_idx.append({"modo": "real", "zoom": 1.0, "indices": resto})
    if gancho and gancho_idx:
        planos_idx.insert(0, {**gancho, "indices": sorted(gancho_idx), "entero": True})
    if not planos_idx:
        planos_idx = [{"modo": "real", "zoom": 1.0, "indices": []}]

    def t(i):
        return palabras[max(0, min(n - 1, i))]["start"]

    salida = []
    for k, p in enumerate(planos_idx, 1):
        # El gancho va entero, en un solo plano; el resto se parte en los silencios.
        tramos = [p["indices"]] if p.get("entero") else (_tramos(p["indices"], palabras) or [[]])
        g = copy.deepcopy(p.get("grafico")) or None
        ancla = None
        if g:
            if g.get("tipo") == "ficha":
                ancla = (g.get("filas") or [{}])[0].get("en")
            elif g.get("tipo") == "efecto":
                ancla = g.get("en", (g.get("elementos") or [{}])[0].get("en"))
            elif g.get("tipo") != "titular" or p.get("modo") == "real":
                ancla = g.get("en")
        zoom = float(p.get("zoom") or 1.0)
        for j, tramo in enumerate(tramos):
            if not tramo:
                continue
            ini, fin = _limites(tramo, palabras, todas)
            plano = {"id": f"p{k}" + (f"-{j + 1}" if j else ""), "src": [ini, fin], "modo": p.get("modo", "real"),
                     "zoom": round(zoom if j % 2 == 0 else (zoom + SALTO_ZOOM if zoom < 1.25 else zoom - SALTO_ZOOM), 2)}
            if j == 0 and p.get("entrada") in ("latigo", "tiras"):
                plano["entrada"] = p["entrada"]
            if j == 0 and p.get("entero"):
                plano["gancho"] = True
            if p.get("fondo") in ("luz", "rejilla"):
                plano["fondo"] = p["fondo"]
            elif p.get("fondo_foto"):
                plano["fondo"] = {"foto": str(p["fondo_foto"])}
            if isinstance(p.get("sacudida"), int) and p["sacudida"] in tramo:
                plano["sacudida"] = round(t(p["sacudida"]), 3)
            if isinstance(p.get("golpe"), int) and p["golpe"] in tramo:
                plano["golpe"] = round(t(p["golpe"]), 3)
            if g and g.get("tipo") == "efecto" and j == 0:
                # Un efecto sobrevive a los cortes de su plano: va en el primer tramo y abarca todos los demás.
                plano["grafico"] = _grafico_en_segundos(g, p["indices"], palabras, ini, p.get("modo", "real"), t)
                abarca = sum(1 for x in tramos if x)  # ojo: no reutilizar «n», que usa t()
                if abarca > 1:
                    plano["abarca"] = abarca
                g = None
            lleva = g and ((ancla is None and j == 0) or (isinstance(ancla, int) and ancla in tramo)
                           or (isinstance(ancla, int) and j == 0 and ancla not in p["indices"]))
            if lleva:
                plano["grafico"] = _grafico_en_segundos(g, tramo, palabras, ini, p.get("modo", "real"), t)
                g = None
            salida.append(plano)
    # Ningún plano entra en el tramo del gancho (ni por el aire de los bordes): lo que abre no se oye dos veces.
    if salida and salida[0].get("gancho"):
        ga, gb = salida[0]["src"]
        for p in salida[1:]:
            a, b = p["src"]
            if a < gb and b > ga:
                if a < ga:
                    p["src"][1] = round(min(b, ga), 3)
                else:
                    p["src"][0] = round(max(a, gb), 3)
    # El primer fotograma enseña el gancho: si el primer plano no abre con un titular, lleva uno con la palabra más
    # larga de lo que dice (las largas suelen ser las que llevan la idea).
    if salida and (salida[0].get("grafico") or {}).get("tipo") != "titular":
        a, b = salida[0]["src"]
        dichas = [w["word"].strip(" ,.;:¿?¡!\"«»") for w in palabras if a - 0.05 <= w["start"] < b]
        palabra = max(dichas, key=len, default="")[:12]
        salida[0].pop("abarca", None)
        salida[0]["grafico"] = {"tipo": "titular", "palabra": palabra[:1].upper() + palabra[1:] or "Ojo",
                                "kicker": [], "en": a}
    return {"bruto": bruto, "kit": kit, "planos": salida}


def _grafico_en_segundos(g: dict, tramo: list[int], palabras: list[dict], ini: float, modo: str, t) -> dict:
    tipo = g.get("tipo")
    dentro = lambda i: i if isinstance(i, int) and i in tramo else tramo[0]  # noqa: E731
    if tipo == "titular":
        k = max(0, min(int(g.get("kicker") or 0), val.PALABRAS_ROTULO, len(tramo) - 1))
        return {"tipo": "titular", "palabra": str(g.get("palabra") or "").strip()[:12] or "Ojo",
                "kicker": [palabras[i]["word"].strip(" ,.;:¿?¡!") for i in tramo[:k]],
                "en": ini if modo == "recorte" else round(t(dentro(g.get("en"))), 3)}
    if tipo == "chat":
        en, envio = dentro(g.get("en")), dentro(g.get("envio"))
        if envio <= en:
            envio = tramo[-1]
        return {"tipo": "chat", "etiqueta": str(g.get("etiqueta") or "Mensaje")[:24], "texto": str(g.get("texto") or "")[:40],
                "en": round(t(en), 3), "envio": round(t(envio), 3)}
    if tipo == "ficha":
        filas = []
        for f in (g.get("filas") or [])[:3]:
            fila = {"etiqueta": str(f.get("etiqueta") or "")[:16], "valor": str(f.get("valor") or "")[:22],
                    "en": round(t(dentro(f.get("en"))), 3)}
            if f.get("cifra") and str(f.get("valor", "")).isdigit():
                fila["cifra"] = True
            if f.get("sufijo"):
                fila["sufijo"] = str(f["sufijo"])[:10]
            filas.append(fila)
        return {"tipo": "ficha", "filas": filas or [{"etiqueta": "", "valor": "", "en": t(tramo[0])}]}
    if tipo == "icono":
        salida = {"tipo": "icono", "en": round(t(dentro(g.get("en"))), 3), "icono": str(g.get("icono") or "chispa"),
                  "lado": "derecha" if g.get("lado") == "derecha" else "izquierda"}
        if g.get("texto"):
            salida["texto"] = str(g["texto"])[:18]
        return salida
    if tipo == "efecto":
        clase = g.get("clase") if g.get("clase") in ("lista", "cifra", "comparacion", "proceso", "grafica") else "lista"
        lugar = g.get("lugar") if g.get("lugar") in ("encima", "partida", "completa") else "encima"
        elementos = [{"texto": str(x.get("texto") or "")[:40], "valor": str(x.get("valor") or "")[:14],
                      "en": round(t(dentro(x.get("en"))), 3)} for x in (g.get("elementos") or [])[:5]]
        salida = {"tipo": "efecto", "clase": clase, "lugar": lugar, "en": round(t(dentro(g.get("en"))), 3),
                  "elementos": elementos or [{"texto": "", "valor": "", "en": round(t(tramo[0]), 3)}]}
        for k, largo in (("titulo", 36), ("sufijo", 10)):
            if g.get(k):
                salida[k] = str(g[k])[:largo]
        return salida
    if tipo == "logos":
        nombres = [str(x)[:40] for x in (g.get("logos") or []) if str(x).strip()][:5]
        return {"tipo": "logos", "en": round(t(dentro(g.get("en"))), 3), "logos": nombres}
    if tipo == "sello":
        salida = {"tipo": "sello", "en": round(t(dentro(g.get("en"))), 3)}
        for k, largo in (("texto", 14), ("cinta", 24)):
            if g.get(k):
                salida[k] = str(g[k])[:largo]
        return salida
    if tipo == "imagen":
        salida = {"tipo": "imagen", "en": round(t(dentro(g.get("en"))), 3), "pie": str(g.get("pie") or "")[:32],
                  "forma": "pantalla" if g.get("forma") == "pantalla" else "tarjeta"}
        for k in ("wikipedia", "web", "propia"):
            if g.get(k):
                salida[k] = str(g[k])[:120]
        return salida
    if tipo == "fondo":
        salida = {"tipo": "fondo", "en": round(t(dentro(g.get("en"))), 3)}
        if g.get("titular"):
            salida["titular"] = str(g["titular"])[:12]
        return salida
    return {"tipo": "titular", "palabra": "Ojo", "kicker": [], "en": ini}


def sanear(m: dict, intentos: int = 4) -> tuple[dict, list[str]]:
    """Arregla lo que el validador marque como error. Devuelve el montaje y lo que se ha cambiado."""
    m = copy.deepcopy(m)
    hechos = []
    for _ in range(intentos):
        errores, _ = val.validar(m)
        if not errores:
            break
        planos = m["planos"]
        # 0. Emoticonos fuera (si la voz del cliente no los usa, o si se pasa de los pocos que usa) y rótulos de
        #    más de PALABRAS_ROTULO palabras, recortados.
        quitar_emojis = (m.get("reglas") or {}).get("emojis", "nunca") != "libre"
        for p in planos:
            g = p.get("grafico") or {}
            fuera = val.NO_ROTULOS.get(g.get("tipo"), set())
            for obj in [g, *g.get("filas", []), *g.get("elementos", [])]:
                for k in val.TEXTOS:
                    if isinstance(obj.get(k), str):
                        texto = val.EMOJI.sub("", obj[k]) if quitar_emojis else obj[k]
                        palabras = texto.split()
                        if obj is g and k in fuera:
                            obj[k] = " ".join(palabras)
                        else:
                            obj[k] = " ".join(palabras[:val.PALABRAS_ROTULO])
            if "kicker" in g:
                g["kicker"] = [w for w in (val.EMOJI.sub("", k).strip() for k in g["kicker"]) if w][-val.PALABRAS_ROTULO:]
        # 1. Máximos por minuto: se quedan los primeros.
        minutos = sum(p["src"][1] - p["src"][0] for p in planos) / 60
        tope = {k: val.maximo(k, minutos, (m.get("reglas") or {}).get("maximos")) for k in val.MAXIMOS}
        cuenta = {k: 0 for k in val.MAXIMOS}
        for p in planos:
            if p.get("entrada") in ("latigo", "tiras"):
                cuenta["transicion"] += 1
                if cuenta["transicion"] > tope["transicion"]:
                    p.pop("entrada")
                    hechos.append(f"Quitada una transición de más en {p['id']}.")
            if "sacudida" in p:
                cuenta["sacudida"] += 1
                if cuenta["sacudida"] > tope["sacudida"]:
                    p.pop("sacudida")
            g = p.get("grafico")
            if g:
                clave = {"chat": "tarjeta", "ficha": "tarjeta"}.get(g["tipo"], g["tipo"])
                cuenta[clave] += 1
                completa = g["tipo"] == "efecto" and g.get("lugar") == "completa"
                if completa:
                    cuenta["completa"] += 1
                if cuenta[clave] > tope[clave]:
                    p.pop("grafico")
                    hechos.append(f"Quitado un gráfico de más en {p['id']}.")
                elif completa and cuenta["completa"] > tope["completa"]:
                    g["lugar"] = "partida"  # una pantalla completa de más pasa a partida
                    hechos.append(f"El efecto de {p['id']} pasa a pantalla partida (ya había otra completa).")
        # 2. Gráficos fuera de su plano (o de su grupo, si abarca varios): se meten dentro.
        for i, p in enumerate(planos):
            g = p.get("grafico")
            if not g:
                continue
            grupo = planos[i:i + p.get("abarca", 1)]
            a, b = grupo[0]["src"][0], grupo[-1]["src"][1]
            for obj in [g, *g.get("filas", [])]:
                for clave in ("en", "envio"):
                    if clave in obj:
                        obj[clave] = min(max(obj[clave], a), b - 0.05)
            if "sacudida" in p:
                p["sacudida"] = min(max(p["sacudida"], a), b - 0.05)
        # 3. Planos demasiado cortos: se alargan sobre el anterior si son contiguos; si no, hacia delante.
        # Los límites son el plano vecino en el bruto y, si lo hay, el tramo del gancho (no se puede pisar).
        gancho = planos[0]["src"] if planos[0].get("gancho") else None
        for i, p in enumerate(planos):
            if p["src"][1] - p["src"][0] >= val.PLANO_MIN or p.get("gancho"):
                continue
            falta = val.PLANO_MIN - (p["src"][1] - p["src"][0]) + 0.01
            siguiente = planos[i + 1]["src"][0] if i + 1 < len(planos) else p["src"][1] + 1
            if gancho and p["src"][1] <= gancho[0] + 0.01:
                siguiente = min(siguiente, gancho[0])
            p["src"][1] = round(min(p["src"][1] + falta, siguiente), 3)
            if p["src"][1] - p["src"][0] < val.PLANO_MIN:
                anterior = planos[i - 1]["src"][1] if i and not planos[i - 1].get("gancho") else 0.0
                if gancho and p["src"][0] >= gancho[1] - 0.01:
                    anterior = max(anterior, gancho[1])
                p["src"][0] = round(max(p["src"][0] - falta, anterior), 3)
        # 4. Dos planos seguidos iguales: cambia el encuadre del segundo.
        for prev, p in zip(planos, planos[1:]):
            if prev["modo"] == p["modo"] and abs(prev.get("zoom", 1) - p.get("zoom", 1)) < val.ZOOM_DISTINTO \
                    and p.get("entrada", "corte") == "corte":
                z = prev.get("zoom", 1)
                p["zoom"] = round(z + SALTO_ZOOM if z < 1.25 else z - SALTO_ZOOM, 2)
                hechos.append(f"Cambiado el encuadre de {p['id']} para que el corte se note.")
    return m, list(dict.fromkeys(hechos))
