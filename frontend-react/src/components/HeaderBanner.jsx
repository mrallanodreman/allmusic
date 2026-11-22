import { useEffect, useState } from 'react';
import { Icon } from './Icons.jsx';

const asset = (name) => `${import.meta.env.BASE_URL}assets/radio-ui/${name}`;

export function HeaderBanner({ live, children }) {
  const [clock, setClock] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setClock(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const timecode = clock.toLocaleTimeString('es-EC', { hour12: false });

  return (
    <header className="masthead" id="arriba">
      <div className="masthead__topline">
        <div className="masthead__topline-identity">
          <span className="masthead__channel">CH 24</span>
          <span>RADIO INDEPENDIENTE / SEÑAL DIGITAL</span>
        </div>
        <div className="masthead__topline-right">
          <span className="masthead__topline-dot" aria-hidden="true" />
          <span>LIVE FROM THE ATTIC</span>
          <span className="masthead__topline-separator" aria-hidden="true">//</span>
          <span>24/7</span>
        </div>
      </div>

      <div className="masthead__inner">
        <div className="masthead__brand">
          <img className="masthead__logo" src={asset('buena-musica-logo.png')} alt="Buena Música" />
          <div className="masthead__brand-copy">
            <span className="masthead__brand-kicker">ESTÉREO / ÁTICO</span>
            <strong>LA MÚSICA<br />NO DUERME.</strong>
            <span className="masthead__stereo">TU FRECUENCIA · TU RADIO</span>
          </div>
        </div>

        <div className="masthead__request">
          <div className="masthead__request-heading">
            <span className="masthead__request-label">
              <Icon name="radio" className="icon" />
              REQUEST LINE
            </span>
            <span className="masthead__request-subtitle">PIDE LA PRÓXIMA CANCIÓN</span>
          </div>
          {children}
        </div>

        <div className="masthead__broadcast">
          <div className="masthead__onair">
            <img src={asset('sticker_on_air.png')} alt="On air — live from the attic" />
          </div>
          <div className="masthead__meta">
            <div className={`masthead__status${live ? ' masthead__status--live' : ' masthead__status--idle'}`}>
              <span className="masthead__status-led" aria-hidden="true" />
              <span>{live ? 'EN VIVO' : 'EN ESPERA'}</span>
            </div>
            <time className="masthead__clock" dateTime={clock.toISOString()}>
              {timecode}
            </time>
            <span className="masthead__clock-label">HORA LOCAL · CABINA</span>
          </div>
        </div>
      </div>

      <div className="masthead__ticker">
        <span>CANAL 24 / RADIO IA</span>
        <span className="masthead__ticker-bars" aria-hidden="true">
          {Array.from({ length: 16 }, (_, index) => <i key={index} />)}
        </span>
        <span>EL PRÓXIMO TEMA LO ELIGES TÚ</span>
        <span className="masthead__ticker-frequency">FRECUENCIA ABIERTA / 24—7</span>
      </div>
    </header>
  );
}
