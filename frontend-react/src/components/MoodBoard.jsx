import { moodSlug, normalizeText } from '../lib/safe.js';
import { Icon } from './Icons.jsx';

const PRESETS = [
  { label: 'Lo-Fi', cost: 1 },
  { label: 'Synthwave', cost: 1 },
  { label: 'Rock 80s', cost: 2 },
  { label: 'Jazz Late', cost: 2 },
  { label: 'Night Dance', cost: 2 },
];

export function MoodBoard({ moods, activeMood, onSelect, pending }) {
  const discovered = moods
    .map((item) => ({ label: normalizeText(item?.mood, 40), uses: Number(item?.uses) || 0 }))
    .filter((item) => item.label && !PRESETS.some((preset) => preset.label.toLowerCase() === item.label.toLowerCase()))
    .slice(0, 5);

  const options = [...PRESETS, ...discovered.map((item) => ({ label: item.label, cost: 1, uses: item.uses }))];

  return (
    <section className="moods panel" id="moods" aria-labelledby="moods-title">
      <div className="section-head">
        <h2 id="moods-title">MOODS / ESTILOS</h2>
        <span className="section-head__hint">activá el ambiente</span>
      </div>
      <ul className="moods__grid">
        {options.map((option) => {
          const active = activeMood === moodSlug(option.label);
          return (
            <li key={option.label}>
              <button
                type="button"
                className={`mood${active ? ' mood--active' : ''}`}
                data-mood={moodSlug(option.label)}
                onClick={() => onSelect(option.label)}
                disabled={pending}
                aria-pressed={active}
              >
                <span className="mood__label">{option.label}</span>
                <span className="mood__cost" aria-label={`${option.cost} tickets`}>
                  <Icon name="bolt" className="icon" /> {option.cost}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
