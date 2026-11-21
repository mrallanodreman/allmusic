import clsx from 'clsx';
import { legacyAsset } from '../../lib/assets.js';

const BACKGROUNDS = [
  { name: 'sidebar', file: 'radio/c24/radio-sidebar.png' },
  { name: 'hero-left', file: 'radio/c24/radio-hero-left.png' },
  { name: 'now', file: 'radio/c24/radio-now-panel.png' },
  { name: 'request', file: 'radio/c24/radio-request-row.png' },
  { name: 'mood', file: 'radio/c24/radio-mood-panel.png' },
  { name: 'top', file: 'radio/c24/radio-top-panel.png' },
  { name: 'queue', file: 'radio/c24/radio-queue-panel.png' },
  { name: 'history', file: 'radio/c24/radio-history-panel.png' },
  { name: 'ticker', file: 'radio/c24/radio-ticker.png' },
];

const MOOD_ART = [
  'radio/c24/mood/mood-paper-clean.png',
  'radio/c24/mood/mood-label.png',
  'radio/c24/mood/mood-lightning.png',
  'radio/c24/mood/mood-face.png',
];

export function BackgroundLayers() {
  return (
    <div className="artboard-layers" aria-hidden="true">
      {BACKGROUNDS.map((layer) => (
        <img
          key={layer.name}
          className={clsx('radio-layer', `layer-${layer.name}`)}
          src={legacyAsset(layer.file)}
          alt=""
        />
      ))}
    </div>
  );
}

export function MoodArtStack() {
  return (
    <div className="mood-art-stack" aria-hidden="true">
      {MOOD_ART.map((file) => (
        <img key={file} src={legacyAsset(file)} alt="" />
      ))}
    </div>
  );
}
