import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchNow, postSuggestion } from '../lib/api.js';
import { isSafeRequestText, normalizeText } from '../lib/safe.js';

const EMPTY = { queue: [], history: [], top_requested: [], moods: [] };

function asArray(value, limit) {
  return Array.isArray(value) ? value.slice(0, limit) : [];
}

export function useRadioData() {
  const [now, setNow] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const [ticketsUsed, setTicketsUsed] = useState(0);
  const [notice, setNotice] = useState('');
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    const controller = new AbortController();
    try {
      const data = await fetchNow(controller.signal);
      if (!mounted.current) return;
      setNow(data && typeof data === 'object' ? data : null);
      setError('');
      setLoading(false);
    } catch (err) {
      if (!mounted.current || err?.name === 'AbortError') return;
      setLoading(false);
      setError('Señal no disponible en este momento.');
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    refresh();
    const timer = window.setInterval(refresh, 6000);
    return () => {
      mounted.current = false;
      window.clearInterval(timer);
    };
  }, [refresh]);

  const submit = useCallback(
    async (rawText, reason = 'web') => {
      if (pending) return { ok: false };
      if (!isSafeRequestText(rawText)) {
        setNotice('Escribí entre 2 y 120 caracteres válidos.');
        return { ok: false };
      }
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 12000);
      setPending(true);
      setNotice('');
      try {
        const result = await postSuggestion(rawText, { signal: controller.signal, reason });
        if (!mounted.current) return { ok: true, result };
        setTicketsUsed((count) => count + 1);
        setNotice(
          `Pedido en cola · posición ${Number(result?.position) || 1} · ${
            normalizeText(result?.track?.title, 80) || 'track solicitado'
          }`
        );
        await refresh();
        return { ok: true, result };
      } catch (err) {
        if (mounted.current) {
          setNotice(
            err?.name === 'AbortError'
              ? 'La petición tardó demasiado. Intentá de nuevo.'
              : normalizeText(err?.message, 120) || 'No se pudo enviar el pedido.'
          );
        }
        return { ok: false };
      } finally {
        window.clearTimeout(timeout);
        if (mounted.current) setPending(false);
      }
    },
    [pending, refresh]
  );

  return {
    now,
    loading,
    error,
    pending,
    ticketsUsed,
    notice,
    refresh,
    submit,
    queue: asArray(now?.queue, 20),
    history: asArray(now?.history, 10),
    topRequested: asArray(now?.top_requested, 10),
    moods: asArray(now?.moods, 20),
  };
}
