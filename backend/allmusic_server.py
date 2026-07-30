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
RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY', '')
RAPIDAPI_HOST = os.environ.get('RAPIDAPI_HOST', 'youtube-mp36.p.rapidapi.com')
ALLMUSIC_ADMIN_KEY = os.environ.get('ALLMUSIC_ADMIN_KEY', 'adminallmusic2024')
if not RAPIDAPI_KEY:
    logger.warning('RAPIDAPI_KEY no configurada — las conversiones fallarán')

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

                if search_results and 'entries' in search_results:
                    for entry in search_results['entries']:
                        if entry and entry.get('id'):
                            video_id = entry.get('id', '')
                            duration = entry.get('duration', 0)

                            if not video_id or len(video_id) != 11 or video_id.startswith('UC'):
                                continue
                            if not all(c.isalnum() or c in '-_' for c in video_id):
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

            conn = http.client.HTTPSConnection(RAPIDAPI_HOST, timeout=20)
            headers = {
                'x-rapidapi-key': RAPIDAPI_KEY,
                'x-rapidapi-host': RAPIDAPI_HOST
            }

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
                        return {'success': False, 'error': f'HTTP {res.status}'}
                except json.JSONDecodeError:
                    if attempt == max_retries - 1:
                        return {'success': False, 'error': 'Error al parsear respuesta JSON'}
                    time.sleep(1)
                except Exception as e:
                    if attempt == max_retries - 1:
                        return {'success': False, 'error': str(e)}
                    time.sleep(1)

            return {'success': False, 'error': f'Máximo de reintentos alcanzado ({max_retries} intentos)'}
        finally:
            try:
                conn.close()
            except:
                pass

    def stream_via_rapidapi(self, mp3_url):
        """Streaming directo desde URL de RapidAPI"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'audio/mpeg,audio/*,*/*',
                'Accept-Encoding': 'identity',
                'Range': 'bytes=0-'
            }
            response = requests.get(mp3_url, headers=headers, stream=True, timeout=10)
            if response.status_code in [200, 206]:
                def generate():
                    try:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                yield chunk
                    except Exception as e:
                        logger.error(f"❌ Error durante streaming: {str(e)}")
                return Response(
                    generate(),
                    mimetype='audio/mpeg',
                    headers={
                        'Content-Type': 'audio/mpeg',
                        'Accept-Ranges': 'bytes',
                        'Cache-Control': 'no-cache',
                        'Access-Control-Allow-Origin': '*'
                    }
                )
            return None
        except Exception as e:
            logger.error(f"❌ Error en stream: {str(e)}")
            return None

    def stream_via_ytdlp(self, video_id):
        """Stream usando yt-dlp (sin cookies de navegador)"""
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            cmd = [
                'yt-dlp',
                '-f', 'bestaudio[ext=m4a]/bestaudio/best',
                '--get-url', '--no-warnings', '--no-update',
                '--no-cookies',
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
                    response = requests.get(audio_url, headers=headers, stream=True, timeout=30)
                    if response.status_code in [200, 206]:
                        def generate():
                            try:
                                for chunk in response.iter_content(chunk_size=65536):
                                    if chunk:
                                        yield chunk
                            except Exception as e:
                                logger.error(f"❌ Error streaming yt-dlp: {str(e)}")
                        return Response(
                            generate(),
                            mimetype='audio/mp4',
                            headers={
                                'Content-Type': 'audio/mp4',
                                'Accept-Ranges': 'bytes',
                                'Cache-Control': 'no-cache',
                                'Access-Control-Allow-Origin': '*'
                            }
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
                return jsonify({'error': result.get("error", "Error desconocido")}), 400

        mp3_url = music_server.cache[video_id].get('link')
        if not mp3_url:
            return jsonify({'error': 'No hay URL'}), 400

        # Proxy streaming
        stream_resp = music_server.stream_via_rapidapi(mp3_url)
        if stream_resp:
            return stream_resp
        return redirect(mp3_url)
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
