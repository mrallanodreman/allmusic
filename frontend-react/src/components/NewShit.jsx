import { useCallback, useEffect, useRef, useState } from 'react';
import { Icon } from './Icons.jsx';
import { Equalizer } from './Equalizer.jsx';

const asset = (name) => `${import.meta.env.BASE_URL}assets/newshit/${name}`;

const ARTISTS = [
  {
    name: 'Razimbrain',
    fullName: 'Razimbrein, LA MENTE',
    tag: 'HIP-HOP · MÉXICO',
    image: asset('razimbrain.webp'),
    alt: 'Retrato editorial de Razimbrain con bandana y audífonos',
    summary:
      'Rapero venezolano que crea desde México. Versos de lógica precisa y un sonido chill que pide tiempo. LXXI, su álbum de 2026, reúne nueve piezas entre ellas APNEA y DANZA DE LA FRANQUEZA.',
  },
  {
    name: 'Vittorio',
    fullName: 'VITTORIO × LA ANTORCHA',
    tag: 'URBANO · ECUADOR',
    image: asset('vittorio.webp'),
    alt: 'Vittorio actuando junto a La Antorcha en KulturURBANA 2026, Quito',
    summary:
      'Artista venezolano que compartió escenario con La Antorcha y Rayo Pluzz en KulturURBANA 2026, Plaza Belmonte, Quito. Crónica fotográfica publicada en el blog de edgemarketing.tech.',
  },
];

const ROTATION_MS = 7000;

function useReducedMotion() {
  const [reduce, setReduce] = useState(
    () => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  );
  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!media) return undefined;
    const update = () => setReduce(media.matches);
    media.addEventListener?.('change', update);
    return () => media.removeEventListener?.('change', update);
  }, []);
  return reduce;
}

export function NewShit({ playing, onToggle, hasStream }) {
  const [index, setIndex] = useState(0);
  const [hold, setHold] = useState(false);
  const [status, setStatus] = useState('');
  const sectionRef = useRef(null);
  const reduceMotion = useReducedMotion();
  const artist = ARTISTS[index];

  // Rotación automática: se detiene al pasar el mouse, al enfocar y con movimiento reducido.
  useEffect(() => {
    if (hold || reduceMotion) return undefined;
    const timer = window.setInterval(() => setIndex((current) => (current + 1) % ARTISTS.length), ROTATION_MS);
    return () => window.clearInterval(timer);
  }, [hold, reduceMotion]);

  const handleBlur = useCallback((event) => {
    if (!sectionRef.current?.contains(event.relatedTarget)) setHold(false);
  }, []);

  const openRadio = useCallback(() => {
    const radio = document.getElementById('reproductor');
    radio?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' });
    if (!playing && hasStream) onToggle();
    setStatus(`Radio desplegado · recomendado: ${artist.name}`);
  }, [artist.name, hasStream, onToggle, playing, reduceMotion]);

  const change = useCallback((next) => {
    setIndex(next);
    setStatus(`Recomendado: ${ARTISTS[next].name}`);
  }, []);

  return (
    <section
      className="newshit panel"
      id="newshit"
      aria-labelledby="newshit-title"
      ref={sectionRef}
      onMouseEnter={() => setHold(true)}
      onMouseLeave={() => setHold(false)}
      onFocusCapture={() => setHold(true)}
      onBlurCapture={handleBlur}
    >
      <div className="section-head">
        <h2 id="newshit-title">NEWSHIT</h2>
        <span className="section-head__hint">recomendados</span>
      </div>

      <div className="newshit__stage">
        <article className="newshit__card" key={artist.name}>
          <button
            type="button"
            className="newshit__open"
            onClick={openRadio}
            aria-label={`Desplegar el radio y escuchar a ${artist.name}`}
          >
            <span className="newshit__sleeve-wrap">
              <span className={`newshit__disc ${playing ? 'newshit__disc--spin' : ''}`} aria-hidden="true">
                <span className="newshit__disc-label">{artist.name}</span>
              </span>
              <img
                className="newshit__sleeve"
                src={artist.image}
                alt={artist.alt}
                width="400"
                height="400"
                fetchPriority="high"
              />
              <span className="newshit__summary">
                <strong>{artist.fullName}</strong>
                <span>{artist.summary}</span>
                <em>ABRIR RADIO →</em>
              </span>
            </span>
          </button>

          <div className="newshit__mini">
            <button
              type="button"
              className="newshit__play"
              onClick={onToggle}
              disabled={!hasStream}
              aria-label={playing ? 'Pausar la radio' : `Escuchar la radio · ${artist.name}`}
            >
              <Icon name={playing ? 'pause' : 'play'} />
            </button>
            <span className="newshit__meta">
              <strong>{artist.name}</strong>
              <small>{artist.tag}</small>
            </span>
            <Equalizer active={playing} compact />
          </div>
        </article>
      </div>

      <div className="newshit__dots" role="group" aria-label="Elegir recomendado">
        {ARTISTS.map((item, position) => (
          <button
            type="button"
            key={item.name}
            className={`newshit__dot ${position === index ? 'is-active' : ''}`}
            aria-label={`Mostrar a ${item.name}`}
            aria-pressed={position === index}
            onClick={() => change(position)}
          />
        ))}
      </div>
      <p className="sr-only" role="status" aria-live="polite">
        {status}
      </p>
    </section>
  );
}
