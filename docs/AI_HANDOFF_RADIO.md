# Handoff — IA Radio (estado final)

## Decisión vigente

El 2026-11-21 el usuario pidió **conservar el último diseño anterior al
artboard C24**. Ese diseño es la UI React estilo fanzine del commit `762077b`.
El commit `64711c7` (`revert(radio): volver al diseno fanzine previo al
artboard C24`) dejó esa versión como base y está pusheado a `master`.
Sobre esa base, el commit `cae7e8a` enriqueció la UI sin cambiar datos ni
endpoints: reproductor protagonista, rail lateral con `Los 10 más pedidos`,
ecualizador/ondas sobre la carátula y revelado por scroll accesible.

No reactivar sin pedirlo explícitamente:

- `e28d6f5` artboard C24 en React + reparación de dos PNG legacy.
- `3f1b94b` / `8fc9307` / `88c34c0` capa RETRO, toggle y láminas horneadas.
- `docs/AI_HANDOFF_RADIO_C24.md` y `scripts/inspect_radio_ui.py` (borrados en el
  revert porque describían ese diseño).

La reparación de `frontend/assets/radio/c24/{radio-mood-panel.png,mood/mood-label.png}`
se conservó: los archivos están corregidos, aunque la UI actual no los usa.

## Cómo está la UI ahora

`frontend-react/src/App.jsx` renderiza `DecorLayer`, `HeaderBanner`, `Sidebar`,
`PlayerStage`, `RequestBar`, `MoodBoard`, `QueuePanel`, `HistoryPanel`,
`NowPlayingBar` y, en un `<aside class="rail">`, `TopRequested`. Los datos
siguen viniendo de `/radio/now`, `/radio/top`, `/radio/queue`,
`/radio/history` y el POST de pedidos; no se inventaron datos ni se tocó
`backend/allmusic_server.py`.

Detalles de `cae7e8a`:

- `PlayerStage`: carátula grande con marco/recorte fanzine, título, artista,
  progreso y tiempos, `CANAL 24` / `EN VIVO`.
- `Equalizer`: 16 barras con modos `--active`, `--compact` y `--wave`; el wave
  es un overlay `pointer-events: none` sobre la carátula.
- `TopRequested`: `01..10`, título, artista y contador, con `clip-path`,
  papel recortado y sombras desplazadas; empty state si no hay pedidos.
- `useInView.js`: `IntersectionObserver` propio, sin dependencias nuevas.
  El contenido es visible por defecto; si el observer no dispara (pestaña en
  segundo plano), no queda oculto. Todo movimiento está tras
  `prefers-reduced-motion: no-preference`.
- Sin librerías nuevas: `package.json` sigue con React 18.3.1 y Vite 5.4.11.

Seguridad: `{valor}` en JSX, sin `dangerouslySetInnerHTML`, `innerHTML`, `eval`,
`new Function` ni `console.log`. Única URL externa: portadas de `i.ytimg.com`
validadas por `safeUrl` en `frontend-react/src/lib/safe.js`.

## Verificación del deploy (2026-11-21 / 2026-11-22)

| comprobación | resultado |
|---|---|
| `npm run build` en `frontend-react/` | 47 módulos, `index-D5UnPAPu.js` 161.80 kB, `index-C_DDHY4o.css` 19.96 kB |
| webhook `693647409` | `status_code: 200`, `delivered_at: 2026-11-22T01:48:47.974Z` |
| bundle servido en `http://192.168.1.5:2426/allmusic/radio` | `index-D5UnPAPu.js` + `index-C_DDHY4o.css` |
| DOM en BrowserOS | `.app: true`, `.radio-artboard: false`, `.legacy-decor: false`, `.rail: true` |
| reproductor / rail | carátula 313×313 px visible, riel a la derecha, sin overflow horizontal |
| ecualizador | 32 barras (16 en controles + 16 en wave), 59 animaciones activas con `playing=true` |
| imágenes locales | 12 en el DOM, 0 rotas |
| tests de seguridad | 11/11 en `/tmp/opencode/allmusic-test` |
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
usar la IP interna para verificar. **Sin barra final**: `/allmusic/radio` sirve
el React (`id="root"` y `assets/index-*.js`); `/allmusic/radio/` cae en el
catch-all del sitio legacy y muestra el HTML grande de AllMusic PRO.

## Notas para la próxima IA

- BrowserOS (`http://127.0.0.1:9200/mcp`) abre pestañas en background: antes de
  medir, esperar ~2-3 s y llamar `document.getAnimations().forEach(a=>a.finish())`.
- El rate limiter de Flask es 30 req/s / 200 por minuto por IP. No lanzar
  inspecciones en bucle: se obtienen 429 falsos que parecen imágenes rotas.
- `supabase/` está untracked: dejarlo fuera de todos los commits.
- Push con `GH_CONFIG_DIR=/home/pctorre/.config/gh`; sin esa variable git puede
  usar la cuenta aislada `life360-ec` y el push devuelve 403.
- Reporte legible por máquina: `/tmp/opencode/radio-report.json` (head, bundle,
  delivery, endpoints y mediciones del DOM).
- Confirmación visual final pendiente del cliente en
  `http://192.168.1.5:2426/allmusic/radio` (sin slash).
