import { Icon } from './Icons.jsx';
import { Equalizer } from './Equalizer.jsx';
import { formatTime, normalizeText, safeUrl } from '../lib/safe.js';

const asset = (name) => `${import.meta.env.BASE_URL}assets/radio-ui/${name}`;

export function NowPlayingBar({
  now,
  playing,
  onToggle,
  volume,
  onVolume,
  onSkip,
  advancing,
  activeMood,
  hasStream,
}) {
  const track = now?.track;
  const title = normalizeText(track?.title, 80) || 'Señal IA Radio 24/7';
  const cover = safeUrl(track?.thumbnail);
  const elapsed = Number(track?.elapsed) || 0;
  const duration = Number(track?.duration) || 0;
  const progress = duration > 0 ? Math.min(100, Math.max(0, (elapsed / duration) * 100)) : 0;
  const volumePct = Math.round((Number(volume) || 0) * 100);

  return (
    <div className="nowbar" role="region" aria-label="Barra de reproducción">
      <div className="nowbar__progress" style={{ width: `${progress}%` }} aria-hidden="true" />
      <div className="nowbar__inner">
        <button
          type="button"
          className="nowbar__play"
          onClick={onToggle}
          disabled={!hasStream}
          aria-label={playing ? 'Pausar transmisión' : 'Reproducir transmisión'}
        >
          <Icon name={playing ? 'pause' : 'play'} className="icon" />
        </button>
        <button
          type="button"
          className="nowbar__skip"
          onClick={onSkip}
          disabled={advancing || !now?.playing}
          aria-label="Solicitar siguiente tema"
          title="Solicitar siguiente tema"
        >
          <Icon name="skip" className="icon" />
        </button>
        {cover ? <img className="nowbar__cover" src={cover} alt="" /> : <img className="nowbar__rec" src={asset('badge_rec_dot.png')} alt="" aria-hidden="true" />}
        <div className="nowbar__info">
          <span className="nowbar__label">NOW PLAYING · CANAL 24</span>
          <strong title={title}>{title}</strong>
        </div>
        <Equalizer active={playing} compact />
        <span className="nowbar__time">{formatTime(elapsed)} / {formatTime(duration)}</span>
        <label className="nowbar__volume" aria-label="Volumen">
          <Icon name={volumePct === 0 ? 'mute' : 'volume'} className="icon" />
          <input
            type="range"
            min="0"
            max="100"
            step="1"
            value={volumePct}
            onChange={(e) => onVolume(Number(e.target.value) / 100)}
          />
        </label>
        {activeMood ? <span className="nowbar__mood">{activeMood}</span> : null}
      </div>
    </div>
  );
}
