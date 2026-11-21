import { Icon } from './Icons.jsx';

const LINKS = [
  { id: 'reproductor', label: 'Reproductor', icon: 'radio' },
  { id: 'moods', label: 'Moods', icon: 'bolt' },
  { id: 'top10', label: 'Pedidos', icon: 'star' },
  { id: 'cola', label: 'Cola', icon: 'list' },
  { id: 'historial', label: 'Historial', icon: 'clock' },
];

export function Sidebar({ ticketsUsed }) {
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
            <a className="sidebar__link" href={`#${link.id}`}>
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
