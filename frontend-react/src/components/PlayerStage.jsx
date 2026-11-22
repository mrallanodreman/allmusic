import { Icon } from './Icons.jsx';
import { Equalizer } from './Equalizer.jsx';
import { formatTime, safeUrl } from '../lib/safe.js';

const asset = (name) => `${import.meta.env.BASE_URL}assets/radio-ui/${name}`;

export function PlayerStage({
  now,
  playing,
  onToggle,
  volume,
  onVolume,
  onSkip,
  advancing,
  audioError,
  hasStream,
  hasPlayable,
  mode = 'radio',
  selectedTrack,
  personalElapsed = 0,
  personalDuration = 0,
  searchOpen = false,
  onSearch,
  onRadio,
}) {
  const personal = mode === 'personal';
  const track = personal ? selectedTrack : now?.track;
  const title = track?.title || (personal ? 'Elegí una canción en el buscador' : 'Sin pista en el aire');
  const artist = track?.artist || (personal ? 'Tu selección suena solo para vos' : 'La cabina está armando la rotación');
  const cover = safeUrl(track?.thumbnail);
  const elapsed = personal ? Number(personalElapsed) || 0 : Number(track?.elapsed) || 0;
  const duration = personal ? Number(personalDuration) || 0 : Number(track?.duration) || 0;
  const progress = duration > 0 ? Math.min(100, Math.max(0, (elapsed / duration) * 100)) : 0;
  const live = Boolean(now?.playing);
  const volumePct = Math.round((Number(volume) || 0) * 100);

  return (
    <div className="stage-shell">
      <section className="stage panel" id="reproductor" aria-labelledby="stage-title">
        <div className="stage__head">
          <div className="stage__brand">
            <span className="stage__kicker">
              {personal ? 'ALLMUSIC · ESCUCHA A TU GUSTO' : 'IA RADIO · SEÑAL 24/7'}
            </span>
            <h1 className="stage__title" id="stage-title">
              {personal ? 'TU MÚSICA' : 'CANAL 24 MIX'}
            </h1>
          </div>
          <div className="stage__badges">
            {personal ? (
              <span className="stage__personal-badge">
                <Icon name="music" className="icon" />
                PERSONAL
              </span>
            ) : (
              <>
                <img src={asset('badge_rec_dot.png')} alt="REC" className="stage__rec" />
                <span className="stage__live">{live ? 'EN VIVO' : 'EN ESPERA'}</span>
              </>
            )}
          </div>
        </div>

        <div className="stage__body">
          <figure className="stage__cover-wrap">
            <div className="stage__cover">
              {cover ? (
                <img src={cover} alt={`Carátula de ${title}`} />
              ) : (
                <span className="stage__cover-fallback" aria-hidden="true">C24</span>
              )}
              <Equalizer active={playing} wave />
              <span className="stage__frame" aria-hidden="true" />
            </div>
            <figcaption className="stage__cover-caption">
              <span>{personal ? 'ALLMUSIC' : 'CANAL 24'}</span>
              <span>{personal ? 'MODO PERSONAL' : live ? 'EN VIVO' : 'EN ESPERA'}</span>
            </figcaption>
          </figure>

          <div className="stage__info">
            <p className="stage__eyebrow">
              {personal ? 'SONANDO PARA VOS' : live ? 'SONANDO AHORA' : 'IA RADIO · EN ESPERA'}
            </p>
            <p className="stage__track" title={title}>{title}</p>
            <p className="stage__artist" title={artist}>{artist}</p>
            <div
              className="stage__progress"
              role="progressbar"
              aria-valuemin="0"
              aria-valuemax="100"
              aria-valuenow={Math.round(progress)}
              aria-label="Progreso de la pista"
            >
              <span style={{ width: `${progress}%` }} />
            </div>
            <div className="stage__times">
              <span>{formatTime(elapsed)}</span>
              <span>{duration > 0 ? formatTime(duration) : !personal && live ? 'EN VIVO' : '--:--'}</span>
            </div>
            <div className="stage__footer">
              <div className="stage__controls" role="group" aria-label="Controles de reproducción y selección">
                <button
                  type="button"
                  className="control control--transport"
                  onClick={onToggle}
                  disabled={!hasPlayable}
                  aria-label={playing ? 'Pausar audio' : 'Reproducir audio'}
                  title={playing ? 'Pausar' : 'Reproducir'}
                >
                  <Icon name={playing ? 'pause' : 'play'} className="icon" />
                  <span className="control__caption">{playing ? 'PAUSA' : 'PLAY'}</span>
                </button>
                <button
                  type="button"
                  className={`control control--search${searchOpen ? ' control--selected' : ''}`}
                  onClick={onSearch}
                  aria-label={searchOpen ? 'Cerrar buscador de música' : 'Buscar una canción para escuchar'}
                  aria-controls="buscar-musica"
                  aria-expanded={searchOpen}
                  title="Buscar canción"
                >
                  <Icon name="search" className="icon" />
                  <span className="control__caption">BUSCAR</span>
                </button>
                <button
                  type="button"
                  className={`control control--radio${!personal ? ' control--selected' : ''}`}
                  onClick={onRadio}
                  disabled={!hasStream}
                  aria-label="Volver a la transmisión en vivo de Canal 24"
                  aria-pressed={!personal}
                  title="Escuchar Radio 24/7"
                >
                  <Icon name="radio" className="icon" />
                  <span className="control__caption">RADIO</span>
                </button>
                <label className="stage__volume" aria-label="Volumen">
                  <Icon name={volumePct === 0 ? 'mute' : 'volume'} className="icon" />
                  <input
                    type="range"
                    min="0"
                    max="100"
                    step="1"
                    value={volumePct}
                    onChange={(event) => onVolume(Number(event.target.value) / 100)}
                  />
                  <span className="stage__volume-value">{volumePct}%</span>
                </label>
                <Equalizer active={playing} />
              </div>
              <p className="stage__signal" role="status">
                {audioError || (personal
                  ? `ALLMUSIC · ${playing ? 'REPRODUCCIÓN PERSONAL' : 'LISTO PARA ESCUCHAR'}`
                  : advancing ? 'SOLICITANDO SIGUIENTE…'
                    : `CANAL 24 · ${live ? 'TRANSMISIÓN CONTINUA' : 'SEÑAL EN ESPERA'}`)}
              </p>
            </div>
          </div>
        </div>
      </section>
      {!personal ? (
        <img className="stage__tape" src={asset('tape_canal_24_mix.png')} alt="" aria-hidden="true" />
      ) : null}
    </div>
  );
}
