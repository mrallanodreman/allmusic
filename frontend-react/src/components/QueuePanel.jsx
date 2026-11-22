import { formatTime, normalizeText, safeUrl } from '../lib/safe.js';
import { useInView } from '../hooks/useInView.js';
import { Icon } from './Icons.jsx';

export function QueuePanel({ items, nextMood, likedIds = [], likePending = [], onToggleLike }) {
  const list = Array.isArray(items) ? items.slice(0, 8) : [];
  const mood = normalizeText(nextMood?.mood, 80);
  const liked = new Set(likedIds);
  const pending = new Set(likePending);
  const [revealRef, visible] = useInView();

  return (
    <section
      ref={revealRef}
      className={`queue panel reveal${visible ? ' reveal--in' : ''}`}
      id="cola"
      aria-labelledby="queue-title"
    >
      <div className="section-head">
        <h2 id="queue-title">SIGUIENTE EN LA COLA</h2>
        <span className="section-head__hint">{list.length} pendientes</span>
      </div>
      {list.length === 0 ? (
        <div className="queue__empty" role="status">
          <p className="empty">
            <Icon name="list" className="icon" />
            Cola vacía · pedí la primera canción
          </p>
          {mood ? (
            <p className="queue__mood">
              <span className="queue__mood-label">SIGUIENTE MOOD</span>
              <strong className="queue__mood-name">{mood}</strong>
            </p>
          ) : null}
        </div>
      ) : (
        <ol className="queue__list">
          {list.map((item, index) => {
            const title = normalizeText(item?.title, 90) || 'Sin título';
            const artist = normalizeText(item?.artist, 60);
            const cover = safeUrl(item?.thumbnail);
            const minutes = Number(item?.eta_minutes);
            return (
              <li className="queue__item" key={normalizeText(item?.request_id, 60) || normalizeText(item?.video_id, 60) || index}>
                <span className="queue__pos">{String(index + 1).padStart(2, '0')}</span>
                {cover ? <img className="queue__thumb" src={cover} alt="" loading="lazy" /> : <span className="queue__thumb queue__thumb--empty" />}
                <span className="queue__text">
                  <strong title={title}>{title}</strong>
                  {artist ? <small title={artist}>{artist}</small> : null}
                </span>
                <span className="queue__eta">{[0, 1, 2].includes(minutes) ? `~${minutes} min` : formatTime(item?.eta_seconds)}</span>
                {item?.video_id ? (
                  <button
                    className={`like-button${liked.has(item.video_id) ? ' is-liked' : ''}`}
                    type="button"
                    aria-label={`${liked.has(item.video_id) ? 'Quitar me gusta de' : 'Me gusta'} ${title}`}
                    aria-pressed={liked.has(item.video_id)}
                    disabled={pending.has(item.video_id)}
                    onClick={() => onToggleLike?.(item)}
                  >
                    ♥
                  </button>
                ) : null}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
