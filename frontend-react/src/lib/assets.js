const PREFIX =
  typeof window !== 'undefined' && window.location?.pathname?.startsWith('/allmusic')
    ? '/allmusic'
    : '';

/** Recursos del artboard histórico servidos por Flask desde frontend/assets. */
export function legacyAsset(path) {
  const clean = String(path || '').replace(/^\/+/, '');
  return `${PREFIX}/assets/${clean}`;
}

/** Stickers/recortes generados para esta UI, copiados al build por Vite. */
export function uiAsset(name) {
  return `${import.meta.env.BASE_URL}assets/radio-ui/${name}`;
}

/** Enlaces internos respetando el prefijo del proxy inverso. */
export function appUrl(path = '/') {
  const clean = String(path || '').replace(/^\/+/, '');
  if (!clean) return `${PREFIX}/` || '/';
  return `${PREFIX}/${clean}`;
}

/** Fallback local para portadas remotas que fallan. */
export function fallbackImage(event) {
  const img = event?.currentTarget;
  if (!img || img.dataset.fallbackApplied) return;
  img.dataset.fallbackApplied = '1';
  img.src = legacyAsset('radio/radio-now-cover.png');
}
