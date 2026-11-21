import { useCallback, useEffect, useRef, useState } from 'react';
import { normalizeText, safeUrl } from '../lib/safe.js';

/** Reproducción manual del stream: el navegador solo conecta tras un clic. */
export function useAudioStream(streamUrl) {
  const audioRef = useRef(null);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState('');
  const url = safeUrl(streamUrl);

  const stop = useCallback(() => {
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.removeAttribute('src');
      audio.load();
      delete audio.dataset.stream;
    }
    setListening(false);
    setError('');
  }, []);

  const start = useCallback(() => {
    const audio = audioRef.current;
    if (!audio || !url) {
      setError('El stream no está disponible en este momento.');
      return;
    }
    setError('');
    if (audio.dataset.stream !== url) {
      audio.dataset.stream = url;
      audio.src = url;
      audio.load();
    }
    const attempt = audio.play();
    if (attempt && typeof attempt.then === 'function') {
      attempt
        .then(() => setListening(true))
        .catch((err) => {
          setListening(false);
          setError(
            err?.name === 'NotAllowedError'
              ? 'El navegador requiere otro clic para iniciar el audio.'
              : normalizeText(err?.message, 120) || 'No se pudo conectar con el stream.'
          );
        });
    } else {
      setListening(true);
    }
  }, [url]);

  const toggle = useCallback(() => {
    if (listening) stop();
    else start();
  }, [listening, start, stop]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return undefined;
    const handleError = () => {
      setListening(false);
      setError('La transmisión se interrumpió. Probá de nuevo.');
    };
    audio.addEventListener('error', handleError);
    return () => audio.removeEventListener('error', handleError);
  }, []);

  useEffect(() => {
    if (!listening || !url) return;
    const audio = audioRef.current;
    if (audio && audio.dataset.stream !== url) {
      audio.dataset.stream = url;
      audio.src = url;
      audio.load();
      const attempt = audio.play();
      if (attempt && typeof attempt.catch === 'function') attempt.catch(() => setListening(false));
    }
  }, [listening, url]);

  return { audioRef, listening, error, hasStream: Boolean(url), toggle, stop };
}
