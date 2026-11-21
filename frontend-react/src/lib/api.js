import { isSafeRequestText, normalizeText } from './safe.js';

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
