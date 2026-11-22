import { useEffect, useId, useRef, useState } from 'react';
import { Icon } from './Icons.jsx';

/**
 * Control de volumen tipo fader de cabina, adaptado para Canal 24.
 * Referencia de diseño: "Radio" de kalikapurnabinsanghaclub (knsdc),
 * https://uiverse.io/kalikapurnabinsanghaclub/grumpy-dodo-60 (MIT).
 * La atribución y la licencia están en UiverseVolumeFader.LICENSE.md.
 *
 * Se utiliza el valor del único <audio> de IA Radio, en ambos modos.
 */
export function VolumeFader({ volume, onVolume, compact = false }) {
  const id = useId();
  const containerRef = useRef(null);
  const lastAudibleRef = useRef(0.8);
  const [open, setOpen] = useState(false);

  const number = Number(volume);
  const level = Math.round(Math.max(0, Math.min(1, Number.isFinite(number) ? number : 0)) * 100);

  useEffect(() => {
    if (level > 0) lastAudibleRef.current = level / 100;
  }, [level]);

  useEffect(() => {
    if (!compact || !open) return undefined;

    const onOutside = (event) => {
      if (!containerRef.current?.contains(event.target)) setOpen(false);
    };
    const onEscape = (event) => {
      if (event.key === 'Escape') {
        setOpen(false);
        containerRef.current?.querySelector('.snd-fader-trigger')?.focus();
      }
    };
    document.addEventListener('pointerdown', onOutside);
    document.addEventListener('keydown', onEscape);
    return () => {
      document.removeEventListener('pointerdown', onOutside);
      document.removeEventListener('keydown', onEscape);
    };
  }, [compact, open]);

  const setLevel = (percentage) => {
    const next = Math.max(0, Math.min(100, Number(percentage) || 0));
    onVolume(next / 100);
  };

  const toggleMute = () => {
    if (level === 0) onVolume(lastAudibleRef.current || 0.8);
    else onVolume(0);
  };

  const onRangeKeyDown = (event) => {
    // El input se rota visualmente; arriba debe aumentar el volumen.
    if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
      event.preventDefault();
      setLevel(level + (event.key === 'ArrowUp' ? 1 : -1));
    }
  };

  const fader = (
    <div className="snd-fader-panel" style={{ '--fader-pct': `${level}%` }}>
      <div className="snd-fader-head">
        <span className="snd-fader-label" id={id + '-label'}>VOL 01</span>
        <span className="snd-fader-status" aria-hidden="true" />
      </div>
      <div className="snd-fader-container">
        <span className="snd-fader-ruler snd-fader-ruler--left" aria-hidden="true" />
        <input
          type="range"
          className="snd-audio-fader"
          id={id}
          aria-labelledby={id + '-label'}
          aria-valuetext={`${level} por ciento`}
          aria-orientation="vertical"
          min="0"
          max="100"
          step="1"
          value={level}
          onChange={(event) => setLevel(event.target.value)}
          onKeyDown={onRangeKeyDown}
          title={`Volumen ${level}%`}
        />
        <span className="snd-fader-ruler snd-fader-ruler--right" aria-hidden="true" />
      </div>
      <div className="snd-fader-bottom">
        <button
          type="button"
          className="snd-fader-mute"
          onClick={toggleMute}
          title={level === 0 ? 'Restaurar volumen' : 'Silenciar'}
          aria-label={level === 0 ? 'Restaurar volumen' : 'Silenciar'}
          aria-pressed={level === 0}
        >
          <Icon name={level === 0 ? 'mute' : 'volume'} className="icon" />
        </button>
        <output htmlFor={id} className="snd-fader-readout" aria-label="Nivel de volumen">
          {String(level).padStart(2, '0')}<small>%</small>
        </output>
      </div>
      <span className="snd-fader-footnote" aria-hidden="true">CANAL 24 / MASTER</span>
    </div>
  );

  if (!compact) {
    return <div className="snd-regulator-context snd-regulator-context--main" aria-label="Control de volumen del reproductor">{fader}</div>;
  }

  return (
    <div className="snd-regulator-context snd-regulator-context--compact" ref={containerRef}>
      <button
        type="button"
        className={`snd-fader-trigger${open ? ' snd-fader-trigger--open' : ''}`}
        aria-label={`Volumen ${level}%. ${open ? 'Cerrar control' : 'Abrir control'}`}
        aria-controls={id + '-popover'}
        aria-expanded={open}
        title={`Volumen ${level}%`}
        onClick={() => setOpen((previous) => !previous)}
      >
        <Icon name={level === 0 ? 'mute' : 'volume'} className="icon" />
        <span>{level}%</span>
      </button>
      {open ? (
        <div className="snd-fader-popover" id={id + '-popover'} role="group" aria-label="Fader de volumen">
          {fader}
        </div>
      ) : null}
    </div>
  );
}
