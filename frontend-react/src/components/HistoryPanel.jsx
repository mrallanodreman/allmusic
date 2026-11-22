import { normalizeText, safeUrl } from '../lib/safe.js';
import { useInView } from '../hooks/useInView.js';
import { Icon } from './Icons.jsx';

export function HistoryPanel({ items }) {
  const list = Array.isArray(items) ? items.slice(0, 6) : [];
  const [revealRef, visible] = useInView();

  return (
    <section
      ref={revealRef}
      className={`history panel reveal${visible ? ' reveal--in' : ''}`}
      id="historial"
      aria-labelledby="history-title"
    >
      <div className="section-head">
        <h2 id="history-title">HISTORIAL RECIENTE</h2>
        <span className="section-head__hint">últimas en el aire</span>
      </div>
      {list.length === 0 ? (
        <p className="empty" role="status">
          <Icon name="clock" className="icon" />
          Sin historial todavía
        </p>
      ) : (
        <ul className="history__list">
          {list.map((item, index) => {
            const title = normalizeText(item?.title, 80) || 'Sin título';
            const artist = normalizeText(item?.artist, 50);
            const cover = safeUrl(item?.thumbnail);
            return (
              <li className="history__item" key={normalizeText(item?.video_id, 60) || `${title}-${index}`}>
                {cover ? <img src={cover} alt="" loading="lazy" /> : <span className="history__dot" aria-hidden="true" />}
                <span className="history__text">
                  <strong title={title}>{title}</strong>
                  {artist ? <small title={artist}>{artist}</small> : null}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
