"""Trabajos en segundo plano: cada agente lanza lo que tarda (escanear, planificar, escribir…) en un hilo aparte."""
import contextvars
import threading


def en_segundo_plano(funcion, *args):
    """El hilo hereda el negocio en el que se lanza: así usa sus claves (claves.NEGOCIO)."""
    contexto = contextvars.copy_context()
    threading.Thread(target=contexto.run, args=(funcion, *args), daemon=True).start()
