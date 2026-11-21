import { useEffect, useState } from 'react';
import { Icon } from './Icons.jsx';

const asset = (name) => `${import.meta.env.BASE_URL}assets/radio-ui/${name}`;

export function HeaderBanner({ live }) {
  const [clock, setClock] = useState(() => new Date());

  useEffect(() => {
    const timer = window.setInterval(() => setClock(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const timecode = clock.toLocaleTimeString('es-EC', { hour12: false });

  return (
    <header className="masthead" id="arriba">
      <div className="masthead__brand">
        <img className="masthead__logo" src={asset('sticker_canal_24.png')} alt="Canal 24" />
        <span className="masthead__stereo">ESTÉREO · SEÑAL PRINCIPAL</span>
      </div>
      <div className="masthead__onair">
        <img src={asset('sticker_on_air.png')} alt="On air, live from the attic" />
      </div>
      <div className="masthead__meta">
        <div className="masthead__status">
          <Icon name="radio" className="icon" />
          <span>{live ? 'TRANSMISIÓN CONTINUA' : 'SEÑAL EN ESPERA'}</span>
        </div>
        <time className="masthead__clock" dateTime={clock.toISOString()}>
          {timecode}
        </time>
      </div>
    </header>
  );
}
