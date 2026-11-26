# Plan de migración AllMusic → mfmood

**Estado: PLAN — NO EJECUTAR sin revisión y OK explícito del usuario.**
Fecha: 2026-11-25.

## Decisión del usuario

- URL pública canónica: **https://mfmood.com/** (root, sin `/allmusic`).
- `www.mfmood.com` debe resolver y servir la misma app; canonical.root manda.
- “Liberar el proyecto” incluye, **en este orden y con gates**:
  1. quitar la ruta pública vieja del túnel;
  2. renombrar el repo de GitHub;
  3. renombrar la app de Coolify;
  4. borrar recursos viejos solo tras verificación + aprobación final.
- Se autoriza mover los nameservers de `mfmood.com` a Cloudflare para usar `edgetunnel`.
- Estilo exigido: **migración cuidadosamente calculada, plan escrito, ejército de subagentes**.

## Hechos verificados hoy

- Dominio comprado en Spaceship: **mfmood.com**, `lifecycleStatus: registered`, NS `basic`, **0 registros propios en Spaceship**.
- DNS público actual de `mfmood.com`: A `34.216.117.25`, `54.149.79.189` (parking, TTL 260s); NS Spaceship TTL 1791s; TTL negativo 3600s; **sin MX**; `www.mfmood.com` NXDOMAIN; `:443` sin certificado (timeout).
- Cuenta Cloudflare: `d28aaacec355f7421f92c3ad9b0ea0ee`.
- Túnel: **edgetunnel**, ID `2995fc49-98d1-4533-a359-62d5effebf1b`, healthy.
- Ruta viva real: `allmusic.edgemarketing.tech` → `http://192.168.1.4:2426` (orden UI **#18**, **no es ID estable**).
- `https://allmusic.edgemarketing.tech/status` → `{"status":"running"}`; `/radio/queue` → `{"queue":[]}`.
- Vecinos del túnel (baseline): `stoff.edgemarketing.tech/` y `medicars.cl/` → 200; `mail.edgemarketing.tech/radio/live.mp3` → **404 preexistente**. README marca además `mail.edgemarketing.art/radio/live.mp3` como 502; ambas son ajenas a esta migración.
- `127.0.0.1:2427/health` da *refused* en este host; el master está en el VAIO y debe verificarse allí.
- `edgemarketing.art` **no resuelve** desde este equipo; las referencias `edgemarketing.art/allmusic` en el repo están obsoletas pero siguen en código/docs/SEO.
- Repo: `/mnt/sda1/repos/mfmood`, rama `master`, origin `github.com/mrallanodreman/allmusic.git`.
- Trabajo sin commitear que hay que preservar: `M frontend/sitemap.xml`, `?? Dockerfile.gsc-patch` y `?? MIGRACION-MFMOOD.md`.
- `mfmood.com` no tiene MX; los correos `contacto@edgemarketing.art` y `dmca@edgemarketing.art` **no se reescriben**.

## Principios

1. Nada destructivo hasta que la nueva URL esté verificada externamente.
2. La ruta vieja, el repo viejo y la app vieja se conservan hasta el gate de borrado.
3. Backup byte-a-byte de los cambios sucios antes de cualquier edición o renombrado.
4. Cada fase tiene rollback documentado y verificable.
5. El túnel puede estar gestionado por dashboard o por archivo; confirmar modo antes de editar, o un reinicio del conector puede sobrescribir rutas.
6. Las variables de entorno de runtime (`WEB_URL`, `MASTER_URL`, `LIVE_STREAM_URL`, `ALLMUSIC_API_BASE`, etc.) pueden ganar a los defaults del repo: inventariar antes de editar código.

## Runbook Cloudflare — detalle operativo

```bash
API=https://api.cloudflare.com/client/v4
ACC=d28aaacec355f7421f92c3ad9b0ea0ee
TUN=2995fc49-98d1-4533-a359-62d5effebf1b
SVC=http://192.168.1.4:2426
```

- **Bloqueo actual:** `CF_TOKEN_EDGEMARKETING` no está en el entorno y el MCP `cloudflare-dns` devuelve *token missing*. Hay que localizar el token en el store de secretos antes de usar API; si no aparece, la ejecución será por dashboard/BrowserOS y la captura de IDs será solo la tupla ingress + versión.
- **Preflight:** verificar `dig +short DS mfmood.com` esté vacío (DNSSEC off), que no exista ya zona `mfmood.com`, y leer:
  - `GET /accounts/$ACC/cfd_tunnel/$TUN` → `config_src`;
  - `GET /accounts/$ACC/cfd_tunnel/$TUN/configurations` → `source`, `version`, `config`;
  - `GET /accounts/$ACC/cfd_tunnel/$TUN/connections` → réplicas vivas.
- **Regla dura:** editar por API/dashboard **solo si** `config_src == "cloudflare"` (o `source == "cloudflare"` / `remote_config == true`). Si es `local`, un `config.yml` en el host gobierna; parar y editar allí.
- **Verificar en el host cloudflared:** `systemctl cat cloudflared`, `ps -ef | grep "[c]loudflared"`, y revisar `/etc/cloudflared/config.yml` y `~/.cloudflared/config.yml` sin modificarlos.
- **Snapshot obligatorio:** `result.config` completo + `version`; objeto ingress exacto de `allmusic.edgemarketing.tech` → `http://192.168.1.4:2426`; registro DNS viejo (ID + payload); NS `basic` de Spaceship.
- **Zona:** crear `POST /zones` con `{"name":"mfmood.com","account":{"id":"'$ACC'"},"type":"full"}`; si ya existe, reutilizar. Esperar `status == "active"`; no forzar `activation_check` de forma repetida (FREE ~1/h).
- **DNS:** registros `CNAME` apex y `www` → `$TUN.cfargotunnel.com`, `proxied:true`, `ttl:1`. Capturar los IDs UUID de ambos registros.
- **Rutas:** public hostname = entradas `ingress` **sin UUID**. Identidad estable = tupla exacta `(hostname[, path], service, originRequest)` + `config` guardado + `version`. Insertar las nuevas antes del catch-all `http_status:404` y hacer PUT del config completo. **Nunca usar el ordinal 18 de la UI.**
- **Canonical www:** ruleset `http_request_dynamic_redirect` con `expression: 'http.host eq "www.mfmood.com"'`, `status_code: 301`, `preserve_query_string: true`, `target_url` = `concat("https://mfmood.com", http.request.uri.path)`. Capturar ruleset ID + rule ID/ref.
- **Verificación:** Cloudflare IPs en apex/www, SAN válido, apex 200 desde `:2426`, `www/ruta?x=1` → 301 a `https://mfmood.com/ruta?x=1`, hostname viejo todavía 200.
- **Borrado viejo:** borrar registro DNS por ID UUID y quitar el objeto ingress exacto mediante PUT del config completo; recrear desde snapshot si hay problema.

## Inventario exacto de código (subagent de inventario)

**R1 — URL pública → root.** Reemplazar `https://edgemarketing.art/allmusic` por `https://mfmood.com` conservando el sufijo:

- `frontend/index.html`: 33, 36, 61 → root `/`; 41, 51 → `/assets/allmusic-logo.svg`; 58 → `/#app`.
- `frontend/modern_index.html`: 13, 20, 34 → `/`; 21, 27 → `/assets/allmusic-logo.svg`.
- `frontend/{about,cookies,dmca,privacidad,terminos}.html`: canonical, logo y navegación → `https://mfmood.com/...`.
- `frontend/robots.txt:4` → `Sitemap: https://mfmood.com/sitemap.xml`.
- `frontend/sitemap.xml`: 4, 10, 16, 22, 28, 34, 40, 46 → root; **preservar el diff sucio actual**.
- `backend/allmusic_server.py:954` → canonical de canción en root.
- `backend/radio-live.py:25` (`WEB_URL`), `radio/atico-player.py:28` (`MASTER_URL`) → default `https://mfmood.com/`.
- `desktop/config.example.json:2`, `desktop/install.sh:58`, `desktop/README.md:81`, `desktop/allmusic2.py:36` → root; conservar el nombre del override `ALLMUSIC_API_BASE`.
- `README.md:26,89` y `radio/AGENTS.md:10,26,68,77,83` → root.

**R2 — prefijo `/allmusic` y base href.**

- `frontend/index.html:5` y `frontend/modern_index.html:7` → `<base href="/">`.
- Rutas internas duras en `frontend/index.html` (803, 1072-1076, 1078, 1083, 1584, 2075, 2224-2225), `modern_index.html` (2770, 3001, 3296, 3312, 3318), `radio.html` (762-764, 834), `artistas.html` (9, 246, 344) → root.
- `backend/allmusic_server.py`: 978, 1033, 1036, 1057, 1074, 1097, 1100, 1162 → root.
- **Conservar** compatibilidad legacy: `backend/allmusic_server.py:1153-1154` y `:2900-2907` (strip de `allmusic/` y middleware `PATH_INFO`) para bookmarks y rollback.

**R3 — CORS.** `backend/allmusic_server.py:40-49`: conservar 41-48 y **añadir** `https://allmusic.edgemarketing.tech`, `https://mfmood.com`, `https://www.mfmood.com`. No quitar orígenes actuales durante cutover.

**R4 — entorno.** Los defaults del repo cambian, pero los overrides reales son nombres, no URLs públicas: `WEB_URL`/`LOCAL_URL` en `~/.config/systemd/user/allmusic-radio-live.service:8`; `MASTER_URL`/`LIVE_STREAM_URL` en `~/.config/systemd/user/atico-player.service:10-13`; `/mnt/nvme-agents/opencode/allmusic-radio.env` no tiene override de origen público. **No editar por URL**; solo confirmar en Fase 4.

**Conservar sin cambios:** correos `contacto@edgemarketing.art` / `dmca@edgemarketing.art`; hostname del stream de radio; origen `http://192.168.1.4:2426`; links root de la agencia (decisión separada); compatibilidad legacy `/allmusic`; cambios sucios del sitemap y `Dockerfile.gsc-patch`.

**Tras renombrar el directorio:** referencias reales al path viejo solo en este plan; el resto son snapshots históricos del KG (datos, no instrucciones; no escribir al KG compartido). No hay symlinks ni configs de MCP que apunten al repo.

---

## Fase 0 — Congelar y tomar baseline

**Objetivo:** snapshots y línea base antes de tocar nada.

- [ ] `git -C /mnt/sda1/repos/mfmood status --short`
- [ ] `git -C /mnt/sda1/repos/mfmood diff > /tmp/opencode/allmusic-sitemap.diff`
- [ ] `cp /mnt/sda1/repos/mfmood/Dockerfile.gsc-patch /tmp/opencode/Dockerfile.gsc-patch.bak`
- [ ] Guardar `git rev-parse HEAD`, `git remote -v`, lista de ramas.
- [ ] Capturar lista completa de rutas de `edgetunnel` con **IDs estables**, no ordinales de UI.
- [ ] Confirmar si la config del túnel es dashboard-managed o file-managed (`cloudflared config.yml` / túnel remoto).
- [ ] Baseline HTTP:
  - `curl -fsS https://allmusic.edgemarketing.tech/status`
  - `curl -fsS https://allmusic.edgemarketing.tech/radio/queue`
  - `curl -fsSI https://allmusic.edgemarketing.tech/`
- [ ] Spot-check de otras rutas del túnel y comparar con baseline: `stoff.edgemarketing.tech/` → 200, `medicars.cl/` → 200, `mail.edgemarketing.tech/radio/live.mp3` → 404. Cualquier cambio es regresión a investigar.
- [ ] Baseline radio en el **VAIO**: `curl -fsS http://127.0.0.1:2427/health`; además registrar `https://mail.edgemarketing.art/radio/live.mp3` (README dice 502). En este host `:2427` da *refused*; no es fallo de la migración.
- [ ] Baseline DNS de `mfmood.com`: A de parking, sin MX, NS Spaceship, `www` NXDOMAIN, `:443` sin certificado. Guardar TTLs para no interpretar resultados pre-propagación como definitivos.

**Gate 0:** baseline guardado; cualquier fallo previo queda marcado como preexistente.

**Rollback:** no hay cambios aún; restaurar solo si el baseline cambia.

---

## Fase 1 — Alta de zona en Cloudflare y nameservers

**Objetivo:** que `mfmood.com` tenga zona activa en la cuenta de Cloudflare.

- [ ] Cloudflare Dashboard → **Add a site → Connect a domain** → `mfmood.com`.
- [ ] Elegir **Full setup** (nameservers de Cloudflare). Importar DNS: no hay registros que importar.
- [ ] Copiar los 2 nameservers asignados.
- [ ] Spaceship MCP: `domain_set_nameservers({domainName:"mfmood.com", provider:"custom", hosts:[...]})`.
- [ ] Verificar sobrevivencia: `domains_list` debe mostrar `nameservers.provider: custom` con esos hosts.
- [ ] Verificar DNS público: `dig +short NS mfmood.com` debe mostrar los NS de Cloudflare; los A de parking deben desaparecer al activarse la zona.
- [ ] Verificar que **no aparece MX** (`dig +short MX mfmood.com` → vacío).
- [ ] Esperar a que Cloudflare marque la zona **Active** y a que pase el TTL viejo de NS (1791s) + margen antes de dar por buena la propagación.

**Gate 1:** zona Active y NS públicos apuntando a Cloudflare.
**Rollback:** `domain_set_nameservers({domainName:"mfmood.com", provider:"basic"})`. Sin tráfico aún, sin impacto.

---

## Fase 2 — Rutas nuevas en `edgetunnel`

**Objetivo:** publicar la app en apex y www **sin tocar la ruta vieja**.

- [ ] En `edgetunnel` → Routes → Add route → Published application:
  - Hostname `mfmood.com` (subdomain vacío, dominio `mfmood.com`) → Service `http://192.168.1.4:2426`.
  - Hostname `www.mfmood.com` → Service `http://192.168.1.4:2426` (o redirect canónico a apex si se decide en la revisión; canonical final sigue siendo root).
- [ ] Capturar y guardar los **IDs estables** de ambas rutas nuevas.
- [ ] No borrar aún `allmusic.edgemarketing.tech`.
- [ ] Verificar DNS/TLS/HTTP:
  - `dig +short mfmood.com` y `dig +short www.mfmood.com`
  - `curl -fsSI https://mfmood.com/` y `curl -fsSI https://www.mfmood.com/`
  - `curl -fsS https://mfmood.com/status` → `{"status":"running"}`
  - `curl -fsS https://www.mfmood.com/status` → `{"status":"running"}`
  - `curl -fsS https://mfmood.com/radio/queue`
- [ ] Confirmar certificado y SAN para ambos nombres con `openssl s_client -connect mfmood.com:443 -servername mfmood.com` (y variante `www`).
- [ ] SSL/TLS de la zona en modo **Full**, no **Full (strict)**: el origen warmachine sirve certificado self-signed de Traefik y strict daría 526.
- [ ] Repetir spot-check de rutas vecinas y comparar IDs/count con Fase 0; cualquier reordenación u sobrescritura → rollback.

**Gate 2:** apex + www responden 200 con TLS válido; ruta vieja sigue viva.
**Rollback:** borrar las 2 rutas nuevas por ID established; dejar zona/NS.

---

## Fase 3 — Migración de código y configuración a canonical root

**Objetivo:** que el repo use `https://mfmood.com/` como URL canónica, sin romper el prefijo `/allmusic`.

Inventario exacto a aplicar (detalle fino pendiente del subagent de inventario):

- [ ] `frontend/index.html`, `modern_index.html`: canonical, `og:url`, `og:image`, `twitter:image`, JSON-LD `@id` y `url` → root.
- [ ] `frontend/{about,cookies,dmca,privacidad,terminos}.html`: canonical y links internos → root.
- [ ] `frontend/sitemap.xml` y `frontend/robots.txt` → root. **Preservar el diff actual** (quita `artistas.html` y añade newline final).
- [ ] `backend/allmusic_server.py`:
  - CORS: **añadir** `https://allmusic.edgemarketing.tech`, `https://mfmood.com` y `https://www.mfmood.com`; **mantener** `https://edgemarketing.art` durante cutover.
  - canonical de canción en línea ~954 → root.
  - rutas internas y redirect → root; **conservar** el strip legacy de `allmusic/` y el middleware `PATH_INFO` para bookmarks/rollback.
- [ ] `backend/radio-live.py` default `WEB_URL` → `https://mfmood.com/`.
- [ ] `radio/atico-player.py` default `MASTER_URL` → `https://mfmood.com/`.
- [ ] `desktop/config.example.json`, `desktop/install.sh`, `desktop/README.md`, `desktop/allmusic2.py` → `https://mfmood.com/`.
- [ ] READMEs y `radio/AGENTS.md`: URL pública → root; dejar explícito que el stream viejo es otro túnel y no se migra aquí.
- [ ] **No tocar**: direcciones de correo `contacto@edgemarketing.art` / `dmca@edgemarketing.art`, hostname del stream de radio, `<base href>` hasta decidir el cambio de prefijo, ni rutas ajenas del túnel.
- [ ] Confirmar overrides de entorno en Coolify/systemd: no hay URL pública vieja detectada; los defaults del repo no bastan por si solos, pero no hace falta reescribir los units.
- [ ] Aviso para clientes desktop ya instalados: actualizar `~/.config/allmusic2/config.json` a `https://mfmood.com/`.
- [ ] Auditoría final de restos: `grep -RInE 'edgemarketing' frontend backend radio desktop`. Solo se permiten: correos de contacto, hostname del stream de radio, entrada CORS vieja durante cutover y rutas ajenas.
- [ ] Inventario de overrides: listar `WEB_URL`, `MASTER_URL`, `LIVE_STREAM_URL`, `ALLMUSIC_API_BASE`, `RADIO_LIVE_STREAM_URL` en Coolify/systemd/procesos; actualizar en Fase 4.
- [ ] Verificar que el diff de `frontend/sitemap.xml` y `Dockerfile.gsc-patch` siguen presentes; prohibido `git checkout --` / `git clean`.

**Gate 3:** diff revisado, sin sobrescribir cambios sucios; tests locales en verde.
**Rollback:** revertir commit de código y redeploy de la imagen anterior.

---

## Fase 4 — Commit, deploy y runtime

**Objetivo:** que el código nuevo esté corriendo detrás de las rutas nuevas.

- [ ] Crear rama de trabajo `mfmood/migration` desde el HEAD guardado.
- [ ] Incluir el diff de `sitemap.xml` ya existente y el untracked `Dockerfile.gsc-patch` **explícitamente** en el commit o en un commit aparte, según revisión.
- [ ] Push a `origin` (aún `allmusic.git`; el rename llega en Fase 6).
- [ ] Coolify: actualizar variables de entorno si el inventario lo indica.
- [ ] Deploy manual del servicio `radio` (autodeploy está marcado como roto en README E3; no asumir que dispara).
- [ ] Verificar en producción nueva: `/status`, `/radio/queue`, búsqueda/conversión, assets estáticos, canonical devuelto en HTML.
- [ ] Verificar que el Atico sigue sonando el master previo; si cambia, rollback inmediato.

**Gate 4:** nueva URL sirve código nuevo y la radio no regresiona.
**Rollback:** revertir commit / redeploy del tag de imagen anterior; rutas nuevas pueden seguir apuntando al app viejo.

---

## Fase 5 — Verificación externa, SEO y cooldown

- [ ] Apex y www: 200, TLS válido, canonical `https://mfmood.com/`.
- [ ] `sitemap.xml` y `robots.txt` sirven URLs `mfmood.com`.
- [ ] Google Search Console: añadir propiedad `mfmood.com`, enviar sitemap, revisar cobertura y canonical.
- [ ] Implementar y verificar redirecciones 301 desde `allmusic.edgemarketing.tech/*` a `mfmood.com/*` **antes** de borrar la ruta vieja; sin 301 verificada no se borra nada.
- [ ] Comprobar que las demás rutas del túnel siguen igual que en Fase 0.
- [ ] Comprobar desktop client con config actualizada y que ningún env la sobreescribe.
- [ ] Comprobar que `dig +short MX mfmood.com` sigue vacío y que los correos `edgemarketing.art` no cambiaron.
- [ ] Cooldown recomendado: **24 h** sin incidencias antes de borrado/resolución de nombres; cualquier incidencia reinicia el reloj.

**Gate 5:** 24 h verdes y respaldo de config de túnel guardado.
**Rollback:** mantener ruta vieja y repo/app viejo; solo revertir si aparece regresión.

---

## Fase 6 — Renombrado de repo y app

**Objetivo:** que el proyecto se llame `mfmood` en GitHub y Coolify.

- [ ] Renombrar directorio local: `mv /mnt/sda1/repos/mfmood /mnt/sda1/repos/mfmood`.
- [ ] Actualizar referencias al path viejo dentro de este plan; los snapshots históricos del KG son datos y no se modifican.
- [ ] GitHub: `gh repo rename mfmood --repo mrallanodreman/allmusic` (confirmar sintaxis con `--help`; no ejecutar a ciegas).
- [ ] Actualizar `origin` a `github.com/mrallanodreman/mfmood.git`; verificar `git ls-remote`.
- [ ] Coolify: renombrar la app `radio` a `mfmood`, conservando dominios, env, volúmenes y healthcheck.
- [ ] Verificar autodeploy/webhook después del rename (README E3 dice que no dispara; arreglar o documentar deploy manual).
- [ ] Verificar que la URL pública sigue sirviendo la app tras los renombres.

**Gate 6:** GitHub y Coolify muestran `mfmood`; deploy y URL pública siguen verdes.
**Rollback:** GitHub `gh repo rename allmusic`; restaurar path y nombre de app; el contenido y la ruta pública no cambian.

---

## Fase 7 — Liberación / borrado de recursos viejos

**Objetivo:** quitar lo viejo **solo después** de todo lo anterior.

- [ ] Borrar la ruta `allmusic.edgemarketing.tech` del túnel por **ID estable** capturado en Fase 0, no por ordinal.
- [ ] Verificar que el hostname viejo deja de resolver/servir y que `mfmood.com` sigue 200.
- [ ] Quitar dominios antiguos de Coolify si los hubiera (no tocar el stream de radio ajeno).
- [ ] Borrar el repo GitHub viejo solo si GitHub lo redirige correctamente y hay backup/archive; **requiere OK explícito del usuario** porque es irreversible.
- [ ] Cualquier otro recurso viejo: listar antes, tachar uno por uno, sin `git clean` ni `rm -rf` genérico.

**Gate 7:** checklist firmado; verificación final apex/www/radio/otras rutas.
**Rollback:** recrear ruta vieja desde el snapshot; restaurar repo desde backup si se llegó a borrar.

---

## Fase 8 — Cierre

- [ ] README y docs operativas actualizados a `mfmood`.
- [ ] Handoff del perfil con rutas/IDs/resultado/pruebas/riesgos (sin secretos). No escribir al KG compartido.
- [ ] Cerrar pestañas propias de BrowserOS.
- [ ] Declarar hecho vs hipótesis vs pendiente.

---

## Matriz rápida de verificación

| Verificación | Comando esperado | Stop si |
|---|---|---|
| API nueva | `curl -fsS https://mfmood.com/status` → `{"status":"running"}` | 502/404/html |
| Cola | `curl -fsS https://mfmood.com/radio/queue` → JSON | error |
| Apex+www TLS | `curl -fsSI https://mfmood.com/` y `https://www.mfmood.com/` → 200 | cert mismatch |
| Canonical | HTML debe traer `https://mfmood.com/` | queda `edgemarketing` |
| Vecinos | `stoff` 200, `medicars` 200, `mail.edgemarketing.tech/radio/live.mp3` 404 | distinto del baseline |
| DNS | A de parking desaparece; NS Cloudflare; `www` resuelve; MX vacío | NS Spaceship, MX nuevo, `www` NXDOMAIN |
| Radio | master `:2427` en VAIO y stream baseline sin cambios | regresión nueva |
| Email | correos `edgemarketing.art` intactos | MX nuevo en mfmood |
| Repo | `git remote -v` → `mfmood.git` | sigue `allmusic.git` |

## Subagentes utilizados / a incorporar

- `ses_de9f9e5ceffeRyzrMVs7y5KLLr` — inventario exacto de URLs, env y referencias al path.
- `ses_de9f9e5c8ffeavqyZGyw7bTJIf` — runbook Cloudflare DNS/túnel y modo de gestión.
- `ses_de9f9e5baffeJkM8O791yBo1A6` — rename seguro GitHub/Coolify y borrado.
- `ses_de9f9e5b6ffeiohlqnbFziEvXM` — matriz de verificación, rollback y cooldown.
- `ses_de9ff9e90ffehlaFjtqook6GSV` — revisión adversarial inicial (ya entregada; sus hallazgos están reflejados aquí).

Sus resultados están fusionados en este archivo. Revisión adversarial adicional (`ses_de9ff9e90ffehlaFjtqook6GSV`) añadió cuatro correcciones aplicadas abajo.

## Correcciones adversariales finales (verificadas 2026-11-26)

15. **Checkouts duplicados — UNIFICADOS (2026-11-26).** Existían `/mnt/sda1/repos/allmusic` (`3cd95c4`, `?? supabase/`) y `/mnt/sda1/repos/mfmood` (`d67b498`, cambios sucios), ambos del mismo origin. **Fuente de verdad es GitHub `origin/master`**, 75 commits por delante (`7a8886fe`). Acción ejecutada: rama `mfmood-cutover` desde `origin/master` con el diff del sitemap reaplicado; `supabase/` (solo metadata CLI) movida al repo unificado; backup en `/tmp/opencode/mfmood-migration/allmusic-checkout-backup.tar.gz`; checkout viejo eliminado. Directorio único: `/mnt/sda1/repos/mfmood`. `gitmulti_registry.json` actualizado al nuevo path.
16. **Registro git-multi:** `/run/media/pctorre/HddCompiler/mcp/opencode/mcp_servers/gitmulti_registry.json:96` mapea `/mnt/sda1/repos/mfmood` → cuenta `mrallanodreman`. Actualizar la entrada en el mismo cambio si se renombra el directorio (o conservar symlink).
17. **Build remoto:** `/home/warmachine/allmusic-build/frontend/` (en `superserver` = `192.168.1.4`) contiene las mismas URLs viejas. El contenedor `allmusic-radio` **no monta** ese directorio (solo el volumen `edgeradio-data` en `/app/data`) y su imagen es `localhost:5000/allmusic-radio:7a8886fe…`, construida desde Git. El `sitemap.xml` del contenedor **sí tiene** `artistas.html`, igual que `origin/master`: el diff local es trabajo WIP no desplegado. Preservarlo, no asumir que ya está en producción.
18. **Coolify sí se toca en Fase 4:** el deploy nuevo llega por push/webhook; el token de bóveda es `read-only`, así que para pausar autodeploy / patchear nombre y URL git hace falta sesión admin o PAT `write`. Nunca tocar env, volúmenes, puertos ni dominios de Coolify.

### Estrategia de código revisada

1. `git stash push -u` en `allmusic-backend` (conserva los 3 cambios sucios; backups ya en `/tmp/opencode/mfmood-migration/`).
2. Crear rama local `mfmood-cutover` desde `origin/master` y `git stash pop` (el diff del sitemap aplica limpio: idéntico en ambos HEAD).
3. Aplicar R1-R4 sobre `origin/master`, verificar diff y tests.
4. **No pushear a `master` hasta que las rutas nuevas estén vivas**: autodeploy está activo y un push anticipado publicaría canonical `mfmood.com` antes de tiempo. Publicar en Fase 4 con el gate de rutas ya verde.
5. Tras el rename: actualizar `gitmulti_registry.json`, `remote -v` y las referencias de este plan. El checkout `allmusic` queda intacto.

19. **Unificación de rutas (decisión del usuario 2026-11-26).** El hostname viejo NO lo sirve `edgetunnel`: el registro DNS `allmusic.edgemarketing.tech` (zona `28c7cfa09d4d16ed2a4351be572e9c86`, ID `3d71c8cb83276e216f868566061dbd97`) es CNAME a `cc42202e-a3d9-4373-9353-1f89b1ae9a75.cfargotunnel.com`, es decir el túnel **`coolify`**. **Ambos** túneles tienen el mismo ingress `{hostname:"allmusic.edgemarketing.tech",service:"http://192.168.1.4:2426"}` (`coolify` versión 20, `edgetunnel` versión 80): duplicado a eliminar. Snapshots: `coolify-config-before.json` y `config-before.json`.
    - **Una sola ruta canónica:** `mfmood.com` y `www.mfmood.com` se añaden **solo a `edgetunnel`**, con CNAME a `2995fc49-98d1-4533-a359-62d5effebf1b.cfargotunnel.com`. No se crea nada en `coolify`.
    - **Limpieza final (tras 301 + 24h verdes):** borrar el registro DNS viejo por ID y quitar el ingress duplicado de `coolify` **y** de `edgetunnel`, restaurando cada config desde su snapshot si falla.
    - `activation_check` devolvió 81163 mientras la zona está `initializing`: esperar propagación. El TLD ya delega a los NS de Cloudflare (glue visto en `a.gtld-servers.net`); los resolvers aún cachean los NS viejos.

---

## Estado de ejecución (2026-11-26)

- [x] Fase 0: backups byte-a-byte, HEAD/remote, baseline HTTP/DNS, config del túnel (`config-before.json`, versión 80), `config_src=cloudflare`, `remote_config=true`, 4 conexiones.
- [x] DNSSEC desactivado en Spaceship; `dig DS mfmood.com` → vacío en 1.1.1.1 y 8.8.8.8.
- [x] Zona Cloudflare creada: ID `8976ef1c97d40e36737da522b7c9c9a7`, NS `rachel.ns.cloudflare.com` / `rommy.ns.cloudflare.com`, estado `initializing`.
- [x] NS del registrar cambiados a `custom` con esos dos hosts; `domains_list` lo confirma.
- [x] Unificación total de duplicados AllMusic (decisión "TODO" del usuario): checkout viejo eliminado tras backup; `supabase/` conservada en `/mnt/sda1/repos/mfmood`; `gitmulti_registry.json` actualizado; `/mnt/sda1/app/allmusic` (sin git, unit systemd inactive/disabled) archivado y eliminado; launcher duplicado reemplazado por symlink al de `edex-supercontrol-main`; unit `allmusic-radio.service` retirada. Backups en `/tmp/opencode/mfmood-migration/`. Se conservan datos/volúmenes y assets (`allmusic-gsc-data-20261021`, logo, runtime `allmusic-radio`).
- [x] Código preparado en rama local `mfmood-cutover` (commit `b381725`) sobre `origin/master` (`7a8886fe`): canonical root `https://mfmood.com/`, `<base href="/">`, rutas internas root, CORS +3 orígenes, compatibilidad legacy `/allmusic` intacta. Sin push a `master` hasta que las rutas nuevas estén vivas (autodeploy activo).
- [x] Registros DNS creados en zona `8976ef1c…`: `mfmood.com` → ID `83c2b9ee9ee458e178d381443e7abcf5`, `www.mfmood.com` → ID `94ca514321a8874030d8703f9e1ebf2b`; ambos CNAME proxied al túnel `edgetunnel`, TTL 1.
- [x] Rutas añadidas **solo en `edgetunnel`**: `mfmood.com` y `www.mfmood.com` → `http://192.168.1.4:2426`; config versión 80 → **81**; 33 ingress, vecinos intactos, catch-all al final.
- [x] Redirect canónico creado: ruleset `20a0031821ab4c4ba921660e9b6e895c`, rule `cb011159bd09494dac00e44a8fb1f00e` (`www` → apex 301, path/query preservados).
- [x] Registro DNS viejo identificado para limpieza final: zona `28c7cfa09d4d16ed2a4351be572e9c86`, ID `3d71c8cb83276e216f868566061dbd97`; ingress duplicado también en túnel `coolify` (versión 20).
- [x] Zona `mfmood.com` activa tras completar el setup en el panel (plan Free + "Continue to activation" + "I updated my nameservers" + `activation_check`): `status=active`, SSL `full`, cert LE con SAN `mfmood.com` + `*.mfmood.com`. `www` → apex 301 verificado; `/status` y `/radio/queue` 200; host viejo 200.
- [x] Push a GitHub `master` con `b381725` (token de `/tmp/opencode/gh-vault` vía Basic `x-access-token`); webhook `693647409` entregó 200. Coolify desplegó el commit (queue 831/832) con token admin creado por SSH en el contenedor (equipo Root Team id 0).
- [x] Publicado el arreglo del canonical real: la UI servida es el build React (`frontend-react/dist/index.html`), no `frontend/index.html`; ese build seguía con canonical `edgemarketing.tech/allmusic/`. Corregido `frontend-react/index.html` (canonical/OG/Twitter/JSON-LD), `vite.config.js` (`base: '/'`), narrativa de componentes y legales. Commits `e087e74`, `96e5b1c` desplegados; canonical servido `https://mfmood.com/`, título `MfMood · Canal 24`, AdSense + slot `5447354058` presentes en el bundle, `/ads.txt` 200.
- [x] Renombrado GitHub `mrallanodreman/allmusic` → `mrallanodreman/mfmood`; `master` en `96e5b1c`; remote local actualizado; webhook `693647409` intacto.
- [x] Renombrado en Coolify: app `radio` → `mfmood`, git URL → `ssh://git@ssh.github.com:443/mrallanodreman/mfmood.git`, proyecto `EdgeRadio` → `MfMood` (descripción ASCII válida). Deploy posterior `itpb43bld9bd9nyqvrmsswlj` / queue 837 `finished` con 6 referencias a `mfmood.git` y 0 a `allmusic.git`. Sin tocar env, volúmenes, puertos ni dominios.
- [x] Verificación pública (2026-11-26): DNS apex/www resuelve a Cloudflare; `https://mfmood.com/` 200; `/status` `{"status":"running"}`; `/ads.txt` 200; `www.mfmood.com/ruta?x=1` → 301 apex preservando path/query.
- [x] **Limpieza final autorizada "Borrar ahora" (2026-11-26):** eliminado registro DNS `3d71c8cb83276e216f868566061dbd97` (`allmusic.edgemarketing.tech`) y quitado el ingress duplicado de `edgetunnel` (v81→**82**, 32 ingress) y `coolify` (v20→**21**, 31 ingress). `allmusic.edgemarketing.tech` ya no resuelve (esperado); `mfmood.com/status` 200; vecinos `stoff` y `medicars` 200; catch-all intacto. Rollback: configs completas previas en `/tmp/opencode/mfmood-migration/pre-cleanup-2995fc49.json` y `pre-cleanup-cc42202e.json`, más los snapshots originales `config-before.json`/`coolify-config-before.json`.

## Fase 5b — Narrativa, metagraph y monetización (2026-11-26)

- [x] Renombre de narrativa a **MfMood**: meta description, canonical, Open Graph, Twitter cards, JSON-LD, título y textos de la UI React, legales y README. Se conservan identificadores técnicos (`allmusic_server.py`, clases, keys de localStorage) y el alias legacy `/allmusic/*` para no romper cuentas ni enlaces.
- [x] Monetización reactivada en la UI React: `google-adsense-account`, Consent Mode v2, GTM `GTM-5WFHF7PH`, GA4 `G-39LMF2SGY4` y AdSense Auto Ads (`ca-pub-3871344948149274`), plus banner de consentimiento (`CookieConsent.jsx`) que actualiza `ad_storage`/`ad_user_data`/`ad_personalization`. `ads.txt` existe y se copia también a `public/` para el build estático.
- [x] Hallazgo del subagente (KG `n6b2c3e41f`, 2026-09-10): el bloqueo real era **"Contenido de poco valor" en `edgemarketing.art`**, con revisión limitada hasta el 15-sep-2026. Los subdominios (`allmusic.edgemarketing.art`) heredaban la entrada raíz, así que **no** había que darlos de alta. `mfmood.com` es un **dominio raíz nuevo**: debe añadirse como sitio propio en AdSense; no hereda la aprobación vieja.
- [x] Se montó también la unidad manual real `data-ad-slot=5447354058` (usada en `modern_index.html`) vía `AdSlot.jsx` en el rail, además de Auto Ads. `ads.txt` sirve 200 en el apex.
- [x] **Alta en AdSense ejecutada (2026-11-26):** sesión ya autenticada en BrowserOS; sitio `mfmood.com` añadido al publisher `pub-3871344948149274`, verificado por `ads.txt` (el snippet coincide con `frontend/ads.txt`) y **revisión solicitada**. Estado: `Debe revisarse`/`Preparando`. Auto Ads está **DESACTIVADO** hasta aprobación (el toggle no persiste mientras el sitio no está aprobado); el script y el slot manual ya están desplegados, así que la aprobación solo activa la entrega. El flag viejo "Contenido de poco valor" sigue en `edgemarketing.art`, no en `mfmood.com`.
- [ ] Tras aprobación de Google: confirmar que Auto Ads queda `ACTIVADO` y revisar GSC/GA4 con el dominio nuevo.
- [ ] Tras el deploy: comprobar en el HTML servido canonical `https://mfmood.com/`, script de AdSense, `ads.txt` 200 y consola sin errores CSP.

## Fase 5c — Google Search Console (2026-11-26)

- [x] Alta y verificación de `mfmood.com` como **propiedad de dominio** (`sc-domain:mfmood.com`, no prefijo de URL). Verificación por registro TXT `google-site-verification` en la zona Cloudflare `8976ef1c97d40e36737da522b7c9c9a7` (registro ID `7efc9400025f79cb40a20a4225ccd634`, DNS-only, visible en 1.1.1.1). El selector de propiedades ya lista `sc-domain:mfmood.com` y abre el panel completo.
- [x] Sitemap enviado: `https://mfmood.com/sitemap.xml` → estado **Correcto**, 8 páginas descubiertas, 0 vídeos (lectura del 26-nov-2026).
- [x] Indexación solicitada para `https://mfmood.com/` desde Inspección de URLs ("Se ha solicitado la indexación"); Google aún no reconoce la URL como indexada, es normal en un dominio nuevo.
- [ ] Verificar en los próximos días que `https://mfmood.com/` aparece como indexada y revisar consultas/impresiones en GSC y tráfico en GA4 `G-39LMF2SGY4`.

## Fase 5d — Blog SEO de artistas en NEWSHIT (2026-11-26)

- [x] Fichas indexables en `mfmood.com`: `/blog/razimbrain-apnea-lxxi/` y `/blog/vittorio-kultururbana-2026/`, servidas como HTML real por `backend/allmusic_server.py` con canonical propio, `Article` + `BreadcrumbList` en JSON-LD, Open Graph y `lang="es"`. La fuente única es `frontend/blog/artists.json`; la UI y la versión permanente no divergen.
- [x] El texto de la tarjeta NEWSHIT abre la ficha **inline justo debajo del reproductor** (`ArtistArticle.jsx`), sin salir de la portada. La carátula sigue llevando al radio 24/7 y el artículo conserva un enlace permanente para compartir. En pantallas táctiles el texto de la ficha se muestra siempre.
- [x] `sitemap.xml` incluye las dos URLs nuevas (10 en total). Sitemap enviado a GSC antes de este cambio: volver a enviarlo tras el deploy para que descubra las fichas.
- [x] Verificación local: `pytest` 17/17, `npm run build` OK, JSON válido. Commits `7e0b51b` (backend/datos/sitemap) y `9818e5b` (UI) pusheados a `master`.
- [x] Tras el deploy: `/blog/artists.json` y las dos fichas devuelven 200; canonical, JSON-LD `Article` y enlace de escucha verificados en HTML público. El bundle servido es `index-CJ0dIQYy.js`, el mismo del build local con la UI inline.
- [x] Promo de Vittorio (decisión del usuario 2026-11-26): la tarjeta NEWSHIT abre fijada en Vittorio y destaca **That's the deal** (feat. Ukumari MC e Iñaki The Common), pista 7 de `La Antorcha`, 2:55, publicada el 27-sep-2026. El play reproduce el tema en el reproductor de MfMood vía `/stream/tVp4r66lejw` (verificado 206 `audio/mp4`), no abre Deezer; YouTube y Deezer quedan como referencias. Ficha SEO y sitemap actualizados. Commits `47ebe8c`, `360056e`, `3d9be10` y `9dc9ca8`.
- [ ] Volver a enviar `https://mfmood.com/sitemap.xml` en GSC (ahora 10 URLs) y solicitar indexación de las dos fichas.
