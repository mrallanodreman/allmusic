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

RUN mkdir -p /app/data
ENV ALLMUSIC_DATA_DIR=/app/data

# EdgeRadio: IA Radio (:2426) + cabina master stream (:2427)
EXPOSE 2426 2427

COPY start.sh .
RUN chmod +x start.sh

CMD ["./start.sh"]
