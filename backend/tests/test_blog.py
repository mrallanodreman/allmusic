"""Pruebas del blog SEO de artistas servido por el backend."""
import importlib.util
import os
import sys

import pytest

sys_path = os.path.join(os.path.dirname(__file__), '..')
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

os.environ.setdefault('MODERATOR_KEY', 'test-mod-key')
os.environ.setdefault('VIRUSTOTAL_STRICT', 'false')

_spec = importlib.util.spec_from_file_location(
    'allmusic_server_blog',
    os.path.join(sys_path, 'allmusic_server.py'),
)
srv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(srv)


@pytest.fixture()
def client():
    srv.app.config['TESTING'] = True
    with srv.app.test_client() as c:
        yield c


def test_blog_index_json_expone_los_dos_articulos(client):
    r = client.get('/blog/artists.json')
    assert r.status_code == 200
    data = r.get_json()
    slugs = {item['slug'] for item in data['articles']}
    assert {'razimbrain-apnea-lxxi', 'vittorio-kultururbana-2026'} <= slugs


def test_articulo_es_html_indexable_con_canonical_y_schema(client):
    r = client.get('/blog/razimbrain-apnea-lxxi/')
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert '<link rel="canonical" href="https://mfmood.com/blog/razimbrain-apnea-lxxi/">' in html
    assert 'application/ld+json' in html
    assert '"@type": "Article"' in html
    assert '<h1>Razimbrain: APNEA y las nueve piezas de LXXI</h1>' in html
    assert 'Escuchar APNEA' in html


def test_articulo_inexistente_da_404(client):
    assert client.get('/blog/no-existe/').status_code == 404


def test_sitemap_incluye_articulos(client):
    r = client.get('/sitemap.xml')
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert 'https://mfmood.com/blog/razimbrain-apnea-lxxi/' in body
    assert 'https://mfmood.com/blog/vittorio-kultururbana-2026/' in body
