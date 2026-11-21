# Handoff — IA Radio (estado final)

## Decisión vigente

El 2026-11-21 el usuario pidió **conservar el último diseño anterior al
artboard C24**. Ese diseño es la UI React estilo fanzine del commit `762077b`.
El commit `64711c7` (`revert(radio): volver al diseno fanzine previo al
artboard C24`) dejó esa versión como estado final y está pusheado a `master`.

No reactivar sin pedirlo explícitamente:

- `e28d6f5` artboard C24 en React + reparación de dos PNG legacy.
- `3f1b94b` / `8fc9307` / `88c34c0` capa RETRO, toggle y láminas horneadas.
- `docs/AI_HANDOFF_RADIO_C24.md` y `scripts/inspect_radio_ui.py` (borrados en el
  revert porque describían ese diseño).

La reparación de `frontend/assets/radio/c24/{radio-mood-panel.png,mood/mood-label.png}`
se conservó: los archivos están corregidos, aunque la UI actual no los usa.

## Cómo está la UI ahora

`frontend-react/src/App.jsx` renderiza `DecorLayer`, `HeaderBanner`, `Sidebar`,
`PlayerStage`, `RequestBar`, `MoodBoard`, `TopRequested`, `QueuePanel`,
`HistoryPanel` y `NowPlayingBar`. Los datos siguen viniendo de `/radio/now`,
`/radio/top`, `/radio/queue`, `/radio/history` y el POST de pedidos; no se
inventaron datos ni se tocó `backend/allmusic_server.py`.

Seguridad: `{valor}` en JSX, sin `dangerouslySetInnerHTML`, `innerHTML`, `eval`,
`new Function` ni `console.log`. Única URL externa: portadas de `i.ytimg.com`
validadas por `safeUrl` en `frontend-react/src/lib/safe.js`.

## Verificación del deploy (2026-11-21)

| comprobación | resultado |
|---|---|
| `npm run build` en `frontend-react/` | 46 módulos, `index-_ctsnuPU.js` 160.22 kB, `index-mslemx7l.css` 14.90 kB |
| webhook `693647409` | `status_code: 200`, `delivered_at: 2026-11-21T23:28:08.52Z` |
| bundle servido en `http://192.168.1.5:2426/allmusic/radio` | `index-_ctsnuPU.js` + `index-mslemx7l.css` |
| DOM en BrowserOS | `.app: true`, `.radio-artboard: false`, `.legacy-decor: false` |
| imágenes locales | 12 en el DOM, 0 rotas |
| portada externa | `i.ytimg.com` responde 200; en headless puede quedar `complete:false` con `naturalWidth:720` (no es un asset roto) |

Texto real visible en la comprobación: `CANAL 24 MIX`, `EN VIVO`, `SONANDO AHORA`,
`El Combo Palacio - Topic`, `Pedir una canción o un mood`, `TICKETS USADOS 00`.

## Publicar un cambio

```bash
cd /mnt/sda1/repos/allmusic
npm --prefix frontend-react run build
GH_CONFIG_DIR=/home/pctorre/.config/gh git push origin master
# esperar a que el HTML servido cambie de hash
curl -sS http://192.168.1.5:2426/allmusic/radio | grep -oE 'assets/index-[A-Za-z0-9_-]+\.(js|css)'
GH_CONFIG_DIR=/home/pctorre/.config/gh gh api \
  repos/mrallanodreman/allmusic/hooks/693647409/deliveries \
  --jq '.[0] | {status_code, delivered_at, event}'
```

`https://edgemarketing.tech/allmusic/*` da 403 de Cloudflare desde este entorno;
usar la IP interna para verificar.

## Notas para la próxima IA

- BrowserOS (`http://127.0.0.1:9200/mcp`) abre pestañas en background: antes de
  medir, esperar ~2-3 s y llamar `document.getAnimations().forEach(a=>a.finish())`.
- El rate limiter de Flask es 30 req/s / 200 por minuto por IP. No lanzar
  inspecciones en bucle: se obtienen 429 falsos que parecen imágenes rotas.
- `supabase/` está untracked: dejarlo fuera de todos los commits.
- Confirmación visual final pendiente del cliente en
  `http://192.168.1.5:2426/allmusic/radio`.
