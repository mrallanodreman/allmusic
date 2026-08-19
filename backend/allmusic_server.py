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
import datetime
import subprocess
import mimetypes
from urllib.parse import quote, unquote

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

# Config desde variables de entorno
# RAPIDAPI_KEY acepta una o varias keys separadas por coma (rotación automática:
# si una app de RapidAPI agota su cuota diaria (429/403), se prueba la siguiente).
RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', '')
RAPIDAPI_KEYS = [k.strip() for k in RAPIDAPI_KEY.split(',') if k.strip()]
RAPIDAPI_HOST = os.environ.get('RAPIDAPI_HOST', 'youtube-mp36.p.rapidapi.com')
ALLMUSIC_ADMIN_KEY = os.environ.get('ALLMUSIC_ADMIN_KEY', 'adminallmusic2024')

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

os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(ARTIST_UPLOADS_DIR, exist_ok=True)


class AllMusicServer:
    def __init__(self):
        self.cache = {}

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

            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'default_search': 'ytsearch10:',
                'ignoreerrors': True,
                'force_generic_extractor': False,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                search_results = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
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

    def convert_to_mp3(self, video_id, max_retries=20):
        """Convierte un video de YouTube a MP3 usando RapidAPI"""
        try:
            logger.info(f"🎵 Convirtiendo video ID: {video_id}")
            MAX_DURATION_SECONDS = 7200

            try:
                ydl_opts = {'quiet': True, 'no_warnings': True}
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
                                    return {'success': False, 'error': f'API no disponible: {response_text[:100]}'}
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
                                return {'success': False, 'error': str(e)}
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

            return {'success': False, 'error': f'Límite de conversiones diarias agotado en todas las keys disponibles ({len(RAPIDAPI_KEYS)}). Intenta más tarde.'}
        except Exception as e:
            logger.error(f"❌ Error inesperado en convert_to_mp3: {e}")
            return {'success': False, 'error': str(e)}

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
            ctype = response.headers.get('Content-Type', 'audio/mpeg')
            out_headers['Content-Type'] = ctype if ctype.startswith('audio/') else 'audio/mpeg'
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
                        out_headers = {
                            'Content-Type': response.headers.get('Content-Type', 'audio/mp4'),
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
        all_results = music_server.search_youtube(query, max_results=max_results)
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
        return jsonify({'error': str(e)}), 500


@app.route('/stream/<video_id>')
def stream(video_id):
    try:
        if not video_id or len(video_id) != 11:
            return jsonify({'error': 'ID inválido'}), 400
        if video_id.startswith('UC'):
            return jsonify({'error': 'ID de canal'}), 400

        # PRIMARIO: yt-dlp (YouTube directo, sin cookies)
        ytdlp_response = music_server.stream_via_ytdlp(video_id)
        if ytdlp_response:
            return ytdlp_response
        logger.warning(f"⚠️ yt-dlp falló para {video_id}, fallback RapidAPI")

        # FALLBACK: RapidAPI
        if video_id not in music_server.cache:
            result = music_server.convert_to_mp3(video_id)
            if result.get('success'):
                music_server.cache[video_id] = result
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
        music_server.cache.pop(video_id, None)
        result = music_server.convert_to_mp3(video_id)
        if result.get('success') and result.get('link'):
            music_server.cache[video_id] = result
            stream_resp = music_server.stream_via_rapidapi(result['link'])
            if stream_resp:
                return stream_resp

        return jsonify({'success': False, 'error': 'No se pudo iniciar el stream. Inténtalo de nuevo.'}), 502
    except Exception as e:
        logger.error(f"❌ Error en /stream: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/download/<video_id>.mp3')
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
            return jsonify({'error': f'No se pudo obtener el MP3: {err}'}), 502

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
            except:
                pass
            return jsonify({'error': f'Error al descargar MP3: {str(e)}'}), 500

        return send_from_directory(DOWNLOADS_DIR, file_name, mimetype='audio/mpeg', as_attachment=True, download_name=file_name, conditional=False)
    except Exception as e:
        logger.error(f"❌ Error en /download: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/convert/<video_id>')
def convert(video_id):
    try:
        if not video_id or len(video_id) != 11:
            return jsonify({'error': 'ID inválido'}), 400
        if video_id.startswith('UC'):
            return jsonify({'error': 'ID de canal'}), 400
        if video_id in music_server.cache:
            return jsonify(music_server.cache[video_id])
        result = music_server.convert_to_mp3(video_id)
        if result.get('success'):
            music_server.cache[video_id] = result
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/play')
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
        return jsonify({'error': str(e)}), 500


@app.route('/status')
def status():
    return jsonify({
        'status': 'running',
        'cache_size': len(music_server.cache),
        'endpoints': ['/search', '/convert', '/stream', '/download', '/play', '/status']
    })


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

@app.route('/')
def index():
    idx_path = os.path.join(FRONTEND_DIR, 'index.html')
    modern_path = os.path.join(FRONTEND_DIR, 'modern_index.html')
    if os.path.exists(modern_path):
        return send_from_directory(FRONTEND_DIR, 'modern_index.html')
    return send_from_directory(FRONTEND_DIR, 'index.html')


@app.route('/<path:filename>')
def frontend_files(filename):
    file_path = os.path.join(FRONTEND_DIR, filename)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return send_from_directory(FRONTEND_DIR, filename)
    # Redirect clean legal/static paths (no extension) to their .html file.
    # The path may arrive prefixed with 'allmusic/' (reverse proxy), so strip it.
    rel = filename
    if rel.startswith('allmusic/'):
        rel = rel[len('allmusic/'):]
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

def _load_users():
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def _save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

@app.route('/users/register', methods=['POST'])
def user_register():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get('email') or '').strip().lower()[:120]
    name  = (data.get('name') or '').strip()[:50]
    if not email or '@' not in email:
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
def user_lookup():
    email = (request.args.get('email') or '').strip().lower()
    if not email:
        return jsonify({'error': 'Email requerido'}), 400
    users = _load_users()
    user = next((u for u in users if u['email'] == email), None)
    if not user:
        return jsonify({'found': False}), 404
    return jsonify({'found': True, 'user': user})

@app.route('/users', methods=['GET'])
def list_users():
    secret = request.args.get('key', '')
    if secret != ALLMUSIC_ADMIN_KEY:
        return jsonify({'error': 'No autorizado'}), 403
    users = _load_users()
    return jsonify({'total': len(users), 'users': users})


# ── PLAYLISTS ──────────────────────────────────────────────────────────────────
PLAYLISTS_FILE = os.path.join(DATA_DIR, 'playlists.json')

def _load_playlists():
    try:
        with open(PLAYLISTS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def _save_playlists(pls):
    with open(PLAYLISTS_FILE, 'w') as f:
        json.dump(pls, f, indent=2)

@app.route('/playlists', methods=['GET'])
def get_playlists():
    return jsonify(_load_playlists())

@app.route('/playlists', methods=['POST'])
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
    try:
        with open(ARTISTS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def _save_artists(arts):
    with open(ARTISTS_FILE, 'w') as f:
        json.dump(arts, f, indent=2)

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

def _load_artist_accounts():
    try:
        with open(ARTIST_ACCOUNTS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def _save_artist_accounts(accounts):
    with open(ARTIST_ACCOUNTS_FILE, 'w') as f:
        json.dump(accounts, f, indent=2)

def _slugify_artist(text):
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text[:50]

def _hash_artist_pwd(salt, pwd):
    return hashlib.sha256((salt + pwd).encode('utf-8')).hexdigest()

def _create_artist_token(artist_id):
    token = secrets.token_hex(32)
    ARTIST_SESSIONS[token] = {'artist_id': artist_id, 'expires': time.time() + 30 * 24 * 3600}
    return token

def _get_current_artist():
    auth = request.headers.get('Authorization', '')
    token = auth.replace('Bearer ', '').strip()
    if not token:
        return None
    session = ARTIST_SESSIONS.get(token)
    if not session or time.time() > session['expires']:
        if session:
            del ARTIST_SESSIONS[token]
        return None
    accounts = _load_artist_accounts()
    return next((a for a in accounts if a['id'] == session['artist_id']), None)

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
def artist_auth_register():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get('email') or '').strip().lower()[:120]
    password = (data.get('password') or '').strip()
    artist_name = (data.get('artist_name') or data.get('name') or '').strip()[:80]
    genre = (data.get('genre') or '').strip()[:60]
    if not email or '@' not in email:
        return jsonify({'error': 'Email inválido'}), 400
    if len(password) < 6:
        return jsonify({'error': 'La contraseña debe tener al menos 6 caracteres'}), 400
    if not artist_name:
        return jsonify({'error': 'Nombre artístico requerido'}), 400
    accounts = _load_artist_accounts()
    if any(a['email'] == email for a in accounts):
        return jsonify({'error': 'Este email ya está registrado'}), 409
    salt = secrets.token_hex(16)
    pwd_hash = _hash_artist_pwd(salt, password)
    base_slug = _slugify_artist(artist_name)
    slug = _unique_artist_slug(base_slug, accounts)
    artist_id = f"art_{int(time.time() * 1000)}"
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
def artist_auth_login():
    data = request.get_json(force=True, silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = (data.get('password') or '').strip()
    if not email or not password:
        return jsonify({'error': 'Email y contraseña requeridos'}), 400
    accounts = _load_artist_accounts()
    artist = next((a for a in accounts if a['email'] == email), None)
    if not artist or _hash_artist_pwd(artist['salt'], password) != artist['pwd_hash']:
        return jsonify({'error': 'Email o contraseña incorrectos'}), 401
    token = _create_artist_token(artist['id'])
    return jsonify({'ok': True, 'token': token, 'artist': _artist_safe(artist)})

@app.route('/artists/profile', methods=['GET'])
def artist_get_profile():
    artist = _get_current_artist()
    if not artist:
        return jsonify({'error': 'No autorizado'}), 401
    return jsonify(_artist_safe(artist))

@app.route('/artists/profile', methods=['PUT'])
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

    track_id = f"trk_{int(time.time() * 1000)}"
    track_dir = os.path.normpath(os.path.join(ARTIST_UPLOADS_DIR, artist['id'], 'tracks'))
    os.makedirs(track_dir, exist_ok=True)
    filename = f"{track_id}{ext}"
    save_path = os.path.normpath(os.path.join(track_dir, filename))
    if not save_path.startswith(os.path.normpath(ARTIST_UPLOADS_DIR)):
        return jsonify({'error': 'Acceso denegado'}), 403
    f.save(save_path)
    size = os.path.getsize(save_path)

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
def track_play(track_id):
    accounts = _load_artist_accounts()
    owner, track = _find_track_owner(track_id, accounts)
    if not track:
        return jsonify({'error': 'Track no encontrado'}), 404
    track['plays_count'] = track.get('plays_count', 0) + 1
    _save_artist_accounts(accounts)
    return jsonify({'ok': True, 'plays_count': track['plays_count']})


@app.route('/tracks/<track_id>/download', methods=['POST'])
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


# ── MAIN ───────────────────────────────────────────────────────────────────────

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

    try:
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n🛑 Servidor detenido por el usuario")
    except Exception as e:
        print(f"\n❌ Error al iniciar servidor: {e}")
