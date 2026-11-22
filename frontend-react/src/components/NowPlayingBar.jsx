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
  hasPlayable,
  mode = 'radio',
  selectedTrack,
  personalElapsed = 0,
  personalDuration = 0,
  onSearch,
  onRadio,
  searchOpen = false,
}) {
  const personal = mode === 'personal';
  const track = personal ? selectedTrack : now?.track;
  const title = normalizeText(track?.title, 80) || (personal ? 'Elegí tu música' : 'Señal IA Radio 24/7');
  const cover = safeUrl(track?.thumbnail);
  const elapsed = personal ? Number(personalElapsed) || 0 : Number(track?.elapsed) || 0;
  const duration = personal ? Number(personalDuration) || 0 : Number(track?.duration) || 0;
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
          disabled={!hasPlayable}
          aria-label={playing ? 'Pausar audio' : 'Reproducir audio'}
        >
          <Icon name={playing ? 'pause' : 'play'} className="icon" />
        </button>
        {!personal ? (
          <button
            type="button"
            className="nowbar__skip"
            onClick={onSkip}
            disabled={advancing || !now?.playing}
            aria-label="Solicitar siguiente tema de la radio para todos los oyentes"
            title="Siguiente tema de Radio 24/7"
          >
            <Icon name="skip" className="icon" />
          </button>
        ) : null}
        <button
          type="button"
          className={`nowbar__mode-button${searchOpen ? ' nowbar__mode-button--active' : ''}`}
          onClick={onSearch}
          aria-label="Abrir buscador de música"
          aria-expanded={searchOpen}
          title="Buscar música para vos"
        >
          <Icon name="search" className="icon" />
        </button>
        <button
          type="button"
          className={`nowbar__mode-button${!personal ? ' nowbar__mode-button--active' : ''}`}
          onClick={onRadio}
          disabled={!hasStream}
          aria-label="Sintonizar Radio Canal 24"
          aria-pressed={!personal}
          title="Radio 24/7"
        >
          <Icon name="radio" className="icon" />
        </button>
        {cover ? (
          <img className="nowbar__cover" src={cover} alt="" />
        ) : (
          <img className="nowbar__rec" src={asset('badge_rec_dot.png')} alt="" aria-hidden="true" />
        )}
        <div className="nowbar__info">
          <span className="nowbar__label">
            {personal ? 'TU MÚSICA · SOLO PARA VOS' : 'NOW PLAYING · CANAL 24'}
          </span>
          <strong title={title}>{title}</strong>
        </div>
        <Equalizer active={playing} compact />
        <span className="nowbar__time">
          {formatTime(elapsed)} / {duration > 0 ? formatTime(duration) : '--:--'}
        </span>
        <label className="nowbar__volume" aria-label="Volumen">
          <Icon name={volumePct === 0 ? 'mute' : 'volume'} className="icon" />
          <input
            type="range"
            min="0"
            max="100"
            step="1"
            value={volumePct}
            onChange={(event) => onVolume(Number(event.target.value) / 100)}
          />
        </label>
        {!personal && activeMood ? <span className="nowbar__mood">{activeMood}</span> : null}
      </div>
    </div>
  );
}
