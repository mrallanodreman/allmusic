#!/usr/bin/env python3
"""Serve Vite's production bundle under /allmusic for a browser smoke test.

No external backend is touched; this verifies DOM mounting, JS/CSS load and
the React route views at the same prefix as the real Cloudflare deployment.
"""
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

DIST = Path(__file__).resolve().parents[1] / 'dist'

class Handler(BaseHTTPRequestHandler):
    def send_file(self, file, mime=None):
        if not file.is_file() or DIST not in file.resolve().parents:
            self.send_error(404)
            return
        data = file.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mime or mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, obj):
        data = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/allmusic':
            self.send_response(308)
            self.send_header('Location', '/allmusic/')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        if path in ('/allmusic/', '/allmusic/radio'):
            return self.send_file(DIST / 'index.html', 'text/html; charset=utf-8')
        if path.startswith('/allmusic/assets/'):
            relative = path.removeprefix('/allmusic/')
            if '..' in Path(relative).parts:
                return self.send_error(403)
            return self.send_file(DIST / relative)
        if path == '/allmusic/radio/now':
            return self.send_json({
                'playing': False, 'track': None, 'queue': [],
                'history': [], 'top_requested': [], 'moods': [], 'stream_url': ''
            })
        if path == '/allmusic/playlists':
            return self.send_json([])
        if path == '/allmusic/tracks/public':
            return self.send_json({'tracks': []})
        self.send_error(404)

    def log_message(self, fmt, *args):
        if '/assets/' not in str(args):
            super().log_message(fmt, *args)

if __name__ == '__main__':
    print('AllMusic smoke server listening on 127.0.0.1:8123', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8123), Handler).serve_forever()
