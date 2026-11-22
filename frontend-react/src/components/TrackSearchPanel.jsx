import { useEffect, useRef, useState } from 'react';
import { Icon } from './Icons.jsx';
import { searchTracks } from '../lib/api.js';
import { formatTime, normalizeText, safeUrl } from '../lib/safe.js';

/**
 * Buscador desplegable debajo del reproductor.
 * Los resultados se reproducen solo para el oyente, sin intervenir
 * en el orden de la señal compartida o consumir tickets de pedidos.
 */
export function TrackSearchPanel({ onClose, onSelect, onRadio, mode, selectedTrack }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [busy, setBusy] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState('');
  const fieldRef = useRef(null);
  const controllerRef = useRef(null);
  const sequenceRef = useRef(0);

  useEffect(() => {
    fieldRef.current?.focus({ preventScroll: true });
    return () => {
      sequenceRef.current += 1;
      controllerRef.current?.abort();
    };
  }, []);

  async function submitSearch(event) {
    event.preventDefault();
    const clean = normalizeText(query, 100);
    if (clean.length < 2) {
      setError('Escribí al menos dos caracteres.');
      setResults([]);
      return;
    }
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const sequence = ++sequenceRef.current;
    const timeout = window.setTimeout(() => controller.abort(), 20000);
    setError('');
    setBusy(true);
    setSearched(false);
    setResults([]);
    try {
      const response = await searchTracks(clean, { signal: controller.signal, limit: 12 });
      if (sequence !== sequenceRef.current) return;
      const list = (Array.isArray(response?.results) ? response.results : [])
        .filter((item) => /^[A-Za-z0-9_-]{11}$/.test(String(item?.id || '')))
        .slice(0, 12);
      setResults(list);
      setSearched(true);
    } catch (err) {
      if (sequence !== sequenceRef.current) return;
      setSearched(true);
      setError(err?.name === 'AbortError'
        ? 'La búsqueda tardó demasiado. Volvé a intentarlo.'
        : normalizeText(err?.message, 160) || 'No se pudo buscar música en este momento.');
    } finally {
      window.clearTimeout(timeout);
      if (sequence === sequenceRef.current) setBusy(false);
    }
  }

  return (
    <section
      className="personal-search panel"
      id="buscar-musica"
      aria-label="Buscar y escuchar música personalmente"
    >
      <header className="personal-search__head">
        <div className="personal-search__heading">
          <span className="personal-search__eyebrow">CANAL 24 / MODO PERSONAL</span>
          <h2><Icon name="search" className="icon" /> BUSCA TU MÚSICA</h2>
          <p>¿No querés escuchar la radio? Elegí un tema y sonará solo para vos.</p>
        </div>
        <button className="personal-search__close" type="button" onClick={onClose} aria-label="Cerrar buscador">
          <Icon name="x" className="icon" />
        </button>
      </header>

      <form className="personal-search__form" onSubmit={submitSearch} role="search">
        <label htmlFor="personal-track-query">CANCIÓN / ARTISTA / ÁLBUM</label>
        <div className="personal-search__entry">
          <Icon name="search" className="icon" />
          <input
            ref={fieldRef}
            id="personal-track-query"
            type="search"
            autoComplete="off"
            maxLength={100}
            placeholder="Ej.: Arctic Monkeys, Soda Stereo, rock de los 80..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-describedby="personal-search-description"
          />
          <button type="submit" disabled={busy || query.trim().length < 2}>
            {busy ? 'BUSCANDO…' : 'BUSCAR'}
          </button>
        </div>
      </form>

      <div className="personal-search__context" id="personal-search-description">
        <span>ESCUCHA INDIVIDUAL · SIN ALTERAR LA PROGRAMACIÓN</span>
        <button type="button" onClick={onRadio}>
          <Icon name="radio" className="icon" />
          VOLVER A RADIO 24/7
        </button>
      </div>

      {error ? <p className="personal-search__message personal-search__message--error" role="alert">{error}</p> : null}
      {busy ? <p className="personal-search__message" role="status">Buscando canciones en AllMusic…</p> : null}
      {searched && !busy && !error && results.length === 0 ? (
        <p className="personal-search__message" role="status">
          No encontramos resultados. Probá con otro título o artista.
        </p>
      ) : null}
      {!searched && !busy ? (
        <p className="personal-search__message personal-search__message--hint">
          Tu canción no se añadirá a la cola pública de la radio.
        </p>
      ) : null}

      {results.length > 0 ? (
        <div className="personal-search__results" aria-label="Resultados de búsqueda">
          <div className="personal-search__results-title">
            <strong>RESULTADOS</strong>
            <span>{results.length} OPCIONES</span>
          </div>
          <ul className="personal-search__list">
            {results.map((item, index) => {
              const id = String(item.id);
              const title = normalizeText(item.title, 160) || 'Sin título';
              const artist = normalizeText(item.uploader || item.artist, 100) || 'YouTube';
              const cover = safeUrl(item.thumbnail);
              const seconds = Number(item.duration);
              const selected = mode === 'personal' && selectedTrack?.id === id;
              return (
                <li key={`${id}-${index}`}>
                  <button
                    className={`personal-search__result${selected ? ' personal-search__result--selected' : ''}`}
                    type="button"
                    onClick={() => onSelect(item)}
                    aria-label={`Escuchar ${title}, ${artist}`}
                    aria-pressed={selected}
                  >
                    <span className="personal-search__index">{String(index + 1).padStart(2, '0')}</span>
                    {cover ? <img src={cover} alt="" loading="lazy" /> : (
                      <span className="personal-search__art-fallback"><Icon name="music" className="icon" /></span>
                    )}
                    <span className="personal-search__result-info">
                      <strong title={title}>{title}</strong>
                      <small title={artist}>{artist}</small>
                    </span>
                    <span className="personal-search__result-time">
                      {Number.isFinite(seconds) && seconds > 0 ? formatTime(seconds) : '—'}
                    </span>
                    <span className="personal-search__result-action">
                      <Icon name="play" className="icon" />
                      {selected ? 'REPETIR' : 'ESCUCHAR'}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
