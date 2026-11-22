import { useEffect, useRef, useState } from 'react';

const OPTIONS = { threshold: 0.12, rootMargin: '0px 0px -30px 0px' };

// Revelado suave sin dependencias: si no hay IntersectionObserver, el contenido queda visible.
export function useInView() {
  const ref = useRef(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    if (typeof IntersectionObserver === 'undefined') {
      setVisible(true);
      return undefined;
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setVisible(true);
        observer.disconnect();
      }
    }, OPTIONS);
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return [ref, visible];
}
