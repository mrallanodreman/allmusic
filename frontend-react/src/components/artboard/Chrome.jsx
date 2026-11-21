import { useEffect, useState } from 'react';
import clsx from 'clsx';
import { appUrl } from '../../lib/assets.js';
import { normalizeText } from '../../lib/safe.js';

const NAV_ITEMS = [
  { id: 'live', label: 'En vivo' },
  { id: 'historial', label: 'Historial' },
  { id: 'buscar', label: 'Buscar', href: appUrl('/') },
  { id: 'playlists', label: 'Playlists', href: appUrl('/') },
  { id: 'musica', label: 'Tu música', href: appUrl('/') },
];

export function ArtboardNav({ onListen, onAdvance, onRefresh, listening, advancing }) {
  return (
    <>
      <nav className="artboard-nav" aria-label="Navegación de C24 Radio">
        {NAV_ITEMS.map((item) => (
          <a
            key={item.id}
            className={clsx('hotspot', `hit-${item.id}`)}
            href={item.href || `#${item.id}`}
            aria-label={item.label}
          >
            {item.label}
          </a>
        ))}
      </nav>
      <button
        type="button"
        className={clsx('hotspot', 'hit-listen', listening && 'is-listening')}
        onClick={onListen}
        aria-label={listening ? 'Detener la transmisión' : 'Escuchar en vivo'}
      >
        {listening ? 'Detener' : 'Escuchar en vivo'}
      </button>
      <button
        type="button"
        className="hotspot hit-advance"
        onClick={onAdvance}
        disabled={advancing}
        aria-label="Siguiente pista"
      >
        Siguiente
      </button>
      <button
        type="button"
        className="hotspot hit-refresh"
        onClick={onRefresh}
        aria-label="Actualizar estado"
      >
        Actualizar
      </button>
    </>
  );
}

function BroadcastClock() {
  const [clock, setClock] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setClock(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <time className="broadcast-clock" dateTime={clock.toISOString()}>
      {clock.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        second: '2-digit',
      })}
    </time>
  );
}

export function BroadcastRuntime({ ticker, live }) {
  const text = normalizeText(ticker, 180) || 'CANAL 24 RADIO // 24/7';
  return (
    <div className="runtime-state">
      <BroadcastClock />
      <span className={clsx('state-badge', live ? 'is-live' : 'is-paused')}>
        {live ? 'En vivo' : 'En pausa'}
      </span>
      <div className="ticker-window" aria-live="polite">
        <span>{text}</span>
        <span aria-hidden="true">{text}</span>
      </div>
    </div>
  );
}

export function Toast({ message }) {
  const [visible, setVisible] = useState('');

  useEffect(() => {
    if (!message) return undefined;
    setVisible(message);
    const timer = window.setTimeout(() => setVisible(''), 3200);
    return () => window.clearTimeout(timer);
  }, [message]);

  return (
    <div className={clsx('toast', visible && 'is-visible')} role="status" aria-live="polite">
      {visible}
    </div>
  );
}
