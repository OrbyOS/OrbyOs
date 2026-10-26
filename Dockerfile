# Imagen para servir la app en la nube (Render, Railway, Fly.io, un VPS…).
FROM python:3.12-slim AS web

# ffmpeg para montar; libgl1 y libglib2.0-0 los necesita OpenCV (MediaPipe) para recortar la silueta.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY radar radar
COPY motor_reels motor_reels
# Descarga el modelo de transcripción al construir, para que la primera edición no espere.
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"

ENV RADAR_DATA_DIR=/datos RADAR_COOKIE_SEGURA=1 PORT=8000
VOLUME /datos
EXPOSE 8000
# Un solo proceso: los análisis y las ediciones corren en hilos de este proceso.
CMD ["sh", "-c", "uvicorn radar.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]

# El worker de renders del motor de reels (estilo «De editor»): Node, Remotion y su navegador. Va en un contenedor
# aparte para que la web no cargue con ellos: la web deja los encargos en la cola y este los hace de uno en uno.
FROM web AS renders
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
      libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
      libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 fonts-noto-color-emoji \
 && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y --no-install-recommends nodejs \
 && rm -rf /var/lib/apt/lists/*
RUN cd motor_reels/remotion && npm ci && npx remotion browser ensure
CMD ["python", "-m", "motor_reels", "trabajar", "/datos/cola_renders"]
