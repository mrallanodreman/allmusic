import { Icon } from './Icons.jsx';
import { Equalizer } from './Equalizer.jsx';
import { formatTime, normalizeText, safeUrl } from '../lib/safe.js';

const asset = (name) => `${import.meta.env.BASE_URL}assets/radio-ui/${name}`;

export function NowPlayingBar({ now, playing, onToggle, activeMood }) {
  const track = now?.track;
  const title = normalizeText(track?.title, 80) || 'Señal IA Radio 24/7';
  const cover = safeUrl(track?.thumbnail);
  const elapsed = Number(track?.elapsed) || 0;
  const duration = Number(track?.duration) || 0;
  const progress = duration > 0 ? Math.min(100, Math.max(0, (elapsed / duration) * 100)) : 0;
  const stream = safeUrl(now?.stream_url);

  return (
    <div className="nowbar" role="region" aria-label="Barra de reproducción">
      <div className="nowbar__progress" style={{ width: `${progress}%` }} aria-hidden="true" />
      <div className="nowbar__inner">
        <button
          type="button"
          className="nowbar__play"
          onClick={onToggle}
          aria-label={playing ? 'Pausar transmisión' : 'Reproducir transmisión'}
        >
          <Icon name={playing ? 'pause' : 'play'} className="icon" />
        </button>
        {cover ? <img className="nowbar__cover" src={cover} alt="" /> : <img className="nowbar__rec" src={asset('badge_rec_dot.png')} alt="" aria-hidden="true" />}
        <div className="nowbar__info">
          <span className="nowbar__label">NOW PLAYING · CANAL 24</span>
          <strong title={title}>{title}</strong>
        </div>
        <Equalizer active={playing} compact />
        <span className="nowbar__time">{formatTime(elapsed)} / {formatTime(duration)}</span>
        {activeMood ? <span className="nowbar__mood">{activeMood}</span> : null}
        {stream ? (
          <a className="nowbar__stream" href={stream} target="_blank" rel="noopener noreferrer">
            ESCUCHAR EN VIVO
          </a>
        ) : null}
      </div>
    </div>
  );
}
