import { Icon } from './Icons.jsx';
import { VolumeFader } from './VolumeFader.jsx';
import { AudioReactiveMeter } from './AudioReactiveMeter.jsx';
import { formatTime, safeUrl } from '../lib/safe.js';

const asset = (name) => `${import.meta.env.BASE_URL}assets/radio-ui/${name}`;

/**
 * Canal 24 / cabina editorial.
 * Tres áreas independientes: arte de portada, información/controles,
 * y un fader de volumen físico. Ninguna imagen incluye texto del UI;
 * cada acción sigue enlazada al stream real de App.
 */
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
  analyserRef,
}) {
  const personal = mode === 'personal';
  const track = personal ? selectedTrack : now?.track;
  const title = track?.title || (personal ? 'Elegí una canción' : 'Sin pista en el aire');
  const artist = track?.artist || (personal ? 'Escuchá tu música, sin alterar la radio' : 'La cabina está preparando la rotación');
  const cover = safeUrl(track?.thumbnail);
  const elapsed = personal ? Number(personalElapsed) || 0 : Number(track?.elapsed) || 0;
  const duration = personal ? Number(personalDuration) || 0 : Number(track?.duration) || 0;
  const progress = duration > 0 ? Math.min(100, Math.max(0, (elapsed / duration) * 100)) : 0;
  const live = Boolean(now?.playing);

  const stateLabel = personal ? 'MODO PERSONAL' : live ? 'EN VIVO' : 'EN ESPERA';
  const signalLabel = audioError || (personal
    ? `ALLMUSIC · ${playing ? 'ESCUCHA PERSONAL' : 'LISTO PARA ESCUCHAR'}`
    : advancing ? 'SOLICITANDO SIGUIENTE TEMA…'
      : `CANAL 24 · ${live ? 'TRANSMISIÓN CONTINUA' : 'SEÑAL EN ESPERA'}`);

  return (
    <div className="stage-shell">
      <section className="stage panel" id="reproductor" aria-labelledby="stage-title">
        <header className="stage__head">
          <div className="stage__brand">
            <svg className="stage__crown" viewBox="0 0 72 52" fill="none" aria-hidden="true">
              <path d="M6 41 3 12 21 28 32 3 47 26 69 7 62 43 6 41Z" stroke="currentColor" strokeWidth="4" strokeLinejoin="round" />
              <path d="m10 49 53-1" stroke="currentColor" strokeWidth="4" strokeLinecap="round" />
            </svg>
            <div className="stage__title-paper">
              <h1 className="stage__title" id="stage-title">
                {personal ? (
                  <>TU <em>MÚSICA</em></>
                ) : (
                  <>CANAL <em>24</em> MIX</>
                )}
              </h1>
            </div>
          </div>
          <div className="stage__badges">
            <span className="stage__station-label">
              {personal ? 'ALLMUSIC' : 'IA RADIO'}
              <small>{personal ? 'ESCUCHA PERSONAL' : 'SEÑAL 24/7'}</small>
            </span>
            <span className={`stage__rec-sticker${live && !personal ? ' stage__rec-sticker--live' : ''}`} aria-label={live && !personal ? 'Transmisión en directo' : 'Cabina en espera'}>
              REC <i aria-hidden="true" />
            </span>
            <span className={`stage__live${personal ? ' stage__live--personal' : ''}`}>
              {stateLabel}
            </span>
          </div>
        </header>

        <div className="stage__body">
          <figure className="stage__cover-wrap">
            <div className="stage__cover">
              {cover ? (
                <img src={cover} alt={`Portada de ${title}`} />
              ) : (
                <span className="stage__cover-fallback" aria-hidden="true">
                  <strong>C24</strong>
                  <small>{personal ? 'TU MÚSICA' : 'LA RADIO'}</small>
                </span>
              )}
            </div>
            <figcaption className="stage__cover-caption">
              <span>{personal ? 'ALLMUSIC' : 'CANAL 24'}</span>
              <span>{stateLabel}</span>
            </figcaption>
          </figure>

          <div className="stage__info">
            <div className="stage__song-header">
              <span className="stage__eyebrow">
                {personal ? 'TU SELECCIÓN' : live ? 'SONANDO AHORA' : 'EN ESPERA'}
                <span className="stage__eyebrow-slashes" aria-hidden="true">///</span>
              </span>
            </div>
            <p className="stage__track" title={title}>{title}</p>
            <p className="stage__artist" title={artist}>{artist}</p>
            <div className="stage__tags" aria-label="Modo de reproducción">
              <span>{personal ? 'ALLMUSIC' : 'CANAL 24'}</span>
              <span>{personal ? 'A TU GUSTO' : 'RADIO IA'}</span>
              <span>{personal ? 'SOLO PARA VOS' : '24/7'}</span>
            </div>

            <div className="stage__timeline">
              <div className="stage__meter">
                <span className="sr-only">
                  Vúmetro conectado al audio real
                </span>
                <AudioReactiveMeter analyserRef={analyserRef} active={playing} variant="main" />
              </div>
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
            </div>

            <div className="stage__controls" role="group" aria-label="Controles de música">
              <button
                type="button"
                className="control control--transport"
                onClick={onToggle}
                disabled={!hasPlayable}
                aria-label={playing ? 'Pausar audio' : 'Reproducir audio'}
                title={playing ? 'Pausar audio' : 'Reproducir audio'}
              >
                <Icon name={playing ? 'pause' : 'play'} className="icon" />
              </button>
              <button
                type="button"
                className={`control control--search${searchOpen ? ' control--selected' : ''}`}
                onClick={onSearch}
                aria-label={searchOpen ? 'Cerrar buscador de música' : 'Buscar una canción para escuchar'}
                aria-controls="buscar-musica"
                aria-expanded={searchOpen}
                title="Buscar música"
              >
                <Icon name="search" className="icon" />
              </button>
              <button
                type="button"
                className={`control control--radio${!personal ? ' control--selected' : ''}`}
                onClick={onRadio}
                disabled={!hasStream}
                aria-label="Volver a la transmisión en vivo de Canal 24"
                aria-pressed={!personal}
                title="Radio 24/7"
              >
                <Icon name="radio" className="icon" />
              </button>
              <span className="stage__mode-label">
                MODO:
                <strong>{personal ? 'TU MÚSICA' : 'RADIO IA'} <b aria-hidden="true">///</b></strong>
              </span>
            </div>
          </div>

          <aside className="stage__fader" aria-label="Consola de volumen">
            <VolumeFader volume={volume} onVolume={onVolume} />
          </aside>
        </div>

        <footer className="stage__footer">
          <p className="stage__signal" role="status">{signalLabel}</p>
        </footer>
      </section>
      {!personal ? (
        <img className="stage__tape" src={asset('tape_canal_24_mix.png')} alt="" aria-hidden="true" />
      ) : null}
    </div>
  );
}
