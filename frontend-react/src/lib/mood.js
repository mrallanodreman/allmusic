import { normalizeText } from './safe.js';

/** Moods inferidos de la señal, con las mismas reglas del dashboard C24 histórico. */
const RULES = [
  {
    key: 'jazz',
    pattern: /jazz|piano|bossa/i,
    label: 'JAZZ LATE',
    detail: 'Una franja nocturna con groove, piano y espacio para respirar.',
  },
  {
    key: 'lofi',
    pattern: /lo[- ]?fi|chill|ambient|relax/i,
    label: 'LO-FI / CHILL',
    detail: 'Baja las luces: texturas suaves y una señal para escuchar sin prisa.',
  },
  {
    key: 'synthwave',
    pattern: /synthwave|retro/i,
    label: 'SYNTHWAVE',
    detail: 'Neón, bajos analógicos y carretera nocturna en modo 2000s.',
  },
  {
    key: 'indie',
    pattern: /indie|alternative/i,
    label: 'INDIE ALT',
    detail: 'Guitarras al frente, señal alternativa y rotación fuera del molde.',
  },
  {
    key: 'night',
    pattern: /house|electronic|dance/i,
    label: 'NIGHT DANCE',
    detail: 'Pulso electrónico activado: la cabina está en modo pista.',
  },
  {
    key: 'rock',
    pattern: /rock/i,
    label: 'ROCK SIGNAL',
    detail: 'Amplificadores encendidos y clásicos con voltaje de radio.',
  },
  {
    key: 'kpop',
    pattern: /k-pop/i,
    label: 'K-POP MODE',
    detail: 'Pop de alto voltaje en la rotación de C24.',
  },
];

const STANDBY = {
  key: '',
  label: 'SIGNAL STANDBY',
  detail: 'La cabina está lista para recibir el próximo pedido.',
};

const LIVE_DEFAULT = {
  key: '',
  label: 'CANAL 24 MIX',
  detail: 'La señal está activa. El mood se infiere de la programación actual.',
};

export function inferMood(now) {
  const track = now?.track;
  const source = `${normalizeText(track?.reason, 160)} ${normalizeText(track?.title, 160)}`;
  const match = RULES.find((rule) => rule.pattern.test(source));
  if (match) return match;
  return now?.playing ? LIVE_DEFAULT : STANDBY;
}
