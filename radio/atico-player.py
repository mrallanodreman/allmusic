#!/usr/bin/env python3
"""AtiCo-Player — conecta la IA Radio 24/7 de AllMusic con la bocina del Atico.

Lee el estado de la radio (radio_state.json / /radio/now) y, cuando cambia el
track actual, ordena a Home Assistant reproducir su link en media_player.atico.

Además:
  - Detecta el fin REAL de la pista (media_duration/media_position de HA) y pide
    a la radio avanzar (POST /radio/advance) justo antes de que termine, para que
    la siguiente ya esté lista y no haya corte ni silencio.
  - Si el Cast queda en idle sin que cambie el current, lo re-dispara.
"""
import json
import time
import urllib.request
import urllib.error
import sys
import os

RADIO = os.environ.get('RADIO_URL', 'http://127.0.0.1:2426')
MASTER_URL = os.environ.get('MASTER_URL', 'https://edgemarketing.art/allmusic')
MASTER_ADMIN_KEY = os.environ.get('ALLMUSIC_ADMIN_KEY', '')
LIVE_STREAM_URL = os.environ.get('LIVE_STREAM_URL', 'https://mail.edgemarketing.art/radio/live.mp3')
HA_URL = os.environ.get('HA_URL', 'http://127.0.0.1:8124')
HA_TOKEN_PATH = '/dev/shm/ha_token.txt'
SPEAKER = 'media_player.atico'
POLL = float(os.environ.get('POLL', '3'))
FADE_AHEAD = float(os.environ.get('FADE_AHEAD', '6'))  # avanza 6s antes del final


def ha_token():
    with open(HA_TOKEN_PATH) as f:
        return f.read().strip()


def ha_get(path):
    req = urllib.request.Request(HA_URL + path, headers={'Authorization': f'Bearer {ha_token()}'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        raise RuntimeError(f'HA GET {path} -> {e.code}: {body}')


def ha_post(path, payload):
    req = urllib.request.Request(
        HA_URL + path,
        data=json.dumps(payload).encode(),
        headers={'Authorization': f'Bearer {ha_token()}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        raise RuntimeError(f'HA POST {path} -> {e.code}: {body}')


def radio_get(path):
    with urllib.request.urlopen(RADIO + path, timeout=10) as r:
        return json.loads(r.read().decode())


def radio_post(path, payload=None):
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        RADIO + path, data=data,
        headers={'Content-Type': 'application/json'}, method='POST',
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def publish_master(now, track, playing, elapsed):
    if not MASTER_ADMIN_KEY or not track:
        return
    public_track = dict(track)
    public_track['elapsed'] = max(0, elapsed or public_track.get('elapsed') or 0)
    payload = {
        'playing': bool(playing),
        'track': public_track,
        'queue': now.get('queue', []),
        'history': now.get('history', []),
        # Unifica ranking de "más pedidos" local <-> nube (ver allmusic_server.py
        # /radio/master): la nube fusiona esto como peer_count, no lo suma directo.
        'request_stats_top': now.get('top_requested', []),
    }
    req = urllib.request.Request(
        MASTER_URL + '/radio/master',
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'X-Admin-Key': MASTER_ADMIN_KEY},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def play_url(url):
    # El Atico es un Nest Mini: reproduce bien streams LIVE continuos (como el
    # master de la IA Radio). Servirlo como audio/mpeg hace que el Cast lo trate
    # como radio y no lo corte por buffering.
    ha_post('/api/services/media_player/play_media',
            {'entity_id': SPEAKER, 'media_content_id': url, 'media_content_type': 'audio/mpeg'})
    time.sleep(1.5)
    try:
        ha_post('/api/services/media_player/media_play', {'entity_id': SPEAKER})
    except Exception:
        pass


def speaker_state():
    try:
        s = ha_get(f'/api/states/{SPEAKER}')
    except Exception:
        return None, None, None
    attrs = s.get('attributes', {})
    return s.get('state'), attrs.get('media_position'), attrs.get('media_duration')


def main():
    stream_started = False
    log("🎧 AtiCo-Player iniciado. Maestro:", LIVE_STREAM_URL)
    while True:
        try:
            now = radio_get('/radio/now')
            track = now.get('track') if isinstance(now, dict) else None
            playing = now.get('playing', False) if isinstance(now, dict) else False
            sp, pos, dur = speaker_state()

            if not stream_started:
                try:
                    play_url(LIVE_STREAM_URL)
                    stream_started = True
                except Exception as e:
                    log('⚠ play maestro fallo:', e)
                    stream_started = False

            # Heartbeat del estado hacia el master/dashboard
            try:
                publish_master(now, track, sp == 'playing', pos)
            except Exception as e:
                log('⚠ heartbeat master fallo:', e)

            # Si el Cast queda idle pero la radio está reproduciendo, re-dispara
            if sp == 'idle' and playing:
                log('🔄 Cast idle, re-disparando el stream maestro')
                try:
                    play_url(LIVE_STREAM_URL)
                    stream_started = True
                except Exception as e:
                    log('⚠ re-play fallo:', e)
                    stream_started = False
                time.sleep(POLL)
                continue

        except Exception as e:
            log('! error:', e)
        time.sleep(POLL)


def log(*args):
    print(time.strftime('%F %T'), *args, flush=True)


if __name__ == '__main__':
    main()
