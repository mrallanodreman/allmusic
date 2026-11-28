import { useEffect, useState } from 'react';

const KEY = 'am_cookie_consent';

/**
 * Consent Mode v2 para MfMood. El default ya viene denegado en index.html;
 * este banner solo actualiza la señal cuando el visitante decide.
 */
export function CookieConsent() {
  const [choice, setChoice] = useState(() => {
    try { return window.localStorage.getItem(KEY); } catch { return null; }
  });

  useEffect(() => {
    if (!choice) return;
    try { window.localStorage.setItem(KEY, choice); } catch { /* sin storage */ }
    window.dataLayer = window.dataLayer || [];
    const granted = choice === 'all';
    window.dataLayer.push(() => {
      (window.gtag || function () {})('consent', 'update', {
        ad_storage: granted ? 'granted' : 'denied',
        analytics_storage: granted ? 'granted' : 'denied',
        ad_user_data: granted ? 'granted' : 'denied',
        ad_personalization: granted ? 'granted' : 'denied',
      });
    });
  }, [choice]);

  if (choice) return null;

  return (
    <section className="cookie-consent" role="dialog" aria-label="Preferencias de cookies">
      <p>
        Usamos cookies propias y de terceros de Google Analytics para medir la audiencia.
      </p>
      <div className="cookie-consent__actions">
        <button type="button" onClick={() => setChoice('all')}>Aceptar todo</button>
        <button type="button" onClick={() => setChoice('essential')}>Solo esenciales</button>
      </div>
    </section>
  );
}
