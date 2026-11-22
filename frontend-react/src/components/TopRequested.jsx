import { normalizeText, safeUrl } from '../lib/safe.js';
import { useInView } from '../hooks/useInView.js';

export function TopRequested({ items }) {
  const list = Array.isArray(items) ? items.slice(0, 10) : [];
  const [revealRef, visible] = useInView();

  return (
    <section
      ref={revealRef}
      className={`top panel reveal${visible ? ' reveal--in' : ''}`}
      id="top10"
      aria-labelledby="top-title"
    >
      <img
        className="top__banner"
        src={`${import.meta.env.BASE_URL}assets/radio-ui/banner_top_10.png`}
        alt=""
        aria-hidden="true"
      />
      <h2 className="sr-only" id="top-title">Los 10 más pedidos</h2>
      {list.length === 0 ? (
        <p className="empty" role="status">Todavía no hay pedidos registrados.</p>
      ) : (
        <ol className="top__list">
          {list.map((item, index) => {
            const title = normalizeText(item?.title, 90) || 'Sin título';
            const artist = normalizeText(item?.artist, 60);
            const cover = safeUrl(item?.thumbnail);
            return (
              <li
                className={`top__item${index === 0 ? ' top__item--first' : ''}`}
                key={normalizeText(item?.video_id, 60) || `${title}-${index}`}
              >
                <span className="top__rank">{String(index + 1).padStart(2, '0')}</span>
                {cover ? <img className="top__thumb" src={cover} alt="" loading="lazy" /> : <span className="top__thumb top__thumb--empty" />}
                <span className="top__text">
                  <strong title={title}>{title}</strong>
                  {artist ? <small title={artist}>{artist}</small> : null}
                </span>
                <span className="top__count" aria-label={`${Number(item?.request_count) || 0} pedidos`}>
                  {Number(item?.request_count) || 0}
                </span>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
