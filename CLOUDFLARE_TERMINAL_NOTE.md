# Nota operativa: error de Terminal en Coolify (restricción de Cloudflare)

## Síntoma
Al abrir el recurso `radio` en Coolify (proyecto EdgeRadio), el panel **Terminal/Exec** del navegador muestra:
```
Error: Terminal connection error: WebSocket error occurred
Error: Terminal websocket connection lost. Reconnecting...
```

## Causa probable
El Terminal web embebido de Coolify usa un **WebSocket** (`wss://`). Si el sitio está detrás de Cloudflare, Cloudflare está bloqueando o corrompiendo esa conexión WebSocket (fréen Websockets deshabilitados o modo SSL incompatible).

## Para el desarrollador/compañero
1. En **Cloudflare** → la zona de `edgemarketing.art`:
   - **Network** → activa `WebSockets: On`.
   - **SSL/TLS** → usa `Full (strict)` (evita `Flexible` mientras el WebSocket falle).
2. Si sigue sin funcionar, intentar abrir Coolify por la **URL directa del servidor** (sin Cloudflare) para aislar el problema.
3. No cambiar código de AllMusic para este error: es de infraestructura (Cloudflare ↔ Coolify WebSocket), no del backend.

Registrar la nota en el día a día del proyecto: los cambios de dominio que pasen por Cloudflare deben revisar estos ajustes antes de implementar Terminal/Exec.
