#!/usr/bin/env python3
"""Emisión MP3 continua de la cabina master de AllMusic."""

import json
import os
import queue
import select
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOST = os.environ.get('LIVE_RADIO_HOST', '127.0.0.1')
PORT = int(os.environ.get('LIVE_RADIO_PORT', '2427'))
# Fuente primaria = la radio web (Railway, donde están las peticiones de oyentes);
# fallback = la IA Radio local (:2426) por si se cae la red y el cloud no responde.
WEB_URL = os.environ.get('WEB_URL', 'https://edgemarketing.art/allmusic')
LOCAL_URL = os.environ.get('LOCAL_URL', 'http://127.0.0.1:2426')
FFMPEG = os.environ.get('FFMPEG', '/usr/bin/ffmpeg')
CHUNK_SIZE = 16384
CLIENTS = set()
CLIENTS_LOCK = threading.Lock()
STATUS = {'video_id': None, 'title': None, 'clients': 0, 'encoding': False,
          'next_request': None, 'request_count': 0}


def _source_url():
    """URL de la fuente activa: la web (Railway) si responde Y está reproduciendo,
    si no la local (:2426). Web arriba pero sin pista (playing=false) no cuenta,
    para no dejar el encoder mudo mientras local sí tiene audio."""
    try:
        with urllib.request.urlopen(WEB_URL + '/radio/now', timeout=4) as response:
            data = json.loads(response.read().decode())
        if data.get('playing'):
            return WEB_URL
    except Exception:
        pass
    return LOCAL_URL


def _fetch_json(path, timeout=8):
    """GET JSON desde la fuente activa (web con fallback local)."""
    url = _source_url() + path
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode())


def radio_now():
    try:
        return _fetch_json('/radio/now')
    except Exception:
        return {'playing': False, 'track': None}


def radio_next_request():
    """Próximo pedido de oyentes (next_request) y ranking (top_requested) de la fuente activa."""
    try:
        data = _fetch_json('/radio/now', timeout=5)
        nxt = data.get('next_request')
        top = data.get('top_requested') or []
        return nxt, len(top)
    except Exception:
        return None, 0


def radio_advance():
    """Pide a la fuente activa rotar al siguiente pedido de inmediato."""
    try:
        url = _source_url() + '/radio/advance'
        req = urllib.request.Request(url, method='POST')
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


def fanout(data):
    with CLIENTS_LOCK:
        clients = list(CLIENTS)
    for client in clients:
        try:
            client.put_nowait(data)
        except queue.Full:
            try:
                client.get_nowait()
                client.put_nowait(data)
            except (queue.Empty, queue.Full):
                pass


def start_encoder(track):
    elapsed = max(0, float(track.get('elapsed') or 0))
    command = [
        FFMPEG, '-nostdin', '-hide_banner', '-loglevel', 'error',
        '-re', '-ss', f'{elapsed:.2f}', '-i', track['link'],
        '-vn', '-c:a', 'libmp3lame', '-b:a', '192k', '-ar', '44100', '-ac', '2',
        '-f', 'mp3', 'pipe:1',
    ]
    return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)


def broadcast_loop():
    process = None
    current_id = None
    next_poll = 0
    next_req_poll = 0
    track = None
    while True:
        now = time.monotonic()
        if now >= next_poll:
            next_poll = now + 1
            try:
                state = radio_now()
                candidate = state.get('track') if state.get('playing') else None
                candidate_id = (candidate or {}).get('video_id')
                if candidate_id and candidate_id != current_id:
                    if process:
                        process.terminate()
                        process.wait(timeout=3)
                    track = candidate
                    process = start_encoder(track)
                    current_id = candidate_id
                    STATUS.update(video_id=current_id, title=track.get('title'), encoding=True)
                elif process and process.poll() is not None and candidate:
                    # La IA Radio rotó pero el encoder aun no arranca con la nueva pista.
                    track = candidate
                    process = start_encoder(track)
            except Exception:
                time.sleep(1)

        # Ver la cola de pedidos (position/ETA) para exponerla en /health y,
        # si hay pedido pendiente al terminar la pista, pedir avance rápido.
        if now >= next_req_poll:
            next_req_poll = now + 5
            nxt, cnt = radio_next_request()
            STATUS['next_request'] = nxt
            STATUS['request_count'] = cnt
            if process and process.poll() is not None and nxt:
                # Fin de pista y hay pedido en cola: asegurar que la IA Radio
                # avance a ese pedido (por si la rotación automática no se dio).
                radio_advance()

        if not process or not process.stdout:
            STATUS['encoding'] = False
            time.sleep(0.2)
            continue

        ready, _, _ = select.select([process.stdout], [], [], 0.5)
        if ready:
            chunk = os.read(process.stdout.fileno(), CHUNK_SIZE)
            if chunk:
                STATUS['encoding'] = True
                fanout(chunk)


class LiveRadioHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    server_version = 'AllMusicLive/1.0'

    def do_HEAD(self):
        if self.path.split('?', 1)[0] == '/live.mp3':
            self.live_headers(head_only=True)
            return
        self.send_error(404)

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path == '/health':
            payload = json.dumps(STATUS).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if path != '/live.mp3':
            self.send_error(404)
            return

        client = queue.Queue(maxsize=128)
        with CLIENTS_LOCK:
            CLIENTS.add(client)
            STATUS['clients'] = len(CLIENTS)
        try:
            self.live_headers()
            while True:
                chunk = client.get(timeout=20)
                self.wfile.write(f'{len(chunk):X}\r\n'.encode('ascii'))
                self.wfile.write(chunk)
                self.wfile.write(b'\r\n')
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError, queue.Empty):
            pass
        finally:
            with CLIENTS_LOCK:
                CLIENTS.discard(client)
                STATUS['clients'] = len(CLIENTS)

    def live_headers(self, head_only=False):
        self.send_response(200)
        self.send_header('Content-Type', 'audio/mpeg')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Accept-Ranges', 'none')
        self.send_header('icy-name', 'AllMusic IA Radio - Master')
        self.send_header('icy-pub', '1')
        if not head_only:
            self.send_header('Transfer-Encoding', 'chunked')
        self.end_headers()

    def log_message(self, fmt, *args):
        return


def main():
    threading.Thread(target=broadcast_loop, daemon=True).start()
    ThreadingHTTPServer((HOST, PORT), LiveRadioHandler).serve_forever()


if __name__ == '__main__':
    main()
