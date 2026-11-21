# AllMusic

Proyecto único de AllMusic: plataforma web, mini-app de escritorio y radio 24/7
que suena en el Atico. Antes esto vivía en tres sitios (web en `allmusic-backend`,
app en el repo público `AllMusic2.0` y la radio sin versionar en disco); ahora todo
está aquí y este repo es la fuente de verdad.

> 🙋 ¿Eres colaborador? Antes de tocar infra lee el
> **[Reporte de errores y permisos](#-reporte-de-errores-y-permisos-para-colaboradores)**.

## Layout

| ruta | qué es | dónde corre |
|---|---|---|
| `backend/allmusic_server.py` | API AllMusic (búsqueda, conversión, cola de radio) | web pública: túnel Cloudflare → warmachine `192.168.1.4/.5:2426` (contenedor Coolify `radio`); copia local en VAIO (`allmusic-radio.service`, `:2426`) |
| `backend/radio-live.py` | motor de la radio: lee la cola y transcodifica a MP3 192kbps/44.1kHz | master activo: `allmusic-radio-live.service` en el VAIO (`:2427`) |
| `frontend/` | sitio web + assets de la radio (C24, moods, artistas) | servido por el backend |
| `desktop/allmusic2.py` | mini-player GTK de escritorio (oculto con F9 / launcher) | en el PC del usuario, contra la API |
| `radio/atico-player.py` | manda el stream a `media_player.atico_2` vía Home Assistant | `atico-player.service` (solo VAIO) |
| `radio/AGENTS.md` | doc operativa del pipeline (leer antes de tocar la radio) | — |
| `start.sh`, `Dockerfile`, `railway.json` | arranque conjunto backend+radio y build/deploy | `Dockerfile` → Coolify/warmachine (autodeploy desde GitHub); `railway.json` es legacy de Railway |

## Hosting y despliegue (fuente de verdad)

**La web se hostea en Coolify, no en checkouts locales ni en Railway.** El repositorio
de GitHub `mrallanodreman/allmusic` (rama `master`) se conecta a Coolify mediante
webhook; cada push despliega el app `radio` (id `10`, UUID
`9bzhluyvn5v7u8eyro5nllul`) en warmachine como contenedor `allmusic-radio :2426`.

```
GitHub mrallanodreman/allmusic (master)
  └─ push ──> webhook 693647409
               URL  https://app.edgemarketing.tech/webhooks/source/github/events/manual
               secreto compartido con Coolify (manual_webhook_secret_github del app radio)
                  └─> Coolify: queue_application_deployment("radio")
                        └─> Dockerfile multi-stage -> contenedor allmusic-radio :2426
                              └─> túnel Cloudflare ~/.cloudflared/edgemarketing-web.yml
                                    hostname edgemarketing.tech / www
                                    path ^/allmusic(?:/.*)?$ -> http://192.168.1.5:2426
```

Si GitHub devuelve 200 pero no se despliega, revisar el audit de Coolify:
`webhook.github.signature_failed` = el secreto del hook no coincide con el de Coolify;
`webhook.deployment.queued` = ok. Comprobar con
`GET /repos/mrallanodreman/allmusic/hooks/693647409/deliveries`.

"Radio IA" **no es un subdominio**: es la pestaña del reproductor en
`edgemarketing.tech/allmusic/` que carga un iframe `./radio?embedded=1` servido por
este mismo backend. Rutas: `/radio` (UI React), `/radio-legacy` (dashboard anterior),
`/radio/now` (datos reales), `/assets/*` (JS/CSS/PNG del build).

Los checkouts del sitio EdgeMarketing que definen `ALLMUSIC_UPSTREAM` apuntando a
`allmusic-server-production.up.railway.app` **no están en la ruta pública de
`/allmusic`**: ese túnel va directo al backend de Coolify. Railway está retirado;
no hace falta editar esos checkouts para publicar cambios de AllMusic.

Verificación tras un push: el audit debe mostrar `webhook.deployment.queued` y
`curl http://192.168.1.5:2426/radio` debe servir `id="root"` y `assets/index-*.js`.

## Pipeline de la radio

```
Web (edgemarketing.tech/allmusic -> túnel CF -> Coolify :2426)  <- fuente de verdad: pedidos + rotación
  v
backend/radio-live.py (VAIO, ffmpeg, :2427) -> MP3 continuo
  v
stream LAN http://192.168.1.2:2427/live.mp3   (público: https://mail.edgemarketing.art/radio/live.mp3, HOY ROTO — ver Estado conocido)
  v
radio/atico-player.py -> media_player.atico_2 (bocina del Atico)
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

## Nota operativa: Terminal/Exec en Coolify

Si el panel **Terminal/Exec** de Coolify muestra `Terminal websocket connection lost` / `WebSocket error occurred`:

- El Terminal usa WebSocket; **primero intentar por IP directa** de warmachine: `http://192.168.1.4:8000` (sin Cloudflare de por medio).
- Verificado 2026-10-08 en la zona `edgemarketing.art`: **WebSockets: on** y **SSL/TLS: full** ya estaban. No subir a `Full (strict)`: el origen (warmachine) sirve el certificado *default* de Traefik (self-signed) y strict rompería el sitio con 526.
- Stack de realtime de Coolify (soketi `:6001`) verificado vivo — el WS no lo bloquea nada en infra.
- Si aun así falla vía Cloudflare, no es el código de AllMusic: revisar en la consola de Coolify los **permisos del usuario/miembro** sobre el recurso `radio` (rol) antes de tocar el backend.

## Runtime vs repo

- El backend se despliega en **warmachine (Coolify)** con el `Dockerfile` del repo
  (autodeploy desde GitHub, servicio app `radio`, `192.168.1.4:2426`). El servicio
  `allmusic-server` de **Railway quedó sin deploys** (trial vencido 2026-09-10) y
  `railway.json` queda como legacy.
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

## Estado conocido (verificado 2026-10-07)

- `:2426` en el VAIO **sí está vivo** (`allmusic-radio.service`, copia local del
  backend): `radio-atico.sh` apunta a `127.0.0.1:2426` y `/search` + `/convert`
  existen y responden. `:2427` es el stream MP3 del master, no una API.
- `atico-player.service` usa `LIVE_STREAM_URL=http://192.168.1.2:2427/live.mp3`
  (master LAN del VAIO). Ojo: la IP es por DHCP — si cambia, actualizar la unit.
  Entidad vieja `media_player.atico` quedó `unavailable` tras el cambio de red;
  la activa es `media_player.atico_2`.
- El stream público `https://mail.edgemarketing.art/radio/live.mp3` responde **502 Bad
  Gateway** (antes 404): la regla del túnel (`mail → 192.168.1.4:2123`) apunta al gateway de
  warmachine, que no responde. Ver **E1** en el reporte de errores.
- El servicio `allmusic-server` de Railway no tiene despliegues activos.
- El repo público `mrallanodreman/AllMusic2.0` queda como puntero a este monorepo.

## 🚨 Reporte de errores y permisos (para colaboradores)

> Verificado **2026-10-09** (web en vivo + API de Coolify).
> ⚠️ **Sin secretos aquí**: este es un reporte para trabajar, no un volcado de claves.
> Ningún token/env de producción va en este repo. Si necesitas uno, pídelo por canal privado y
> rótalo solo en Coolify.

### 🐛 Errores y problemas (estado actual)

| # | Problema | Síntoma | Causa probable | Dónde se arregla | Estado |
|---|---|---|---|---|---|
| E1 | Stream público de la radio caído | `https://mail.edgemarketing.art/radio/live.mp3` → **502 Bad Gateway** | Túnel Cloudflare `mail` → `192.168.1.4:2123`; el gateway de warmachine no responde | Cloudflare Tunnel **y** warmachine (SSH) | 🔴 activo |
| E2 | Cola de radio y master sin conectar | `/allmusic/radio/now` → `playing:true` pero `queue:0`, `top_requested:0`, `master:false`, `master_offline:false` | El master local (VAIO `:2427`) no publica rotación/pedidos; `radio-live.py` fuera o sin feed | VAIO: `allmusic-radio-live.service` + `atico-player.service` | 🔴 activo |
| E3 | Autodeploy GitHub→Coolify **no dispara** | `git push` a `master` no redeployaba | Webhook apuntaba al dominio viejo `.art` (502) y GitHub no tenía el secreto que Coolify exige (`webhook.github.signature_failed`) | Fix 2026-11-21: URL → `app.edgemarketing.tech` y secreto alineado con `manual_webhook_secret_github` de `radio`; verificado `webhook.deployment.queued` | 🟢 resuelto |
| E4 | Terminal/Exec de Coolify | `Terminal websocket connection lost` / `WebSocket error occurred` | Ya verificado WebSockets:on y SSL:full en CF y soketi vivo → sospecha: **rol del miembro** sobre el recurso `radio` | Coolify (roles) o Terminal por IP directa `http://192.168.1.4:8000` | 🔴 activo |
| E5 | Cabina de IA Radio (iframe) en blanco | `X-Frame-Options: DENY` bloqueaba el iframe `radio.html?embedded=1` | Cabecera demasiado estricta | Fix `SAMEORIGIN` en `92050aa` — **ya desplegado y verificado** | 🟢 resuelto |
| E6 | Reproducir desde Historial fallaba | Error `MEDIA_ERR`/JS al reproducir desde Historial; Búsqueda sí funcionaba | El historial guardaba enlaces directos que **expiran** | Fix: guardar `videoId` y resolver enlace fresco (`3077d67`) | 🟢 resuelto |
| E7 | Errores de consola “violates CSP” (adsense/cloudflareinsights) | Scripts legítimos bloqueados por CSP estricta | CSP nueva demasiado cerrada | Fix: permitir `pagead2.googlesyndication.com` y `static.cloudflareinsights.com` + `frame-src`/`connect-src` | 🟢 resuelto |
| E8 | Logo SVG roto | `allmusic-logo.svg` no servía | Base href / prefijo `/allmusic/` | Fix de `frontend_files` — 200 `image/svg+xml` | 🟢 resuelto |

Detalle de E2 (verificado en vivo): la API declara `playing:true` pero con cola vacía no hay
rotación real; el Ático depende del master local, no del contenedor.

### 🔐 Permisos y roles que necesitamos (para editar sin fricción)

"Poder hacer lo que sea sin problemas" = cada colaborador debe tener el rol mínimo **suficiente**
para diagnosticar y desplegar. Esto NO significa compartir contraseñas: se otorgan **roles** y
**tokens con scope** (mínimo privilegio).

| Plataforma | Qué necesitamos | Para qué | Rol sugerido |
|---|---|---|---|
| GitHub `mrallanodreman/allmusic` | Admin/Maintain para **@TheBooth** y **@Dazm22** | editar settings, webhooks, branch protection, colaboradores, releases | **Admin** |
| Coolify (proyecto EdgeRadio, servicio `radio`) | Rol **Owner/Admin** del equipo + token de API | deploy/restart, ver logs, editar variables, Terminal/Exec | **Owner** |
| Cloudflare (zona `edgemarketing.art`) | Edición de zona (no contraseña) | Network → WebSockets, SSL/TLS, arreglar túnel `mail` | **Member (edit)** |
| warmachine `192.168.1.4` | Acceso **SSH** | revisar gateway `:2123`, Traefik, contenedor, ruta del túnel | usuario admin |
| VAIO (radio local) | acceso systemd `allmusic-radio-live` / `atico-player` | arreglar stream local `:2427` y la cola | usuario con systemd |
| RapidAPI / VirusTotal | **ya configuradas** en Coolify (verificado: `/convert` responde) | conversión y sanitizado de subidas | set en Coolify |

⚠️ **Regla de oro:** los secretos viven solo en Coolify (variables del entorno) y en respaldos
**cifrados**. Si alguien te pide una clave por el repo/issue, no la des por escrito en GitHub.

### 🛠 Guía para ayudar a arreglar (checklist por error)

1. **E1 (stream público):** con acceso al túnel CF y SSH a warmachine, validar que `192.168.1.4:2123`
   responda y revisar las rutas de Traefik para el host `mail`.
2. **E2 (cola/master):** en el VAIO: `systemctl --user status allmusic-radio-live` y `atico-player`.
   Fijar `LIVE_STREAM_URL` (la IP es por **DHCP**; hoy apunta a `192.168.1.2:2427`).
3. **E3 (autodeploy):** resuelto 2026-11-21. Webhook `693647409` → `https://app.edgemarketing.tech/webhooks/source/github/events/manual`
   con el mismo secreto que Coolify; un push de prueba encoló `webhook.deployment.queued` para `radio`.
4. **E4 (Terminal):** subir el rol del miembro en Coolify o probar el Terminal por IP directa
   (`http://192.168.1.4:8000`) para aislar si es Cloudflare.
5. Marcar avances en el issue **#1** (issues → commits → pushes).

### 📌 Resumen

- Web y API **operativas**: `/status`, `/search`, `/convert`, `/radio/now`, logo, cabeceras → OK.
- Tests de seguridad: **11/11 passing**.
- Quedan **3 errores activos**, todos de **infraestructura** (túnel, master local y rol de Coolify),
  no de código del backend. El autodeploy quedó restablecido el 2026-11-21.
- La lista de permisos de arriba desbloquea a los colaboradores para resolverlos solos.
