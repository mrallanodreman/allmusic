import { isSafeRequestText, normalizeText, safeUrl } from './safe.js';

const PREFIX =
  typeof window !== 'undefined' && window.location?.pathname?.startsWith('/allmusic')
    ? '/allmusic'
    : '';

function endpoint(path) {
  return `${PREFIX}${path}`;
}

async function requestJson(path, { signal, method = 'GET', body } = {}) {
  const options = {
    method,
    signal,
    cache: 'no-store',
    credentials: 'same-origin',
  };
  if (body !== undefined) {
    options.headers = { 'Content-Type': 'application/json' };
    options.body = JSON.stringify(body);
  }
  const response = await fetch(endpoint(path), options);
  if (!response.ok) {
    let message = 'No se pudo completar la acción. Intentá de nuevo.';
    try {
      const data = await response.json();
      if (data && typeof data.error === 'string') {
        message = normalizeText(data.error, 120);
      }
    } catch {
      // Respuesta no JSON: se mantiene el mensaje genérico.
    }
    throw new Error(message);
  }
  return response.json();
}

export function fetchNow(signal) {
  return requestJson('/radio/now', { signal });
}

export function fetchMoods(signal) {
  return requestJson('/radio/moods', { signal });
}

export function postSuggestion(query, { signal, reason = 'web' } = {}) {
  const cleanQuery = normalizeText(query, 120);
  if (!isSafeRequestText(cleanQuery)) {
    return Promise.reject(new Error('Pedido inválido. Usá hasta 120 caracteres.'));
  }
  return requestJson('/radio/suggest', {
    method: 'POST',
    signal,
    body: {
      query: cleanQuery,
      reason: normalizeText(reason, 60),
      agent: 'ia-radio-web',
    },
  });
}

export function postAdvance({ signal } = {}) {
  return requestJson('/radio/advance', { method: 'POST', signal, body: {} });
}

/* Búsqueda personal: usa el mismo catálogo que el reproductor clásico.
   No envía pedidos a la cola compartida ni cambia el estado de Radio IA. */
export function searchTracks(query, { signal, limit = 12 } = {}) {
  const clean = normalizeText(query, 100);
  if (clean.length < 2) {
    return Promise.reject(new Error('Escribí al menos dos caracteres para buscar.'));
  }
  const size = Math.min(20, Math.max(1, Math.floor(Number(limit)) || 12));
  return requestJson(`/search?q=${encodeURIComponent(clean)}&limit=${size}`, { signal });
}

const YOUTUBE_VIDEO_ID = /^[A-Za-z0-9_-]{11}$/;

/* Stream local en el mismo origen. fast=1 reduce el timeout de yt-dlp en el
   backend; evita generar URLs externas sin validar. */
export function getTrackStreamUrl(videoId) {
  const id = normalizeText(videoId, 16);
  return YOUTUBE_VIDEO_ID.test(id) ? endpoint(`/stream/${encodeURIComponent(id)}?fast=1`) : null;
}

/* Fallback compatible con el reproductor original (convert/<id>).
   Solo se utilizan enlaces https seguros; nunca se ejecutan URLs arbitrarias. */
export async function resolveTrackUrl(videoId, { signal } = {}) {
  const id = normalizeText(videoId, 16);
  if (!YOUTUBE_VIDEO_ID.test(id)) throw new Error('Identificador de canción inválido.');
  const data = await requestJson(`/convert/${encodeURIComponent(id)}`, { signal });
  if (!data?.success || !data?.link) return null;
  return safeUrl(data.link);
}
