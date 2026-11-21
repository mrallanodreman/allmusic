const CONTROL_CHARS = /[\u0000-\u001f\u007f]/g;
const REQUEST_PATTERN = /^[\p{L}\p{N}\s,.'&!?¿¡:()\-]+$/u;

export function normalizeText(value, max = 160) {
  if (typeof value !== 'string' && typeof value !== 'number') return '';
  return String(value)
    .replace(CONTROL_CHARS, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, max);
}

export function isSafeRequestText(value, max = 120) {
  const text = normalizeText(value, max);
  return text.length >= 2 && text.length <= max && REQUEST_PATTERN.test(text);
}

// Solo https: o rutas relativas seguras. Nunca javascript:, data:, blob: ni //host.
export function safeUrl(value) {
  const text = normalizeText(value, 2048);
  if (!text || text.includes('\\')) return null;
  if (text.startsWith('/')) {
    if (text.startsWith('//') || text.includes('..')) return null;
    return text;
  }
  try {
    const url = new URL(text);
    return url.protocol === 'https:' ? url.href : null;
  } catch {
    return null;
  }
}

export function formatTime(seconds) {
  const n = Number(seconds);
  if (!Number.isFinite(n) || n < 0) return '--:--';
  const total = Math.floor(n);
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const secs = total % 60;
  const mm = String(minutes).padStart(2, '0');
  const ss = String(secs).padStart(2, '0');
  return `${hours > 0 ? `${hours}:` : ''}${mm}:${ss}`;
}

export function moodSlug(value) {
  return normalizeText(value, 40)
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '') || 'default';
}
