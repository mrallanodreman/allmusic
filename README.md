# AllMusic

Proyecto único de AllMusic: plataforma web, mini-app de escritorio y radio 24/7
que suena en el Atico. Antes esto vivía en tres sitios (web en `allmusic-backend`,
app en el repo público `AllMusic2.0` y la radio sin versionar en disco); ahora todo
está aquí y este repo es la fuente de verdad.

## Layout

| ruta | qué es | dónde corre |
|---|---|---|
| `backend/allmusic_server.py` | API AllMusic (búsqueda, conversión, cola de radio) | Railway, servicio `allmusic-server` |
| `backend/radio-live.py` | motor de la radio: lee la cola y transcodifica a MP3 192kbps/44.1kHz | contenedor EdgeRadio **y** `allmusic-radio-live.service` en el VAIO (`:2427`) |
| `frontend/` | sitio web + assets de la radio (C24, moods, artistas) | servido por el backend |
| `desktop/allmusic2.py` | mini-player GTK de escritorio (oculto con F9 / launcher) | en el PC del usuario, contra la API |
| `radio/atico-player.py` | manda el stream a `media_player.atico` vía Home Assistant | `atico-player.service` (solo VAIO) |
| `radio/AGENTS.md` | doc operativa del pipeline (leer antes de tocar la radio) | — |
| `start.sh`, `Dockerfile`, `railway.json` | arranque conjunto backend+radio y build/deploy | Railway |

## Pipeline de la radio

```
Web (Railway · edgemarketing.art/allmusic)   <- fuente de verdad: pedidos + rotación
  v
backend/radio-live.py (ffmpeg, :2427) -> MP3 continuo
  v
Cloudflare Tunnel (edgemail-tunel) -> https://mail.edgemarketing.art/radio/live.mp3
  v
radio/atico-player.py -> media_player.atico (bocina del Atico)
```

Atico y la web suenan la **misma** cola: el master local lidera desde la web, que es
donde viven los pedidos de los oyentes.

## Seguridad y decisiones clave (auditoría 2026-10)

- **Sin endpoints de admin**: todo acceso de moderación es solo servidor↔servidor
  con `MODERATOR_KEY` (header `X-Moderator-Key`). `ALLMUSIC_ADMIN_KEY` queda como
  alias deprecado. Endpoints `/admin/*`, `/radio/blacklist`, `GET /users` retirados (404).
- **Subidas de audio**: whitelist de extensiones + firma (magic bytes) + límite de
  tamaño. Segunda capa: VirusTotal por SHA-256. Detalle solo en logs; el usuario
  recibe mensajes de validación útiles sin revelar internas.
- **Auth artistas**: JWT HS256 (30 min) firmado con `JWT_SECRET`, bcrypt (legacy
  SHA-256 se migra al primer login), rate limit 5/min en login/register.
- **"Nunca Confiar en el Usuario"**: rate limiting por IP en todos los endpoints
  sensibles. Solo clientes marcados (≥6 intentos sensibles/60s o 429) reciben
  fingerprint silencioso (pantalla+tz+idioma+UA+geo IP), retenido **máx. 15 días**
  y borrado automático. Clientes normales no se capturan.
- **Errores interno-only**: `str(e)` nunca llega al usuario; respuestas genéricas
  + logs detallados. `/status` solo devuelve `{'status':'running'}`.
- **Cabeceras**: CSP, HSTS, nosniff, frame-deny, Referrer-Policy en todas las rutas.
- **Caché delimitada**: conversión TTL 30 min / 200 entradas; búsquedas TTL 5 min / 100;
  JSON DB con caché por `mtime`; miniaturas desktop ≤100.
- **Tests**: `backend/tests/test_security.py` (auth, rate limit, validación, headers).

## Variables de entorno

Ver `.env.example`. Obligatorias en producción: `MODERATOR_KEY`, `JWT_SECRET`,
`RAPIDAPI_KEY`, `VIRUSTOTAL_API_KEY`. Sin ellas, los endpoints afectados fallan
de forma segura (fail-closed).

## Nota operativa: error de Terminal en Coolify (restricción de Cloudflare)

Si el panel **Terminal/Exec** de Coolify muestra `Terminal websocket connection lost` / `WebSocket error occurred`:

- Es una restricción de Cloudflare, no del código. El Terminal usa un WebSocket (`wss://`).
- Soluciones: en Cloudflare **Network → WebSockets: on** y **SSL/TLS → Full (strict)** (evitar “Flexible”).
- No tocar código de AllMusic para este error.

## Runtime vs repo

- El backend/radio se despliega en Railway con `Dockerfile` + `start.sh`
  (proyecto `allmusic`, servicio `allmusic-server`, entorno `production`).
- La radio se **ejecuta** en el VAIO desde
  `/run/media/pctorre/HddCompiler/allmusic-radio/` (servicios user systemd
  `allmusic-radio-live` y `atico-player`), no desde este repo: el disco de
  ejecutables es HddCompiler según la política de discos. Este repo es el origen
  del código — se versiona aquí primero y luego se propaga al runtime.
- `radio/AGENTS.md` y `desktop/README.md` son de uso local del VAIO.

## Web

- URL pública: <https://edgemarketing.art/allmusic>
- La app de escritorio habla con la API por URL configurable
  (`desktop/config.example.json`).

## Estado conocido

- El *fallback* a la IA local `:2426` (EdgeRadio IA) está muerto en el VAIO: no hay
  ningún proceso escuchando en ese puerto, aunque `backend/radio-live.py` y
  `radio-atico.sh` lo referencian.
- `radio-atico.sh` apunta a `:2426` y a endpoints `/search` y `/convert` que ya no
  existen; la API de la radio en el VAIO está en `:2427`.
- El servicio `allmusic-server` de Railway no tiene despliegues activos.
- El repo público `mrallanodreman/AllMusic2.0` queda como puntero a este monorepo.
