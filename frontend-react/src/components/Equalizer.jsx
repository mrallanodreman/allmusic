const BARS = Array.from({ length: 16 }, (_, index) => ({
  index,
  lo: 0.16 + ((index * 3) % 5) * 0.05,
  hi: 0.5 + ((index * 5) % 9) * 0.055,
  delay: -((index * 130) % 900) / 1000,
}));

export function Equalizer({ active, compact = false, wave = false }) {
  const className = [
    'equalizer',
    active ? 'equalizer--active' : '',
    compact ? 'equalizer--compact' : '',
    wave ? 'equalizer--wave' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div
      className={className}
      role="img"
      aria-label={active ? 'Visualizador de sonido activo' : 'Visualizador de sonido en pausa'}
    >
      {BARS.map((bar) => (
        <span
          key={bar.index}
          className="equalizer__bar"
          style={{
            '--bar': bar.index,
            '--eq-lo': bar.lo,
            '--eq-hi': bar.hi,
            '--eq-delay': `${bar.delay}s`,
          }}
        />
      ))}
    </div>
  );
}
