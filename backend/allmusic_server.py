#!/usr/bin/env python3
"""
AllMusic Server - Railway Edition
yt-dlp + YouTube MP3 API - Adaptado para Railway
"""
from flask import Flask, jsonify, request, Response, send_from_directory, redirect
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import shutil
import yt_dlp
import http.client
import json
import time
import requests
import threading
import logging
import os
import re
import sys
import secrets
import hashlib
import hmac
import datetime
import subprocess
import mimetypes
import random
from urllib.parse import quote, unquote

# Carga variables desde .env en desarrollo local (si existe). En producción
# (Railway) las variables llegan del entorno y este bloque no hace nada.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
except ImportError:
    pass

app = Flask(__name__)
CORS(app, origins=[
    'http://localhost:2425',
    'http://localhost:2426',
    'http://127.0.0.1:2425',
    'http://127.0.0.1:2426',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'https://edgemarketing.art',
    'http://edgemarketing.art',
])

# Rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per minute", "30 per second"],
    storage_uri="memory://",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Límite de tamaño de petición/subida (50 MB por defecto, configurable)
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 50 * 1024 * 1024))

# ── ABUSO / FINGERPRINTING ("Nunca Confiar en el Usuario") ──────────────────
# Cliente normal: no se captura nada. Solo cuando una IP muestra actividad
# sospechosa (≥6 acciones sensibles en 60s, o 429s repetidos) se le captura
# fingerprint (pantalla+tz+idioma+UA+geo IP aproximada) por MÁXIMO 15 días.
ABUSE_TTL_SECONDS = 15 * 24 * 3600
ABUSE_WINDOW = 60
ABUSE_THRESHOLD = 6
_ip_hits = {}
SENSITIVE_ENDPOINTS = {'user_lookup', 'artist_auth_login', 'artist_auth_register', 'radio_suggest', 'user_register'}


def _client_ip():
    fwd = request.headers.get('X-Forwarded-For', '')
    if fwd:
        return fwd.split(',')[0].strip()
    return request.remote_addr or ''


def _load_abuse():
    now = time.time()
    try:
        with open(ABUSE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    pruned = {ip: rec for ip, rec in data.items() if isinstance(rec, dict) and now - float(rec.get('ts', 0)) < ABUSE_TTL_SECONDS}
    if len(pruned) != len(data):
        try:
            with open(ABUSE_FILE, 'w', encoding='utf-8') as f:
                json.dump(pruned, f, indent=2)
        except OSError:
            pass
    return pruned


def _save_abuse(data):
    try:
        with open(ABUSE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass


def _note_sensitive_hit(endpoint):
    ip = _client_ip()
    if not ip:
        return
    now = time.time()
    hits = [t for t in _ip_hits.get(ip, []) if now - t < ABUSE_WINDOW]
    hits.append(now)
    _ip_hits[ip] = hits
    if len(hits) >= ABUSE_THRESHOLD:
        data = _load_abuse()
        if ip not in data:
            data[ip] = {'ts': now, 'hits': len(hits)}
        else:
            data[ip]['ts'] = now
            data[ip]['hits'] = int(data[ip].get('hits', 0)) + len(hits)
        _save_abuse(data)
        _ip_hits[ip] = []


def _geo_ip(ip):
    try:
        r = requests.get(f'http://ip-api.com/json/{ip}?fields=status,country,regionName,city,timezone', timeout=3)
        if r.status_code == 200 and r.json().get('status') == 'success':
            j = r.json()
            return {'country': j.get('country'), 'region': j.get('regionName'), 'city': j.get('city'), 'tz': j.get('timezone')}
    except requests.RequestException:
        pass
    return {}


@app.route('/abuse/fingerprint', methods=['POST'])
@limiter.limit('3 per minute')
def abuse_fingerprint():
    """Captura silenciosa de fingerprint SOLO de clientes ya sospechosos (429s /
    intentos sensibles repetidos). Se purga a los 15 días."""
    ip = _client_ip()
    data = request.get_json(force=True, silent=True) or {}
    record = {
        'ts': time.time(),
        'ua': (request.headers.get('User-Agent') or '')[:200],
        'screen': str(data.get('screen') or '')[:40],
        'tz': str(data.get('tz') or '')[:60],
        'lang': str(data.get('lang') or '')[:20],
    }
    store = _load_abuse()
    existing = store.get(ip, {})
    existing.update(record)
    existing['geo'] = _geo_ip(ip)
    store[ip] = existing
    _save_abuse(store)
    return jsonify({'ok': True})


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'No encontrado'}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({'error': 'Método no permitido'}), 405

@app.errorhandler(429)
def rate_limited(e):
    return jsonify({'error': 'Demasiadas solicitudes. Intenta más tarde.'}), 429

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Error interno'}), 500


@app.before_request
def abuse_strict_limit():
    """Los IPs/dispositivos ya marcados tienen un límite más estricto (10/min)
    sobre endpoints sensibles, para frenar rotación de IP y fuerza bruta."""
    if request.endpoint not in SENSITIVE_ENDPOINTS and not request.path.startswith('/artists/auth'):
        return None
    if request.endpoint in SENSITIVE_ENDPOINTS:
        _note_sensitive_hit(request.endpoint or '')
    ip = _client_ip()
    store = _load_abuse()
    if ip and ip in store:
        now = time.time()
        hits = [t for t in store[ip].get('_hits', []) if now - t < 60]
        hits.append(now)
        store[ip]['_hits'] = hits
        _save_abuse(store)
        if len(hits) > 10:
            return jsonify({'error': 'Demasiadas solicitudes. Intenta más tarde.'}), 429
    return None


@app.after_request
def set_security_headers(resp):
    """Cabeceras de seguridad en todas las respuestas."""
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    # SAMEORIGIN (no DENY): la cabina de IA Radio (radio.html?embedded=1) se
    # renderiza en un iframe del propio sitio; DENY la volvía blanca.
    resp.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    resp.headers.setdefault('Strict-Transport-Security', 'max-age=63072000; includeSubDomains')
    resp.headers.setdefault(
        'Content-Security-Policy',
        "default-src 'self'; img-src 'self' data: https:; media-src 'self' https:; "
        "script-src 'self' 'unsafe-inline' https://pagead2.googlesyndication.com https://static.cloudflareinsights.com; "
        "style-src 'self' 'unsafe-inline'; "
        "frame-src 'self' https://googleads.g.doubleclick.net https://pagead2.googlesyndication.com; "
        "connect-src 'self' https: data: wss:"
    )
    return resp

# Config desde variables de entorno
# RAPIDAPI_KEY acepta una o varias keys separadas por coma (rotación automática:
# si una app de RapidAPI agota su cuota diaria (429/403), se prueba la siguiente).
RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', '')
RAPIDAPI_KEYS = [k.strip() for k in RAPIDAPI_KEY.split(',') if k.strip()]
RAPIDAPI_HOST = os.environ.get('RAPIDAPI_HOST', 'youtube-mp36.p.rapidapi.com')

# Acceso de moderación (solo servidor↔servidor, sin vista pública).
# Sin valor por defecto: si falta, los endpoints protegidos quedan DESHABILITADOS
# (fail-closed) y se registra un aviso explícito.
MODERATOR_KEY = os.environ.get('MODERATOR_KEY', '') or os.environ.get('ALLMUSIC_ADMIN_KEY', '')
if os.environ.get('ALLMUSIC_ADMIN_KEY'):
    logger.warning('ALLMUSIC_ADMIN_KEY está deprecada: usa MODERATOR_KEY')
if not MODERATOR_KEY:
    logger.warning('MODERATOR_KEY no configurada — endpoints de moderación deshabilitados')


def _is_moderator():
    """True si el request trae el token de moderación (solo servidor↔servidor)."""
    if not MODERATOR_KEY:
        return False
    provided = request.headers.get('X-Moderator-Key', '')
    return bool(provided) and hmac.compare_digest(provided, MODERATOR_KEY)

# JWT de artistas: secreto obligatorio en producción; en desarrollo se genera uno
# efímero (los tokens no sobreviven reinicios).
_JWT_SECRET = os.environ.get('JWT_SECRET', '')
if not _JWT_SECRET:
    _JWT_SECRET = secrets.token_hex(32)
    logger.warning('JWT_SECRET no definido — tokens de artistas se invalidarán al reiniciar')

# VirusTotal (segunda capa de validación de subidas de artistas)
VIRUSTOTAL_API_KEY = os.environ.get('VIRUSTOTAL_API_KEY', '')
VIRUSTOTAL_STRICT = os.environ.get('VIRUSTOTAL_STRICT', 'true').lower() in ('1', 'true', 'yes')

# 3ra capa: fallback local (yt-dlp en IP residencial) cuando las keys de
# RapidAPI se agotan. Ver ytfallback-server / hallazgo allmusic-rapidapi-key-rotation.
YTFALLBACK_URL = os.environ.get('YTFALLBACK_URL', '')  # ej. https://ytfallback.edgemarketing.art
YTFALLBACK_TOKEN = os.environ.get('YTFALLBACK_TOKEN', '')

if not RAPIDAPI_KEYS:
    logger.warning('RAPIDAPI_KEY no configurada — las conversiones fallarán')
if not YTFALLBACK_URL:
    logger.info('YTFALLBACK_URL no configurada — sin 3ra capa de fallback')
else:
    logger.info(f'🔑 {len(RAPIDAPI_KEYS)} key(s) de RapidAPI cargadas para rotación')

# Directorios de datos (persistentes en Railway)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('ALLMUSIC_DATA_DIR', os.path.join(BASE_DIR, 'data'))
DOWNLOADS_DIR = os.path.join(DATA_DIR, 'downloads')
ARTIST_UPLOADS_DIR = os.path.join(DATA_DIR, 'artist_uploads')
FRONTEND_DIR = os.environ.get('ALLMUSIC_FRONTEND_DIR', os.path.join(os.path.dirname(BASE_DIR), 'frontend'))
# Build de la UI React (IA Radio). Si no existe, /radio sirve el dashboard legacy.
REACT_DIST_DIR = os.environ.get(
    'ALLMUSIC_REACT_DIST_DIR', os.path.join(os.path.dirname(BASE_DIR), 'frontend-react', 'dist')
)

os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(ARTIST_UPLOADS_DIR, exist_ok=True)
ABUSE_FILE = os.path.join(DATA_DIR, 'abuse_fingerprints.json')


class AllMusicServer:
    CACHE_TTL_SECONDS = 30 * 60
    CACHE_MAX_ENTRIES = 200
    SEARCH_CACHE_TTL = 5 * 60
    SEARCH_CACHE_MAX = 100

    def __init__(self):
        self.cache = {}
        self._cache_ts = {}
        self._search_cache = {}  # query -> (timestamp, results), volátil

    def _search_cache_get(self, key):
        entry = self._search_cache.get(key)
        if entry and (time.time() - entry[0]) < self.SEARCH_CACHE_TTL:
            return entry[1]
        self._search_cache.pop(key, None)
        return None

    def _search_cache_set(self, key, results):
        if len(self._search_cache) >= self.SEARCH_CACHE_MAX:
            oldest = min(self._search_cache, key=lambda k: self._search_cache[k][0])
            self._search_cache.pop(oldest, None)
        self._search_cache[key] = (time.time(), results)

    def _cache_prune(self):
        """Expira entradas viejas y acota el tamaño (evita crecimiento sin límite)."""
        now = time.time()
        expired = [k for k, ts in self._cache_ts.items() if now - ts > self.CACHE_TTL_SECONDS]
        for k in expired:
            self.cache.pop(k, None)
            self._cache_ts.pop(k, None)
        if len(self.cache) > self.CACHE_MAX_ENTRIES:
            for k in sorted(self._cache_ts, key=self._cache_ts.get)[: len(self.cache) - self.CACHE_MAX_ENTRIES]:
                self.cache.pop(k, None)
                self._cache_ts.pop(k, None)

    def cache_set(self, key, value):
        self.cache[key] = value
        self._cache_ts[key] = time.time()
        self._cache_prune()

    def cache_pop(self, key):
        self.cache.pop(key, None)
        self._cache_ts.pop(key, None)

    def cache_get(self, key):
        self._cache_prune()
        return self.cache.get(key)

    def extract_video_id(self, url):
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})'
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def search_youtube(self, query, max_results=10):
        """Busca videos en YouTube usando yt-dlp"""
        try:
            logger.info(f"🔍 Buscando: {query}")
            MAX_DURATION_SECONDS = 7200

            # Pool ampliado (x3): en queries genericas ("lofi", "chill") YouTube
            # llena los primeros puestos con radios EN VIVO 24/7 y proximos,
            # que se filtran abajo. Con un pool chico quedaba 1 solo resultado
            # util y la app parecia rota.
            pool = min(max(max_results * 4, 24), 60)

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'default_search': 'ytsearch%d:' % pool,
                'ignoreerrors': True,
                'force_generic_extractor': False,
                'socket_timeout': 30,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                search_results = ydl.extract_info(f"ytsearch{pool}:{query}", download=False)
                results = []
                filtered_count = 0
                live_filtered_count = 0

                if search_results and 'entries' in search_results:
                    for entry in search_results['entries']:
                        if entry and entry.get('id'):
                            video_id = entry.get('id', '')
                            duration = entry.get('duration', 0)

                            if not video_id or len(video_id) != 11 or video_id.startswith('UC'):
                                continue
                            if not all(c.isalnum() or c in '-_' for c in video_id):
                                continue
                            # Streams en vivo/próximos no tienen un audio fijo que
                            # convertir — RapidAPI los rechaza con "Not available
                            # for live video" y yt-dlp no tiene qué extraer. "was_live"
                            # (un directo ya terminado) sí queda con duración real y
                            # se puede convertir normal, así que no se filtra.
                            if entry.get('live_status') in ('is_live', 'is_upcoming'):
                                live_filtered_count += 1
                                continue
                            if duration and duration > MAX_DURATION_SECONDS:
                                filtered_count += 1
                                continue

                            thumb = entry.get('thumbnail', '')
                            if not thumb:
                                thumbs = entry.get('thumbnails') or []
                                preferred = next((t['url'] for t in reversed(thumbs) if t.get('url') and t.get('width',0) >= 120), '')
                                if not preferred:
                                    preferred = next((t['url'] for t in thumbs if t.get('url')), '')
                                thumb = preferred or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

                            result = {
                                'id': video_id,
                                'title': entry.get('title', 'Sin título'),
                                'url': f"https://www.youtube.com/watch?v={video_id}",
                                'thumbnail': thumb,
                                'duration': duration,
                                'uploader': entry.get('uploader', 'Desconocido'),
                                'view_count': entry.get('view_count', 0)
                            }
                            results.append(result)

                if filtered_count > 0:
                    logger.info(f"🚫 Filtrados {filtered_count} videos por duración (>2h)")
                if live_filtered_count > 0:
                    logger.info(f"🚫 Filtrados {live_filtered_count} videos en vivo/próximos (no convertibles)")
                logger.info(f"✅ Encontrados {len(results)} resultados válidos")
                return results
        except Exception as e:
            logger.error(f"❌ Error en búsqueda: {str(e)}")
            return []

    def convert_to_mp3(self, video_id, max_retries=5):
        """Convierte un video de YouTube a MP3 usando RapidAPI"""
        try:
            logger.info(f"🎵 Convirtiendo video ID: {video_id}")
            MAX_DURATION_SECONDS = 7200

            try:
                ydl_opts = {'quiet': True, 'no_warnings': True, 'socket_timeout': 20}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
                    duration = info.get('duration', 0)
                    if duration and duration > MAX_DURATION_SECONDS:
                        duration_hours = duration / 3600
                        return {'success': False, 'error': f'Audio muy largo ({duration_hours:.1f}h). Máximo: 2h'}
            except Exception as e:
                logger.warning(f"⚠️ No se pudo verificar duración: {e}")

            if not RAPIDAPI_KEYS:
                return {'success': False, 'error': 'RAPIDAPI_KEY no configurada'}

            quota_errors = []
            for key_index, api_key in enumerate(RAPIDAPI_KEYS):
                conn = http.client.HTTPSConnection(RAPIDAPI_HOST, timeout=20)
                headers = {
                    'x-rapidapi-key': api_key,
                    'x-rapidapi-host': RAPIDAPI_HOST
                }
                try:
                    for attempt in range(max_retries):
                        try:
                            conn.request("GET", f"/dl?id={video_id}", headers=headers)
                            res = conn.getresponse()
                            data = res.read()

                            if res.status == 200:
                                response_text = data.decode("utf-8").strip()
                                if not response_text.startswith('{') and not response_text.startswith('['):
                                    return {'success': False, 'error': 'Servicio de conversión no disponible'}
                                response_json = json.loads(response_text)
                                status = response_json.get('status', 'unknown')

                                if status == 'ok':
                                    return {
                                        'success': True,
                                        'link': response_json.get('link'),
                                        'title': response_json.get('title'),
                                        'duration': response_json.get('duration'),
                                        'filesize': response_json.get('filesize', 0)
                                    }
                                elif status == 'processing':
                                    wait_time = min(10.0, 1.0 * (1.5 ** attempt))
                                    time.sleep(wait_time)
                                    continue
                                elif status == 'fail':
                                    error_msg = response_json.get('msg', 'Error desconocido')
                                    if 'Long audio' in error_msg or 'duration' in error_msg.lower():
                                        error_msg = "Audio muy largo (>2h). Intenta con una canción más corta."
                                    return {'success': False, 'error': error_msg}
                                else:
                                    return {'success': False, 'error': f'Estado desconocido: {status}'}
                            else:
                                if res.status in (429, 403):
                                    # Cuota diaria de ESTA key agotada — probar la siguiente
                                    # key de RAPIDAPI_KEYS (rotación) antes de rendirse.
                                    logger.warning(f"⚠️ Key #{key_index + 1} agotada (HTTP {res.status}), probando siguiente")
                                    quota_errors.append(f'key #{key_index + 1}: HTTP {res.status}')
                                    break
                                return {'success': False, 'error': f'HTTP {res.status}'}
                        except json.JSONDecodeError:
                            if attempt == max_retries - 1:
                                return {'success': False, 'error': 'Error al parsear respuesta JSON'}
                            time.sleep(1)
                        except Exception as e:
                            if attempt == max_retries - 1:
                                return {'success': False, 'error': 'Error de conversión'}
                            time.sleep(1)
                    else:
                        return {'success': False, 'error': f'Máximo de reintentos alcanzado ({max_retries} intentos)'}
                finally:
                    try:
                        conn.close()
                    except Exception:
                        pass

            logger.warning(f"⚠️ Todas las keys de RapidAPI agotadas ({len(RAPIDAPI_KEYS)}), probando 3ra capa local")
            fallback_result = self._convert_via_local_fallback(video_id)
            if fallback_result is not None:
                return fallback_result

            return {'success': False, 'error': 'Servicio de conversión no disponible temporalmente'}
        except Exception as e:
            logger.error(f"❌ Error inesperado en convert_to_mp3: {e}")
            return {'success': False, 'error': 'Error de conversión'}

    def _convert_via_local_fallback(self, video_id):
        """3ra capa: yt-dlp corriendo en una máquina residencial (no bloqueada
        por YouTube a diferencia del datacenter de Railway), expuesto vía
        túnel Cloudflare propio con auth por token. Devuelve None si no está
        configurado o no responde, para que el llamador use el mensaje de
        error estándar de cuota agotada."""
        if not YTFALLBACK_URL or not YTFALLBACK_TOKEN:
            return None
        try:
            resp = requests.get(
                f"{YTFALLBACK_URL.rstrip('/')}/convert/{video_id}",
                headers={'X-Fallback-Token': YTFALLBACK_TOKEN},
                timeout=35
            )
            data = resp.json()
            if data.get('success'):
                logger.info("✅ Conversión resuelta por la 3ra capa local")
                # No devolvemos el link de googlevideo directo: el datacenter de
                # Railway recibe 403 al leerlo (bloqueo por IP). En su lugar
                # apuntamos al /stream/<id> del ytfallback, que proxea el audio
                # desde la IP residencial local donde YouTube no bloquea.
                data['link'] = f"{YTFALLBACK_URL.rstrip('/')}/stream/{video_id}"
            else:
                logger.warning(f"⚠️ 3ra capa local respondió sin éxito: {data.get('error')}")
            return data
        except Exception as e:
            logger.warning(f"⚠️ 3ra capa local no disponible: {e}")
            return None

    def stream_via_rapidapi(self, mp3_url):
        """Streaming directo desde URL de RapidAPI.

        Se reenvía el header Range del cliente para permitir seek/resume en
        streams largos, y se omite el read-timeout para que un stream que se
        esticle (throttling de YouTube/CDN) no se trunque silenciosamente: el
        generador simplemente deja de recibir datos hasta que el origen vuelve
        a enviarlos, en lugar de abortar a los 10s.
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'audio/mpeg,audio/*,*/*',
                'Accept-Encoding': 'identity',
            }
            rng = request.headers.get('Range')
            if rng:
                headers['Range'] = rng

            response = requests.get(mp3_url, headers=headers, stream=True, timeout=(10, None))
            if response.status_code not in (200, 206):
                logger.warning(f"⚠️ RapidAPI stream status {response.status_code} para {mp3_url}")
                return None

            out_headers = {
                'Cache-Control': 'no-cache',
                'Access-Control-Allow-Origin': '*',
                'Accept-Ranges': response.headers.get('Accept-Ranges', 'bytes'),
            }
            # Safari/iOS valida que el MIME coincida con el contenedor real.
            # Los fallbacks suelen entregar M4A con Content-Type video/mp4; marcarlo
            # como audio/mpeg hace que Safari legacy descarte el stream sin reproducir.
            ctype = response.headers.get('Content-Type', 'audio/mpeg').split(';', 1)[0].strip().lower()
            if ctype in ('video/mp4', 'application/mp4', 'audio/x-m4a'):
                ctype = 'audio/mp4'
            elif ctype in ('video/webm', 'application/webm'):
                ctype = 'audio/webm'
            elif not ctype.startswith('audio/'):
                ctype = 'application/octet-stream'
            out_headers['Content-Type'] = ctype
            if response.status_code == 206 and response.headers.get('Content-Range'):
                out_headers['Content-Range'] = response.headers['Content-Range']
            if response.headers.get('Content-Length'):
                out_headers['Content-Length'] = response.headers['Content-Length']
            # No se reenvía Content-Disposition: attachment (rompería la reproducción inline en <audio>).

            return Response(
                response.raw,
                status=response.status_code,
                headers=out_headers,
                direct_passthrough=True,
            )
        except Exception as e:
            logger.error(f"❌ Error en stream rapidapi: {str(e)}")
            return None

    def stream_via_ytdlp(self, video_id):
        """Stream usando yt-dlp (sin cookies de navegador)"""
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            cmd = [
                'yt-dlp',
                '-f', 'bestaudio[ext=m4a]/bestaudio',
                '--get-url', '--no-warnings', '--no-update',
                '--no-cookies',
                '--extractor-args', 'youtube:player_client=web_embedded,tv,android',
                url
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                audio_url = result.stdout.strip().split('\n')[-1]
                if audio_url and audio_url.startswith('http'):
                    logger.info(f"✅ yt-dlp URL obtenida para {video_id}")
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Accept': 'audio/mpeg,audio/mp4,audio/*,*/*',
                        'Accept-Encoding': 'identity',
                        'Referer': 'https://www.youtube.com/',
                        'Origin': 'https://www.youtube.com',
                    }
                    client_range = request.headers.get('Range')
                    if client_range:
                        headers['Range'] = client_range
                    response = requests.get(audio_url, headers=headers, stream=True, timeout=(10, None))
                    if response.status_code in [200, 206]:
                        upstream_type = response.headers.get('Content-Type', 'audio/mp4').split(';', 1)[0].strip().lower()
                        if upstream_type in ('video/mp4', 'application/mp4', 'audio/x-m4a'):
                            upstream_type = 'audio/mp4'
                        elif upstream_type in ('video/webm', 'application/webm'):
                            upstream_type = 'audio/webm'
                        elif not upstream_type.startswith('audio/'):
                            upstream_type = 'application/octet-stream'
                        out_headers = {
                            'Content-Type': upstream_type,
                            'Accept-Ranges': response.headers.get('Accept-Ranges', 'bytes'),
                            'Cache-Control': 'no-cache',
                            'Access-Control-Allow-Origin': '*',
                        }
                        if response.status_code == 206 and response.headers.get('Content-Range'):
                            out_headers['Content-Range'] = response.headers['Content-Range']
                        if response.headers.get('Content-Length'):
                            out_headers['Content-Length'] = response.headers['Content-Length']
                        return Response(
                            response.raw,
                            status=response.status_code,
                            headers=out_headers,
                            direct_passthrough=True,
                        )
            logger.warning(f"⚠️ yt-dlp falló para {video_id}, usando fallback RapidAPI")
            return None
        except subprocess.TimeoutExpired:
            logger.warning(f"⏱️ yt-dlp timeout para {video_id}")
            return None
        except Exception as e:
            logger.error(f"❌ yt-dlp error: {str(e)}")
            return None


music_server = AllMusicServer()


# ── RUTAS API ──────────────────────────────────────────────────────────────────

@app.route('/search')
@limiter.limit("30 per minute")
def search():
    query = request.args.get('q', '').strip()
    try:
        limit = int(request.args.get('limit', 20))
        offset = int(request.args.get('offset', 0))
    except ValueError:
        return jsonify({'error': 'Invalid limit or offset parameter'}), 400
    if limit < 1 or limit > 50:
        limit = 20
    if offset < 0:
        offset = 0
    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400
    try:
        max_results = min(offset + limit, 50)
        cache_key = f'{query}|{max_results}'
        all_results = music_server._search_cache_get(cache_key)
        if all_results is None:
            all_results = music_server.search_youtube(query, max_results=max_results)
            music_server._search_cache_set(cache_key, all_results)
        total = len(all_results) if len(all_results) < 50 else 100
        paginated_results = all_results[offset:offset + limit]
        return jsonify({
            'success': True,
            'results': paginated_results,
            'count': len(paginated_results),
            'total': total,
            'limit': limit,
            'offset': offset
        })
    except Exception as e:
        logger.error(f"❌ Error en /search: {str(e)}")
        return jsonify({'error': 'Error interno'}), 500


@app.route('/stream/<video_id>')
@limiter.limit("60 per minute")
def stream(video_id):
    try:
        if not video_id or len(video_id) != 11:
            return jsonify({'error': 'ID inválido'}), 400
        if video_id.startswith('UC'):
            return jsonify({'error': 'ID de canal'}), 400

        # El player legacy necesita primer byte rápido. En Railway, yt-dlp suele
        # consumir 15-30 s antes de fallar; ?fast=1 salta esa penalización y usa
        # directamente el proveedor estable/caché.
        fast_mode = request.args.get('fast') == '1'

        # Si ya existe un enlace resuelto, úsalo antes de volver a ejecutar yt-dlp.
        music_server._cache_prune()
        if video_id in music_server.cache:
            cached_url = music_server.cache[video_id].get('link')
            if cached_url:
                cached_response = music_server.stream_via_rapidapi(cached_url)
                if cached_response:
                    return cached_response
                music_server.cache_pop(video_id)

        # PRIMARIO para clientes modernos: yt-dlp (YouTube directo, sin cookies).
        if not fast_mode:
            ytdlp_response = music_server.stream_via_ytdlp(video_id)
            if ytdlp_response:
                return ytdlp_response
            logger.warning(f"⚠️ yt-dlp falló para {video_id}, fallback RapidAPI")
        else:
            logger.info(f"⚡ fast stream para {video_id}: omitiendo yt-dlp")

        # FALLBACK / FAST: RapidAPI + proxy residencial
        music_server._cache_prune()
        if video_id not in music_server.cache:
            result = music_server.convert_to_mp3(video_id)
            if result.get('success'):
                music_server.cache_set(video_id, result)
            else:
                # Si RapidAPI falló, intentar 3ra capa local directamente
                fallback = music_server._convert_via_local_fallback(video_id)
                if fallback and fallback.get('success') and fallback.get('link'):
                    music_server.cache_set(video_id, fallback)
                else:
                    return jsonify({'success': False, 'error': result.get("error", "Error desconocido")}), 502

        mp3_url = music_server.cache[video_id].get('link')
        if not mp3_url:
            return jsonify({'success': False, 'error': 'No hay URL de audio'}), 502

        stream_resp = music_server.stream_via_rapidapi(mp3_url)
        if stream_resp:
            return stream_resp

        # El link cacheado puede haber expirado (las URLs de RapidAPI caducan).
        # Renovarlo y reintentar una vez antes de rendirse.
        logger.warning(f"⚠️ Link caducado/expirado para {video_id}; renovando vía RapidAPI")
        music_server.cache_pop(video_id)
        result = music_server.convert_to_mp3(video_id)
        if result.get('success') and result.get('link'):
            music_server.cache_set(video_id, result)
            stream_resp = music_server.stream_via_rapidapi(result['link'])
            if stream_resp:
                return stream_resp

        # Último recurso: 3ra capa local
        fallback = music_server._convert_via_local_fallback(video_id)
        if fallback and fallback.get('success') and fallback.get('link'):
            music_server.cache_set(video_id, fallback)
            stream_resp = music_server.stream_via_rapidapi(fallback['link'])
            if stream_resp:
                return stream_resp

        return jsonify({'success': False, 'error': 'No se pudo iniciar el stream. Inténtalo de nuevo.'}), 502
    except Exception as e:
        logger.error(f"❌ Error en /stream: {str(e)}")
        return jsonify({'error': 'Error interno'}), 500


@app.route('/download/<video_id>.mp3')
@limiter.limit("10 per minute")
def download_mp3(video_id):
    try:
        if not video_id or len(video_id) != 11 or video_id.startswith('UC'):
            return jsonify({'error': 'ID inválido'}), 400

        file_name = f"{video_id}.mp3"
        file_path = os.path.join(DOWNLOADS_DIR, file_name)

        if os.path.exists(file_path):
            return send_from_directory(DOWNLOADS_DIR, file_name, mimetype='audio/mpeg', as_attachment=True, download_name=file_name, conditional=False)

        result = music_server.convert_to_mp3(video_id)
        if not result or not result.get('success'):
            err = (result or {}).get('error', 'Conversión fallida')
            return jsonify({'error': 'No se pudo obtener el MP3'}), 502

        mp3_url = result.get('link')
        if not mp3_url:
            return jsonify({'error': 'No se pudo obtener el enlace de MP3'}), 502

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'audio/mpeg,audio/*,*/*',
            'Accept-Encoding': 'identity'
        }
        try:
            with requests.get(mp3_url, headers=headers, stream=True, timeout=60) as r:
                if r.status_code != 200:
                    return jsonify({'error': f'HTTP {r.status_code} al descargar MP3'}), 502
                tmp_path = file_path + '.part'
                with open(tmp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp_path, file_path)
        except Exception as e:
            try:
                if os.path.exists(file_path + '.part'):
                    os.remove(file_path + '.part')
            except Exception:
                pass
            return jsonify({'error': 'Error al descargar'}), 500

        return send_from_directory(DOWNLOADS_DIR, file_name, mimetype='audio/mpeg', as_attachment=True, download_name=file_name, conditional=False)
    except Exception as e:
        logger.error(f"❌ Error en /download: {str(e)}")
        return jsonify({'error': 'Error interno'}), 500


@app.route('/convert/<video_id>')
@limiter.limit("20 per minute")
def convert(video_id):
    try:
        if not video_id or len(video_id) != 11:
            return jsonify({'error': 'ID inválido'}), 400
        if video_id.startswith('UC'):
            return jsonify({'error': 'ID de canal'}), 400
        music_server._cache_prune()
        if video_id in music_server.cache:
            return jsonify(music_server.cache[video_id])
        result = music_server.convert_to_mp3(video_id)
        if result.get('success'):
            music_server.cache_set(video_id, result)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': 'Error interno'}), 500


@app.route('/play')
@limiter.limit("20 per minute")
def play():
    query = request.args.get('q', '').strip()
    video_id = request.args.get('id', '').strip()
    try:
        if video_id:
            return redirect(f'/stream/{video_id}')
        elif query:
            results = music_server.search_youtube(query, max_results=1)
            if results:
                return redirect(f'/stream/{results[0]["id"]}')
        return jsonify({'error': 'Se requiere "q" (query) o "id" (video_id)'}), 400
    except Exception as e:
        return jsonify({'error': 'Error interno'}), 500


@app.route('/status')
def status():
    # Respuesta mínima: no exponer endpoints internos ni métricas de infraestructura
    return jsonify({'status': 'running'})


# ── CANCIONES DINÁMICAS (SEO) ─────────────────────────────────────────────────
# Página por canción "/allmusic/cancion/<artista>/<titulo>": busca en YouTube,
# muestra la letra (Lyrics.ovh) y reproduce con el link directo del CDN.
# Debe definirse ANTES del catch-all /<path:filename>.

LYRICS_CACHE_DIR = os.path.join(DATA_DIR, 'lyrics_cache')
os.makedirs(LYRICS_CACHE_DIR, exist_ok=True)
SONG_PAGE_TTL = 7 * 24 * 3600  # 7 días para páginas populares


def _lyrics_from_cache(artist, title):
    key = re.sub(r'[^a-z0-9]+', '_', (artist + '-' + title).lower()).strip('_')
    path = os.path.join(LYRICS_CACHE_DIR, key + '.json')
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            age = time.time() - data.get('ts', 0)
            if age < SONG_PAGE_TTL:
                return data.get('lyrics')
        except Exception:
            pass
    return None


def _lyrics_to_cache(artist, title, lyrics):
    key = re.sub(r'[^a-z0-9]+', '_', (artist + '-' + title).lower()).strip('_')
    path = os.path.join(LYRICS_CACHE_DIR, key + '.json')
    try:
        with open(path, 'w') as f:
            json.dump({'artist': artist, 'title': title, 'lyrics': lyrics, 'ts': time.time()}, f)
    except Exception as e:
        logger.warning(f"⚠️ No se pudo cachear letra: {e}")


def _fetch_lyrics(artist, title):
    cached = _lyrics_from_cache(artist, title)
    if cached:
        return cached
    try:
        url = f"https://api.lyrics.ovh/v1/{quote(artist)}/{quote(title)}"
        r = requests.get(url, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
        if r.status_code == 200:
            lyrics = r.json().get('lyrics', '')
            if lyrics:
                _lyrics_to_cache(artist, title, lyrics)
                return lyrics
    except Exception as e:
        logger.warning(f"⚠️ Error Lyrics.ovh {artist} - {title}: {e}")
    return None


def _song_meta_from_slug(artist_slug, title_slug):
    """Convierte slugs url a nombres legibles."""
    artist = re.sub(r'[-_]+', ' ', artist_slug).strip().title()
    title = re.sub(r'[-_]+', ' ', title_slug).strip().title()
    return artist, title


def _search_videos(artist, title):
    """Busca la canción; prioriza videos que no sean 'letra/lyrics' como principal,
    pero devuelve todos los resultados para que el player pueda probar varios."""
    query = f"{artist} {title}"
    try:
        results = music_server.search_youtube(query, max_results=10)
    except Exception as e:
        logger.warning(f"⚠️ Búsqueda falló: {e}")
        return []
    if not results:
        return []
    # Ordenar: videos que no son "letra/lyrics/cover" primero (mejor calidad de audio).
    bad = re.compile(r'\(?(letra|lyrics?|official audio|audio oficial|cover|playlist|album completo)\)?', re.I)
    results.sort(key=lambda r: 1 if bad.search(r.get('title', '')) else 0)
    return results


def _song_page_html(artist, title, video, lyrics, video_ids):
    canon = f"https://edgemarketing.art/allmusic/cancion/{quote(artist.lower().replace(' ', '-'))}/{quote(title.lower().replace(' ', '-'))}"
    page_title = f"{artist} - {title} (Letra) | AllMusic"
    desc = f"Escucha gratis {artist} - {title} en AllMusic. Letra completa y reproductor sin registro. 🎧"
    thumb = video.get('thumbnail', '')
    video_id = video['id']
    uploader = video.get('uploader', 'YouTube')

    # Letra en <pre> escapada (o aviso si no hay).
    if lyrics:
        import html as _html
        lyrics_block = f"<pre id=\"lyrics\">{_html.escape(lyrics)}</pre>"
        lyrics_meta = f"{len(lyrics.split())} palabras de letra"
    else:
        lyrics_block = '<p class="no-lyrics">No encontramos la letra completa para esta canción. Escúchala gratis en el reproductor de abajo. 🎵</p>'
        lyrics_meta = "Letra no disponible, pero sí la canción"

    related = []
    try:
        related = music_server.search_youtube(f"{artist} música", max_results=5)
    except Exception:
        related = []
    related_links = ''
    for r in related[:5]:
        rel_slug = (quote(r['title'].replace(' ', '-')[:60].lower())) if r.get('title') else ''
        related_links += f'<li><a href="/allmusic/cancion/{quote(artist.lower().replace(" ", "-"))}/{rel_slug}">🎵 {_html.escape(r["title"])}</a></li>'
    if not related_links:
        related_links = '<li>No hay sugerencias.</li>'

    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page_title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canon}">
<meta property="og:type" content="music.song">
<meta property="og:title" content="{artist} - {title}">
<meta property="og:description" content="{desc}">
<meta property="og:image" content="{thumb}">
<meta property="og:url" content="{canon}">
<meta name="robots" content="index,follow">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "MusicRecording",
  "name": "{title}",
  "byArtist": {{"@type": "MusicGroup", "name": "{artist}"}},
  "inAlbum": {{"@type": "MusicAlbum", "name": "{artist} - {title}"}},
  "url": "{canon}",
  "audio": {{"@type": "AudioObject", "contentUrl": "{canon}"}},
  "isFamilyFriendly": true
}}
</script>
<style>
  *{{margin:0;box-sizing:border-box}}
  body{{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#0f1117;color:#e6e6e6;min-height:100vh;line-height:1.5}}
  .wrap{{max-width:760px;margin:0 auto;padding:24px 16px 80px}}
  header{{display:flex;align-items:center;gap:12px;margin-bottom:20px}}
  header .logo{{font-size:20px;font-weight:800;color:#fff;text-decoration:none}}
  header .logo span{{color:#ff4d6d}}
  h1{{font-size:26px;margin-bottom:6px;color:#fff}}
  .sub{{color:#9aa0aa;font-size:14px;margin-bottom:20px}}
  .card{{background:#1a1e27;border-radius:14px;padding:20px;margin-bottom:20px}}
  .player{{display:flex;flex-direction:column;gap:14px}}
  .btn{{background:#ff4d6d;color:#fff;border:0;padding:14px 22px;border-radius:30px;font-size:16px;font-weight:700;cursor:pointer}}
  .btn:disabled{{opacity:.5;cursor:wait}}
  .meta{{color:#b8bcc4;font-size:13px}}
  #lyrics{{white-space:pre-wrap;font-family:inherit;font-size:15px;color:#e6e6e6;line-height:1.7;max-height:600px;overflow:auto}}
  .no-lyrics{{color:#9aa0aa}}
  .rel{{list-style:none;padding:0}}
  .rel a{{color:#8ecbff;text-decoration:none;display:block;padding:8px 0;border-bottom:1px solid #252a35}}
  footer{{margin-top:30px;color:#777;font-size:12px;text-align:center}}
  footer a{{color:#8ecbff;text-decoration:none}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <a class="logo" href="/allmusic/">🎧 All<span>Music</span></a>
  </header>
  <h1>{artist} - {title}</h1>
  <div class="sub">🎶 {lyrics_meta} · Escúchala gratis, sin registro · <a href="/allmusic/dmca.html" style="color:#8ecbff">DMCA</a></div>

  <div class="card">
    <div class="player">
      <button id="playBtn" class="btn" onclick="playSong()">▶ Reproducir gratis</button>
      <div class="meta" id="status">Listo para reproducir · {uploader}</div>
      <div id="playerErr" style="color:#ff6b6b;font-size:13px"></div>
    </div>
  </div>

  <div class="card">
    <h2 style="font-size:18px;margin-bottom:12px;color:#fff">📜 Letra</h2>
    {lyrics_block}
  </div>

  <div class="card">
    <h2 style="font-size:18px;margin-bottom:12px;color:#fff">🎧 Más de {artist}</h2>
    <ul class="rel">{related_links}</ul>
  </div>

  <footer>
    <p><a href="/allmusic/">Inicio</a> · <a href="/allmusic/terminos.html">Términos</a> · <a href="/allmusic/privacidad.html">Privacidad</a> · <a href="/allmusic/dmca.html">DMCA</a></p>
    <p>AllMusic © {datetime.date.today().year} · Reproduce música de YouTube sin registro</p>
  </footer>
</div>

<audio id="audio"></audio>
<script>
  const VIDEO_IDS={json.dumps(video_ids)};
  async function playSong(){{
    const btn=document.getElementById('playBtn');
    const status=document.getElementById('status');
    const err=document.getElementById('playerErr');
    btn.disabled=true;btn.textContent='⏳ Cargando...';err.textContent='';
    const a=document.getElementById('audio');
    let played=false;
    for(const id of VIDEO_IDS){{
      try{{
        const c=await (await fetch('/allmusic/convert/'+id)).json();
        if(c&&c.success&&c.link){{
          a.src=c.link;a.play();
          status.textContent='▶ Reproduciendo · {uploader}';
          played=true;break;
        }}
      }}catch(e){{/* prueba siguiente */}}
    }}
    if(!played){{
      err.textContent='⚠️ No pudimos obtener el audio. Inténtalo de nuevo en unos segundos.';
      status.textContent='Error al reproducir';
    }}
    btn.disabled=false;btn.textContent='▶ Reproducir gratis';
  }}
</script>
</body>
</html>'''


@app.route('/cancion/<artist_slug>/<title_slug>')
def cancion(artist_slug, title_slug):
    artist, title = _song_meta_from_slug(artist_slug, title_slug)
    if not artist or not title:
        return redirect('/allmusic/')
    videos = _search_videos(artist, title)
    if not videos:
        return redirect('/allmusic/')
    video = videos[0]
    video_ids = [v['id'] for v in videos]
    lyrics = _fetch_lyrics(artist, title)
    html = _song_page_html(artist, title, video, lyrics, video_ids)
    return Response(html, mimetype='text/html')


# ── FRONTEND ───────────────────────────────────────────────────────────────────

def is_legacy_device(ua):
    """iPads/iPhones viejos (iOS 9-13) reciben el frontend legacy.
    El modern_index usa JS/CSS moderno que rompe en Safari antiguos."""
    if not ua:
        return False
    m = re.search(r'OS (\d+)[_.]', ua)
    if not m:
        return False
    try:
        version = int(m.group(1))
    except ValueError:
        return False
    return 9 <= version <= 13 and re.search(r'iPad|iPod|iPhone', ua)


@app.route('/')
def index():
    ua = request.headers.get('User-Agent', '')
    legacy_path = os.path.join(FRONTEND_DIR, 'index-legacy.html')
    if is_legacy_device(ua) and os.path.exists(legacy_path):
        return send_from_directory(FRONTEND_DIR, 'index-legacy.html')
    idx_path = os.path.join(FRONTEND_DIR, 'index.html')
    modern_path = os.path.join(FRONTEND_DIR, 'modern_index.html')
    if os.path.exists(modern_path):
        return send_from_directory(FRONTEND_DIR, 'modern_index.html')
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/<path:filename>')
def frontend_files(filename):
    file_path = os.path.join(FRONTEND_DIR, filename)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        resp = send_from_directory(FRONTEND_DIR, filename)
        # La parrilla de la radio se refresca con cada deploy/cambio de assets:
        # nunca cachear los assets de radio para que la UI C24 se vea al instante.
        if '/assets/radio/' in '/' + filename or filename.startswith('assets/radio/'):
            resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            resp.headers['Pragma'] = 'no-cache'
            resp.headers['Expires'] = '0'
        return resp
    # Redirect clean legal/static paths (no extension) to their .html file.
    # The path may arrive prefixed with 'allmusic/' (reverse proxy), so strip it.
    rel = filename
    if rel.startswith('allmusic/'):
        rel = rel[len('allmusic/'):]
    # Sirve el archivo cuando llega con prefijo 'allmusic/' (p. ej. <base href="/allmusic/">)
    rel_path = os.path.join(FRONTEND_DIR, rel)
    if os.path.exists(rel_path) and os.path.isfile(rel_path):
        return send_from_directory(FRONTEND_DIR, rel)
    if '.' not in os.path.basename(rel):
        html_path = os.path.join(FRONTEND_DIR, rel + '.html')
        if os.path.exists(html_path) and os.path.isfile(html_path):
            return redirect('/allmusic/' + rel + '.html')
    # SPA fallback
    idx = os.path.join(FRONTEND_DIR, 'index.html')
    if os.path.exists(idx):
        return send_from_directory(FRONTEND_DIR, 'index.html')
    return jsonify({'error': 'Not found'}), 404


# ── USERS ──────────────────────────────────────────────────────────────────────
USERS_FILE = os.path.join(DATA_DIR, 'users.json')

_JSON_FILE_CACHE = {}  # path -> (mtime, data): evita releer disco en cada request


def _load_json_cached(path):
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return []
    cached = _JSON_FILE_CACHE.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        _JSON_FILE_CACHE[path] = (mtime, data)
        return data
    except (OSError, ValueError):
        return []


def _load_users():
    data = _load_json_cached(USERS_FILE)
    return data if isinstance(data, list) else []

def _save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)
    _JSON_FILE_CACHE.pop(USERS_FILE, None)

@app.route('/users/register', methods=['POST'])
@limiter.limit("10 per minute")
def user_register():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get('email') or '').strip().lower()[:120]
    name  = (data.get('name') or '').strip()[:50]
    if not email or not re.match(r'^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$', email):
        return jsonify({'error': 'Correo inválido'}), 400
    if not name:
        return jsonify({'error': 'Nombre requerido'}), 400
    users = _load_users()
    existing = next((u for u in users if u['email'] == email), None)
    if existing:
        return jsonify({'user': existing, 'already_existed': True})
    user = {
        'id': max((u['id'] for u in users), default=0) + 1,
        'name': name,
        'email': email,
        'registered_at': datetime.datetime.utcnow().isoformat() + 'Z',
    }
    users.append(user)
    _save_users(users)
    return jsonify({'user': user, 'already_existed': False}), 201

@app.route('/users/lookup', methods=['GET'])
@limiter.limit("20 per minute")
def user_lookup():
    email = (request.args.get('email') or '').strip().lower()
    if not email:
        return jsonify({'error': 'Email requerido'}), 400
    users = _load_users()
    user = next((u for u in users if u['email'] == email), None)
    if not user:
        return jsonify({'found': False}), 404
    return jsonify({'found': True, 'user': user})

# ── Endpoints admin retirados (requieren moderación del lado del servidor) ────
@app.route('/users', methods=['GET', 'POST', 'PUT', 'DELETE'])
def users_removed():
    return jsonify({'error': 'No disponible'}), 404

@app.route('/radio/blacklist', methods=['GET', 'POST', 'DELETE'])
@app.route('/radio/admin/blacklist', methods=['GET', 'POST', 'DELETE'])
def blacklist_removed():
    return jsonify({'error': 'No disponible'}), 404

@app.route('/admin/login', methods=['POST'])
def admin_login_removed():
    return jsonify({'error': 'No disponible'}), 404


# Nota: no existe endpoint público para listar usuarios. La moderación se hace
# directamente en el servidor (sin vista pública), según requerimiento del proyecto.

# ── PLAYLISTS ──────────────────────────────────────────────────────────────────
PLAYLISTS_FILE = os.path.join(DATA_DIR, 'playlists.json')

def _load_playlists():
    data = _load_json_cached(PLAYLISTS_FILE)
    return data if isinstance(data, list) else []

def _save_playlists(pls):
    with open(PLAYLISTS_FILE, 'w') as f:
        json.dump(pls, f, indent=2)
    _JSON_FILE_CACHE.pop(PLAYLISTS_FILE, None)

@app.route('/playlists', methods=['GET'])
def get_playlists():
    return jsonify(_load_playlists())

@app.route('/playlists', methods=['POST'])
@limiter.limit("20 per minute")
def create_playlist():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Nombre requerido'}), 400
    pls = _load_playlists()
    pl = {
        'id': max((p['id'] for p in pls), default=0) + 1,
        'name': name,
        'tracks': [],
        'created_by': (data.get('created_by') or 'Anónimo').strip()[:40],
        'created_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'updated_at': datetime.datetime.utcnow().isoformat() + 'Z',
    }
    pls.append(pl)
    _save_playlists(pls)
    return jsonify(pl)

@app.route('/playlists/<int:pl_id>', methods=['DELETE'])
def delete_playlist(pl_id):
    pls = [p for p in _load_playlists() if p['id'] != pl_id]
    _save_playlists(pls)
    return jsonify({'ok': True})

@app.route('/playlists/<int:pl_id>/tracks', methods=['POST'])
def add_track(pl_id):
    pls = _load_playlists()
    pl = next((p for p in pls if p['id'] == pl_id), None)
    if not pl:
        return jsonify({'error': 'Playlist no encontrada'}), 404
    track = request.get_json(force=True, silent=True) or {}
    pl['tracks'].append(track)
    pl['updated_at'] = datetime.datetime.utcnow().isoformat() + 'Z'
    _save_playlists(pls)
    return jsonify(pl)

@app.route('/playlists/<int:pl_id>/tracks/<int:idx>', methods=['DELETE'])
def remove_track(pl_id, idx):
    pls = _load_playlists()
    pl = next((p for p in pls if p['id'] == pl_id), None)
    if not pl:
        return jsonify({'error': 'Playlist no encontrada'}), 404
    if 0 <= idx < len(pl['tracks']):
        pl['tracks'].pop(idx)
    _save_playlists(pls)
    return jsonify(pl)


# ── ARTISTS ────────────────────────────────────────────────────────────────────
ARTISTS_FILE = os.path.join(DATA_DIR, 'artists.json')

def _load_artists():
    data = _load_json_cached(ARTISTS_FILE)
    return data if isinstance(data, list) else []

def _save_artists(arts):
    with open(ARTISTS_FILE, 'w') as f:
        json.dump(arts, f, indent=2)
    _JSON_FILE_CACHE.pop(ARTISTS_FILE, None)

@app.route('/artists', methods=['GET'])
def get_artists():
    return jsonify(_load_artists())

@app.route('/artists/<int:artist_id>/songs', methods=['GET'])
def get_artist_songs(artist_id):
    arts = _load_artists()
    a = next((x for x in arts if x['id'] == artist_id), None)
    if not a:
        return jsonify({'error': 'Artista no encontrado'}), 404
    return jsonify(a.get('songs', []))

@app.route('/artists/request_invite', methods=['POST'])
def artist_request_invite():
    data = request.get_json(force=True, silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Nombre requerido'}), 400
    arts = _load_artists()
    nid = max((a['id'] for a in arts), default=0) + 1
    artist = {'id': nid, 'name': name, 'email': data.get('email', ''), 'genre': data.get('genre', ''), 'description': data.get('description', ''), 'songs': [], 'status': 'pending'}
    arts.append(artist)
    _save_artists(arts)
    return jsonify({'ok': True, 'artist': artist})


# ── ARTIST ACCOUNTS (auth + file upload) ──────────────────────────────────────
ARTIST_ACCOUNTS_FILE = os.path.join(DATA_DIR, 'artist_accounts.json')
ARTIST_SESSIONS = {}

ALLOWED_AUDIO_EXTS = {'.mp3', '.wav', '.flac', '.ogg', '.aac', '.m4a', '.wma'}
ALLOWED_FILE_EXTS = ALLOWED_AUDIO_EXTS | {'.zip', '.rar', '.pdf'}
MAX_ARTIST_FILE_SIZE = 200 * 1024 * 1024

# Firmas de bytes iniciales (magic numbers) de los formatos de audio permitidos.
_AUDIO_MAGIC = {
    '.mp3': (b'ID3', b'\xff\xfb', b'\xff\xf3', b'\xff\xf2'),
    '.wav': (b'RIFF',),
    '.flac': (b'fLaC',),
    '.ogg': (b'OggS',),
    '.aac': (b'\xff\xf1', b'\xff\xf9'),
    '.m4a': (b'ftyp',),
    '.wma': (b'\x30\x26\xb2\x75',),
}


def _is_valid_audio_upload(save_path, ext):
    """Sanitizador de subida: la extensión debe estar en la lista blanca y los
    bytes iniciales deben corresponder a un contenedor de audio real (no un
    documento/ejecutable renombrado)."""
    ext = ext.lower()
    if ext not in _AUDIO_MAGIC:
        return False
    try:
        with open(save_path, 'rb') as fh:
            head = fh.read(16)
    except OSError:
        return False
    if ext == '.m4a':
        return len(head) >= 8 and head[4:8] == b'ftyp'
    return any(head.startswith(sig) for sig in _AUDIO_MAGIC[ext])


def _virustotal_check(file_path):
    """Segunda capa: consulta VirusTotal por el hash SHA-256 del archivo.
    Devuelve (ok, detalle). Si VIRUSTOTAL_API_KEY no está y VIRUSTOTAL_STRICT es
    true, el archivo se rechaza (fail-closed)."""
    import hashlib as _h
    try:
        sha = _h.sha256()
        with open(file_path, 'rb') as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b''):
                sha.update(chunk)
        digest = sha.hexdigest()
    except OSError as e:
        return False, f'no se pudo leer el archivo: {e}'

    if not VIRUSTOTAL_API_KEY:
        if VIRUSTOTAL_STRICT:
            return False, 'VIRUSTOTAL_API_KEY no configurada: validación obligatoria'
        logger.warning('VIRUSTOTAL_API_KEY no configurada — capa 2 omitida (modo no estricto)')
        return True, 'omitido'

    try:
        resp = requests.get(
            f'https://www.virustotal.com/api/v3/files/{digest}',
            headers={'x-apikey': VIRUSTOTAL_API_KEY},
            timeout=20,
        )
        if resp.status_code == 404:
            # Archivo nuevo para VirusTotal: se sube para análisis y se rechaza
            # por defecto hasta que la comunidad lo valide.
            return False, 'archivo desconocido para VirusTotal; envíalo manualmente'
        if resp.status_code != 200:
            return (False, f'VirusTotal respondió HTTP {resp.status_code}') if VIRUSTOTAL_STRICT else (True, f'VT HTTP {resp.status_code}')
        stats = resp.json().get('data', {}).get('attributes', {}).get('last_analysis_stats', {})
        malicious = int(stats.get('malicious', 0) or 0)
        suspicious = int(stats.get('suspicious', 0) or 0)
        if malicious > 0 or suspicious > 0:
            return False, f'VirusTotal marcó {malicious} maliciosos / {suspicious} sospechosos'
        return True, 'limpio'
    except requests.RequestException as e:
        return (False, f'VirusTotal no disponible: {e}') if VIRUSTOTAL_STRICT else (True, 'VT no disponible')

def _load_artist_accounts():
    data = _load_json_cached(ARTIST_ACCOUNTS_FILE)
    return data if isinstance(data, list) else []

def _save_artist_accounts(accounts):
    with open(ARTIST_ACCOUNTS_FILE, 'w') as f:
        json.dump(accounts, f, indent=2)
    _JSON_FILE_CACHE.pop(ARTIST_ACCOUNTS_FILE, None)

def _slugify_artist(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text[:50]

def _hash_artist_pwd(salt, pwd):
    """Hash seguro con bcrypt. Para cuentas viejas (sha256+salt) se verifica
    con el esquema legacy y se re-hashea a bcrypt en el primer login exitoso."""
    try:
        import bcrypt
        return bcrypt.hashpw(pwd.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('ascii')
    except ImportError:
        # Fallback solo si bcrypt no está instalado: PBKDF2-HMAC-SHA256
        return 'pbkdf2$' + hashlib.pbkdf2_hmac('sha256', pwd.encode('utf-8'), salt.encode('utf-8'), 200_000).hex()


def _verify_artist_pwd(artist, pwd):
    """Verifica password con el esquema guardado; indica si hay que re-hashear."""
    stored = artist.get('pwd_hash', '')
    # bcrypt ($2b$...)
    if stored.startswith('$2'):
        try:
            import bcrypt
            return bcrypt.checkpw(pwd.encode('utf-8'), stored.encode('ascii')), False
        except ImportError:
            return False, False
    # pbkdf2
    if stored.startswith('pbkdf2$'):
        calc = 'pbkdf2$' + hashlib.pbkdf2_hmac('sha256', pwd.encode('utf-8'), artist.get('salt', '').encode('utf-8'), 200_000).hex()
        return hmac.compare_digest(calc, stored), True
    # legacy sha256+salt
    calc = hashlib.sha256((artist.get('salt', '') + pwd).encode('utf-8')).hexdigest()
    return hmac.compare_digest(calc, stored), True


def _create_artist_token(artist_id):
    """JWT firmado HS256, vida corta (30 min) + id único (jti) para revocación."""
    import jwt
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        'sub': artist_id,
        'iat': int(now.timestamp()),
        'exp': int((now + datetime.timedelta(minutes=30)).timestamp()),
        'jti': secrets.token_hex(8),
        'aud': 'allmusic-artist',
    }
    token = jwt.encode(payload, _JWT_SECRET, algorithm='HS256')
    ARTIST_SESSIONS[token] = {'artist_id': artist_id, 'expires': payload['exp']}
    return token


def _get_current_artist():
    auth = request.headers.get('Authorization', '')
    token = auth.replace('Bearer ', '').strip()
    if not token:
        return None
    try:
        import jwt
        claims = jwt.decode(token, _JWT_SECRET, algorithms=['HS256'], audience='allmusic-artist')
        artist_id = claims.get('sub')
    except Exception:
        # Compatibilidad con tokens opacos viejos (dict en memoria) mientras existan
        session = ARTIST_SESSIONS.get(token)
        if not session or time.time() > session['expires']:
            ARTIST_SESSIONS.pop(token, None)
            return None
        artist_id = session['artist_id']
    if not artist_id:
        return None
    accounts = _load_artist_accounts()
    return next((a for a in accounts if a['id'] == artist_id), None)

def _unique_artist_slug(base, accounts, exclude_id=None):
    slug = base
    i = 2
    taken = {a['slug'] for a in accounts if a.get('id') != exclude_id}
    while slug in taken:
        slug = f"{base}-{i}"
        i += 1
    return slug

def _artist_safe(artist):
    return {k: v for k, v in artist.items() if k not in ('pwd_hash', 'salt')}

@app.route('/artists/auth/register', methods=['POST'])
@limiter.limit("5 per minute")
def artist_auth_register():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get('email') or '').strip().lower()[:120]
    password = (data.get('password') or '').strip()
    artist_name = (data.get('artist_name') or data.get('name') or '').strip()[:80]
    genre = (data.get('genre') or '').strip()[:60]
    if not email or not re.match(r'^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$', email):
        return jsonify({'error': 'Email inválido'}), 400
    if len(password) < 8:
        return jsonify({'error': 'La contraseña debe tener al menos 8 caracteres'}), 400
    if not artist_name:
        return jsonify({'error': 'Nombre artístico requerido'}), 400
    accounts = _load_artist_accounts()
    if any(a['email'] == email for a in accounts):
        return jsonify({'error': 'Este email ya está registrado'}), 409
    salt = secrets.token_hex(16)
    pwd_hash = _hash_artist_pwd(salt, password)
    base_slug = _slugify_artist(artist_name)
    slug = _unique_artist_slug(base_slug, accounts)
    artist_id = f"art_{secrets.token_hex(8)}"
    os.makedirs(os.path.join(ARTIST_UPLOADS_DIR, artist_id), exist_ok=True)
    artist = {
        'id': artist_id, 'email': email, 'pwd_hash': pwd_hash, 'salt': salt,
        'artist_name': artist_name, 'slug': slug, 'bio': '', 'genre': genre,
        'header_image': '', 'avatar': '',
        'albums': [], 'files': [],
        'tracks': [], 'is_premium': False, 'premium_plan': 'free', 'earnings': 0.0,
        'social': {'instagram': '', 'spotify': '', 'youtube': ''},
        'created_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'status': 'active'
    }
    accounts.append(artist)
    _save_artist_accounts(accounts)
    token = _create_artist_token(artist_id)
    return jsonify({'ok': True, 'token': token, 'artist': _artist_safe(artist)}), 201

@app.route('/artists/auth/login', methods=['POST'])
@limiter.limit("5 per minute")
def artist_auth_login():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()
    if not email or not password:
        return jsonify({'error': 'Email y contraseña requeridos'}), 400
    accounts = _load_artist_accounts()
    artist = next((a for a in accounts if a['email'] == email), None)
    if not artist:
        return jsonify({'error': 'Email o contraseña incorrectos'}), 401
    ok, needs_rehash = _verify_artist_pwd(artist, password)
    if not ok:
        return jsonify({'error': 'Email o contraseña incorrectos'}), 401
    if needs_rehash:
        # Migración transparente de hash antiguo a bcrypt
        artist['pwd_hash'] = _hash_artist_pwd(artist.get('salt', ''), password)
        artist['salt'] = secrets.token_hex(16)
        idx = next((i for i, a in enumerate(accounts) if a['id'] == artist['id']), None)
        if idx is not None:
            accounts[idx] = artist
            _save_artist_accounts(accounts)
    token = _create_artist_token(artist['id'])
    return jsonify({'ok': True, 'token': token, 'artist': _artist_safe(artist)})

@app.route('/artists/profile', methods=['GET'])
def artist_get_profile():
    artist = _get_current_artist()
    if not artist:
        return jsonify({'error': 'No autorizado'}), 401
    return jsonify(_artist_safe(artist))

@app.route('/artists/profile', methods=['PUT'])
@limiter.limit("20 per minute")
def artist_update_profile():
    artist = _get_current_artist()
    if not artist:
        return jsonify({'error': 'No autorizado'}), 401
    data = request.get_json(force=True, silent=True) or {}
    accounts = _load_artist_accounts()
    idx = next((i for i, a in enumerate(accounts) if a['id'] == artist['id']), None)
    if idx is None:
        return jsonify({'error': 'Artista no encontrado'}), 404
    a = accounts[idx]
    if data.get('artist_name', '').strip():
        new_name = data['artist_name'].strip()[:80]
        new_slug = _unique_artist_slug(_slugify_artist(new_name), accounts, exclude_id=a['id'])
        a['artist_name'] = new_name
        a['slug'] = new_slug
    if 'bio' in data: a['bio'] = str(data['bio'])[:1000]
    if 'genre' in data: a['genre'] = str(data['genre'])[:60]
    if isinstance(data.get('social'), dict):
        for k in ('instagram', 'spotify', 'youtube'):
            if k in data['social']:
                a['social'][k] = str(data['social'][k])[:200]
    _save_artist_accounts(accounts)
    return jsonify({'ok': True, 'artist': _artist_safe(a)})

@app.route('/artists/profile/header', methods=['POST'])
@limiter.limit("10 per minute")
def artist_upload_header():
    artist = _get_current_artist()
    if not artist:
        return jsonify({'error': 'No autorizado'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'No se recibió archivo'}), 400
    f = request.files['file']
    ext = os.path.splitext(f.filename or '')[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
        return jsonify({'error': 'Solo JPG, PNG o WEBP'}), 400
    artist_dir = os.path.join(ARTIST_UPLOADS_DIR, artist['id'])
    os.makedirs(artist_dir, exist_ok=True)
    save_path = os.path.join(artist_dir, f'header{ext}')
    f.save(save_path)
    url = f'/artists/share/{artist["id"]}/header{ext}'
    accounts = _load_artist_accounts()
    idx = next((i for i, a in enumerate(accounts) if a['id'] == artist['id']), None)
    if idx is not None:
        accounts[idx]['header_image'] = url
        _save_artist_accounts(accounts)
    return jsonify({'ok': True, 'url': url})

@app.route('/artists/profile/avatar', methods=['POST'])
@limiter.limit("10 per minute")
def artist_upload_avatar():
    artist = _get_current_artist()
    if not artist:
        return jsonify({'error': 'No autorizado'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'No se recibió archivo'}), 400
    f = request.files['file']
    ext = os.path.splitext(f.filename or '')[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
        return jsonify({'error': 'Solo JPG, PNG o WEBP'}), 400
    artist_dir = os.path.join(ARTIST_UPLOADS_DIR, artist['id'])
    os.makedirs(artist_dir, exist_ok=True)
    f.save(os.path.join(artist_dir, f'avatar{ext}'))
    url = f'/artists/share/{artist["id"]}/avatar{ext}'
    accounts = _load_artist_accounts()
    idx = next((i for i, a in enumerate(accounts) if a['id'] == artist['id']), None)
    if idx is not None:
        accounts[idx]['avatar'] = url
        _save_artist_accounts(accounts)
    return jsonify({'ok': True, 'url': url})

@app.route('/artists/profile/albums', methods=['POST'])
@limiter.limit("20 per minute")
def artist_add_album():
    artist = _get_current_artist()
    if not artist:
        return jsonify({'error': 'No autorizado'}), 401
    data = request.get_json(force=True, silent=True) or {}
    title = (data.get('title') or '').strip()[:120]
    if not title:
        return jsonify({'error': 'Título requerido'}), 400
    album = {
        'id': f"alb_{int(time.time() * 1000)}",
        'title': title,
        'year': int(data.get('year') or datetime.datetime.utcnow().year),
        'description': (data.get('description') or '')[:500],
        'cover': '',
        'created_at': datetime.datetime.utcnow().isoformat() + 'Z',
    }
    accounts = _load_artist_accounts()
    idx = next((i for i, a in enumerate(accounts) if a['id'] == artist['id']), None)
    if idx is None:
        return jsonify({'error': 'Artista no encontrado'}), 404
    accounts[idx]['albums'].append(album)
    _save_artist_accounts(accounts)
    return jsonify({'ok': True, 'album': album}), 201

@app.route('/artists/profile/albums/<album_id>', methods=['DELETE'])
def artist_delete_album(album_id):
    artist = _get_current_artist()
    if not artist:
        return jsonify({'error': 'No autorizado'}), 401
    accounts = _load_artist_accounts()
    idx = next((i for i, a in enumerate(accounts) if a['id'] == artist['id']), None)
    if idx is None:
        return jsonify({'error': 'Artista no encontrado'}), 404
    accounts[idx]['albums'] = [a for a in accounts[idx]['albums'] if a['id'] != album_id]
    _save_artist_accounts(accounts)
    return jsonify({'ok': True})

@app.route('/artists/profile/files', methods=['POST'])
@limiter.limit("10 per minute")
def artist_upload_file():
    artist = _get_current_artist()
    if not artist:
        return jsonify({'error': 'No autorizado'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'No se recibió archivo'}), 400
    f = request.files['file']
    ext = os.path.splitext(f.filename or '')[1].lower()
    if ext not in ALLOWED_FILE_EXTS:
        return jsonify({'error': f'Tipo no permitido. Acepta: {", ".join(sorted(ALLOWED_FILE_EXTS))}'}), 400
    safe_name = re.sub(r'[^\w\.\-]', '_', os.path.basename(f.filename or 'file'))[:120]
    artist_dir = os.path.join(ARTIST_UPLOADS_DIR, artist['id'])
    os.makedirs(artist_dir, exist_ok=True)
    save_path = os.path.normpath(os.path.join(artist_dir, safe_name))
    if not save_path.startswith(os.path.normpath(artist_dir)):
        return jsonify({'error': 'Acceso denegado'}), 403
    f.save(save_path)
    size = os.path.getsize(save_path)
    if size > MAX_ARTIST_FILE_SIZE:
        os.remove(save_path)
        return jsonify({'error': 'Archivo demasiado grande (máximo 200 MB)'}), 413
    # Sanitizador + VirusTotal para archivos de audio
    if ext in ALLOWED_AUDIO_EXTS:
        if not _is_valid_audio_upload(save_path, ext):
            os.remove(save_path)
            return jsonify({'error': 'El archivo no es un audio válido o está corrupto. Sube un .mp3, .wav, .flac, .ogg, .aac, .m4a o .wma'}), 400
        vt_ok, vt_detail = _virustotal_check(save_path)
        if not vt_ok:
            os.remove(save_path)
            logger.warning(f'🚫 Subida rechazada por VirusTotal: {vt_detail}')
            return jsonify({'error': 'El archivo no superó la validación de seguridad'}), 400
    entry = {
        'name': safe_name, 'size': size, 'ext': ext,
        'uploaded_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'url': f'/artists/share/{artist["id"]}/{safe_name}',
    }
    accounts = _load_artist_accounts()
    idx = next((i for i, a in enumerate(accounts) if a['id'] == artist['id']), None)
    if idx is not None:
        accounts[idx]['files'] = [fi for fi in accounts[idx]['files'] if fi['name'] != safe_name]
        accounts[idx]['files'].append(entry)
        _save_artist_accounts(accounts)
    return jsonify({'ok': True, 'file': entry}), 201

@app.route('/artists/profile/files/<filename>', methods=['DELETE'])
def artist_delete_file(filename):
    artist = _get_current_artist()
    if not artist:
        return jsonify({'error': 'No autorizado'}), 401
    safe_name = re.sub(r'[^\w\.\-]', '_', filename)[:120]
    artist_dir = os.path.join(ARTIST_UPLOADS_DIR, artist['id'])
    file_path = os.path.normpath(os.path.join(artist_dir, safe_name))
    if not file_path.startswith(os.path.normpath(artist_dir)):
        return jsonify({'error': 'Acceso denegado'}), 403
    if os.path.isfile(file_path):
        os.remove(file_path)
    accounts = _load_artist_accounts()
    idx = next((i for i, a in enumerate(accounts) if a['id'] == artist['id']), None)
    if idx is not None:
        accounts[idx]['files'] = [fi for fi in accounts[idx]['files'] if fi['name'] != safe_name]
        _save_artist_accounts(accounts)
    return jsonify({'ok': True})

@app.route('/artists/share/<artist_id>/<filename>')
def artist_serve_file(artist_id, filename):
    safe_id = re.sub(r'[^\w\-]', '', artist_id)[:40]
    safe_file = re.sub(r'[^\w\.\-]', '_', filename)[:120]
    artist_dir = os.path.join(ARTIST_UPLOADS_DIR, safe_id)
    file_path = os.path.normpath(os.path.join(artist_dir, safe_file))
    if not file_path.startswith(os.path.normpath(ARTIST_UPLOADS_DIR)):
        return jsonify({'error': 'Acceso denegado'}), 403
    if not os.path.isfile(file_path):
        return jsonify({'error': 'Archivo no encontrado'}), 404
    return send_from_directory(artist_dir, safe_file)

@app.route('/artists/public/<slug>', methods=['GET'])
def artist_public_profile(slug):
    accounts = _load_artist_accounts()
    artist = next((a for a in accounts if a.get('slug') == slug), None)
    if not artist:
        return jsonify({'error': 'Artista no encontrado'}), 404
    safe = {k: v for k, v in artist.items() if k not in ('pwd_hash', 'salt', 'email')}
    return jsonify(safe)


# ── TRACKS (música subida por artistas) ─────────────────────────────────────

def _find_track_owner(track_id, accounts=None):
    """Devuelve (artista, track) que posee track_id, o (None, None)."""
    accounts = accounts if accounts is not None else _load_artist_accounts()
    for a in accounts:
        for t in a.get('tracks', []):
            if t.get('id') == track_id:
                return a, t
    return None, None


def _find_artist_track(artist, track_id):
    for t in artist.get('tracks', []):
        if t.get('id') == track_id:
            return t
    return None


@app.route('/tracks', methods=['POST'])
@limiter.limit("10 per minute")
def track_upload():
    artist = _get_current_artist()
    if not artist:
        return jsonify({'error': 'No autorizado'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'No se recibió archivo'}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({'error': 'Archivo sin nombre'}), 400
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in ALLOWED_AUDIO_EXTS:
        return jsonify({'error': f'Tipo no permitido. Acepta: {", ".join(sorted(ALLOWED_AUDIO_EXTS))}'}), 400
    if (request.form.get('rights_declared') or '').strip().lower() != 'true':
        return jsonify({'error': 'Debes declarar que tienes los derechos'}), 400

    title = (request.form.get('title') or '').strip()[:200]
    genre = (request.form.get('genre') or '').strip()[:60]
    is_public = (request.form.get('is_public') or '').strip().lower() == 'true'

    track_id = f"trk_{secrets.token_hex(8)}"
    track_dir = os.path.normpath(os.path.join(ARTIST_UPLOADS_DIR, artist['id'], 'tracks'))
    os.makedirs(track_dir, exist_ok=True)
    filename = f"{track_id}{ext}"
    save_path = os.path.normpath(os.path.join(track_dir, filename))
    if not save_path.startswith(os.path.normpath(ARTIST_UPLOADS_DIR)):
        return jsonify({'error': 'Acceso denegado'}), 403
    f.save(save_path)
    size = os.path.getsize(save_path)

    # Sanitizador: firma de audio real + segunda capa VirusTotal
    if size > MAX_ARTIST_FILE_SIZE:
        os.remove(save_path)
        return jsonify({'error': 'Archivo demasiado grande (máximo 200 MB)'}), 413
    if not _is_valid_audio_upload(save_path, ext):
        os.remove(save_path)
        return jsonify({'error': 'El archivo no es un audio válido o está corrupto. Sube un .mp3, .wav, .flac, .ogg, .aac, .m4a o .wma'}), 400
    vt_ok, vt_detail = _virustotal_check(save_path)
    if not vt_ok:
        os.remove(save_path)
        logger.warning(f'🚫 Track rechazado por VirusTotal: {vt_detail}')
        return jsonify({'error': 'El archivo no superó la validación de seguridad'}), 400

    cover = ''
    cover_file = request.files.get('cover')
    if cover_file and cover_file.filename:
        cext = os.path.splitext(cover_file.filename)[1].lower()
        if cext in ('.jpg', '.jpeg', '.png', '.webp'):
            cover_name = f"cover_{track_id}{cext}"
            cover_path = os.path.normpath(os.path.join(ARTIST_UPLOADS_DIR, artist['id'], cover_name))
            if cover_path.startswith(os.path.normpath(ARTIST_UPLOADS_DIR)):
                cover_file.save(cover_path)
                cover = f'/artists/share/{artist["id"]}/{cover_name}'

    now = datetime.datetime.utcnow().isoformat() + 'Z'
    track = {
        'id': track_id,
        'title': title or os.path.basename(f.filename),
        'genre': genre,
        'cover': cover,
        'filename': os.path.basename(f.filename),
        'ext': ext,
        'url': f'/tracks/{track_id}/audio',
        'size': size,
        'duration': 0,
        'is_public': is_public,
        'is_premium': False,
        'price': 0,
        'rights_declared': True,
        'rights_declared_at': now,
        'plays_count': 0,
        'downloads_count': 0,
        'earned': 0.0,
        'created_at': now,
    }
    accounts = _load_artist_accounts()
    idx = next((i for i, a in enumerate(accounts) if a['id'] == artist['id']), None)
    if idx is None:
        return jsonify({'error': 'Artista no encontrado'}), 404
    accounts[idx].setdefault('tracks', []).append(track)
    _save_artist_accounts(accounts)
    return jsonify({'ok': True, 'track': track}), 201


@app.route('/tracks', methods=['GET'])
def track_list():
    artist = _get_current_artist()
    if not artist:
        return jsonify({'error': 'No autorizado'}), 401
    return jsonify({'tracks': artist.get('tracks', [])})


@app.route('/tracks/public', methods=['GET'])
def track_public_list():
    q = (request.args.get('q') or '').strip().lower()
    genre = (request.args.get('genre') or '').strip().lower()
    accounts = _load_artist_accounts()
    tracks = []
    for a in accounts:
        for t in a.get('tracks', []):
            if not t.get('is_public'):
                continue
            if q and q not in (t.get('title') or '').lower() and q not in (a.get('artist_name') or '').lower():
                continue
            if genre and genre != (t.get('genre') or '').lower():
                continue
            entry = dict(t)
            entry['artist_name'] = a.get('artist_name', '')
            tracks.append(entry)
    return jsonify({'tracks': tracks})


@app.route('/tracks/<track_id>', methods=['GET'])
def track_detail(track_id):
    accounts = _load_artist_accounts()
    owner, track = _find_track_owner(track_id, accounts)
    if not track:
        return jsonify({'error': 'Track no encontrado'}), 404
    current = _get_current_artist()
    if not track.get('is_public') and (not current or current['id'] != owner['id']):
        return jsonify({'error': 'Track no encontrado'}), 404
    result = dict(track)
    result['artist_name'] = owner.get('artist_name', '')
    return jsonify(result)


@app.route('/tracks/<track_id>', methods=['PATCH'])
def track_update(track_id):
    artist = _get_current_artist()
    if not artist:
        return jsonify({'error': 'No autorizado'}), 401
    accounts = _load_artist_accounts()
    idx = next((i for i, a in enumerate(accounts) if a['id'] == artist['id']), None)
    if idx is None:
        return jsonify({'error': 'Artista no encontrado'}), 404
    a = accounts[idx]
    track = _find_artist_track(a, track_id)
    if not track:
        return jsonify({'error': 'Track no encontrado'}), 404
    data = request.get_json(force=True, silent=True) or {}

    old_public = bool(track.get('is_public'))
    new_public = data['is_public'] if 'is_public' in data else old_public
    if isinstance(new_public, str):
        new_public = new_public.strip().lower() == 'true'

    if not old_public and new_public and not track.get('rights_declared'):
        return jsonify({'error': 'Debes re-declarar que tienes los derechos'}), 400

    if 'title' in data:
        track['title'] = str(data['title']).strip()[:200] or track.get('title', '')
    if 'genre' in data:
        track['genre'] = str(data['genre']).strip()[:60]
    if 'is_public' in data:
        track['is_public'] = bool(new_public)
    if 'is_premium' in data:
        val = data['is_premium']
        track['is_premium'] = bool(val) if not isinstance(val, str) else val.strip().lower() == 'true'
    if 'price' in data:
        try:
            track['price'] = float(data['price'])
        except (TypeError, ValueError):
            track['price'] = 0
    if 'cover' in data:
        track['cover'] = str(data['cover'])[:500]
    _save_artist_accounts(accounts)
    return jsonify({'ok': True, 'track': track})


@app.route('/tracks/<track_id>', methods=['DELETE'])
def track_delete(track_id):
    artist = _get_current_artist()
    if not artist:
        return jsonify({'error': 'No autorizado'}), 401
    accounts = _load_artist_accounts()
    idx = next((i for i, a in enumerate(accounts) if a['id'] == artist['id']), None)
    if idx is None:
        return jsonify({'error': 'Artista no encontrado'}), 404
    a = accounts[idx]
    track = _find_artist_track(a, track_id)
    if not track:
        return jsonify({'error': 'Track no encontrado'}), 404
    track_dir = os.path.normpath(os.path.join(ARTIST_UPLOADS_DIR, a['id'], 'tracks'))
    file_path = os.path.normpath(os.path.join(track_dir, f"{track_id}{track.get('ext', '')}"))
    if file_path.startswith(os.path.normpath(ARTIST_UPLOADS_DIR)) and os.path.isfile(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            logger.warning(f"⚠️ No se pudo borrar archivo del track {track_id}: {e}")
    a['tracks'] = [t for t in a.get('tracks', []) if t.get('id') != track_id]
    _save_artist_accounts(accounts)
    return jsonify({'ok': True})


@app.route('/tracks/<track_id>/play', methods=['POST'])
@limiter.limit("30 per minute")
def track_play(track_id):
    accounts = _load_artist_accounts()
    owner, track = _find_track_owner(track_id, accounts)
    if not track:
        return jsonify({'error': 'Track no encontrado'}), 404
    track['plays_count'] = track.get('plays_count', 0) + 1
    _save_artist_accounts(accounts)
    return jsonify({'ok': True, 'plays_count': track['plays_count']})


@app.route('/tracks/<track_id>/download', methods=['POST'])
@limiter.limit("30 per minute")
def track_download(track_id):
    accounts = _load_artist_accounts()
    owner, track = _find_track_owner(track_id, accounts)
    if not track:
        return jsonify({'error': 'Track no encontrado'}), 404
    current = _get_current_artist()
    is_owner = current is not None and current['id'] == owner['id']
    if not track.get('is_public') and not is_owner:
        return jsonify({'error': 'Track no encontrado'}), 404
    is_premium = bool(track.get('is_premium'))
    requester_premium = current is not None and bool(current.get('is_premium'))
    if is_premium and not requester_premium and not is_owner:
        return jsonify({
            'error': 'requiere_premium',
            'message': 'Esta canción requiere licencia para descargar'
        }), 402
    track['downloads_count'] = track.get('downloads_count', 0) + 1
    if is_premium:
        amount = float(track.get('price') or 0) or 1.0
        track['earned'] = float(track.get('earned') or 0) + amount
        owner['earnings'] = float(owner.get('earnings') or 0) + amount
    _save_artist_accounts(accounts)
    return jsonify({
        'url': f'/tracks/{track_id}/audio',
        'downloads_count': track['downloads_count'],
        'ok': True
    })


@app.route('/tracks/<track_id>/audio')
def track_audio(track_id):
    accounts = _load_artist_accounts()
    owner, track = _find_track_owner(track_id, accounts)
    if not track:
        return jsonify({'error': 'Track no encontrado'}), 404
    current = _get_current_artist()
    if not track.get('is_public') and (not current or current['id'] != owner['id']):
        return jsonify({'error': 'Track no encontrado'}), 404
    ext = track.get('ext', '.mp3')
    track_dir = os.path.normpath(os.path.join(ARTIST_UPLOADS_DIR, owner['id'], 'tracks'))
    filename = f"{track_id}{ext}"
    file_path = os.path.normpath(os.path.join(track_dir, filename))
    if not file_path.startswith(os.path.normpath(ARTIST_UPLOADS_DIR)) or not os.path.isfile(file_path):
        return jsonify({'error': 'Archivo no encontrado'}), 404
    mime = mimetypes.guess_type(filename)[0] or 'audio/mpeg'
    return send_from_directory(track_dir, filename, mimetype=mime, conditional=True)


# ── PREMIUM / MONETIZACIÓN ───────────────────────────────────────────────────

@app.route('/premium/status', methods=['GET'])
def premium_status():
    artist = _get_current_artist()
    if not artist:
        return jsonify({'error': 'No autorizado'}), 401
    earnings = 0.0
    for t in artist.get('tracks', []):
        if t.get('is_premium'):
            earnings += float(t.get('earned') or 0)
    return jsonify({
        'is_premium': bool(artist.get('is_premium')),
        'plan': artist.get('premium_plan', 'free'),
        'earnings': earnings,
        'premium_since': artist.get('premium_since'),
    })


@app.route('/premium/activate', methods=['POST'])
@limiter.limit("20 per minute")
def premium_activate():
    artist = _get_current_artist()
    if not artist:
        return jsonify({'error': 'No autorizado'}), 401
    accounts = _load_artist_accounts()
    idx = next((i for i, a in enumerate(accounts) if a['id'] == artist['id']), None)
    if idx is None:
        return jsonify({'error': 'Artista no encontrado'}), 404
    accounts[idx]['is_premium'] = True
    accounts[idx]['premium_plan'] = 'premium'
    accounts[idx]['premium_since'] = datetime.datetime.utcnow().isoformat() + 'Z'
    _save_artist_accounts(accounts)
    return jsonify({
        'ok': True,
        'is_premium': True,
        'plan': 'premium',
        'premium_since': accounts[idx]['premium_since'],
    })


@app.route('/artists/earnings', methods=['GET'])
def artist_earnings():
    artist = _get_current_artist()
    if not artist:
        return jsonify({'error': 'No autorizado'}), 401
    if not artist.get('is_premium'):
        return jsonify({'error': 'Acción reservada para artistas premium'}), 403
    total = 0.0
    premium_tracks = []
    for t in artist.get('tracks', []):
        if t.get('is_premium'):
            earned = float(t.get('earned') or 0)
            total += earned
            premium_tracks.append({
                'id': t.get('id'),
                'title': t.get('title'),
                'downloads_count': t.get('downloads_count', 0),
                'earned': earned,
            })
    return jsonify({'total': total, 'tracks': premium_tracks})


# ── IA RADIO ─────────────────────────────────────────────────────────────────
# Radio continua "escrita" por agentes de IA: cualquier agente (vía MCP) o
# usuario puede sugerir una canción con /radio/suggest; la radio la toca
# cuando le toca turno. Con la cola vacía, elige sola vía search_youtube
# sobre un pool de moods/géneros (mismo patrón HTTP search→convert que ya
# usa play-song.sh/Home Assistant, sin costo de LLM).
RADIO_FILE = os.path.join(DATA_DIR, 'radio_state.json')
RADIO_LOCK = threading.Lock()
RADIO_MAX_QUEUE = 30
RADIO_MAX_HISTORY = 25
RADIO_MAX_REQUEST_STATS = 250
RADIO_QUEUE_REVIEW_SECONDS = 5
RADIO_FALLBACK_TRACK_SECONDS = 210  # usado si no hay duración conocida
# Moods semilla para arrancar el autofeedback. Se van descubriendo más solos:
# cada canción reproducida o solicitada registra su mood y se agrega aquí.
RADIO_SEED_MOODS = [
    'lofi chill beats', 'synthwave retro', 'indie rock 2020s', 'jazz piano relax',
    'rock clásico 80s', 'pop latino', 'deep house mix', 'bossa nova classics',
    'música electrónica ambient', 'k-pop hits', 'rock en español', 'cumbia suave',
    'funk groove', 'soul classics', 'disco hits 70s 80s', 'R&B smooth',
    'blues guitar', 'country classics', 'reggae chill', 'ska punk',
    'metal instrumental', 'post-rock ambient', 'dream pop', 'shoegaze',
    'guitarra española', 'tango clásico', 'folklór latino', 'cumbia villera',
    'trip hop', 'drum and bass chill', 'house tropical', 'techno melodic',
    'alternative rock 2000s', 'emo hits', 'punk rock classics', 'grunge legends',
    'hip hop old school', 'trap instrumental', 'afrobeat', 'world music',
]
# Tope duro para no quedarse pegado. Subido de 480 a 3600 (1h): el reproductor
# del Atico controla el fin REAL de cada pista via media_position y pide avanzar
# con POST /radio/advance, así que este solo es una red de seguridad para
# playlists largas. Las canciones suenan completas.
RADIO_MAX_TRACK_SECONDS = 3600
RADIO_MASTER_TTL_SECONDS = 15
_RADIO_LIVE_STREAM_URL_RAW = os.environ.get('RADIO_LIVE_STREAM_URL', '').strip()
RADIO_LIVE_UPSTREAM = os.environ.get('RADIO_LIVE_UPSTREAM', 'http://192.168.1.5:2427/live.mp3').strip()


def _radio_live_stream_url():
    """URL del stream para clientes web.

    Usa proxy same-origin por defecto (/radio/live.mp3) para evitar DNS/CORS.
    Si se configura RADIO_LIVE_STREAM_URL con una URL explícita no-legacy, se
    respeta. El valor legacy roto conocido se ignora.
    """
    url = _RADIO_LIVE_STREAM_URL_RAW
    legacy_broken = {
        'https://mail.edgemarketing.art/live.mp3',
        'https://mail.edgemarketing.art/radio/live.mp3',
        'http://mail.edgemarketing.art/live.mp3',
        'http://mail.edgemarketing.art/radio/live.mp3',
    }
    if url in legacy_broken:
        url = ''
    if url:
        return url
    prefix = '/allmusic' if request.path.startswith('/allmusic') else ''
    return f'{prefix}/radio/live.mp3'


RADIO_LIVE_STREAM_URL = _RADIO_LIVE_STREAM_URL_RAW or ''

RADIO_FALLBACK_QUERIES = RADIO_SEED_MOODS

# Reglas clásicas del propietario: géneros/estilos que la radio NO reproduce.
# Se aplican al título y al artista de cada candidata (y a las queries de
# rotación), tanto en auto-rotación como en las sugerencias de agentes/usuario.
# Editable: añade o quita palabras aquí. Normalización quita acentos y pasa a
# minúsculas para que 'Reggaetón' y 'REGGAETON' caigan igual.
RADIO_BLACKLIST = [
    'bachata', 'vallenato', 'reggaeton', 'reggaetón', 'dembow', 'guaracha',
    'corridos tumbados', 'narcocorrido', 'banda sinaloense', 'genre reggaeton',
    'mariachi', 'pachanga', 'trap latino', 'wisin', 'ozuna', 'bad bunny',
    'rapido y furioso', 'daddy yankee', 'maluma', 'anuel', 'karol g', 'j balvin',
    'feid', 'myke towers', 'rush', 'rauw alejandro', 'farruko', 'sech', 'chencho',
]


def _normalize(text):
    """Minúsculas y sin acentos para comparar contenido innecesariamente."""
    import unicodedata
    if not text:
        return ''
    nfkd = unicodedata.normalize('NFKD', str(text))
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _radio_is_blocked(text):
    """True si el texto (título/artista/query) cae en la lista negra."""
    t = _normalize(text)
    return any(_normalize(w) in t for w in RADIO_BLACKLIST)


def _load_radio():
    try:
        with open(RADIO_FILE, 'r') as f:
            state = json.load(f)
            if not isinstance(state, dict):
                raise ValueError('estado de radio inválido')
            state.setdefault('current', None)
            state.setdefault('queue', [])
            state.setdefault('history', [])
            state.setdefault('request_stats', {})
            if not isinstance(state.get('request_stats'), dict):
                state['request_stats'] = {}
            state.setdefault('discovered_moods', {})
            state.setdefault('top_index', 0)
            return state
    except Exception:
        return {'current': None, 'queue': [], 'history': [], 'request_stats': {}, 'discovered_moods': {}, 'top_index': 0}


def _save_radio(state):
    with open(RADIO_FILE, 'w') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _normalize_mood(text):
    """Mood normalizado (listo para comparar) y su forma limpia para query."""
    t = _normalize(str(text or '').strip())
    if not t:
        return '', ''
    return t, str(text).strip()[:80]


def _radio_moods(state):
    """Pool de moods descubiertos + semilla. Devuelve {mood_norm: {mood, uses}}."""
    moods = {_normalize_mood(m)[0]: {'mood': m, 'uses': 0} for m in RADIO_SEED_MOODS}
    for key, entry in (state.get('discovered_moods') or {}).items():
        if isinstance(entry, dict):
            moods[key] = entry
    return moods


def _radio_discover_mood(state, mood):
    """Registra un mood (de una canción reproducida o solicitada) para que el
    random lo reutilice. Autofeedback: cada canción alimenta sus propios moods."""
    norm, clean = _normalize_mood(mood)
    if not norm or _radio_is_blocked(norm):
        return
    discovered = state.setdefault('discovered_moods', {})
    cur = discovered.get(norm) or {'mood': clean, 'uses': 0}
    cur['mood'] = clean
    cur['uses'] = int(cur.get('uses') or 0) + 1
    cur['last_used_at'] = datetime.datetime.utcnow().isoformat() + 'Z'
    discovered[norm] = cur


def _radio_pick_mood(state):
    """Escoge un mood del pool con peso por uso (los más usados suenan más,
    pero todos tienen chance)."""
    moods = _radio_moods(state)
    items = list(moods.values())
    if not items:
        return random.choice(RADIO_SEED_MOODS)
    weights = [1 + (int(i.get('uses') or 0) ** 0.5) for i in items]
    total = sum(weights)
    r = random.uniform(0, total)
    acc = 0
    for item, w in zip(items, weights):
        acc += w
        if r <= acc:
            return item['mood']
    return items[-1]['mood']


def _radio_recent_ids(state):
    ids = {h.get('video_id') for h in state.get('history', [])[:8]}
    cur = state.get('current')
    if cur:
        ids.add(cur.get('video_id'))
    return ids


def _radio_item_key(item):
    """Identificador estable para reconciliar la cola local con el master."""
    if not isinstance(item, dict):
        return ''
    return str(item.get('video_id') or item.get('id') or item.get('request_id') or '')


def _radio_merge_queues(primary, secondary):
    """Prioriza solicitudes pendientes y elimina duplicados al sincronizar."""
    merged = []
    seen = set()
    for source in (primary or [], secondary or []):
        for item in source:
            if not isinstance(item, dict):
                continue
            key = _radio_item_key(item)
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            merged.append(item)
            if len(merged) >= RADIO_MAX_QUEUE:
                return merged
    return merged


def _radio_master_is_active(state, now=None):
    """Indica si el master sigue emitiendo y puede recibir solicitudes."""
    master = state.get('master') or {}
    if not isinstance(master, dict) or not master.get('playing') or not master.get('track'):
        return False
    try:
        age = (time.time() if now is None else now) - float(master.get('updated_at') or 0)
    except (TypeError, ValueError):
        return False
    return 0 <= age <= RADIO_MASTER_TTL_SECONDS


def _radio_effective_queue(state):
    """Cola que deben ver la interfaz y el reproductor master."""
    if _radio_master_is_active(state):
        master = state.get('master') or {}
        return _radio_merge_queues(
            state.get('queue', []),
            master.get('queue', []),
        )[:RADIO_MAX_QUEUE]
    return list(state.get('queue') or [])[:RADIO_MAX_QUEUE]


def _radio_reconcile_master(state):
    """Devuelve a la cola una petición que el loop local tomó antes que el master."""
    if not _radio_master_is_active(state):
        return False
    current = state.get('current')
    master_track = (state.get('master') or {}).get('track') or {}
    current_key = _radio_item_key(current)
    master_key = _radio_item_key(master_track)
    if not current_key or current_key == master_key:
        return False

    source = str((current or {}).get('suggested_by') or '').lower()
    if 'allmusic ai radio' not in source:
        pending = list(state.get('queue') or [])
        if not any(_radio_item_key(item) == current_key for item in pending):
            pending.insert(0, {k: v for k, v in current.items() if k != 'started_at'})
            state['queue'] = pending[:RADIO_MAX_QUEUE]
    state['current'] = None
    return True


def _radio_eta_seconds(state, target):
    """Calcula una ETA aproximada sin interrumpir la pista que está al aire."""
    target_key = _radio_item_key(target)
    queue = _radio_effective_queue(state)
    target_position = next(
        (index for index, item in enumerate(queue) if _radio_item_key(item) == target_key),
        None,
    )
    if target_position is None:
        return 0

    active = _radio_master_is_active(state)
    current = ((state.get('master') or {}).get('track') if active else state.get('current')) or {}
    remaining = 0.0
    if current:
        try:
            duration = float(current.get('duration') or RADIO_FALLBACK_TRACK_SECONDS)
        except (TypeError, ValueError):
            duration = float(RADIO_FALLBACK_TRACK_SECONDS)
        try:
            started_at = float(current.get('started_at') or 0)
        except (TypeError, ValueError):
            started_at = 0
        elapsed = max(0, time.time() - started_at) if started_at else 0
        remaining = max(0, duration - elapsed)

    for item in queue[:target_position]:
        try:
            remaining += float(item.get('duration') or RADIO_FALLBACK_TRACK_SECONDS)
        except (TypeError, ValueError):
            remaining += RADIO_FALLBACK_TRACK_SECONDS
    return int(max(0, remaining))


def _radio_public_queue(state, limit=20):
    """Añade ETA efímera a cada elemento que ve la interfaz o el master."""
    public = []
    for item in _radio_effective_queue(state)[:limit]:
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        eta_seconds = _radio_eta_seconds(state, item)
        entry['eta_seconds'] = eta_seconds
        entry['eta_minutes'] = max(0, int(round(eta_seconds / 60)))
        public.append(entry)
    return public



def _radio_register_request(state, found, query=''):
    """Registra una solicitud aceptada y actualiza su conteo persistente."""
    video_id = found.get('id') or found.get('video_id')
    if not video_id:
        return
    stats = state.setdefault('request_stats', {})
    if not isinstance(stats, dict):
        stats = {}
        state['request_stats'] = stats

    item = stats.get(video_id)
    if not isinstance(item, dict):
        item = {}
    try:
        # own_count = pedidos recibidos POR ESTA instancia (local o nube).
        # migración: si venía de antes de la separación, arranca desde request_count.
        own_count = int(item.get('own_count', item.get('request_count')) or 0)
    except (TypeError, ValueError):
        own_count = 0
    try:
        peer_count = int(item.get('peer_count') or 0)
    except (TypeError, ValueError):
        peer_count = 0
    own_count += 1

    item.update({
        'video_id': video_id,
        'title': found.get('title', item.get('title', 'Sin título')),
        'artist': found.get('uploader') or found.get('artist') or item.get('artist', ''),
        'thumbnail': found.get('thumbnail') or item.get('thumbnail', ''),
        'duration': found.get('duration') or item.get('duration') or 0,
        'own_count': own_count,
        'peer_count': peer_count,
        'request_count': own_count + peer_count,
        'last_requested_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'last_query': str(query or '')[:200],
    })
    stats[video_id] = item

    if len(stats) > RADIO_MAX_REQUEST_STATS:
        def count(entry):
            try:
                return int(entry.get('request_count') or 0)
            except (TypeError, ValueError):
                return 0
        ordered = sorted(
            stats.items(),
            key=lambda pair: (count(pair[1]), str(pair[1].get('last_requested_at', ''))),
            reverse=True,
        )
        state['request_stats'] = dict(ordered[:RADIO_MAX_REQUEST_STATS])

    # Cada solicitud alimenta el pool de moods descubiertos (autofeedback)
    if query:
        _radio_discover_mood(state, query)


def _radio_top_requested(state):
    """Devuelve las diez canciones con más solicitudes, sin exponer datos internos."""
    stats = state.get('request_stats') or {}
    if not isinstance(stats, dict):
        return []

    def count(entry):
        try:
            return int(entry.get('request_count') or 0)
        except (TypeError, ValueError):
            return 0

    top = []
    for video_id, item in stats.items():
        if not isinstance(item, dict):
            continue
        request_count = count(item)
        if request_count <= 0:
            continue
        entry = dict(item)
        entry['video_id'] = entry.get('video_id') or video_id
        entry['request_count'] = request_count
        top.append(entry)

    top.sort(
        key=lambda entry: (entry.get('request_count', 0), str(entry.get('last_requested_at', ''))),
        reverse=True,
    )
    return top[:10]


def _radio_public_moods(state, limit=20):
    """Moods descubiertos ordenados por uso (los más usados primero)."""
    moods = _radio_moods(state)
    items = [
        {'mood': e['mood'], 'uses': int(e.get('uses') or 0)}
        for e in moods.values() if isinstance(e, dict) and e.get('mood')
    ]
    items.sort(key=lambda e: e['uses'], reverse=True)
    return items[:limit]


def _radio_resolve_link(video_id):
    """Devuelve link CDN directo (cachea igual que /convert). None si falla."""
    music_server._cache_prune()
    if video_id in music_server.cache:
        cached = music_server.cache[video_id]
        if cached.get('success') and cached.get('link'):
            return cached
    result = music_server.convert_to_mp3(video_id)
    if result.get('success'):
        music_server.cache_set(video_id, result)
        return result
    return None


def _radio_pick_next(state):
    """Saca próxima entrada de la cola, o improvisa una por rotación. Devuelve
    el dict 'current' listo (con link resuelto) o None si todo falló."""
    queue = state.get('queue', [])
    recent = _radio_recent_ids(state)

    while queue:
        item = queue.pop(0)
        # Reglas del propietario: saltar sugerencias que caigan en la lista negra
        if _radio_is_blocked(item.get('title', '') + ' ' + item.get('artist', '')):
            logger.warning(f"📻 Radio: sugerencia bloqueada por lista negra: {item.get('title')}")
            continue
        conv = _radio_resolve_link(item['video_id'])
        if conv:
            return {
                'video_id': item['video_id'],
                'title': item.get('title', 'Sin título'),
                'artist': item.get('artist', ''),
                'thumbnail': item.get('thumbnail', ''),
                'duration': min(item.get('duration') or conv.get('duration') or RADIO_FALLBACK_TRACK_SECONDS, RADIO_MAX_TRACK_SECONDS),
                'link': conv.get('link'),
                'started_at': time.time(),
                'suggested_by': item.get('suggested_by', 'oyente'),
                'reason': item.get('reason', ''),
            }
        logger.warning(f"📻 Radio: no se pudo convertir sugerencia {item.get('video_id')}, saltando")

    # cola vacía → 50% top más pedidos (sucesivo), 50% random
    top = _radio_top_requested(state)
    use_top = random.random() < 0.5 and top

    if use_top:
        idx = state.get('top_index', 0) % len(top)
        item = top[idx]
        state['top_index'] = (idx + 1) % len(top)
        conv = _radio_resolve_link(item['video_id'])
        if conv:
            return {
                'video_id': item['video_id'],
                'title': item.get('title', 'Sin título'),
                'artist': item.get('artist', ''),
                'thumbnail': item.get('thumbnail', ''),
                'duration': min(item.get('duration') or conv.get('duration') or RADIO_FALLBACK_TRACK_SECONDS, RADIO_MAX_TRACK_SECONDS),
                'link': conv.get('link'),
                'started_at': time.time(),
                'suggested_by': 'AllMusic AI Radio',
                'reason': f'top pedidos #{idx+1} ({item.get("request_count")} pedidos)',
            }

    # rotación automática por mood del pool descubierto (autofeedback)
    query = _radio_pick_mood(state)
    results = music_server.search_youtube(query, max_results=10)
    candidates = [
        r for r in results
        if r.get('id') not in recent
        and not _radio_is_blocked(r.get('title', '') + ' ' + r.get('uploader', ''))
    ]
    if not candidates:
        candidates = [r for r in results if not _radio_is_blocked(r.get('title', '') + ' ' + r.get('uploader', ''))]
    if candidates:
        candidate = random.choice(candidates)
        conv = _radio_resolve_link(candidate['id'])
        if conv:
            _radio_discover_mood(state, query)
            return {
                'video_id': candidate['id'],
                'title': candidate.get('title', 'Sin título'),
                'artist': candidate.get('uploader', ''),
                'thumbnail': candidate.get('thumbnail', ''),
                'duration': min(candidate.get('duration') or conv.get('duration') or RADIO_FALLBACK_TRACK_SECONDS, RADIO_MAX_TRACK_SECONDS),
                'link': conv.get('link'),
                'started_at': time.time(),
                'suggested_by': 'AllMusic AI Radio',
                'mood': query,
                'reason': f'rotación automática: {query}',
            }
    return None


def _radio_tick():
    with RADIO_LOCK:
        state = _load_radio()
        now = time.time()
        if _radio_reconcile_master(state):
            _save_radio(state)
        if _radio_master_is_active(state, now):
            return
        cur = state.get('current')
        needs_next = True
        if cur:
            elapsed = now - cur.get('started_at', 0)
            needs_next = elapsed >= (cur.get('duration') or RADIO_FALLBACK_TRACK_SECONDS)
        if not needs_next:
            return
        nxt = _radio_pick_next(state)
        if not nxt:
            return  # todo falló esta vuelta; se reintenta en el próximo tick
        if cur:
            hist = state.setdefault('history', [])
            hist.insert(0, {**{k: v for k, v in cur.items() if k != 'link'}, 'played_at': now})
            state['history'] = hist[:RADIO_MAX_HISTORY]
        state['current'] = nxt
        _save_radio(state)


def _radio_loop():
    logger.info('📻 IA Radio: loop de reproducción iniciado')
    while True:
        try:
            _radio_tick()
        except Exception as e:
            logger.error(f"❌ Radio loop error: {e}")
        time.sleep(RADIO_QUEUE_REVIEW_SECONDS)


def _no_cache(resp):
    """La UI de radio cambia con cada deploy: nunca cachear HTML ni assets."""
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp


@app.route('/radio')
def radio_page():
    """IA Radio 24/7. Sirve el build React; si no hay build, usa el dashboard legacy."""
    react_index = os.path.join(REACT_DIST_DIR, 'index.html')
    if os.path.isfile(react_index):
        return _no_cache(send_from_directory(REACT_DIST_DIR, 'index.html'))
    path = os.path.join(FRONTEND_DIR, 'radio.html')
    if os.path.isfile(path):
        return _no_cache(send_from_directory(FRONTEND_DIR, 'radio.html'))
    return jsonify({'error': 'Radio no disponible'}), 404


@app.route('/radio-legacy')
def radio_legacy_page():
    """Dashboard histórico de la radio, siempre disponible como respaldo."""
    path = os.path.join(FRONTEND_DIR, 'radio.html')
    if os.path.isfile(path):
        return _no_cache(send_from_directory(FRONTEND_DIR, 'radio.html'))
    return jsonify({'error': 'radio.html no encontrado'}), 404


@app.route('/assets/<path:filename>')
@app.route('/allmusic/assets/<path:filename>')
def react_assets(filename):
    """Assets del SPA React (JS/CSS/PNG). Recurre a frontend/assets si no están en el build."""
    rel = os.path.normpath(os.path.join('assets', filename))
    # Bloquear cualquier intento de salir del directorio de assets.
    if rel.startswith('..') or os.path.isabs(rel):
        return jsonify({'error': 'Acceso denegado'}), 403
    react_path = os.path.join(REACT_DIST_DIR, rel)
    if os.path.isfile(react_path):
        return _no_cache(send_from_directory(REACT_DIST_DIR, rel))
    legacy_path = os.path.join(FRONTEND_DIR, rel)
    if os.path.isfile(legacy_path):
        return send_from_directory(FRONTEND_DIR, rel)
    return jsonify({'error': 'Asset no encontrado'}), 404


@app.route('/radio/now')
def radio_now():
    with RADIO_LOCK:
        state = _load_radio()
        if _radio_reconcile_master(state):
            _save_radio(state)
        public_queue = _radio_public_queue(state, 20)
    master = state.get('master')
    master_offline = False
    if master:
        age = time.time() - master.get('updated_at', 0)
        track = master.get('track')
        master_offline = age > RADIO_MASTER_TTL_SECONDS
        if not master_offline and master.get('playing') and track:
            public_track = {k: v for k, v in track.items() if k != 'started_at'}
            public_track['elapsed'] = round(time.time() - track.get('started_at', time.time()), 1)
            return jsonify({
                'playing': True,
                'master': True,
                'stream_url': _radio_live_stream_url(),
                'track': public_track,
                'queue': public_queue[:20],
                'history': master.get('history', [])[:10],
                'top_requested': _radio_top_requested(state),
                'moods': _radio_public_moods(state),
            })
    cur = state.get('current')
    if not cur:
        return jsonify({
            'playing': False,
            'master': bool(master),
            'master_offline': master_offline,
            'queue': public_queue[:20],
            'history': state.get('history', [])[:10],
            'top_requested': _radio_top_requested(state),
            'moods': _radio_public_moods(state),
        })
    elapsed = time.time() - cur.get('started_at', 0)
    track = {k: v for k, v in cur.items() if k != 'started_at'}
    track['elapsed'] = round(elapsed, 1)
    return jsonify({
        'playing': True,
        'master': bool(master),
        'master_offline': master_offline,
        'stream_url': _radio_live_stream_url(),
        'track': track,
        'queue': public_queue[:20],
        'history': state.get('history', [])[:10],
        'top_requested': _radio_top_requested(state),
        'moods': _radio_public_moods(state),
    })


@app.route('/radio/moods')
def radio_moods():
    """Moods descubiertos (autofeedback): los que la radio aprende al reproducir
    o que la gente/agentes solicitan. Ordenados por más usados primero."""
    with RADIO_LOCK:
        state = _load_radio()
    return jsonify({
        'moods': _radio_public_moods(state, 50),
        'total': len(_radio_public_moods(state, 100000)),
    })


@app.route('/radio/live.mp3')
@app.route('/allmusic/radio/live.mp3')
def radio_live_proxy():
    """Proxy same-origin del stream de radio. Evita que la UI dependa de DNS
    público o CORS del upstream; el upstream real se configura por
    RADIO_LIVE_UPSTREAM (default: http://192.168.1.5:2427/live.mp3)."""
    candidates = []
    for value in (
        RADIO_LIVE_UPSTREAM,
        'http://192.168.1.5:2427/live.mp3',
        'http://192.168.1.6:2427/live.mp3',
        'http://192.168.1.2:2427/live.mp3',
        'http://127.0.0.1:2427/live.mp3',
        'http://host.docker.internal:2427/live.mp3',
        'http://172.17.0.1:2427/live.mp3',
        'http://172.18.0.1:2427/live.mp3',
        'http://172.19.0.1:2427/live.mp3',
        'http://172.20.0.1:2427/live.mp3',
        'http://172.21.0.1:2427/live.mp3',
        'http://172.22.0.1:2427/live.mp3',
        'http://172.23.0.1:2427/live.mp3',
    ):
        value = (value or '').strip()
        if value and value not in candidates:
            candidates.append(value)
    upstream_resp = None
    last_exc = None
    for upstream in candidates:
        if not (upstream.startswith('http://') or upstream.startswith('https://')):
            continue
        headers = {}
        ua = request.headers.get('User-Agent')
        if ua:
            headers['User-Agent'] = ua[:200]
        rng = request.headers.get('Range')
        if rng:
            headers['Range'] = rng
        try:
            req = urllib.request.Request(upstream, headers=headers)
            upstream_resp = urllib.request.urlopen(req, timeout=15)
            break
        except Exception as exc:
            last_exc = exc
            logger.warning(f"Radio live proxy error con {upstream}: {exc}")
    if upstream_resp is None:
        logger.warning(f"Radio live proxy sin upstream disponible: {last_exc}")
        return jsonify({'error': 'Stream de radio no disponible', 'detail': str(last_exc)[:200]}), 502

    def generate():
        try:
            while True:
                chunk = upstream_resp.read(8192)
                if not chunk:
                    break
                yield chunk
        finally:
            try:
                upstream_resp.close()
            except Exception:
                pass

    status = getattr(upstream_resp, 'status', 200)
    content_type = upstream_resp.headers.get('Content-Type', 'audio/mpeg')
    resp = Response(stream_with_context(generate()), status=status, content_type=content_type)
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
    resp.headers['Accept-Ranges'] = upstream_resp.headers.get('Accept-Ranges', 'none')
    for header in ('Content-Range', 'Content-Length', 'ICY-Name', 'icy-name', 'ICY-MetaInt', 'icy-metaint'):
        value = upstream_resp.headers.get(header)
        if value:
            resp.headers[header] = value
    return resp


@app.route('/radio/master', methods=['POST'])
def radio_master_update():
    """Heartbeat de la cabina master local (Atico) hacia la emisión pública."""
    if not _is_moderator():
        return jsonify({'error': 'No autorizado'}), 401
    data = request.get_json(force=True, silent=True) or {}
    raw_track = data.get('track') or {}
    link = str(raw_track.get('link') or '')[:2000]
    if data.get('playing') and not (link.startswith('https://') or link.startswith('http://')):
        return jsonify({'error': 'link de transmisión inválido'}), 400
    now = time.time()
    elapsed = max(0, float(raw_track.get('elapsed') or 0))
    allowed = ('video_id', 'title', 'artist', 'thumbnail', 'duration', 'link', 'suggested_by', 'reason', 'mood')
    track = {key: raw_track.get(key) for key in allowed if raw_track.get(key) is not None}
    track['started_at'] = now - elapsed
    raw_queue = data.get('queue') or []
    reported_queue = [item for item in raw_queue[:RADIO_MAX_QUEUE] if isinstance(item, dict)]
    with RADIO_LOCK:
        state = _load_radio()
        pending = list(state.get('queue') or [])
        current_key = _radio_item_key(track)
        pending_for_master = [
            item for item in pending
            if _radio_item_key(item) != current_key
        ]
        effective_queue = _radio_merge_queues(pending_for_master, reported_queue)
        acknowledged_keys = {
            _radio_item_key(item) for item in reported_queue
            if _radio_item_key(item)
        }
        if current_key:
            acknowledged_keys.add(current_key)
        state['queue'] = [
            item for item in pending
            if _radio_item_key(item) not in acknowledged_keys
        ][:RADIO_MAX_QUEUE]
        state['master'] = {
            'updated_at': now,
            'playing': bool(data.get('playing')),
            'track': track,
            'queue': effective_queue[:RADIO_MAX_QUEUE],
            'history': (data.get('history') or [])[:RADIO_MAX_HISTORY],
        }
        # Unifica el ranking de "más pedidos": el heartbeat trae el top_requested
        # de la otra instancia (own_count de ese lado) y aquí se fusiona como
        # peer_count -- reemplazo, no suma, así el heartbeat repetido cada pocos
        # segundos no infla el contador.
        peer_top = data.get('request_stats_top') or []
        if isinstance(peer_top, list):
            stats = state.setdefault('request_stats', {})
            if not isinstance(stats, dict):
                stats = {}
                state['request_stats'] = stats
            for entry in peer_top:
                if not isinstance(entry, dict):
                    continue
                vid = entry.get('video_id')
                if not vid:
                    continue
                try:
                    reported = int(entry.get('request_count') or 0)
                except (TypeError, ValueError):
                    continue
                if reported <= 0:
                    continue
                item = stats.get(vid)
                if not isinstance(item, dict):
                    item = {}
                try:
                    own_count = int(item.get('own_count', 0) or 0)
                except (TypeError, ValueError):
                    own_count = 0
                item.update({
                    'video_id': vid,
                    'title': entry.get('title', item.get('title', 'Sin título')),
                    'artist': entry.get('artist', item.get('artist', '')),
                    'thumbnail': entry.get('thumbnail') or item.get('thumbnail', ''),
                    'duration': entry.get('duration') or item.get('duration') or 0,
                    'own_count': own_count,
                    'peer_count': reported,
                    'request_count': own_count + reported,
                    'last_requested_at': entry.get('last_requested_at') or item.get('last_requested_at', ''),
                })
                stats[vid] = item
        if _radio_reconcile_master(state):
            effective_queue = _radio_effective_queue(state)
            state['master']['queue'] = effective_queue[:RADIO_MAX_QUEUE]
        else:
            effective_queue = _radio_effective_queue(state)
        _save_radio(state)
    public_queue = _radio_public_queue(state, 20)
    return jsonify({
        'ok': True,
        'master': True,
        'queue': public_queue,
        'next_request': public_queue[0] if public_queue else None,
    })


@app.route('/radio/queue')
def radio_queue():
    with RADIO_LOCK:
        state = _load_radio()
        if _radio_reconcile_master(state):
            _save_radio(state)
        return jsonify({'queue': _radio_public_queue(state, RADIO_MAX_QUEUE)})


@app.route('/radio/suggest', methods=['POST'])
@limiter.limit("10 per minute")
def radio_suggest():
    data = request.get_json(force=True, silent=True) or {}
    query = (data.get('query') or '').strip()[:200]
    reason = (data.get('reason') or '').strip()[:200]
    agent = (data.get('agent') or 'agente anónimo').strip()[:60]
    if not query:
        return jsonify({'error': 'query requerido'}), 400
    # Reglas del propietario: no encolar nada que caiga en la lista negra
    if _radio_is_blocked(query):
        return jsonify({'error': 'No disponible'}), 403
    with RADIO_LOCK:
        state = _load_radio()
        _radio_reconcile_master(state)
        queue = state.setdefault('queue', [])
        if len(queue) >= RADIO_MAX_QUEUE:
            return jsonify({'error': 'Cola llena, intenta más tarde'}), 429
        results = music_server.search_youtube(query, max_results=1)
        if not results:
            return jsonify({'error': f'Sin resultados para "{query}"'}), 404
        found = results[0]
        if _radio_is_blocked(found.get('title', '') + ' ' + found.get('uploader', '')):
            return jsonify({'error': 'No disponible'}), 403
        entry = {
            'request_id': secrets.token_hex(8),
            'video_id': found['id'],
            'title': found.get('title', 'Sin título'),
            'artist': found.get('uploader', ''),
            'thumbnail': found.get('thumbnail', ''),
            'duration': found.get('duration', 0),
            'suggested_by': agent,
            'reason': reason,
            'added_at': datetime.datetime.utcnow().isoformat() + 'Z',
        }
        queue.append(entry)
        _radio_register_request(state, found, query)
        if _radio_master_is_active(state):
            state['master']['queue'] = _radio_effective_queue(state)
        public_queue = _radio_public_queue(state, RADIO_MAX_QUEUE)
        position = next(
            (index + 1 for index, item in enumerate(public_queue)
             if _radio_item_key(item) == _radio_item_key(entry)),
            len(public_queue),
        )
        eta_seconds = _radio_eta_seconds(state, entry)
        _save_radio(state)
        return jsonify({
            'queued': True,
            'position': position,
            'eta_seconds': eta_seconds,
            'eta_minutes': max(0, int(round(eta_seconds / 60))),
            'track': entry,
            'top_requested': _radio_top_requested(state),
        }), 201


@app.route('/radio/advance', methods=['POST'])
@limiter.limit("30 per minute")
def radio_advance():
    """Marca la pista actual como vencida para que el loop la rote de inmediato.
    Usado por el reproductor del Atico al detectar que la pista real está por
    terminar antes del tope. NO llama a _radio_tick() aquí porque ese adquiere
    RADIO_LOCK (non-reentrante) -> evitar deadlock; el loop rota en <=5s."""
    with RADIO_LOCK:
        state = _load_radio()
        cur = state.get('current')
        if cur:
            cur['started_at'] = 0
            _save_radio(state)
            return jsonify({'ok': True, 'advanced': True,
                            'was': cur.get('video_id')})
        return jsonify({'ok': True, 'advanced': False, 'was': None})


# ── MAIN ───────────────────────────────────────────────────────────────────────

def _wsgi_app(environ, start_response):
    # Soporta servir la app bajo el prefijo /allmusic (por el proxy). Si la
    # request viene como /allmusic/<path>, se recorta ese prefijo antes de
    # que Flask enrutee; así /allmusic/status -> /status, /allmusic/ -> /.
    path = environ.get('PATH_INFO', '/')
    if path == '/allmusic':
        environ['PATH_INFO'] = '/'
    elif path.startswith('/allmusic/'):
        environ['PATH_INFO'] = path[len('/allmusic'):]
    return _orig_wsgi_app(environ, start_response)


_orig_wsgi_app = app.wsgi_app
app.wsgi_app = _wsgi_app


def _start_radio_loop():
    thread = threading.Thread(target=_radio_loop, daemon=True)
    thread.start()
    logger.info('📻 IA Radio: loop de reproducción iniciado en hilo daemon')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 2426))
    print("🎵" + "="*50)
    print("   AllMusic Server - Railway Edition")
    print("   yt-dlp + YouTube MP3 API")
    print("🎵" + "="*50)
    print(f"🚀 Iniciando servidor en puerto {port}...")
    print(f"🌐 http://0.0.0.0:{port}")
    print(f"🔍 /search?q=CANCION")
    print(f"🎧 /stream/VIDEO_ID")
    _start_radio_loop()

    try:
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n🛑 Servidor detenido por el usuario")
    except Exception as e:
        print(f"\n❌ Error al iniciar servidor: {e}")
