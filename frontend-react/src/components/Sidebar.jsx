import { useEffect, useState } from 'react';
import { Icon } from './Icons.jsx';
import { AudioReactiveMeter } from './AudioReactiveMeter.jsx';

// Navegación principal como en el arte de referencia; los controles propios
// de la Radio IA también quedan accesibles en la franja inferior.
const MAIN = [
  { id: 'reproductor', label: 'EN VIVO', icon: 'radio', kind: 'section' },
  { id: 'historial', label: 'HISTORIAL', icon: 'clock', kind: 'section' },
  { id: 'buscar', label: 'BUSCAR', icon: 'search', kind: 'search' },
  { id: 'playlists', label: 'PLAYLISTS', icon: 'list', kind: 'library' },
  { id: 'mymusic', label: 'TU MÚSICA', icon: 'star', kind: 'library' },
];
const SHORTCUTS = [
  { id: 'moods', label: 'MOODS' },
  { id: 'top10', label: 'TOP 10' },
  { id: 'cola', label: 'COLA' },
];
const SECTION_IDS = ['reproductor', 'historial', 'moods', 'top10', 'cola'];

function getActiveSection() {
  if (typeof window === 'undefined') return 'reproductor';
  const fragment = window.location.hash.slice(1);
  if (fragment === 'buscar-musica') return 'buscar';
  return SECTION_IDS.includes(fragment) ? fragment : 'reproductor';
}

function openLibrary(event, tab) {
  // El iframe de Radio IA comparte origen con AllMusic y puede abrir sus
  // pestañas reales sin perder el estado de reproducción del sitio padre.
  try {
    if (window.parent !== window && typeof window.parent.switchTab === 'function') {
      event.preventDefault();
      window.parent.switchTab(tab);
    }
  } catch {
    // Si cambia el origen, el enlace abre el sitio completo en _top.
  }
}

function formatTimecode(value) {
  const totalFrames = Math.max(0, Math.floor((Number(value) || 0) * 25));
  return [
    Math.floor(totalFrames / 90000),
    Math.floor(totalFrames / 1500) % 60,
    Math.floor(totalFrames / 25) % 60,
    totalFrames % 25,
  ].map((number) => String(number).padStart(2, '0')).join(':');
}

export function Sidebar({ ticketsUsed = 0, onAir = false, elapsed = 0, onOpenSearch, analyserRef, listening = false }) {
  const [activeId, setActiveId] = useState(getActiveSection);
  const [counter, setCounter] = useState(() => formatTimecode(elapsed));

  useEffect(() => {
    const onHashChange = () => setActiveId(getActiveSection());
    window.addEventListener('hashchange', onHashChange);
    if (!('IntersectionObserver' in window)) {
      return () => window.removeEventListener('hashchange', onHashChange);
    }
    const sections = SECTION_IDS.map((id) => document.getElementById(id)).filter(Boolean);
    const observer = new IntersectionObserver((entries) => {
      const visible = entries.filter((entry) => entry.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (visible[0] && window.location.hash !== '#request-input') {
        setActiveId(visible[0].target.id);
      }
    }, { rootMargin: '-18% 0px -62% 0px' });
    sections.forEach((section) => observer.observe(section));
    return () => {
      window.removeEventListener('hashchange', onHashChange);
      observer.disconnect();
    };
  }, []);

  useEffect(() => {
    const baseline = Math.max(0, Number(elapsed) || 0);
    setCounter(formatTimecode(baseline));
    if (!onAir) return undefined;
    const beganAt = Date.now();
    const timer = window.setInterval(() => {
      setCounter(formatTimecode(baseline + (Date.now() - beganAt) / 1000));
    }, 200);
    return () => window.clearInterval(timer);
  }, [elapsed, onAir]);

  return (
    <nav className="sidebar" aria-label="Navegación de IA Radio">
      <div className="sidebar__identity">
        <span>C24 / 001</span>
        <span>SEÑAL PRINCIPAL</span>
        <span className="sidebar__identity-dot" aria-hidden="true" />
      </div>

      <ul className="sidebar__nav">
        {MAIN.map((link) => {
          const current = activeId === link.id;
          const href = link.kind === 'search' ? '#buscar-musica'
            : link.kind === 'library' ? '/allmusic/' : `#${link.id}`;
          return (
            <li key={link.id}>
              <a
                className="sidebar__link"
                href={href}
                target={link.kind === 'library' ? '_top' : undefined}
                aria-current={current ? 'location' : undefined}
                onClick={(event) => {
                  if (link.kind === 'library') {
                    openLibrary(event, link.id);
                  } else if (link.kind === 'search') {
                    event.preventDefault();
                    setActiveId('buscar');
                    onOpenSearch?.();
                  } else {
                    setActiveId(link.id);
                  }
                }}
              >
                <Icon name={link.icon} className="icon sidebar__link-icon" />
                <span>{link.label}</span>
                {current ? <span className="sidebar__active-dot" aria-hidden="true" /> : null}
              </a>
            </li>
          );
        })}
      </ul>

      <div className="sidebar__broadcast">
        <div className="sidebar__master">
          <span className="sidebar__master-ticket">MASTER<br />EN VIVO</span>
          <span className="sidebar__master-247">24/7</span>
        </div>
        <span className="sidebar__caption">CANAL 24 · TRANSMISIÓN CONTINUA</span>
      </div>

      <div className="sidebar__hero" aria-label="IA RADIO">
        <span className="sidebar__hero-ia">IA</span>
        <span className="sidebar__hero-radio">RADIO</span>
        <Icon name="bolt" className="icon sidebar__hero-bolt" />
      </div>

      <div className="sidebar__signal">
        <AudioReactiveMeter analyserRef={analyserRef} active={listening} variant="sidebar" />
      </div>

      <div className="sidebar__station">SEÑAL PRINCIPAL // ÁTICO // QUITO</div>

      <div className="sidebar__footer">
        <div className="sidebar__timecode">
          <span>TCR</span>
          <output aria-label="Tiempo de reproducción actual">{counter}</output>
        </div>
        <div className="sidebar__footer-bottom">
          <span className={`sidebar__record${onAir ? ' sidebar__record--live' : ''}`}>
            {onAir ? 'REC' : 'STBY'}
            <span className="sidebar__record-dot" aria-hidden="true" />
          </span>
          <div className="sidebar__tickets">
            <span>PEDIDOS DE<br />ESTA SESIÓN</span>
            <strong aria-live="polite">{String(ticketsUsed).padStart(2, '0')}</strong>
          </div>
        </div>
      </div>

      <div className="sidebar__shortcuts" aria-label="Accesos rápidos a Radio IA">
        {SHORTCUTS.map((link) => (
          <a
            key={link.id}
            className="sidebar__shortcut"
            href={`#${link.id}`}
            aria-current={activeId === link.id ? 'location' : undefined}
            onClick={() => setActiveId(link.id)}
          >
            {link.label}
          </a>
        ))}
      </div>
    </nav>
  );
}
