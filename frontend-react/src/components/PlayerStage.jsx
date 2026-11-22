import { Icon } from './Icons.jsx';
import { Equalizer } from './Equalizer.jsx';
import { formatTime, safeUrl } from '../lib/safe.js';

const asset = (name) => `${import.meta.env.BASE_URL}assets/radio-ui/${name}`;

export function PlayerStage({ now, playing, onToggle }) {
  const track = now?.track;
  const title = track?.title || 'Sin pista en el aire';
  const artist = track?.artist || 'La cabina está armando la rotación';
  const cover = safeUrl(track?.thumbnail);
  const elapsed = Number(track?.elapsed) || 0;
  const duration = Number(track?.duration) || 0;
  const progress = duration > 0 ? Math.min(100, Math.max(0, (elapsed / duration) * 100)) : 0;
  const live = Boolean(now?.playing);

  return (
    <section className="stage panel" id="reproductor" aria-labelledby="stage-title">
      <img className="stage__tape" src={asset('tape_canal_24_mix.png')} alt="" aria-hidden="true" />
      <div className="stage__head">
        <div className="stage__brand">
          <span className="stage__kicker">IA RADIO · SEÑAL 24/7</span>
          <h1 className="stage__title" id="stage-title">CANAL 24 MIX</h1>
        </div>
        <div className="stage__badges">
          <img src={asset('badge_rec_dot.png')} alt="REC" className="stage__rec" />
          <span className="stage__live">EN VIVO</span>
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
            <span>CANAL 24</span>
            <span>{live ? 'EN VIVO' : 'EN ESPERA'}</span>
          </figcaption>
        </figure>

        <div className="stage__info">
          <p className="stage__eyebrow">{live ? 'SONANDO AHORA' : 'AI RADIO · EN ESPERA'}</p>
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
            <span>{duration > 0 ? formatTime(duration) : live ? 'EN VIVO' : '--:--'}</span>
          </div>
          <div className="stage__footer">
            <div className="stage__controls">
              <button
                type="button"
                className="control"
                onClick={onToggle}
                aria-label={playing ? 'Pausar transmisión' : 'Reproducir transmisión'}
              >
                <Icon name={playing ? 'pause' : 'play'} className="icon" />
              </button>
              <Equalizer active={playing} />
            </div>
            <p className="stage__signal">CANAL 24 · {live ? 'TRANSMISIÓN CONTINUA' : 'SEÑAL EN ESPERA'}</p>
          </div>
        </div>
      </div>
    </section>
  );
}
