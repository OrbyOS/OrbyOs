"""Los gráficos del reel, dibujados fotograma a fotograma con Pillow en capas transparentes de 1080×1920.

Cada efecto es una función `fotograma(t)` que devuelve la capa RGBA en el instante t (en segundos desde que empieza
el bloque). La palabra gigante recibe además la silueta de la persona para quedar por detrás.
"""
import math
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .. import config

ANCHO, ALTO, FPS = 1080, 1920, 30
FUENTES = {"condensada": "Anton.ttf", "redonda": "Poppins-ExtraBold.ttf", "clasica": "Archivo-Bold.ttf"}


@lru_cache(maxsize=64)
def fuente(nombre: str, tam: int) -> ImageFont.FreeTypeFont:
    """Una de las tres de la casa o, con «marca:<ruta>», la tipografía que ha subido el negocio a su Kit."""
    if nombre.startswith("marca:"):
        try:
            return ImageFont.truetype(nombre[6:], tam)
        except OSError:
            nombre = "redonda"
    return ImageFont.truetype(str(config.FUENTES_DIR / FUENTES.get(nombre, "Poppins-ExtraBold.ttf")), tam)


def rgba(hexa: str, alfa: int = 255) -> tuple:
    hexa = (hexa or "#FFFFFF").lstrip("#")
    return tuple(int(hexa[i:i + 2], 16) for i in (0, 2, 4)) + (alfa,)


def _salida_rebote(x: float) -> float:
    """Curva que se pasa un poco y vuelve (para que las cosas «aterricen»)."""
    c1, c3 = 1.70158, 2.70158
    x = min(1.0, max(0.0, x))
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def _suave(x: float) -> float:
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def _vacia() -> Image.Image:
    return Image.new("RGBA", (ANCHO, ALTO), (0, 0, 0, 0))


def texto_con_sombra(texto: str, f: ImageFont.FreeTypeFont, color: tuple, *, sombra: int = 18,
                     contorno: int = 0, fondo: str = "sombra") -> Image.Image:
    """El texto en su propia capa, con una sombra suave debajo para que se lea sobre cualquier fondo. Con
    `fondo="velo"`, en vez de la sombra lleva un velo oscuro y difuso detrás (sin caja: los bordes se pierden)."""
    if fondo == "velo":
        return _texto_con_velo(texto, f, color, contorno=contorno)
    caja = f.getbbox(texto, stroke_width=contorno)
    ancho, alto = caja[2] - caja[0] + sombra * 4, caja[3] - caja[1] + sombra * 4
    capa = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    origen = (sombra * 2 - caja[0], sombra * 2 - caja[1])
    if sombra:
        s = Image.new("RGBA", capa.size, (0, 0, 0, 0))
        ImageDraw.Draw(s).text(origen, texto, font=f, fill=(0, 0, 0, 150), stroke_width=contorno,
                               stroke_fill=(0, 0, 0, 150))
        capa = Image.alpha_composite(capa, s.filter(ImageFilter.GaussianBlur(sombra / 2)))
        d = ImageDraw.Draw(capa)
    d.text(origen, texto, font=f, fill=color, stroke_width=contorno, stroke_fill=(0, 0, 0, 255))
    return capa


def _texto_con_velo(texto: str, f: ImageFont.FreeTypeFont, color: tuple, *, contorno: int = 0) -> Image.Image:
    caja = f.getbbox(texto, stroke_width=contorno)
    margen = max(30, int(f.size * 0.8))
    ancho, alto = caja[2] - caja[0] + margen * 2, caja[3] - caja[1] + margen * 2
    velo = Image.new("L", (ancho, alto), 0)  # una elipse muy desenfocada: se lee el texto y no se ve ningún borde
    ImageDraw.Draw(velo).ellipse((margen * 0.5, margen * 0.75, ancho - margen * 0.5, alto - margen * 0.75), fill=165)
    velo = velo.filter(ImageFilter.GaussianBlur(margen * 0.42))
    capa = Image.new("RGBA", (ancho, alto), (6, 8, 16, 0))
    capa.putalpha(velo)
    ImageDraw.Draw(capa).text((margen - caja[0], margen - caja[1]), texto, font=f, fill=color, stroke_width=contorno,
                              stroke_fill=(0, 0, 0, 255))
    return capa


def _con_alfa(capa: Image.Image, alfa: float) -> Image.Image:
    if alfa >= 1:
        return capa
    c = capa.copy()
    c.putalpha(c.getchannel("A").point(lambda a, k=max(0.0, alfa): int(a * k)))
    return c


def _desenfocar(capa: Image.Image, radio: float) -> Image.Image:
    return capa.filter(ImageFilter.GaussianBlur(radio)) if radio > 0.4 else capa


def _pegar_centrado(base: Image.Image, capa: Image.Image, cx: float, cy: float):
    base.alpha_composite(capa, (int(cx - capa.width / 2), int(cy - capa.height / 2)))


# ---------------------------------------------------------------- palabra gigante

class Choque:
    """Una palabra gigante que entra de golpe, rebota, se balancea y se va. Con silueta, queda detrás de la persona."""

    def __init__(self, texto: str, duracion: float, *, color: str, centro_y: float = 0.36, fuente_: str = "condensada",
                 entrada: str = "golpe", fondo: str = "sombra"):
        self.duracion = duracion
        self.entrada = entrada
        self.cy = ALTO * centro_y
        tam = 420
        f = fuente(fuente_, tam)
        while f.getlength(texto) > ANCHO * 0.94 and tam > 120:
            tam -= 20
            f = fuente(fuente_, tam)
        self.capa = texto_con_sombra(texto, f, rgba(color), sombra=26, fondo=fondo)

    def _forma(self, t: float) -> tuple[float, float, float]:
        """(escala, giro, desenfoque) en el instante t, según cómo entra."""
        if self.entrada == "seco":
            return 1.0, 0.0, 0.0
        if self.entrada == "foco":
            p = _suave(t / 0.32)
            return 1.08 - 0.08 * p, 0.0, 16 * (1 - p)
        if t < 0.16:  # cae desde muy grande
            escala = 2.3 - 1.38 * (t / 0.16) ** 2
        elif t < 0.4:
            escala = 0.92 + 0.08 * _salida_rebote((t - 0.16) / 0.24)
        else:
            escala = 1.0
        giro = 0.0 if t < 0.35 else 3.2 * math.sin(2 * math.pi * 1.1 * (t - 0.35)) * math.exp(-(t - 0.35) * 0.9)
        return escala, giro, 0.0

    def fotograma(self, t: float, silueta=None) -> Image.Image:
        lienzo = _vacia()
        if t < 0 or t > self.duracion:
            return lienzo
        escala, giro, desenfoque = self._forma(t)
        alfa = min(1.0, (self.duracion - t) / 0.18) if self.duracion - t < 0.18 else 1.0
        if self.entrada == "foco":
            alfa = min(alfa, t / 0.18)
        capa = self.capa.resize((max(1, int(self.capa.width * escala)), max(1, int(self.capa.height * escala))),
                                Image.BICUBIC)
        if abs(giro) > 0.05:
            capa = capa.rotate(giro, resample=Image.BICUBIC, expand=True)
        capa = _con_alfa(_desenfocar(capa, desenfoque), alfa)
        _pegar_centrado(lienzo, capa, ANCHO / 2, self.cy)
        if silueta is not None:  # la persona por delante: donde hay persona, la palabra se borra
            a = lienzo.getchannel("A")
            persona = Image.fromarray((silueta * 255).astype("uint8")).resize((ANCHO, ALTO), Image.BILINEAR)
            lienzo.putalpha(Image.composite(Image.new("L", lienzo.size, 0), a, persona))
        return lienzo


# ---------------------------------------------------------------- gancho

def partir_lineas(texto: str, f: ImageFont.FreeTypeFont, ancho_max: float) -> list[str]:
    lineas, actual = [], ""
    for p in texto.split():
        prueba = f"{actual} {p}".strip()
        if f.getlength(prueba) <= ancho_max or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    return lineas


class Gancho:
    """El título del gancho arriba: las palabras aparecen una a una y la más larga va en el color de marca."""

    def __init__(self, texto: str, duracion: float, *, color: str, fuente_: str = "redonda", mayusculas: bool = True,
                 y0: float = 0.06, entrada: str = "pop", fondo: str = "sombra"):
        self.duracion = duracion
        self.entrada = entrada
        texto = texto.upper() if mayusculas else texto
        tam = 92
        f = fuente(fuente_, tam)
        lineas = partir_lineas(texto, f, ANCHO * 0.86)
        while len(lineas) > 3 and tam > 56:
            tam -= 6
            f = fuente(fuente_, tam)
            lineas = partir_lineas(texto, f, ANCHO * 0.86)
        palabras = texto.split()
        clave = max(palabras, key=lambda p: len(re.sub(r"\W", "", p))) if palabras else ""
        self.piezas = []  # (capa, x, y, retraso)
        alto_linea = tam * 1.22
        y = ALTO * y0
        n = 0
        for numero, linea in enumerate(lineas):
            espacio = f.getlength(" ")
            anchos = [f.getlength(p) for p in linea.split()]
            x = (ANCHO - (sum(anchos) + espacio * (len(anchos) - 1))) / 2
            for p, w in zip(linea.split(), anchos):
                capa = texto_con_sombra(p, f, rgba(color) if p == clave else (255, 255, 255, 255), sombra=14,
                                        fondo=fondo)
                retraso = {"subida": numero * 0.14, "fundido": 0.0}.get(entrada, n * 0.07)
                self.piezas.append((capa, x + w / 2, y + alto_linea / 2, retraso))
                x += w + espacio
                n += 1
            y += alto_linea

    def fotograma(self, t: float, silueta=None) -> Image.Image:
        lienzo = _vacia()
        if t < 0 or t > self.duracion:
            return lienzo
        salida = min(1.0, (self.duracion - t) / 0.15) if self.duracion - t < 0.15 else 1.0
        for capa, cx, cy, retraso in self.piezas:
            if self.entrada == "subida":
                p = _suave((t - retraso) / 0.38)
                if p <= 0:
                    continue
                c = _con_alfa(_desenfocar(capa, 10 * (1 - p)), p * salida)
                _pegar_centrado(lienzo, c, cx, cy + 46 * (1 - p))
                continue
            if self.entrada == "fundido":
                p = _suave(t / 0.5)
                if p > 0:
                    _pegar_centrado(lienzo, _con_alfa(capa, p * salida), cx, cy)
                continue
            p = (t - retraso) / 0.22
            if p <= 0:
                continue
            escala = 0.7 + 0.3 * _salida_rebote(p)
            alfa = min(1.0, p * 1.5) * salida
            c = capa.resize((max(1, int(capa.width * escala)), max(1, int(capa.height * escala))), Image.BICUBIC)
            _pegar_centrado(lienzo, _con_alfa(c, alfa), cx, cy)
        return lienzo


# ---------------------------------------------------------------- lista

class Lista:
    """Elementos que entran uno a uno desde la izquierda, marcados en el color de marca: el número en un círculo
    («circulos»), el número grande sin círculo («numeros») o una línea fina a la izquierda («filete»)."""

    def __init__(self, items: list[str], tiempos: list[float], duracion: float, *, color: str, fuente_: str = "redonda",
                 y0: float = 0.5, marca: str = "circulos", fondo: str = "sombra"):
        self.duracion = duracion
        self.tiempos = tiempos
        self.y0 = y0
        f = fuente(fuente_, 62)
        fn = fuente("redonda", 46)
        self.filas = []
        for i, item in enumerate(items):
            texto = item if len(item) <= 34 else item[:33] + "…"
            capa = texto_con_sombra(texto, f, (255, 255, 255, 255), sombra=12, fondo=fondo)
            num = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
            d = ImageDraw.Draw(num)
            n = str(i + 1)
            if marca == "numeros":
                fg = fuente(fuente_, 84)
                caja = fg.getbbox(n)
                d.text((48 - (caja[0] + caja[2]) / 2, 48 - (caja[1] + caja[3]) / 2), n, font=fg, fill=rgba(color))
            elif marca == "filete":
                d.rounded_rectangle((60, 14, 68, 82), radius=4, fill=rgba(color))
            else:
                d.ellipse((4, 4, 92, 92), fill=rgba(color))
                d.text((48 - fn.getlength(n) / 2, 48 - 30), n, font=fn, fill=(255, 255, 255, 255))
            self.filas.append((num, capa))

    def fotograma(self, t: float, silueta=None) -> Image.Image:
        lienzo = _vacia()
        if t < 0 or t > self.duracion:
            return lienzo
        salida = min(1.0, (self.duracion - t) / 0.2) if self.duracion - t < 0.2 else 1.0
        y = ALTO * self.y0
        for (num, capa), t0 in zip(self.filas, self.tiempos):
            p = (t - t0) / 0.25
            if p > 0:
                desplazamiento = (1 - _suave(p)) * -60
                alfa = min(1.0, p * 1.4) * salida
                for pieza, x in ((num, 70 + desplazamiento), (capa, 180 + desplazamiento)):
                    c = pieza.copy()
                    if alfa < 1:
                        c.putalpha(c.getchannel("A").point(lambda a, k=alfa: int(a * k)))
                    lienzo.alpha_composite(c, (int(x), int(y + (96 - c.height) / 2)))
            y += 132
        return lienzo


# ---------------------------------------------------------------- texto en movimiento (modo solo voz)

class Cinetico:
    """Las palabras que suenan, grandes y en el centro, de una en una o de dos en dos."""

    def __init__(self, palabras: list[dict], duracion: float, *, color: str, fuente_: str = "condensada",
                 mayusculas: bool = True):
        self.duracion = duracion
        self.grupos = []
        actual = []
        for w in palabras:
            actual.append(w)
            if len(actual) >= 2 or re.search(r"[.,;:?!]$", w["word"]):
                self.grupos.append(actual)
                actual = []
        if actual:
            self.grupos.append(actual)
        self.capas = []
        for n, g in enumerate(self.grupos):
            texto = " ".join(re.sub(r"[.,;:]+$", "", w["word"]) for w in g)
            texto = texto.upper() if mayusculas else texto
            tam = 170
            f = fuente(fuente_, tam)
            while f.getlength(texto) > ANCHO * 0.9 and tam > 70:
                tam -= 10
                f = fuente(fuente_, tam)
            largo = max((len(w["word"]) for w in g), default=0) >= 7
            self.capas.append((g[0]["start"], g[-1]["end"],
                               texto_con_sombra(texto, f, rgba(color) if largo else (255, 255, 255, 255), sombra=20)))

    def fotograma(self, t: float, silueta=None) -> Image.Image:
        lienzo = _vacia()
        for n, (a, b, capa) in enumerate(self.capas):
            fin = self.capas[n + 1][0] if n + 1 < len(self.capas) else max(b + 0.3, self.duracion)
            if a <= t < fin:
                escala = 0.8 + 0.2 * _salida_rebote((t - a) / 0.18)
                c = capa.resize((max(1, int(capa.width * escala)), max(1, int(capa.height * escala))), Image.BICUBIC)
                _pegar_centrado(lienzo, c, ANCHO / 2, ALTO * 0.5)
                break
        return lienzo


# ---------------------------------------------------------------- fondos, cierre y logo

def fondo(color: str, destino: Path):
    """Fondo para el modo solo voz: el color de marca oscurecido, con un degradado vertical suave."""
    r, g, b, _ = rgba(color)
    franja = Image.new("RGB", (1, 256))
    franja.putdata([(int(r * (0.22 + 0.25 * y / 255)), int(g * (0.22 + 0.25 * y / 255)), int(b * (0.22 + 0.25 * y / 255)))
                    for y in range(256)])
    franja.resize((ANCHO, ALTO), Image.BILINEAR).save(destino)


def cierre(destino: Path, *, color: str, logo: Path | None, nombre: str = ""):
    lienzo = Image.new("RGB", (ANCHO, ALTO), rgba(color)[:3])
    if logo and logo.exists():
        with Image.open(logo) as im:
            im = im.convert("RGBA")
            im.thumbnail((560, 560))
            lienzo.paste(im, (int((ANCHO - im.width) / 2), int(ALTO * 0.42 - im.height / 2)), im)
    elif nombre:
        f = fuente("redonda", 96)
        d = ImageDraw.Draw(lienzo)
        for i, linea in enumerate(partir_lineas(nombre, f, ANCHO * 0.8)[:3]):
            d.text(((ANCHO - f.getlength(linea)) / 2, ALTO * 0.4 + i * 116), linea, font=f, fill=(255, 255, 255))
    lienzo.save(destino)


def logo_esquina(logo: Path, destino: Path, ancho: int = 170):
    with Image.open(logo) as im:
        im = im.convert("RGBA")
        im.thumbnail((ancho, ancho))
        capa = Image.new("RGBA", (im.width + 8, im.height + 8), (0, 0, 0, 0))
        capa.alpha_composite(im, (4, 4))
        capa.save(destino)


def captura_vertical(origen: Path, destino: Path, *, alto: int = ALTO // 2):
    """Una captura recortada para la mitad de arriba (o para la pantalla entera, con `alto`=ALTO)."""
    with Image.open(origen) as im:
        im = im.convert("RGB")
        escala = max(ANCHO / im.width, alto / im.height)
        im = im.resize((int(im.width * escala) + 1, int(im.height * escala) + 1), Image.LANCZOS)
        x = (im.width - ANCHO) // 2
        im.crop((x, 0, x + ANCHO, alto)).save(destino)
