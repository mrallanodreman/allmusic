"""Pruebas mínimas de seguridad: auth, rate limiting y validación de entradas."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

os.environ.setdefault('MODERATOR_KEY', 'test-mod-key')
os.environ.setdefault('VIRUSTOTAL_STRICT', 'false')

import importlib.util

_spec = importlib.util.spec_from_file_location(
    'allmusic_server',
    os.path.join(os.path.dirname(__file__), '..', 'allmusic_server.py'),
)
srv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(srv)


@pytest.fixture()
def client():
    srv.app.config['TESTING'] = True
    srv._ip_hits.clear()
    try:
        os.remove(srv.ABUSE_FILE)
    except OSError:
        pass
    with srv.app.test_client() as c:
        yield c


def test_login_requires_email_and_password(client):
    r = client.post('/artists/auth/login', json={})
    assert r.status_code == 400


def test_login_wrong_password(client):
    client.post('/artists/auth/register', json={
        'email': 'artista@example.com', 'password': 'pass12345', 'artist_name': 'X'})
    r = client.post('/artists/auth/login', json={'email': 'artista@example.com', 'password': 'mal'})
    assert r.status_code == 401
    assert r.get_json()['error'] == 'Email o contraseña incorrectos'


def test_login_rate_limit(client):
    last = None
    for _ in range(6):
        last = client.post('/artists/auth/login', json={'email': 'x@y.co', 'password': 'z'})
    assert last.status_code == 429
    assert last.get_json()['error']


def test_register_validation_email(client):
    r = client.post('/users/register', json={'email': 'no-es-email', 'name': 'n'})
    assert r.status_code == 400


def test_register_password_too_short(client):
    r = client.post('/artists/auth/register', json={
        'email': 'a@b.co', 'password': '123', 'artist_name': 'X'})
    assert r.status_code == 400


def test_stream_invalid_id(client):
    r = client.get('/stream/xyz')
    assert r.status_code == 400


def test_moderate_endpoint_requires_key(client):
    r = client.post('/radio/master', json={'playing': False})
    assert r.status_code == 401


def test_moderate_endpoint_accepts_key(client):
    r = client.post('/radio/master', json={'playing': False},
                    headers={'X-Moderator-Key': 'test-mod-key'})
    assert r.status_code == 200


def test_status_minimal(client):
    r = client.get('/status')
    assert r.status_code == 200
    body = r.get_json()
    assert body == {'status': 'running'}
    assert 'endpoints' not in body


def test_security_headers_present(client):
    r = client.get('/status')
    assert r.headers.get('X-Content-Type-Options') == 'nosniff'
    assert r.headers.get('Strict-Transport-Security')
    assert r.headers.get('Content-Security-Policy')


def test_fingerprint_endpoint(client):
    r = client.post('/abuse/fingerprint',
                    json={'screen': '1920x1080', 'tz': 'America/Guayaquil', 'lang': 'es'})
    assert r.status_code == 200
    assert r.get_json()['ok'] is True
