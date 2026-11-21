FROM node:20-alpine AS react-build

WORKDIR /build
COPY frontend-react/package.json frontend-react/package-lock.json ./
RUN npm ci --no-audit --no-fund
# publicDir de Vite es ../public, que desde /build resuelve a /public
COPY public/ /public/
COPY frontend-react/ ./
RUN npm run build


FROM python:3.12-slim

WORKDIR /app

# Dependencias del sistema: ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencias Python (versiones fijadas)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar backend y frontend
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Build de la UI React (IA Radio)
COPY --from=react-build /build/dist/ ./frontend-react-dist/

# Usuario no-root
RUN groupadd -r app && useradd -r -g app app \
    && mkdir -p /app/data \
    && chown -R app:app /app
USER app

ENV ALLMUSIC_DATA_DIR=/app/data
ENV ALLMUSIC_REACT_DIST_DIR=/app/frontend-react-dist
ENV PORT=2426
ENV PYTHONUNBUFFERED=1

EXPOSE 2426 2427

COPY --chown=app:app --chmod=+x start.sh .

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:2426/status || exit 1

CMD ["./start.sh"]
