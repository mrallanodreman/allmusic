import { useEffect, useState } from 'react';
import { Icon } from './Icons.jsx';

const LINKS = [
  { id: 'reproductor', label: 'Reproductor', icon: 'radio' },
  { id: 'moods', label: 'Moods', icon: 'bolt' },
  { id: 'top10', label: 'Pedidos', icon: 'star' },
  { id: 'cola', label: 'Cola', icon: 'list' },
  { id: 'historial', label: 'Historial', icon: 'clock' },
];

const SECTION_IDS = LINKS.map((link) => link.id);

function hashSection() {
  const hash = window.location.hash.slice(1);
  return SECTION_IDS.includes(hash) ? hash : SECTION_IDS[0];
}

export function Sidebar({ ticketsUsed }) {
  const [activeId, setActiveId] = useState(hashSection);

  useEffect(() => {
    const syncHash = () => setActiveId(hashSection());
    window.addEventListener('hashchange', syncHash);

    if (!('IntersectionObserver' in window)) {
      return () => window.removeEventListener('hashchange', syncHash);
    }

    const sections = SECTION_IDS.map((id) => document.getElementById(id)).filter(Boolean);
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActiveId(visible[0].target.id);
      },
      { rootMargin: '-18% 0px -62% 0px' }
    );
    sections.forEach((section) => observer.observe(section));

    return () => {
      window.removeEventListener('hashchange', syncHash);
      observer.disconnect();
    };
  }, []);

  return (
    <nav className="sidebar" aria-label="Navegación de IA Radio">
      <div className="sidebar__brand">
        <span className="sidebar__bolt"><Icon name="bolt" className="icon" /></span>
        <span className="sidebar__title">IA<br />RADIO</span>
        <span className="sidebar__sub">24/7</span>
      </div>
      <ul className="sidebar__nav">
        {LINKS.map((link) => (
          <li key={link.id}>
            <a
              className="sidebar__link"
              href={`#${link.id}`}
              aria-current={activeId === link.id ? 'location' : undefined}
            >
              <Icon name={link.icon} className="icon" />
              <span>{link.label}</span>
            </a>
          </li>
        ))}
      </ul>
      <div className="sidebar__tickets">
        <span className="sidebar__tickets-label">TICKETS USADOS</span>
        <strong aria-live="polite">{String(ticketsUsed).padStart(2, '0')}</strong>
        <span className="sidebar__tickets-note">reflejo visual de esta sesión</span>
      </div>
    </nav>
  );
}
