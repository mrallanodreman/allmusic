const BARS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];

export function Equalizer({ active, compact = false }) {
  return (
    <div
      className={`equalizer${active ? ' equalizer--active' : ''}${compact ? ' equalizer--compact' : ''}`}
      role="img"
      aria-label={active ? 'Ecualizador activo' : 'Ecualizador detenido'}
    >
      {BARS.map((index) => (
        <span key={index} className="equalizer__bar" style={{ '--bar': index }} />
      ))}
    </div>
  );
}
