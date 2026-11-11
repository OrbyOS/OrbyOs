"""Línea de órdenes del motor de reels (la usa la skill editar-reel; el SaaS llama a las funciones directamente).

Desde producto/app, con el entorno del SaaS:
  .venv/bin/python -m motor_reels preparar <bruto> <carpeta_trabajo> [--backend vision|mediapipe] [--solo-transcribir]
  .venv/bin/python -m motor_reels fotogramas <bruto> <carpeta_trabajo>   (solo los tramos de sus montajes)
  .venv/bin/python -m motor_reels validar  <carpeta_trabajo>/montaje.json
  .venv/bin/python -m motor_reels montar   <carpeta_trabajo>/montaje.json <salida.mp4>
  .venv/bin/python -m motor_reels qa       <salida.mp4> <carpeta_trabajo>
  .venv/bin/python -m motor_reels serie    <carpeta_trabajo>   (varios reels: <carpeta_trabajo>/*/montaje.json)
  .venv/bin/python -m motor_reels vista    <carpeta_trabajo>/montaje.json   (todo menos el render: para el panel de Montaje)
  .venv/bin/python -m motor_reels final    <carpeta_trabajo> <props.json> <salida.mp4> [--musica X --musica-lufs -30 --sfx 0.5]
  python -m motor_reels trabajar <carpeta_cola>                  (worker de renders del servidor: cola.py)
"""
import argparse
import json
import sys
from pathlib import Path

from .motor import montar, preparar, qa, validar


def main():
    ap = argparse.ArgumentParser(prog="motor_reels")
    sub = ap.add_subparsers(dest="orden", required=True)
    p = sub.add_parser("preparar")
    p.add_argument("bruto", type=Path)
    p.add_argument("trabajo", type=Path)
    p.add_argument("--backend", choices=["vision", "mediapipe"])
    p.add_argument("--solo-transcribir", action="store_true")
    fo = sub.add_parser("fotogramas")
    fo.add_argument("bruto", type=Path)
    fo.add_argument("trabajo", type=Path)
    fo.add_argument("--backend", choices=["vision", "mediapipe"])
    v = sub.add_parser("validar")
    v.add_argument("montaje", type=Path)
    m = sub.add_parser("montar")
    m.add_argument("montaje", type=Path)
    m.add_argument("salida", type=Path)
    se = sub.add_parser("serie")
    se.add_argument("trabajo", type=Path)
    vi = sub.add_parser("vista")
    vi.add_argument("montaje", type=Path)
    fi = sub.add_parser("final")
    fi.add_argument("trabajo", type=Path)
    fi.add_argument("props", type=Path)
    fi.add_argument("salida", type=Path)
    fi.add_argument("--musica", type=Path)
    fi.add_argument("--musica-lufs", type=float, default=-30.0)
    fi.add_argument("--sfx", type=float, default=0.5)
    fi.add_argument("--velocidad", type=float, help="la del panel; si no, la de la vista")
    tr = sub.add_parser("trabajar")
    tr.add_argument("cola", type=Path)
    q = sub.add_parser("qa")
    q.add_argument("reel", type=Path)
    q.add_argument("trabajo", type=Path)
    a = ap.parse_args()

    if a.orden == "vista":
        v = montar.preparar_vista(a.montaje.resolve())
        print(json.dumps({"props": str(v["trabajo"] / "props.json"), "velocidad": v["velocidad"],
                          "avisos": v["avisos"]}, ensure_ascii=False))
    elif a.orden == "final":
        trabajo = a.trabajo.resolve()
        vista = json.loads((trabajo / "vista.json").read_text(encoding="utf-8"))
        datos = json.loads(a.props.read_text(encoding="utf-8"))
        print(json.dumps(montar.renderizar_props(trabajo, datos, a.salida.resolve(),
                                                 velocidad=a.velocidad or vista["velocidad"],
                                                 musica=a.musica, musica_lufs=a.musica_lufs, sfx=a.sfx),
                         ensure_ascii=False))
    elif a.orden == "trabajar":
        from . import cola
        print(f"Worker de renders: esperando encargos en {a.cola}", flush=True)
        cola.trabajar(a.cola.resolve())
    elif a.orden == "preparar":
        palabras = preparar.preparar(a.bruto.resolve(), a.trabajo.resolve(), a.backend,
                                     solo_transcribir=a.solo_transcribir)
        print(f"{len(palabras)} palabras en transcripcion.json"
              + ("" if a.solo_transcribir else "; fotogramas y silueta en frames/"))
    elif a.orden == "fotogramas":
        trabajo = a.trabajo.resolve()
        montajes = [json.loads(p.read_text(encoding="utf-8"))
                    for p in [*trabajo.glob("montaje.json"), *trabajo.glob("*/montaje.json")]]
        if not montajes:
            sys.exit("No hay montajes: escribe primero montaje.json (o uno por reel en subcarpetas).")
        rangos = preparar.rangos_de(montajes)
        print(f"{sum(b - a + 1 for a, b in rangos)} fotogramas en {len(rangos)} tramos")
        preparar.fotogramas(a.bruto.resolve(), trabajo, a.backend, rangos=rangos)
    elif a.orden in ("validar", "montar"):
        m = json.loads(a.montaje.read_text(encoding="utf-8"))
        # Lo que el kit del cliente prohíbe (máximo 0, p. ej. logos e iconos en el de un cliente) manda sobre el montaje.
        try:
            prohibidos = {k: 0 for k, v in ((montar.cargar_kit(m["kit"]).get("estilo") or {}).get("montaje", {})
                                            .get("maximos", {})).items() if v == 0}
        except (FileNotFoundError, KeyError):
            prohibidos = {}
        m.setdefault("reglas", {}).setdefault("maximos", {}).update(prohibidos)
        errores, avisos = validar.validar(m)
        errores += validar.repeticiones(m, montar.palabras_del_bruto(m, a.montaje.resolve().parent))
        for x in errores:
            print("ERROR:", x)
        for x in avisos:
            print("AVISO:", x)
        if errores:
            sys.exit(1)
        if a.orden == "validar":
            print("Montaje válido." if not avisos else "Montaje válido, con avisos.")
        else:
            print(json.dumps(montar.montar(a.montaje.resolve(), a.salida.resolve()), ensure_ascii=False))
    elif a.orden == "serie":
        montajes = {p.parent.name: json.loads(p.read_text(encoding="utf-8"))
                    for p in sorted(a.trabajo.glob("*/montaje.json"))}
        if not montajes:
            sys.exit("No hay reels en subcarpetas (<trabajo>/<reel>/montaje.json).")
        for nombre, m in montajes.items():
            errores, avisos = validar.validar(m)
            for x in errores:
                print(f"ERROR [{nombre}]:", x)
        errores, avisos = validar.validar_serie(montajes)
        for x in errores:
            print("ERROR [serie]:", x)
        for x in avisos:
            print("AVISO [serie]:", x)
        print(f"{len(montajes)} reels en la serie.")
    elif a.orden == "qa":
        print(json.dumps(qa.revisar(a.reel.resolve(), a.trabajo.resolve()), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
