import { useEffect, useRef } from 'react';

/**
 * Espectro real: FFT del audio reproducido en el único elemento <audio>.
 * Sin valores aleatorios, oscilaciones por CSS ni barras falsas.
 * El dibujo se hace en canvas para evitar renderizar React 30 veces/s.
 */
const MAIN_BAR_COUNT = 32;
const FRAME_MS = 1000 / 30;

export function AudioReactiveMeter({ analyserRef, active = false, variant = 'main' }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const context = canvas.getContext('2d', { alpha: true });
    if (!context) return undefined;

    let raf = 0;
    let lastFrame = 0;
    const count = variant === 'compact' ? 20 : MAIN_BAR_COUNT;
    const smoothed = new Float32Array(count);
    let spectrum = null;
    let wave = null;
    let lastAnalyser = null;
    let width = 0;
    let height = 0;

    const resize = () => {
      const size = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = Math.max(1, size.width);
      height = Math.max(1, size.height);
      const pixelWidth = Math.max(1, Math.round(width * dpr));
      const pixelHeight = Math.max(1, Math.round(height * dpr));
      if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
        canvas.width = pixelWidth;
        canvas.height = pixelHeight;
      }
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (timestamp) => {
      if (active) raf = window.requestAnimationFrame(draw);
      if (timestamp - lastFrame < FRAME_MS) return;
      lastFrame = timestamp;
      context.clearRect(0, 0, width, height);
      const analyser = active ? analyserRef?.current : null;
      if (analyser !== lastAnalyser) {
        lastAnalyser = analyser;
        spectrum = analyser ? new Uint8Array(analyser.frequencyBinCount) : null;
        wave = analyser ? new Uint8Array(analyser.fftSize) : null;
        smoothed.fill(0);
      }

      let rms = 0;
      if (analyser && spectrum && wave) {
        try {
          analyser.getByteFrequencyData(spectrum);
          analyser.getByteTimeDomainData(wave);
          let energy = 0;
          for (let i = 0; i < wave.length; i += 1) {
            const delta = (wave[i] - 128) / 128;
            energy += delta * delta;
          }
          rms = Math.sqrt(energy / wave.length);
        } catch {
          spectrum.fill(0);
        }
      }

      const gap = variant === 'sidebar' ? 2 : variant === 'compact' ? 1 : 3;
      const barWidth = Math.max(1, (width - (count - 1) * gap) / count);
      const nyquist = analyser?.context?.sampleRate ? analyser.context.sampleRate / 2 : 24000;
      const gradient = context.createLinearGradient(0, height, 0, 0);
      gradient.addColorStop(0, '#ff178d');
      gradient.addColorStop(0.55, '#00e5ee');
      gradient.addColorStop(1, '#f6d600');

      for (let i = 0; i < count; i += 1) {
        let actual = 0;
        if (analyser && spectrum) {
          const minHz = 55 * Math.pow(180, i / count);
          const maxHz = 55 * Math.pow(180, (i + 1) / count);
          const from = Math.min(spectrum.length - 1, Math.max(0, Math.floor(minHz / nyquist * spectrum.length)));
          const to = Math.min(spectrum.length - 1, Math.max(from, Math.ceil(maxHz / nyquist * spectrum.length)));
          let sumSquares = 0;
          for (let index = from; index <= to; index += 1) {
            const sample = spectrum[index] / 255;
            sumSquares += sample * sample;
          }
          const band = Math.sqrt(sumSquares / (to - from + 1));
          // Acentúa la música real, no añade oscilaciones arbitrarias.
          actual = Math.min(1, Math.max(0, (band - 0.035) * 1.55 + rms * 0.2));
        }
        // Respuesta rápida al ataque, caída progresiva como VU físico.
        smoothed[i] = actual > smoothed[i]
          ? smoothed[i] * 0.18 + actual * 0.82
          : smoothed[i] * 0.70 + actual * 0.30;

        const barHeight = Math.max(1, smoothed[i] * (height - 3));
        const x = i * (barWidth + gap);
        context.fillStyle = gradient;
        context.fillRect(x, height - barHeight, barWidth, barHeight);
      }
    };

    resize();
    const observer = typeof ResizeObserver !== 'undefined'
      ? new ResizeObserver(resize) : null;
    observer?.observe(canvas);
    window.addEventListener('resize', resize);
    if (active) raf = window.requestAnimationFrame(draw);
    else draw(FRAME_MS + 1); // una sola imagen en pausa; cero animación simulada

    return () => {
      window.cancelAnimationFrame(raf);
      window.removeEventListener('resize', resize);
      observer?.disconnect();
    };
  }, [active, analyserRef, variant]);

  return (
    <div
      className={`audio-meter audio-meter--${variant}`}
      role="img"
      aria-label={active
        ? 'Espectro de frecuencias de la señal de audio reproducida'
        : 'Medidor de audio en reposo'}
    >
      <canvas ref={canvasRef} aria-hidden="true" />
    </div>
  );
}
