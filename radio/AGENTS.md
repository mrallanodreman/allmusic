# AGENTS.md — Radio continua MfMood → Atico (persistente)

Configuración definitiva y operacional desde **2026-08-30**. La radio de MfMood
suena de forma continua y estable en la bocina **Atico** (Google Nest Mini) y
sobrevive reinicios (todos los servicios user systemd están `enabled`).

## Pipeline (flujo completo)

```
Radio WEB (Railway, mfmood.com)   <- fuente de verdad: cola de
    |                                               pedidos de oyentes + rotación
    v
allmusic-radio-live.service  (master ffmpeg, :2427) -> MP3 continuo 192kbps/44.1kHz
    |  radio-live.py lee track.link desde la WEB (Railway) y transcodifica video->mp3
    |  (fallback auto a la IA local :2426 si el cloud no responde)
    v
Cloudflare Tunnel (edgemail-tunel) -> https://mail.edgemarketing.art/radio/live.mp3
    |
    v
atico-player.service (atico-player.py)  -> reproduce el master en media_player.atico
                                        via HA REST como audio/mpeg (stream LIVE)
```

> **Atico y web suenan la MISMA radio/cola** (2026-08-30). El master local lidera
> desde la web (Railway), donde viven las peticiones de los oyentes. Fuente primaria
> `WEB_URL=https://mfmood.com`, fallback `LOCAL_URL=http://127.0.0.1:2426`.

## Servicios (todos `enabled` = arrancan solos)

| Servicio | Rol | Estado |
|---|---|---|
| `allmusic-radio.service` | IA Radio local :2426 (fallback si cae la web) | active + enabled |
| `allmusic-radio-live.service` | master :2427 → live.mp3 (fuente: web/Railway) | active + enabled |
| `atico-player.service` | reproduce master en el Atico | active + enabled |

## Archivos clave

- `atico-player.py` — reproduce el master stream en el Atico por HA Cast.
- `radio-live.py` — master stream MP3 continuo (:2427), fuente WEB_URL con fallback LOCAL_URL.
- Unit: `~/.config/systemd/user/atico-player.service` y `allmusic-radio*.service`.
- Env (keys/servicios): `/mnt/nvme-agents/opencode/allmusic-radio.env`.

## ⚠️ REGLAS CRÍTICAS (no violar)

1. **El Atico ES un Google Nest Mini (cast_type=audio, solo audio).**
   - NO reproduce video/mp4 (los links `ytfallback.../stream/<id>` son video).
   - NO reproduce streams BUFFERED progresivos sin Content-Length → cortes
     ("se para y retoma adelantado").
   - **SÍ reproduce streams LIVE** (`audio/mpeg`) — el único modo estable.
2. **Reproducir SIEMPRE el master** `https://mail.edgemarketing.art/radio/live.mp3`
   con `media_content_type: "audio/mpeg"` (stream LIVE). NUNCA los links de
   canciones sueltas ni el audio-proxy :2199.
3. **No reactivar** `radio-atico.service` ni `radio-atico-watchdog.timer`
   (loop viejo de canciones /convert) — peleaban por el Atico y causaban
   cortes/saltos. Están DETENIDOS + DISABLED.
4. **Si el Atico queda idle**: el dispositivo físico pudo colgarse. Power-cycle
   (desenchufar ~15s). `atico-player` re-dispara el stream automáticamente.
5. `radio-live.py` consume el `track.link` de la IA Radio (video de ytfallback)
   y lo **transcodifica** a mp3 con ffmpeg — eso es lo correcto y no debe
   cambiarse (el master ya emite audio, no video).

## Cola de pedidos (song requests)

La cola de pedidos vive en el **backend de la web (Railway)**, no en la copia local.
La gente pide en la web → entra a la cola web → `next_request` se expone → el master
local la lee y suena en el Atico al turno (NUNCA interrumpe la canción actual).

API canónica (Railway = mfmood.com, y la copia local :2426 es idéntica):
- `POST /radio/suggest` `{query, reason?, agent?}` → encola un pedido (rate-limit 10/min), devuelve posición.
- `GET  /radio/queue` → cola activa con `position` + `eta_seconds`/`eta_minutes` por canción.
- `GET  /radio/now` → `next_request` (siguiente en cola) + `top_requested` (ranking 10 más pedidos) + `track` (lo que suena, con `link` para transcodificar).
- `POST /radio/advance` → pide rotar a un pedido pendiente al terminar la pista actual.

El master (`radio-live.py`) lee `/radio/now` de la web cada 5s (expone en `/health`
`next_request` + `request_count`) y, si hay pedido pendiente, hace `POST /radio/advance`.

Verificar: `curl https://mfmood.com/radio/queue` y `curl http://127.0.0.1:2427/health`.

## Comandos de operación

- Estado radio: `systemctl --user is-active allmusic-radio allmusic-radio-live atico-player`
- Health master: `curl http://127.0.0.1:2427/health`
- Cola pedidos: `curl https://mfmood.com/radio/queue`
- Reiniciar reproducción: `systemctl --user restart atico-player.service`
- Log: `journalctl --user -u atico-player.service -f`

## Referencia

Todos los nodos en el Knowledge Graph (label `radio-atico-radio-pipeline`,
`atico-player-service`). Detalle y diagnóstico completo en el KG.
