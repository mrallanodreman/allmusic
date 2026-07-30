FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema: ffmpeg + yt-dlp
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Instalar yt-dlp (CLI para streaming directo)
RUN pip install --no-cache-dir yt-dlp

# Dependencias Python del proyecto
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar backend
COPY backend/ ./backend/
# Copiar frontend
COPY frontend/ ./frontend/

# Volumen para datos persistentes (downloads, users, playlists, artist uploads)
VOLUME /data
ENV ALLMUSIC_DATA_DIR=/data

EXPOSE 2426

CMD ["python", "-u", "backend/allmusic_server.py"]
