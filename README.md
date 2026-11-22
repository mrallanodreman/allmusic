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
| `frontend-react/` | AllMusic principal: Radio IA, biblioteca, playlists, cuentas de artistas y cartelera | `/allmusic/` (también `/radio`), build de Vite dentro del contenedor Coolify |
| `docs/AI_HANDOFF_RADIO.md` | handoff del estado final de la UI y cómo verificar el deploy | — |
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

Desde la migración a la UI principal (22-nov-2026), **AllMusic es una sola web React**:
`/allmusic/` carga directamente la cabina Canal 24 con playlists, Tu Música
(autenticación y uploads de artistas), descubrimiento y cartelera; ya no es un
iframe dentro del sitio clásico. `/radio` conserva el mismo build como alias.
`/classic` conserva `modern_index.html` temporalmente por compatibilidad.
`/radio-legacy` conserva el tablero antiguo. `/radio/now` y la API
continúan sin cambios de estructura. El token de artistas se recupera desde
`am_artist_token`; las playlists del backend siguen siendo compartidas.

Los checkouts del sitio EdgeMarketing que definen `ALLMUSIC_UPSTREAM` apuntando a
`allmusic-server-production.up.railway.app` **no están en la ruta pública de
`/allmusic`**: ese túnel va directo al backend de Coolify. Railway está retirado;
no hace falta editar esos checkouts para publicar cambios de AllMusic.

Verificación tras un push: el audit debe mostrar `webhook.deployment.queued` y
`curl http://192.168.1.5:2426/allmusic/radio` debe servir `id="root"` y `assets/index-*.js`.


## Migración de UI principal (noviembre 2026)

**Entrada pública:** `https://edgemarketing.tech/allmusic/` → `backend/allmusic_server.py::index` → `frontend-react-dist/index.html`.
El servidor conserva `/classic` para revertir visualmente sin cambiar datos y
`/radio` como alias. Si falta el build React, se entrega el HTML clásico como
fallback. El menú React dirige a `#playlists`, `#mymusic` y `#cartelera`.

La biblioteca React reutiliza las rutas existentes `/playlists`,
`/tracks/public`, `/artists/auth/*`, `/artists/profile`, `/tracks` y
`/premium/*`. El reproductor tiene una sola etiqueta audio para emisora y
música personal. El historial personal conserva la clave `am_played`.

**Advertencia de datos:** el backend clásico mantiene las playlists globales
sin control de propiedad. El nuevo panel avisa que son compartidas y que no
deben almacenar información privada. Esto requiere una migración posterior
de ACL/cuentas antes de ofrecer listas privadas.

**Reversión si falla el layout:** `/classic` sigue disponible para el frontend
antiguo sin tocar archivos de artistas ni sus claves. Para revertir el index en
servidor, cambiar la prioridad de `index()` y redeplegar; no restaurar el repo
entero ni la base de datos. Comprobar `npm run build` y la web externa
tras el despliegue de Coolify.

## Pipeline de la radio

```
Web (edgemarketing.tech/allmusic -> túnel CF -> Coolify :2426)  <- fuente de verdad: pedidos + rotación
  v
backend/radio-live.py (VAIO, ffmpeg, :2427) -> MP3 continuo
  v
stream LAN http://192.168.1.2:2427/live.mp3   (público: https://mail.edgemarketing.art/radio/live.mp3, sin verificar — ver E1/E2)
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

## Estado conocido (verificado 2026-11-21)

- `:2426` responde por la IP interna: `/allmusic/status` → `{"status":"running"}`,
  y `/search`, `/radio`, `/radio/top`, `/radio/queue`, `/radio/history`,
  `/assets/allmusic-logo.svg` → 200. `:2427` es el stream MP3 del master, no una API.
- La UI React servida en `/radio` es el **diseño fanzine** (`64711c7`), con bundle
  `index-_ctsnuPU.js` + `index-mslemx7l.css`. El artboard C24 y la capa RETRO
  quedaron en el historial de commits pero **no están activos**. Handoff en
  `docs/AI_HANDOFF_RADIO.md`.
- `atico-player.service` usa `LIVE_STREAM_URL=http://192.168.1.2:2427/live.mp3`
  (master LAN del VAIO). Ojo: la IP es por DHCP — si cambia, actualizar la unit.
  Hoy `192.168.1.2:2427` **no responde** y `/radio/now` declara `playing:true`
  con `queue:[]`, `now:null`, `master:false` → ver **E2**.
  Entidad vieja `media_player.atico` quedó `unavailable` tras el cambio de red;
  la activa es `media_player.atico_2`.
- El stream público `https://mail.edgemarketing.art/radio/live.mp3` daba **502 Bad
  Gateway** en chequeos anteriores. El 2026-11-21 el gateway `192.168.1.4:2123`
  sí acepta TCP, pero `mail.edgemarketing.art` no resuelve DNS desde este entorno:
  no se pudo confirmar el arreglo. Ver **E1**.
- Este entorno tampoco resuelve `edgemarketing.art`; las verificaciones públicas
  hay que hacerlas desde otra red. Las URL internas sí son verificables.
- El servicio `allmusic-server` de Railway no tiene despliegues activos.
- El repo público `mrallanodreman/AllMusic2.0` queda como puntero a este monorepo.

## 🚨 Reporte de errores y permisos (para colaboradores)

> Actualizado **2026-11-21**: endpoints internos, build de la UI React, deliverys
> del webhook de GitHub y 11 tests de seguridad reejecutados.
> ⚠️ Las URL públicas (`edgemarketing.art`, `mail.edgemarketing.art`) no se pudieron
> revalidar: este entorno no resuelve esos DNS.
> ⚠️ **Sin secretos aquí**: este es un reporte para trabajar, no un volcado de claves.
> Ningún token/env de producción va en este repo. Si necesitas uno, pídelo por canal privado y
> rótalo solo en Coolify.

### 🐛 Errores y problemas (estado actual)

| # | Problema | Síntoma | Causa probable | Dónde se arregla | Estado |
|---|---|---|---|---|---|
| E1 | Stream público de la radio sin verificar | 502 en 2026-10-09; el 2026-11-21 `mail.edgemarketing.art` no resuelve DNS desde este entorno (el gateway `192.168.1.4:2123` sí acepta TCP) | Túnel Cloudflare `mail` → `192.168.1.4:2123`; queda corroborar ruta/Traefik y DNS público | Cloudflare Tunnel **y** warmachine (SSH), desde otra red | 🟡 pendiente de verificación pública |
| E2 | Cola de radio y master sin conectar | `/allmusic/radio/now` → `playing:true`, `queue:[]`, `top_requested:[]`, `now:null`, `master:false`; `192.168.1.2:2427` no responde (2026-11-21) | El master local (VAIO `:2427`) no publica rotación/pedidos; `radio-live.py` fuera o sin feed | VAIO: `allmusic-radio-live.service` + `atico-player.service` (IP DHCP) | 🔴 activo |
| E3 | Autodeploy GitHub→Coolify **no dispara** | `git push` a `master` no redeployaba | Webhook apuntaba al dominio viejo `.art` (502) y GitHub no tenía el secreto que Coolify exige (`webhook.github.signature_failed`) | Fix 2026-11-21: URL → `app.edgemarketing.tech` y secreto alineado con `manual_webhook_secret_github` de `radio`. Deliverys `23:15`, `23:22`, `23:28` y `23:30Z` → `200`; bundle servido `index-_ctsnuPU.js` | 🟢 resuelto |
| E4 | Terminal/Exec de Coolify | `Terminal websocket connection lost` / `WebSocket error occurred` | Ya verificado WebSockets:on y SSL:full en CF y soketi vivo → sospecha: **rol del miembro** sobre el recurso `radio` | Coolify (roles) o Terminal por IP directa `http://192.168.1.4:8000` (TCP abierto 2026-11-21; WS no probado sin sesión) | 🟡 sin cambios confirmados |
| E5 | Cabina de IA Radio (iframe) en blanco | `X-Frame-Options: DENY` bloqueaba el iframe `radio.html?embedded=1` | Cabecera demasiado estricta | Fix `SAMEORIGIN` en `92050aa` — **ya desplegado y verificado** | 🟢 resuelto |
| E6 | Reproducir desde Historial fallaba | Error `MEDIA_ERR`/JS al reproducir desde Historial; Búsqueda sí funcionaba | El historial guardaba enlaces directos que **expiran** | Fix: guardar `videoId` y resolver enlace fresco (`3077d67`) | 🟢 resuelto |
| E7 | Errores de consola “violates CSP” (adsense/cloudflareinsights) | Scripts legítimos bloqueados por CSP estricta | CSP nueva demasiado cerrada | Fix: permitir `pagead2.googlesyndication.com` y `static.cloudflareinsights.com` + `frame-src`/`connect-src` | 🟢 resuelto |
| E8 | Logo SVG roto | `allmusic-logo.svg` no servía | Base href / prefijo `/allmusic/` | Fix de `frontend_files` — 200 `image/svg+xml` | 🟢 resuelto |

Detalle de E2 (verificado en vivo el 2026-11-21): la API declara `playing:true` pero
`queue:[]`, `top_requested:[]`, `now:null` y `master:false`; `192.168.1.2:2427`
(master LAN, IP DHCP) no acepta conexiones. Sin cola no hay rotación real: el Ático
depende del master local, no del contenedor Coolify. `radio-live.py` y
`atico-player.service` viven en el VAIO, fuera de este repo.

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

1. **E1 (stream público):** `192.168.1.4:2123` ya acepta TCP; falta probar la URL
   pública desde otra red (aquí no resuelve DNS) y revisar las rutas de Traefik para
   el host `mail` en el túnel CF.
2. **E2 (cola/master):** en el VAIO: `systemctl --user status allmusic-radio-live` y `atico-player`.
   `192.168.1.2:2427` está caído; fijar `LIVE_STREAM_URL` (la IP es por **DHCP**).
3. **E3 (autodeploy):** resuelto 2026-11-21. Webhook `693647409` → `https://app.edgemarketing.tech/webhooks/source/github/events/manual`
   con el mismo secreto que Coolify. Verificar con
   `GH_CONFIG_DIR=/home/pctorre/.config/gh gh api repos/mrallanodreman/allmusic/hooks/693647409/deliveries --jq '.[0] | {status_code, delivered_at}'`
   y comparando el hash de `assets/index-*.js` servido.
4. **E4 (Terminal):** subir el rol del miembro en Coolify o probar el Terminal por IP directa
   (`http://192.168.1.4:8000`, TCP abierto) para aislar si es Cloudflare.
5. Marcar avances en el issue **#1** (issues → commits → pushes; sigue abierto).

### 📌 Resumen

- Web y API **operativas por IP interna**: `/status`, `/search`, `/radio`, `/radio/top`,
  `/radio/queue`, `/radio/history`, `/radio/now`, logo y cabeceras → OK.
  El deploy responde con el bundle de la UI fanzine (`64711c7`).
- Tests de seguridad: **11/11 passing**, reejecutados el 2026-11-21 con un entorno
  aislado en `/tmp/opencode/allmusic-test` (1 `DeprecationWarning` de `datetime.utcnow()`,
  no funcional).
- Quedan **2 errores activos** (E1 sin verificación pública, E2 master local) y
  **1 pendiente de confirmación** (E4, rol/Terminal de Coolify): todos son de
  **infraestructura**, no de código del backend. El autodeploy quedó restablecido
  el 2026-11-21 (últimos deliverys `200`).
- La lista de permisos de arriba desbloquea a los colaboradores para resolverlos solos.
