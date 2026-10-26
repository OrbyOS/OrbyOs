"""El equipo de agentes de contenido: investigar, planificar, escribir, editar, publicar, atender y aprender, con
el Kit de marca como base común y una sola cola de aprobaciones."""

# Cada agente lleva una parte del trabajo y se la pasa al siguiente. Los nombres se cambian aquí.
AGENTES = {
    "jefa": {"nombre": "Orby", "rol": "Dirección", "texto": "El resumen de cada mañana, tus aprobaciones y el chat"},
    "analista": {"nombre": "Lupi", "rol": "Investigación",
                 "texto": "Lo que destaca en tu nicho y en tu cuenta, medido contra lo normal de cada cuenta"},
    "estratega": {"nombre": "Plani", "rol": "Estrategia", "texto": "Qué grabar hoy, en qué formato y para qué etapa"},
    "guionista": {"nombre": "Escri", "rol": "Guiones", "texto": "Ganchos y guiones con tu voz, sin cifras inventadas"},
    "editor": {"nombre": "Monti", "rol": "Edición", "texto": "Corta, subtitula y revisa tus vídeos, y hace la v2 con tus notas"},
    "publicador": {"nombre": "Publi", "rol": "Publicación", "texto": "Programa cada vídeo en tus redes con enlace de seguimiento"},
    "comunidad": {"nombre": "Chati", "rol": "Comunidad", "texto": "Manda la guía a quien comenta la palabra clave y te prepara las respuestas"},
}

# Cuánto puede hacer cada agente sin ti.
AUTONOMIAS = {
    "revisar_todo": "Revisar todo",
    "revisar_clave": "Revisar solo lo importante",
    "piloto": "Piloto automático",
}
AUTONOMIA_INICIAL = "revisar_todo"
