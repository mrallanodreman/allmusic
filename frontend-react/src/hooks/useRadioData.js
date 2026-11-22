import { useCallback, useEffect, useRef, useState } from 'react';
import {
  fetchNow,
  getLikedVideoIds,
  postAdvance,
  postLike,
  postSuggestion,
  saveLikedVideoIds,
} from '../lib/api.js';
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
  const [advancing, setAdvancing] = useState(false);
  const [ticketsUsed, setTicketsUsed] = useState(0);
  const [notice, setNotice] = useState('');
  const [likedIds, setLikedIds] = useState(getLikedVideoIds);
  const likedIdsRef = useRef(likedIds);
  const [likePending, setLikePending] = useState([]);
  const [likeCounts, setLikeCounts] = useState({});
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

  const advance = useCallback(async () => {
    if (advancing) return { ok: false };
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 12000);
    setAdvancing(true);
    setNotice('');
    try {
      const result = await postAdvance({ signal: controller.signal });
      if (!mounted.current) return { ok: true, result };
      setNotice(result?.advanced ? 'Solicitud de siguiente enviada a la cabina.' : 'No había pista para saltar.');
      await refresh();
      return { ok: true, result };
    } catch (err) {
      if (mounted.current) {
        setNotice(
          err?.name === 'AbortError'
            ? 'La solicitud tardó demasiado. Intentá de nuevo.'
            : normalizeText(err?.message, 120) || 'No se pudo solicitar el siguiente tema.'
        );
      }
      return { ok: false };
    } finally {
      window.clearTimeout(timeout);
      if (mounted.current) setAdvancing(false);
    }
  }, [advancing, refresh]);

  const toggleLike = useCallback(async (track) => {
    const videoId = normalizeText(track?.video_id, 16);
    if (!/^[A-Za-z0-9_-]{11}$/.test(videoId) || likePending.includes(videoId)) return;
    const liked = !likedIdsRef.current.includes(videoId);
    setLikePending((pendingIds) => [...pendingIds, videoId]);
    try {
      const result = await postLike(track, liked);
      const nextIds = liked
        ? [...new Set([...likedIdsRef.current, videoId])]
        : likedIdsRef.current.filter((id) => id !== videoId);
      likedIdsRef.current = nextIds;
      setLikedIds(nextIds);
      setLikeCounts((counts) => ({ ...counts, [videoId]: Number(result?.like_count) || 0 }));
      saveLikedVideoIds(nextIds);
      await refresh();
    } catch (err) {
      setNotice(normalizeText(err?.message, 120) || 'No se pudo guardar el like.');
    } finally {
      setLikePending((pendingIds) => pendingIds.filter((id) => id !== videoId));
    }
  }, [likePending, refresh]);

  return {
    now,
    loading,
    error,
    pending,
    advancing,
    ticketsUsed,
    notice,
    refresh,
    submit,
    advance,
    toggleLike,
    likedIds,
    likePending,
    likeCounts,
    queue: asArray(now?.queue, 20),
    history: asArray(now?.history, 5),
    topRequested: asArray(now?.top_requested, 10),
    mostLiked: asArray(now?.most_liked, 10),
    moods: asArray(now?.moods, 20),
    nextMood: now?.next_mood && typeof now.next_mood === 'object' ? now.next_mood : null,
  };
}
