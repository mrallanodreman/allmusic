import clsx from 'clsx';
import { fallbackImage, legacyAsset } from '../../lib/assets.js';
import { formatTime, isSafeRequestText, normalizeText, safeUrl } from '../../lib/safe.js';
import { Equalizer } from '../Equalizer.jsx';

const FALLBACK_COVER = legacyAsset('radio/radio-now-cover.png');
const REQUEST_MAX = 120;

const MOOD_CHIPS = [
  { key: 'lofi', query: 'lo-fi chill', label: 'LO-FI', file: 'mood-button-lofi.png' },
  { key: 'synthwave', query: 'synthwave retro', label: 'SYNTHWAVE', file: 'mood-button-synthwave.png' },
  { key: 'rock', query: 'rock clásico 80s', label: 'ROCK 80s', file: 'mood-button-rock80s.png' },
  { key: 'jazz', query: 'jazz piano relax', label: 'JAZZ LATE', file: 'mood-button-jazzlate.png' },
  { key: 'night', query: 'deep house mix', label: 'NIGHT DANCE', file: 'mood-button-nightdance.png' },
];

function trackThumb(item) {
  const direct = safeUrl(item?.thumbnail);
  if (direct) return direct;
  const id = normalizeText(item?.video_id, 64);
  if (/^[A-Za-z0-9_-]{6,64}$/.test(id)) {
    return safeUrl(`https://i.ytimg.com/vi/${id}/hqdefault.jpg`) || FALLBACK_COVER;
  }
  return FALLBACK_COVER;
}

export function NowPanel({ now, live }) {
  const track = now?.track;
  const title = normalizeText(track?.title, 120) || 'Sin pista en el aire';
  const artist = normalizeText(track?.artist || track?.uploader, 120) || 'C24';
  const elapsed = Number(track?.elapsed) || 0;
  const duration = Number(track?.duration) || 0;
  const progress = duration > 0 ? Math.min(100, Math.max(0, (elapsed / duration) * 100)) : 0;

  return (
    <>
      <img
        id="live"
        className="dynamic-cover dynamic-ui"
        src={trackThumb(track)}
        alt="Portada del tema actual"
        onError={fallbackImage}
      />
      <div className={clsx('dynamic-live-copy', 'dynamic-ui', live && 'is-live')} aria-live="polite">
        <div className="now-title" title={title}>{title}</div>
        <div className="now-artist" title={artist}>{artist}</div>
        <div className="now-station">CANAL 24 Pro</div>
        <div className="now-time">
          <span>{formatTime(elapsed)}</span>
          <span>/</span>
          <span>{formatTime(duration)}</span>
          <Equalizer active={live} compact />
        </div>
      </div>
      <div
        className="dynamic-progress dynamic-ui"
        role="progressbar"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={Math.round(progress)}
        aria-label="Progreso de la pista"
      >
        <i style={{ width: `${progress}%` }} />
      </div>
    </>
  );
}

export function RequestPanel({ value, inputRef, onChange, pending, disabled, notice, onSubmit }) {
  const valid = isSafeRequestText(value, REQUEST_MAX);
  const blocked = pending || disabled;

  async function handleSubmit(event) {
    event.preventDefault();
    if (!valid || blocked) return;
    await onSubmit(value);
  }

  return (
    <form className="hit-request" onSubmit={handleSubmit} aria-label="Pedir una canción o un mood">
      <label className="visually-hidden" htmlFor="request-input">
        Canción o mood a encolar
      </label>
      <input
        id="request-input"
        ref={inputRef}
        type="text"
        inputMode="text"
        autoComplete="off"
        maxLength={REQUEST_MAX}
        placeholder="PIDE UNA CANCIÓN O UN MOOD..."
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={blocked}
        aria-describedby="request-help"
      />
      <button type="submit" disabled={!valid || blocked} aria-label="Pedir">
        {pending ? '…' : 'PEDIR'}
      </button>
      <span className="visually-hidden" id="request-help" aria-live="polite">
        {notice || `${value.length}/${REQUEST_MAX} caracteres`}
      </span>
    </form>
  );
}

export function MoodPanel({ mood, pending, onSelect }) {
  return (
    <>
      <section className="dynamic-mood dynamic-ui" aria-labelledby="mood-title">
        <h2 className="visually-hidden" id="mood-title">Mood de la señal</h2>
        <strong className="mood-value">{mood.label}</strong>
        <p className="mood-detail">{mood.detail}</p>
      </section>
      <div className="mood-buttons" aria-label="Moods rápidos">
        {MOOD_CHIPS.map((chip) => {
          const active = mood.key === chip.key;
          return (
            <button
              key={chip.key}
              type="button"
              className={clsx('mood-chip', `mood-chip-button-${chip.key}`, active && 'is-active')}
              style={{ backgroundImage: `url("${legacyAsset(`radio/c24/mood/${chip.file}`)}")` }}
              onClick={() => onSelect(chip.query)}
              disabled={pending}
              aria-label={`Pedir mood ${chip.label}`}
              aria-pressed={active}
            >
              <span className="visually-hidden">{chip.label}</span>
            </button>
          );
        })}
      </div>
    </>
  );
}

export function TopPanel({ items }) {
  const list = Array.isArray(items)
    ? items
        .filter((item) => Number(item?.request_count) > 0)
        .slice(0, 10)
    : [];
  const max = list.reduce((acc, item) => Math.max(acc, Number(item?.request_count) || 0), 0);
  const total = list.reduce((acc, item) => acc + Math.max(0, Number(item?.request_count) || 0), 0);

  return (
    <section className="dynamic-top dynamic-ui" id="top10" aria-labelledby="top-title">
      <h2 className="visually-hidden" id="top-title">Los 10 más pedidos</h2>
      {list.length === 0 ? (
        <p className="empty">Todavía no hay pedidos registrados.</p>
      ) : (
        <ol>
          {list.map((item, index) => {
            const title = normalizeText(item?.title, 90) || 'Sin título';
            const artist = normalizeText(item?.artist, 60) || 'C24';
            const count = Math.max(0, Number(item?.request_count) || 0);
            const width = max > 0 ? Math.max(10, Math.round((count / max) * 100)) : 0;
            return (
              <li className="requested-item" key={normalizeText(item?.video_id, 60) || `${title}-${index}`}>
                <span className="requested-rank">{String(index + 1).padStart(2, '0')}</span>
                <img src={trackThumb(item)} alt="" loading="lazy" onError={fallbackImage} />
                <span className="requested-info">
                  <strong title={title}>{title}</strong>
                  <small title={artist}>{artist}</small>
                  <span className="requested-meter" aria-hidden="true">
                    <i style={{ width: `${width}%` }} />
                  </span>
                </span>
                <span className="requested-count" aria-label={`${count} pedidos`}>
                  <b>{count}</b>
                  <small>PEDIDOS</small>
                </span>
              </li>
            );
          })}
        </ol>
      )}
      <span className="panel-meta">{total > 0 ? `${total} PEDIDOS` : 'ESPERANDO PEDIDOS'}</span>
    </section>
  );
}

export function QueuePanel({ items }) {
  const list = Array.isArray(items) ? items.slice(0, 8) : [];

  return (
    <section className="dynamic-queue dynamic-ui" id="cola" aria-labelledby="queue-title">
      <h2 className="visually-hidden" id="queue-title">Siguiente en la cola</h2>
      {list.length === 0 ? (
        <p className="empty">La cola está vacía.</p>
      ) : (
        <ul>
          {list.map((item, index) => {
            const title = normalizeText(item?.title, 90) || 'Sin título';
            const artist = normalizeText(item?.artist, 60);
            const minutes = Number(item?.eta_minutes);
            const eta =
              Number.isFinite(minutes) && minutes >= 0
                ? minutes < 1
                  ? 'menos de 1 min'
                  : `${minutes} min`
                : '';
            return (
              <li className="q" key={normalizeText(item?.request_id, 60) || normalizeText(item?.video_id, 60) || index}>
                <span className="n">{String(index + 1).padStart(2, '0')}</span>
                <img src={trackThumb(item)} alt="" loading="lazy" onError={fallbackImage} />
                <span className="q-text">
                  <span className="tit" title={title}>{title}</span>
                  <span className="sub" title={artist}>
                    {artist}
                    {normalizeText(item?.suggested_by, 30) ? ` · ${normalizeText(item?.suggested_by, 30)}` : ''}
                    {eta ? ` · ${eta}` : ''}
                  </span>
                </span>
              </li>
            );
          })}
        </ul>
      )}
      <span className="panel-meta">{list.length > 0 ? `${String(list.length).padStart(2, '0')} EN COLA` : 'COLA VACÍA'}</span>
    </section>
  );
}

export function HistoryPanel({ items }) {
  const list = Array.isArray(items) ? items.slice(0, 8) : [];

  return (
    <section className="dynamic-history dynamic-ui" id="historial" aria-labelledby="history-title">
      <h2 className="visually-hidden" id="history-title">Historial reciente</h2>
      {list.length === 0 ? (
        <p className="empty">Todavía no hay historial.</p>
      ) : (
        <ul>
          {list.map((item, index) => {
            const title = normalizeText(item?.title, 90) || 'Sin título';
            return (
              <li key={normalizeText(item?.video_id, 60) || `${title}-${index}`} title={title}>
                {title}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
