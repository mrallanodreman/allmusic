import { useEffect, useRef } from 'react';

/**
 * Unidad manual de AdSense heredada del sitio clásico.
 * Auto Ads ya está cargado en index.html; este bloque garantiza una
 * ubicación estable y medible dentro del rail de MfMood.
 */
export function AdSlot() {
  const ref = useRef(null);

  useEffect(() => {
    const node = ref.current;
    if (!node || node.dataset.mfAdQueued) return;
    node.dataset.mfAdQueued = '1';
    try {
      (window.adsbygoogle = window.adsbygoogle || []).push({});
    } catch { /* AdSense puede no estar disponible aún; no romper la UI */ }
  }, []);

  return (
    <div className="ad-slot" aria-label="Publicidad">
      <ins
        ref={ref}
        className="adsbygoogle"
        style={{ display: 'block' }}
        data-ad-client="ca-pub-3871344948149274"
        data-ad-slot="5447354058"
        data-ad-format="auto"
        data-full-width-responsive="true"
      />
    </div>
  );
}
