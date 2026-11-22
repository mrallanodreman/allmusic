import { useCallback, useEffect, useRef, useState } from 'react';

const INVITE = 'https://discord.gg/YVUQPPyxX';
const SLIDES = [
  { id: 'locutores', title: 'Buscamos locutores', description: 'Tu voz puede estar al aire', image: 'buscamos-locutores.svg' },
  { id: 'djs', title: 'Buscamos DJs', description: 'Mezcla con nosotros', image: 'buscamos-djs.svg' },
  { id: 'unete', title: 'Únete a la señal', description: 'Conecta con la comunidad', image: 'unete.svg' },
];
const asset = (name) => `${import.meta.env.BASE_URL}assets/community/${name}`;

export function CommunityCarousel() {
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(() => Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches));
  const rootRef = useRef(null);
  const touchRef = useRef(null);
  const swipedRef = useRef(false);
  const slide = SLIDES[index];
  const next = useCallback(() => setIndex(i => (i + 1) % SLIDES.length), []);
  const prev = useCallback(() => setIndex(i => (i + SLIDES.length - 1) % SLIDES.length), []);

  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!media) return undefined;
    const update = () => setReduceMotion(media.matches);
    media.addEventListener?.('change', update);
    return () => media.removeEventListener?.('change', update);
  }, []);

  useEffect(() => {
    if (paused || reduceMotion || document.hidden) return undefined;
    const timer = window.setInterval(next, 7000);
    return () => window.clearInterval(timer);
  }, [paused, reduceMotion, next, index]);

  const onBlur = useCallback(event => {
    if (!rootRef.current?.contains(event.relatedTarget)) setPaused(false);
  }, []);
  const onKeys = useCallback(event => {
    if (event.key === 'ArrowLeft') { event.preventDefault(); prev(); }
    if (event.key === 'ArrowRight') { event.preventDefault(); next(); }
  }, [prev, next]);
  const onTouchStart = useCallback(event => {
    touchRef.current = event.changedTouches[0]?.clientX ?? null;
    swipedRef.current = false;
  }, []);
  const onTouchEnd = useCallback(event => {
    if (touchRef.current === null) return;
    const dx = (event.changedTouches[0]?.clientX ?? touchRef.current) - touchRef.current;
    touchRef.current = null;
    if (Math.abs(dx) < 45) return;
    swipedRef.current = true;
    dx > 0 ? prev() : next();
  }, [prev, next]);

  return (
    <section className="community-carousel panel" id="comunidad" aria-roledescription="carrusel"
      aria-labelledby="community-carousel-title" ref={rootRef}
      onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)} onBlurCapture={onBlur} onKeyDown={onKeys}>
      <div className="section-head community-carousel__head">
        <h2 id="community-carousel-title">SÚMATE AL AIRE</h2>
        <span className="section-head__hint">comunidad / discord</span>
      </div>
      <div className="community-carousel__viewport" onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
        <a className="community-carousel__link" href={INVITE} target="_blank" rel="noopener noreferrer"
          onClick={event => { if (swipedRef.current) { event.preventDefault(); swipedRef.current = false; } }}
          aria-label={`${slide.title}. Entrar al Discord de la radio, abre en otra pestaña`}>
          <img key={slide.id} className="community-carousel__image" src={asset(slide.image)}
            alt={`${slide.title}: ${slide.description}`} width="540" height="540" loading="lazy" decoding="async"/>
          <span className="community-carousel__cta">ENTRAR AL DISCORD ↗</span>
        </a>
        <button type="button" className="community-carousel__arrow community-carousel__arrow--prev" aria-label="Anterior cartel" onClick={prev}>‹</button>
        <button type="button" className="community-carousel__arrow community-carousel__arrow--next" aria-label="Siguiente cartel" onClick={next}>›</button>
      </div>
      <div className="community-carousel__foot">
        <div className="community-carousel__dots" role="group" aria-label="Seleccionar convocatoria">
          {SLIDES.map((item, i) => <button key={item.id} type="button"
            aria-label={`Mostrar ${item.title}`} aria-pressed={i === index}
            className={`community-carousel__dot${i === index ? ' is-active' : ''}`} onClick={() => setIndex(i)}/>)}
        </div>
        <span className="community-carousel__count">{String(index + 1).padStart(2, '0')} / 03</span>
      </div>
      <p className="sr-only" role="status" aria-live="polite">{slide.title}</p>
    </section>
  );
}
