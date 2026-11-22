import { normalizeText, safeUrl } from '../lib/safe.js';
import { useInView } from '../hooks/useInView.js';

export function MostLikedPanel({ items, likedIds = [], likePending = [], onToggleLike }) {
  const list = Array.isArray(items) ? items.slice(0, 10) : [];
  const liked = new Set(likedIds);
  const pending = new Set(likePending);
  const [revealRef, visible] = useInView();

  return (
    <section
      ref={revealRef}
      className={`liked panel reveal${visible ? ' reveal--in' : ''}`}
      aria-labelledby="liked-title"
    >
      <div className="section-head">
        <h2 id="liked-title">MÁS LIKEADAS</h2>
        <span className="section-head__hint">favoritas de la comunidad</span>
      </div>
      {list.length === 0 ? (
        <p className="empty" role="status">Todavía no hay likes · elegí una canción de la cola.</p>
      ) : (
        <ol className="liked__list">
          {list.map((item, index) => {
            const videoId = normalizeText(item?.video_id, 16);
            const title = normalizeText(item?.title, 90) || 'Sin título';
            const artist = normalizeText(item?.artist, 60);
            const cover = safeUrl(item?.thumbnail);
            return (
              <li className="liked__item" key={videoId || `${title}-${index}`}>
                <span className="queue__pos">{String(index + 1).padStart(2, '0')}</span>
                {cover ? <img className="queue__thumb" src={cover} alt="" loading="lazy" /> : <span className="queue__thumb queue__thumb--empty" />}
                <span className="queue__text">
                  <strong title={title}>{title}</strong>
                  {artist ? <small title={artist}>{artist}</small> : null}
                </span>
                <span className="liked__count" aria-label={`${Number(item?.like_count) || 0} likes`}>
                  {Number(item?.like_count) || 0} ♥
                </span>
                {videoId ? (
                  <button
                    className={`like-button${liked.has(videoId) ? ' is-liked' : ''}`}
                    type="button"
                    aria-label={`${liked.has(videoId) ? 'Quitar me gusta de' : 'Me gusta'} ${title}`}
                    aria-pressed={liked.has(videoId)}
                    disabled={pending.has(videoId)}
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
