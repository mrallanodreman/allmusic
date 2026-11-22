import { useCallback, useEffect, useRef, useState } from 'react';
import { getTrackStreamUrl, resolveTrackUrl } from '../lib/api.js';
import { normalizeText, safeUrl } from '../lib/safe.js';

/**
 * Un solo elemento <audio> para Radio IA y escucha personal.
 * Radio y canción elegida son modos excluyentes: jamás se mezclan dos streams.
 * El cambio de modo y la reproducción solo se inician mediante interacción.
 */
export function useAudioStream(streamUrl) {
  const audioRef = useRef(null);
  const modeRef = useRef('radio');
  const selectionRef = useRef(null);
  const requestRef = useRef(0);
  const fallbackRef = useRef('');
  const [mode, setMode] = useState('radio');
  const [selectedTrack, setSelectedTrack] = useState(null);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolumeState] = useState(() => {
    try {
      const raw = window.localStorage.getItem('ia-radio-volume');
      if (raw === null || raw === '') return 0.8;
      const n = Number(raw);
      return Number.isFinite(n) ? Math.min(1, Math.max(0, n)) : 0.8;
    } catch {
      return 0.8;
    }
  });

  const radioUrl = safeUrl(streamUrl);

  useEffect(() => {
    const audio = audioRef.current;
    if (audio) audio.volume = volume;
    try {
      window.localStorage.setItem('ia-radio-volume', String(volume));
    } catch {
      // El volumen sigue funcionando aunque localStorage esté bloqueado.
    }
  }, [volume]);

  const attemptPlay = useCallback((sequence) => {
    const audio = audioRef.current;
    if (!audio) return;
    setError('');
    const attempt = audio.play();
    if (attempt && typeof attempt.then === 'function') {
      attempt.then(() => {
        if (requestRef.current === sequence) setListening(true);
      }).catch((err) => {
        if (requestRef.current !== sequence || err?.name === 'AbortError') return;
        setListening(false);
        setError(err?.name === 'NotAllowedError'
          ? 'Tu navegador requiere otro clic para reproducir el audio.'
          : normalizeText(err?.message, 120) || 'No se pudo iniciar el audio.');
      });
    } else {
      setListening(true);
    }
  }, []);

  const setSourceAndPlay = useCallback((src, kind, sequence, reload = false) => {
    const audio = audioRef.current;
    if (!audio || !src) return false;
    audio.pause();
    setListening(false);
    if (reload || audio.dataset.stream !== src || audio.dataset.mode !== kind) {
      audio.dataset.stream = src;
      audio.dataset.mode = kind;
      audio.src = src;
      audio.load();
    }
    attemptPlay(sequence);
    return true;
  }, [attemptPlay]);

  const pause = useCallback(() => {
    const audio = audioRef.current;
    if (audio) audio.pause();
    setListening(false);
    setError('');
  }, []);

  const stop = useCallback(() => {
    requestRef.current += 1;
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.removeAttribute('src');
      audio.removeAttribute('data-stream');
      audio.removeAttribute('data-mode');
      audio.load();
    }
    fallbackRef.current = '';
    setListening(false);
    setElapsed(0);
    setDuration(0);
    setError('');
  }, []);

  const start = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (modeRef.current === 'personal') {
      const track = selectionRef.current;
      const src = track && (safeUrl(track.directSrc) || getTrackStreamUrl(track.id));
      if (!src) {
        setError('Seleccioná una canción en el buscador.');
        return;
      }
      const sequence = ++requestRef.current;
      if (audio.dataset.mode === 'personal' && audio.dataset.stream) {
        attemptPlay(sequence);
      } else {
        setSourceAndPlay(src, 'personal', sequence);
      }
      return;
    }
    if (!radioUrl) {
      setError('La transmisión no está disponible en este momento.');
      return;
    }
    // Sintonizar siempre desde el punto EN VIVO: una pausa no debe
    // reanudar un búfer viejo del stream compartido.
    const sequence = ++requestRef.current;
    setSourceAndPlay(radioUrl, 'radio', sequence, true);
  }, [attemptPlay, radioUrl, setSourceAndPlay]);

  const toggle = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (!audio.paused && !audio.ended) pause();
    else start();
  }, [pause, start]);

  const playTrack = useCallback((result) => {
    const id = normalizeText(result?.id, 16);
    // Los recomendados traen su propio asset local; las búsquedas siguen por
    // el proxy /stream del backend. Nunca se acepta una URL sin validar.
    const directSrc = safeUrl(result?.directSrc);
    const src = directSrc || getTrackStreamUrl(id);
    if (!src) {
      setError('La canción seleccionada no tiene un identificador válido.');
      return false;
    }
    const track = {
      id,
      title: normalizeText(result?.title, 160) || 'Sin título',
      artist: normalizeText(result?.uploader || result?.artist, 100) || 'YouTube',
      thumbnail: safeUrl(result?.thumbnail),
      directSrc,
      duration: Number.isFinite(Number(result?.duration)) ? Math.max(0, Number(result.duration)) : 0,
    };
    modeRef.current = 'personal';
    selectionRef.current = track;
    fallbackRef.current = '';
    setMode('personal');
    setSelectedTrack(track);
    setElapsed(0);
    setDuration(track.duration);
    const sequence = ++requestRef.current;
    return setSourceAndPlay(src, 'personal', sequence);
  }, [setSourceAndPlay]);

  const switchToRadio = useCallback(() => {
    modeRef.current = 'radio';
    selectionRef.current = null;
    fallbackRef.current = '';
    setMode('radio');
    setSelectedTrack(null);
    setElapsed(0);
    setDuration(0);
    const sequence = ++requestRef.current;
    if (!radioUrl) {
      pause();
      setError('Radio 24/7 no disponible en este momento.');
      return false;
    }
    return setSourceAndPlay(radioUrl, 'radio', sequence, true);
  }, [pause, radioUrl, setSourceAndPlay]);

  const setVolume = useCallback((next) => {
    const n = Number(next);
    if (!Number.isFinite(n)) return;
    setVolumeState(Math.min(1, Math.max(0, n)));
  }, []);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return undefined;

    const onPlaying = () => { setListening(true); setError(''); };
    const onPause = () => setListening(false);
    const onEnded = () => setListening(false);
    const onTimeUpdate = () => {
      if (modeRef.current !== 'personal') return;
      setElapsed(Number.isFinite(audio.currentTime) ? audio.currentTime : 0);
    };
    const onDurationChange = () => {
      if (modeRef.current !== 'personal') return;
      setDuration(Number.isFinite(audio.duration) ? audio.duration : (selectionRef.current?.duration || 0));
    };

    const onError = async () => {
      const current = selectionRef.current;
      if (modeRef.current !== 'personal' || !current) {
        setListening(false);
        setError('La transmisión se interrumpió. Intentá de nuevo.');
        return;
      }
      // Mismo fallback que el reproductor clásico (/convert); se intenta una sola vez.
      if (fallbackRef.current === current.id) {
        setListening(false);
        setError('No se pudo reproducir esa canción. Probá con otro resultado.');
        return;
      }
      fallbackRef.current = current.id;
      const sequence = requestRef.current;
      try {
        const direct = await resolveTrackUrl(current.id);
        if (sequence !== requestRef.current || modeRef.current !== 'personal') return;
        if (direct && direct !== audio.dataset.stream) {
          setSourceAndPlay(direct, 'personal', sequence);
        } else {
          setListening(false);
          setError('No se encontró audio reproducible para esa canción.');
        }
      } catch {
        if (sequence === requestRef.current) {
          setListening(false);
          setError('No se pudo conectar con el audio de esa canción.');
        }
      }
    };

    audio.addEventListener('playing', onPlaying);
    audio.addEventListener('pause', onPause);
    audio.addEventListener('ended', onEnded);
    audio.addEventListener('timeupdate', onTimeUpdate);
    audio.addEventListener('durationchange', onDurationChange);
    audio.addEventListener('error', onError);
    return () => {
      audio.removeEventListener('playing', onPlaying);
      audio.removeEventListener('pause', onPause);
      audio.removeEventListener('ended', onEnded);
      audio.removeEventListener('timeupdate', onTimeUpdate);
      audio.removeEventListener('durationchange', onDurationChange);
      audio.removeEventListener('error', onError);
      audio.pause();
    };
  }, [setSourceAndPlay]);

  useEffect(() => {
    // La cabina puede cambiar su URL cuando refresca /radio/now.
    // Nunca reintroducir el stream si el usuario escucha una canción propia.
    if (!radioUrl || modeRef.current !== 'radio') return;
    const audio = audioRef.current;
    if (!audio || audio.paused || audio.dataset.mode !== 'radio') return;
    if (audio.dataset.stream === radioUrl) return;
    const sequence = ++requestRef.current;
    setSourceAndPlay(radioUrl, 'radio', sequence);
  }, [radioUrl, setSourceAndPlay]);

  const hasPlayable = mode === 'personal' ? Boolean(selectedTrack) : Boolean(radioUrl);

  return {
    audioRef,
    listening,
    error,
    hasStream: Boolean(radioUrl),
    hasPlayable,
    mode,
    selectedTrack,
    elapsed,
    duration,
    toggle,
    start,
    pause,
    stop,
    playTrack,
    switchToRadio,
    volume,
    setVolume,
  };
}
