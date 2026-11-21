import clsx from 'clsx';
import { uiAsset } from '../../lib/assets.js';

/**
 * Capa RETRO: 12 recortes del modelado anterior horneados en dos láminas por
 * `scripts/build_retro_decor.py`. Dos peticiones en vez de 12 evitan que el
 * rate limiter de Flask (30 req/s) descarte stickers en la carga inicial.
 */
export function LegacyDecorLayer({ enabled, live }) {
  return (
    <div
      className={clsx('legacy-decor', enabled ? 'is-on' : 'is-off', live && 'is-live')}
      aria-hidden="true"
    >
      <img
        className="legacy-decor__sheet decor-static"
        src={uiAsset('retro_static.png')}
        alt=""
        decoding="async"
      />
      <img
        className="legacy-decor__sheet decor-signal"
        src={uiAsset('retro_signal.png')}
        alt=""
        decoding="async"
      />
    </div>
  );
}

export function DecorToggle({ enabled, onToggle }) {
  return (
    <button
      type="button"
      className={clsx('hotspot', 'hit-decor', enabled && 'is-on')}
      onClick={onToggle}
      aria-pressed={enabled}
    >
      <span>RETRO</span>
      <span className="visually-hidden"> · calcomanías clásicas</span>
    </button>
  );
}
