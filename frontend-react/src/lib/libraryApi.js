import { normalizeText, safeUrl } from './safe.js';

/**
 * API del AllMusic clásico reutilizada por la interfaz React.
 * Nunca se guardan contraseñas y se conserva la clave JWT histórica:
 * am_artist_token (sin migración de cuentas ni pérdida de perfiles).
 */
const PREFIX = typeof window !== 'undefined' && window.location.pathname.startsWith('/allmusic')
  ? '/allmusic' : '';

export function mediaUrl(path) {
  const url = safeUrl(path);
  if (!url) return null;
  if (url.startsWith('/allmusic/')) return url;
  if (url.startsWith('/')) return `${PREFIX}${url}`;
  return url;
}
export function getArtistToken() {
  try { return window.localStorage.getItem('am_artist_token') || ''; }
  catch { return ''; }
}
export function saveArtistToken(token) {
  try {
    if (token) window.localStorage.setItem('am_artist_token', token);
    else window.localStorage.removeItem('am_artist_token');
  } catch { /* sesión en memoria cuando storage no está disponible */ }
}

async function request(path, { method = 'GET', data, form, token, signal } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (data !== undefined) headers['Content-Type'] = 'application/json';
  const response = await fetch(`${PREFIX}${path}`, {
    method, headers, credentials: 'same-origin', cache: 'no-store', signal,
    body: form || (data !== undefined ? JSON.stringify(data) : undefined),
  });
  let body;
  try { body = await response.json(); } catch { body = {}; }
  if (!response.ok) {
    const error = new Error(
      normalizeText(body.error || body.message || 'No se pudo completar la operación.', 200)
    );
    error.status = response.status;
    throw error;
  }
  return body;
}

// Biblioteca compartida, compatible con las listas del sitio antiguo.
export const listPlaylists = (signal) => request('/playlists', { signal });
export const createPlaylist = (name, owner) => request('/playlists', {
  method: 'POST', data: { name: normalizeText(name, 100), created_by: normalizeText(owner, 40) || 'MfMood' },
});
export const removePlaylist = (id) => request(`/playlists/${encodeURIComponent(id)}`, { method: 'DELETE' });
export const addPlaylistTrack = (id, track) => request(
  `/playlists/${encodeURIComponent(id)}/tracks`, { method: 'POST', data: track }
);
export const removePlaylistTrack = (id, position) => request(
  `/playlists/${encodeURIComponent(id)}/tracks/${encodeURIComponent(position)}`,
  { method: 'DELETE' }
);

// Artistas (JWT y perfiles que ya existían).
export const loginArtist = (email, password) => request('/artists/auth/login', {
  method: 'POST', data: { email: email.trim(), password },
});
export const registerArtist = (email, password, artist_name) => request('/artists/auth/register', {
  method: 'POST', data: { email: email.trim(), password, artist_name: normalizeText(artist_name, 80) },
});
export const getArtistProfile = (token) => request('/artists/profile', { token });
export const updateArtistProfile = (token, data) => request('/artists/profile', {
  method: 'PUT', token, data,
});
export const uploadArtistPhoto = (token, kind, file) => {
  if (!['avatar', 'header'].includes(kind)) throw new Error('Tipo de imagen inválido.');
  const form = new FormData();
  form.append('file', file);
  return request(`/artists/profile/${kind}`, { method: 'POST', token, form });
};
export const createArtistAlbum = (token, data) => request('/artists/profile/albums', {
  method: 'POST', token, data,
});
export const removeArtistAlbum = (token, id) => request(
  `/artists/profile/albums/${encodeURIComponent(id)}`, { method: 'DELETE', token }
);
export const uploadArtistFile = (token, file) => {
  const form = new FormData();
  form.append('file', file);
  return request('/artists/profile/files', { method: 'POST', token, form });
};
export const removeArtistFile = (token, name) => request(
  `/artists/profile/files/${encodeURIComponent(name)}`, { method: 'DELETE', token }
);
export const uploadOwnTrack = (token, { file, title, genre, is_public, rights_declared, cover }) => {
  const form = new FormData();
  form.append('file', file);
  form.append('title', normalizeText(title, 200));
  form.append('genre', normalizeText(genre, 60));
  form.append('is_public', String(Boolean(is_public)));
  form.append('rights_declared', String(Boolean(rights_declared)));
  if (cover) form.append('cover', cover);
  return request('/tracks', { method: 'POST', token, form });
};
export const updateOwnTrack = (token, id, data) => request(
  `/tracks/${encodeURIComponent(id)}`, { method: 'PATCH', token, data }
);
export const deleteOwnTrack = (token, id) => request(
  `/tracks/${encodeURIComponent(id)}`, { method: 'DELETE', token }
);
export const activatePremium = (token) => request('/premium/activate', { method: 'POST', token });
export const getPremiumStatus = (token) => request('/premium/status', { token });
export const getArtistEarnings = (token) => request('/artists/earnings', { token });

// Descubrimiento de música subida por la comunidad.
export const listPublicTracks = (query = '', signal) => request(
  `/tracks/public?q=${encodeURIComponent(normalizeText(query, 100))}`, { signal }
);
export const countTrackPlay = (id) => request(`/tracks/${encodeURIComponent(id)}/play`, { method: 'POST' });
export const prepareTrackDownload = (id, token) => request(
  `/tracks/${encodeURIComponent(id)}/download`, { method: 'POST', token }
);

const YOUTUBE_ID = /^[A-Za-z0-9_-]{11}$/;
export function toPersonalTrack(item) {
  if (!item || typeof item !== 'object') return null;
  const id = normalizeText(item.id || item.videoId || '', 50);
  const legacySrc = safeUrl(item.directSrc || item.src || item.url);
  const oldId = /(?:^|\/)stream\/([\w-]{11})(?:\?|$)/.exec(String(item.src || ''));
  const videoId = YOUTUBE_ID.test(id) ? id : oldId?.[1] || '';
  const directSrc = legacySrc && !legacySrc.includes('/stream/') ? mediaUrl(legacySrc) : null;
  if (!videoId && !directSrc) return null;
  return {
    id: videoId,
    title: normalizeText(item.title, 160) || 'Sin título',
    artist: normalizeText(item.artist || item.artist_name || item.uploader, 100) || 'Artista',
    thumbnail: mediaUrl(item.thumbnail || item.thumb || item.cover),
    directSrc,
    duration: Number(item.duration) || 0,
    localTrackId: id && !YOUTUBE_ID.test(id) ? id : '',
  };
}
