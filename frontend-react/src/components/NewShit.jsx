import { useCallback, useEffect, useRef, useState } from 'react';
import { Icon } from './Icons.jsx';
import { AudioReactiveMeter } from './AudioReactiveMeter.jsx';
import { Equalizer } from './Equalizer.jsx';

const asset = (name) => `${import.meta.env.BASE_URL}assets/newshit/${name}`;
// safeUrl solo acepta https absoluto o rutas relativas seguras; dejamos la
// ruta same-origin para que valide igual en local (http) y en producción.
// El query de versión evita que un 404 viejo quede cacheado por el CDN.
const assetHref = (name) => `${new URL(asset(name), window.location.href).pathname}?v=2`;

// Cada recomendado lleva un tema real del catálogo de MfMood. El audio y la
// carátula son assets locales: suenan aunque el proveedor de conversión del
// backend esté sin cuota. El ID de YouTube queda como identificador editorial.
const ARTISTS = [
  {
    name: 'Razimbrain',
    slug: 'razimbrain-apnea-lxxi',
    fullName: 'Razimbrein, LA MENTE',
    tag: 'HIP-HOP · MÉXICO',
    id: '-BjoKWAuDVY',
    title: 'APNEA',
    artist: 'Razimbrein',
    duration: 245,
    directSrc: assetHref('apnea.m4a'),
    thumbnail: assetHref('apnea-art.webp'),
    image: asset('razimbrain.webp'),
    alt: 'Retrato editorial de Razimbrain con bandana y audífonos',
    summary:
      'Rapero venezolano que crea desde México. Versos de lógica precisa y un sonido chill que pide tiempo. LXXI, su álbum de 2026, reúne nueve piezas entre ellas APNEA y DANZA DE LA FRANQUEZA.',
  },
  {
    name: 'Vittorio',
    slug: 'vittorio-kultururbana-2026',
    fullName: 'VITTORIO × LA ANTORCHA',
    tag: 'URBANO · ECUADOR',
    id: '6rzlzB2zq_0',
    title: 'SÓLIDO',
    artist: 'VITTORIO',
    duration: 142,
    directSrc: assetHref('solido.m4a'),
    thumbnail: assetHref('solido-art.webp'),
    image: asset('vittorio.webp'),
    alt: 'Vittorio actuando junto a La Antorcha en KulturURBANA 2026, Quito',
    summary:
      'Artista venezolano que compartió escenario con La Antorcha y Rayo Pluzz en KulturURBANA 2026, Plaza Belmonte, Quito. La ficha completa, con contexto y audio, está en MfMood.',
  },
];

const RECOMMENDED_IDS = new Set(ARTISTS.map((item) => item.id));
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

export function NewShit({ playing, mode, selectedTrack, onToggle, onPlayTrack, onRadio, onOpenArticle, audioError, analyserRef }) {
  const [index, setIndex] = useState(0);
  const [hold, setHold] = useState(false);
  const [status, setStatus] = useState('');
  const sectionRef = useRef(null);
  const reduceMotion = useReducedMotion();
  const artist = ARTISTS[index];
  const isThisTrack = mode === 'personal' && selectedTrack?.id === artist.id;
  const playingRecommended = mode === 'personal' && RECOMMENDED_IDS.has(selectedTrack?.id);
  const sounding = isThisTrack && playing;

  // Rotación automática: se detiene al pasar el mouse, al enfocar, con movimiento
  // reducido y mientras suene un recomendado (así la portada no cambia de canción).
  useEffect(() => {
    if (hold || reduceMotion || playingRecommended) return undefined;
    const timer = window.setInterval(() => setIndex((current) => (current + 1) % ARTISTS.length), ROTATION_MS);
    return () => window.clearInterval(timer);
  }, [hold, reduceMotion, playingRecommended]);

  const handleBlur = useCallback((event) => {
    if (!sectionRef.current?.contains(event.relatedTarget)) setHold(false);
  }, []);

  const openRadio = useCallback(() => {
    const radio = document.getElementById('reproductor');
    radio?.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' });
    // Volver a la señal 24/7 detiene el tema personal: nunca suenan los dos a la vez.
    if (mode !== 'radio' || !playing) onRadio();
    setStatus(`Radio desplegado · recomendado: ${artist.name}`);
  }, [artist.name, mode, onRadio, playing, reduceMotion]);

  // El texto de la portada abre la ficha del artista justo debajo del reproductor.
  // Si el componente se usa fuera de App, la versión permanente sigue funcionando.
  const openArticle = useCallback(() => {
    setStatus(`Abriendo ficha de ${artist.name}`);
    if (onOpenArticle) onOpenArticle(artist.slug);
    else window.location.assign(`/blog/${artist.slug}/`);
  }, [artist.name, artist.slug, onOpenArticle]);

  const toggleTrack = useCallback(() => {
    if (isThisTrack) {
      onToggle();
      setStatus(playing ? `${artist.title} en pausa` : `Reanudando ${artist.title}`);
      return;
    }
    onPlayTrack(artist);
    setStatus(`Sonando ahora: ${artist.title} · ${artist.artist}`);
  }, [artist, isThisTrack, onPlayTrack, onToggle, playing]);

  const change = useCallback((next) => {
    const item = ARTISTS[next];
    setIndex(next);
    if (playingRecommended) {
      // Los puntos funcionan como cambio de pista mientras suena un recomendado.
      onPlayTrack(item);
      setStatus(`Sonando ahora: ${item.title} · ${item.artist}`);
    } else {
      setStatus(`Recomendado: ${item.name}`);
    }
  }, [onPlayTrack, playingRecommended]);

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
          <div className="newshit__cover">
            <button
              type="button"
              className="newshit__open"
              onClick={openRadio}
              aria-label={`Desplegar el radio y escuchar a ${artist.name}`}
            >
              <span className="newshit__sleeve-wrap">
                <span className={`newshit__disc ${sounding ? 'newshit__disc--spin' : ''}`} aria-hidden="true">
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
              </span>
            </button>
            <button
              type="button"
              className="newshit__read"
              onClick={openArticle}
              aria-label={`Leer el artículo de ${artist.name} debajo del reproductor`}
            >
              <span className="newshit__summary">
                <strong>{artist.fullName}</strong>
                <span>{artist.summary}</span>
                <em>LEER ARTÍCULO →</em>
              </span>
            </button>
          </div>

          <div className="newshit__mini">
            <button
              type="button"
              className={`newshit__play${sounding ? ' is-playing' : ''}`}
              onClick={toggleTrack}
              aria-label={sounding
                ? `Pausar ${artist.title}`
                : `Escuchar ${artist.title} de ${artist.name}`}
            >
              <Icon name={sounding ? 'pause' : 'play'} />
            </button>
            <img className="newshit__art" src={artist.thumbnail} alt="" width="32" height="32" />
            <span className="newshit__meta">
              <strong>{isThisTrack ? artist.title : artist.name}</strong>
              <small>{isThisTrack ? `${artist.artist} · SONANDO` : artist.tag}</small>
            </span>
            {analyserRef
              ? <AudioReactiveMeter active={sounding} analyserRef={analyserRef} variant="compact" />
              : <Equalizer active={sounding} compact />}
          </div>
          <button type="button" className="newshit__read-link" onClick={openArticle}>
            Leer ficha de {artist.name} →
          </button>
          {audioError && isThisTrack ? (
            <p className="newshit__error" role="alert">{audioError}</p>
          ) : null}
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
