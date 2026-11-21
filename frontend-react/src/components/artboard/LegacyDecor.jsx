import clsx from 'clsx';
import { uiAsset } from '../../lib/assets.js';

/** Recortes del modelado anterior que ya existían en public/ pero no se usaban. */
const DECOR = [
  { id: 'halftone', file: 'texture_halftone_overlay.png' },
  { id: 'logo', file: 'sticker_canal_24.png' },
  { id: 'tape-live', file: 'tape_en_vivo.png' },
  { id: 'tape-mix', file: 'tape_canal_24_mix.png' },
  { id: 'rec', file: 'badge_rec_dot.png' },
  { id: 'tape-request', file: 'tape_request_line.png' },
  { id: 'eye', file: 'graphic_eye_collage.png' },
  { id: 'stay', file: 'sticker_stay_tuned.png' },
  { id: 'top-banner', file: 'banner_top_10.png' },
  { id: 'on-air', file: 'sticker_on_air.png' },
  { id: 'crosshair', file: 'emblem_target_crosshair.png' },
  { id: 'emblem', file: 'emblem_ia_radio.png' },
];

export function LegacyDecorLayer({ enabled, live }) {
  return (
    <div
      className={clsx('legacy-decor', enabled ? 'is-on' : 'is-off', live && 'is-live')}
      aria-hidden="true"
    >
      {DECOR.map(({ id, file }) => (
        <img
          key={id}
          className={clsx('legacy-decor__item', `decor-${id}`)}
          src={uiAsset(file)}
          alt=""
          loading="lazy"
          decoding="async"
        />
      ))}
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
