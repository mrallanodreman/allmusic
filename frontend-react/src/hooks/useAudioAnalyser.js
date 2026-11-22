import { useCallback, useEffect, useRef } from 'react';

/**
 * Extrae una copia de la señal que YA reproduce <audio> mediante captureStream.
 * No intercepta, mezcla ni sustituye la salida del reproductor.
 *
 * Diferencia importante frente a createMediaElementSource(audio):
 * un stream CDN sin CORS nunca deja mudo al audio principal. Si el navegador
 * no permite capturar esa fuente, las barras permanecen inmóviles; NO se
 * simula música con animaciones CSS.
 */
export function useAudioAnalyser(audioRef) {
  const analyserRef = useRef(null);
  const contextRef = useRef(null);
  const sourceRef = useRef(null);
  const streamRef = useRef(null);
  const cleanupStreamRef = useRef(null);
  const currentUrlRef = useRef('');
  const aliveRef = useRef(true);

  const detach = useCallback(() => {
    if (cleanupStreamRef.current) cleanupStreamRef.current();
    cleanupStreamRef.current = null;
    try { sourceRef.current?.disconnect(); } catch { /* nodo anterior destruido */ }
    sourceRef.current = null;
    streamRef.current = null;
    analyserRef.current = null;
    currentUrlRef.current = '';
  }, []);

  const activate = useCallback(() => {
    // Ejecutado desde un clic (PLAY, RADIO, selección de canción):
    // desbloquea el AudioContext en navegadores que exigen gesto del usuario.
    if (typeof window === 'undefined') return;
    const audio = audioRef.current;
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    const capture = audio && (audio.captureStream || audio.mozCaptureStream);
    if (!audio || !AudioContextClass || typeof capture !== 'function') return;
    try {
      if (!contextRef.current || contextRef.current.state === 'closed') {
        contextRef.current = new AudioContextClass({ latencyHint: 'interactive' });
      }
      if (contextRef.current.state === 'suspended') {
        void contextRef.current.resume().catch(() => {});
      }
    } catch {
      // Ciertos contextos/proveedores restringen el audio procesable.
      // El reproductor seguirá funcionando como antes.
    }
  }, [audioRef]);

  useEffect(() => {
    aliveRef.current = true;
    const audio = audioRef.current;
    if (!audio) return undefined;

    const attach = () => {
      if (!aliveRef.current || audio.paused) return;
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      const capture = audio.captureStream || audio.mozCaptureStream;
      if (!AudioContextClass || typeof capture !== 'function') return;

      const src = audio.currentSrc || audio.src || '';
      if (!src) return;
      if (analyserRef.current && currentUrlRef.current === src) {
        if (contextRef.current?.state === 'suspended') {
          void contextRef.current.resume().catch(() => {});
        }
        return;
      }

      detach();
      let stream;
      try { stream = capture.call(audio); } catch { return; }
      if (!stream || typeof stream.getAudioTracks !== 'function') return;
      streamRef.current = stream;
      currentUrlRef.current = src;

      // Firefox/Chromium pueden registrar la pista tras el evento "playing".
      // Esperamos "addtrack" en vez de conectar un nodo a un stream sin audio.
      const connect = () => {
        if (!aliveRef.current || streamRef.current !== stream) return;
        if (!stream.getAudioTracks().length || analyserRef.current) return;
        try {
          if (!contextRef.current || contextRef.current.state === 'closed') {
            contextRef.current = new AudioContextClass({ latencyHint: 'interactive' });
          }
          const ctx = contextRef.current;
          const source = ctx.createMediaStreamSource(stream);
          const analyser = ctx.createAnalyser();
          analyser.fftSize = 2048;
          analyser.minDecibels = -90;
          analyser.maxDecibels = -18;
          analyser.smoothingTimeConstant = 0.68;
          source.connect(analyser);
          // No conectar al destination. La etiqueta <audio> ya se oye
          // directamente; conectarlo allí duplicaría el sonido.
          sourceRef.current = source;
          analyserRef.current = analyser;
          void ctx.resume().catch(() => {});
        } catch {
          // Nada de barras inventadas ni de silenciar el reproductor.
          detach();
        }
      };

      stream.addEventListener('addtrack', connect);
      cleanupStreamRef.current = () => stream.removeEventListener('addtrack', connect);
      connect();
    };

    const onSourceReset = () => detach();
    const onPlay = () => attach();

    audio.addEventListener('playing', onPlay);
    audio.addEventListener('loadedmetadata', onPlay);
    audio.addEventListener('emptied', onSourceReset);
    if (!audio.paused && audio.readyState > 1) attach();

    return () => {
      aliveRef.current = false;
      audio.removeEventListener('playing', onPlay);
      audio.removeEventListener('loadedmetadata', onPlay);
      audio.removeEventListener('emptied', onSourceReset);
      detach();
      const ctx = contextRef.current;
      contextRef.current = null;
      if (ctx && ctx.state !== 'closed') void ctx.close().catch(() => {});
    };
  }, [audioRef, detach]);

  return { analyserRef, activate };
}
