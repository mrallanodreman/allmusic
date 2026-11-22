import { normalizeText, safeUrl } from '../lib/safe.js';
import { useInView } from '../hooks/useInView.js';

export function MostLikedPanel({ items }) {
  const list = Array.isArray(items) ? items.slice(0, 10) : [];
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
        <p className="empty" role="status">Todavía no hay likes · marcá la canción que suena en el reproductor.</p>
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
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
