import { useCallback, useEffect, useState } from 'react';
import { Icon } from './Icons.jsx';
import { normalizeText } from '../lib/safe.js';
import {
  listPlaylists, createPlaylist, removePlaylist, addPlaylistTrack,
  removePlaylistTrack, listPublicTracks, toPersonalTrack, mediaUrl,
  countTrackPlay, prepareTrackDownload, getArtistToken,
} from '../lib/libraryApi.js';

const getHistory = () => {
  try {
    const items = JSON.parse(window.localStorage.getItem('am_played') || '[]');
    return Array.isArray(items) ? items.slice(0, 50) : [];
  } catch { return []; }
};

export function LibraryPanel({ onPlay, onPlayQueue, selectedTrack, historyVersion = 0 }) {
  const [tab, setTab] = useState('playlists');
  const [playlists, setPlaylists] = useState([]);
  const [opened, setOpened] = useState(null);
  const [name, setName] = useState('');
  const [owner, setOwner] = useState('');
  const [query, setQuery] = useState('');
  const [publicTracks, setPublicTracks] = useState([]);
  const [history, setHistory] = useState(getHistory);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  const refreshPlaylists = useCallback(async () => {
    const data = await listPlaylists();
    setPlaylists(Array.isArray(data) ? data : []);
  }, []);

  useEffect(() => {
    let alive = true;
    listPlaylists().then((data) => {
      if (alive) setPlaylists(Array.isArray(data) ? data : []);
    }).catch((err) => { if (alive) setError(err.message); });
    return () => { alive = false; };
  }, []);

  useEffect(() => { setHistory(getHistory()); }, [historyVersion]);

  const run = async (action) => {
    setLoading(true);
    setError('');
    setNotice('');
    try {
      const message = await action();
      if (message) setNotice(message);
    } catch (err) { setError(err.message || 'No se pudo completar la acción.'); }
    finally { setLoading(false); }
  };

  const create = (event) => {
    event.preventDefault();
    if (!name.trim()) return;
    void run(async () => {
      await createPlaylist(name.trim(), owner.trim());
      setName('');
      await refreshPlaylists();
      return 'Playlist creada en tu biblioteca compartida.';
    });
  };

  const remove = (id) => {
    if (!window.confirm('¿Eliminar esta playlist compartida y todas sus referencias?')) return;
    void run(async () => {
      await removePlaylist(id);
      if (opened === id) setOpened(null);
      await refreshPlaylists();
      return 'Playlist eliminada.';
    });
  };

  const addCurrent = (playlistId) => void run(async () => {
    const track = toPersonalTrack(selectedTrack);
    if (!track) throw new Error('Primero elegí una canción para añadirla.');
    await addPlaylistTrack(playlistId, {
      id: track.id || track.localTrackId,
      videoId: track.id || '',
      title: track.title,
      artist: track.artist,
      thumb: track.thumbnail || '',
      src: track.directSrc || (track.id ? `stream/${track.id}` : ''),
    });
    await refreshPlaylists();
    return `Añadida: ${track.title}`;
  });

  const removeTrack = (pl, idx) => void run(async () => {
    await removePlaylistTrack(pl.id, idx);
    await refreshPlaylists();
    return 'Canción retirada de la playlist.';
  });

  const discover = (event) => {
    event?.preventDefault();
    void run(async () => {
      const data = await listPublicTracks(query.trim());
      setPublicTracks(Array.isArray(data.tracks) ? data.tracks : []);
      return '';
    });
  };

  const listen = (track) => {
    const selected = toPersonalTrack(track);
    if (selected) {
      onPlay(selected);
      if (selected.localTrackId) void countTrackPlay(selected.localTrackId).catch(() => {});
    } else setError('Esta canción no tiene un audio reproducible.');
  };

  const listenAll = (tracks, index = 0) => {
    const playable = tracks.map(toPersonalTrack).filter(Boolean);
    if (!playable.length) { setError('Esta lista todavía no tiene canciones reproducibles.'); return; }
    const selected = toPersonalTrack(tracks[index]);
    const position = Math.max(0, playable.findIndex(t => t.id === selected?.id && t.directSrc === selected?.directSrc));
    onPlayQueue(playable, position);
  };

  const download = (track) => void run(async () => {
    const id = String(track.id || '');
    if (!id.startsWith('trk_')) throw new Error('Solo se pueden descargar archivos publicados por artistas.');
    const result = await prepareTrackDownload(id, getArtistToken());
    const src = mediaUrl(result?.url);
    if (!src) throw new Error('El servidor no devolvió un archivo válido.');
    const anchor = document.createElement('a');
    anchor.href = src;
    anchor.download = `${normalizeText(track.title, 90) || 'musica'}.mp3`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    return 'Descarga solicitada.';
  });

  const current = playlists.find(p => p.id === opened);
  const tracks = Array.isArray(current?.tracks) ? current.tracks : [];

  return (
    <section id="playlists" className="music-workspace" aria-labelledby="library-heading">
      <header className="music-workspace__header">
        <span className="music-workspace__edition">ALLMUSIC / ARCHIVOS DE LA CABINA</span>
        <h2 id="library-heading">TU <em>BIBLIOTECA</em></h2>
        <p>Playlists del AllMusic original, descubrimiento independiente e historial personal. Todo con el reproductor de Canal 24.</p>
      </header>

      <div className="music-workspace__tabs" role="group" aria-label="Secciones de biblioteca">
        <button type="button" className={tab === 'playlists' ? 'is-active' : ''} onClick={() => setTab('playlists')}>
          <Icon name="list" className="icon" /> PLAYLISTS
        </button>
        <button type="button" className={tab === 'discover' ? 'is-active' : ''} onClick={() => { setTab('discover'); if (!publicTracks.length) discover(); }}>
          <Icon name="search" className="icon" /> DESCUBRIR
        </button>
        <button type="button" className={tab === 'history' ? 'is-active' : ''} onClick={() => { setHistory(getHistory()); setTab('history'); }}>
          <Icon name="clock" className="icon" /> ESCUCHADAS
        </button>
      </div>
      {error ? <p className="music-workspace__error" role="alert">{error}</p> : null}
      {notice ? <p className="music-workspace__notice" role="status">{notice}</p> : null}

      {tab === 'playlists' ? (
        <>
          <form className="music-workspace__form" onSubmit={create}>
            <label htmlFor="pl-name">NUEVA PLAYLIST</label>
            <input id="pl-name" value={name} maxLength={100} placeholder="Nombre de la lista…" onChange={e => setName(e.target.value)} />
            <input aria-label="Tu nombre en la playlist" value={owner} maxLength={40} placeholder="Creada por…" onChange={e => setOwner(e.target.value)} />
            <button type="submit" disabled={loading || !name.trim()}>CREAR +</button>
          </form>
          <p className="music-workspace__caption">Las playlists del sistema clásico son compartidas entre visitantes. No guardes aquí información privada.</p>
          {opened && current ? (
            <div className="music-workspace__sheet">
              <div className="music-workspace__sheet-head">
                <button type="button" onClick={() => setOpened(null)}>← TODAS LAS PLAYLISTS</button>
                <h3>{normalizeText(current.name, 100)}</h3>
                <span>{tracks.length} TEMAS</span>
              </div>
              <div className="music-workspace__actions">
                <button type="button" disabled={!tracks.length} onClick={() => listenAll(tracks)}>▶ REPRODUCIR TODO</button>
                <button type="button" disabled={!selectedTrack || loading} onClick={() => addCurrent(current.id)}>+ AÑADIR TEMA ACTUAL</button>
              </div>
              {tracks.length ? <div className="music-workspace__track-list">
                {tracks.map((track, index) => (
                  <div className="music-workspace__track" key={`${index}-${track.id || track.title}`}>
                    <span className="music-workspace__index">{String(index + 1).padStart(2, '0')}</span>
                    <div><strong>{normalizeText(track.title, 120) || 'Canción'}</strong><small>{normalizeText(track.artist, 90)}</small></div>
                    <button type="button" onClick={() => listenAll(tracks, index)} title="Reproducir tema">▶</button>
                    <button type="button" onClick={() => removeTrack(current, index)} disabled={loading} aria-label={`Quitar ${track.title} de la lista`}>×</button>
                  </div>
                ))}
              </div> : <p className="music-workspace__empty">Añadí música desde el buscador y volvé a esta playlist.</p>}
            </div>
          ) : (
            <div className="music-workspace__cards">
              {playlists.map(pl => (
                <article className="music-workspace__playlist" key={pl.id}>
                  <span className="music-workspace__playlist-art"><Icon name="music" className="icon" /></span>
                  <div>
                    <strong>{normalizeText(pl.name, 110)}</strong>
                    <small>{(pl.tracks || []).length} canciones · {normalizeText(pl.created_by, 55)}</small>
                  </div>
                  <button type="button" onClick={() => setOpened(pl.id)}>ABRIR</button>
                  <button type="button" disabled={loading} onClick={() => remove(pl.id)} aria-label={`Eliminar playlist ${pl.name}`}>×</button>
                </article>
              ))}
              {!playlists.length ? <p className="music-workspace__empty">Aún no hay playlists. Creá la primera.</p> : null}
            </div>
          )}
        </>
      ) : null}

      {tab === 'discover' ? (
        <div className="music-workspace__sheet">
          <form className="music-workspace__form" onSubmit={discover}>
            <label htmlFor="community-search">MÚSICA DE ARTISTAS INDEPENDIENTES</label>
            <input id="community-search" placeholder="Buscá por artista o canción" value={query} onChange={e => setQuery(e.target.value)} maxLength={100} />
            <button type="submit" disabled={loading}>BUSCAR</button>
          </form>
          <p className="music-workspace__caption">Canciones originales subidas por artistas de AllMusic.</p>
          <div className="music-workspace__track-list">
            {publicTracks.map(track => (
              <div className="music-workspace__track" key={track.id}>
                <span className="music-workspace__index">♪</span>
                <div><strong>{normalizeText(track.title, 120)}</strong><small>{normalizeText(track.artist_name, 90)} · {normalizeText(track.genre, 45)}</small></div>
                <button type="button" onClick={() => listen(track)}>▶ OÍR</button>
                <button type="button" onClick={() => download(track)} disabled={loading} title="Solicitar descarga">↓</button>
              </div>
            ))}
            {!publicTracks.length ? <p className="music-workspace__empty">No hay canciones publicadas para esta búsqueda.</p> : null}
          </div>
        </div>
      ) : null}

      {tab === 'history' ? (
        <div className="music-workspace__sheet">
          <div className="music-workspace__sheet-head">
            <h3>ESCUCHADAS EN ESTE NAVEGADOR</h3>
            <button type="button" onClick={() => {
              if (!window.confirm('¿Borrar el historial de música escuchada en este navegador?')) return;
              try { window.localStorage.removeItem('am_played'); } catch { /* no storage */ }
              setHistory([]);
            }}>BORRAR HISTORIAL</button>
          </div>
          <div className="music-workspace__track-list">
            {history.map((track, index) => (
              <div className="music-workspace__track" key={`${index}-${track.ts || track.title}`}>
                <span className="music-workspace__index">{String(index + 1).padStart(2, '0')}</span>
                <div><strong>{normalizeText(track.title, 120)}</strong><small>{normalizeText(track.artist, 80)}</small></div>
                <button type="button" onClick={() => listen(track)}>▶ REPETIR</button>
              </div>
            ))}
            {!history.length ? <p className="music-workspace__empty">Todavía no has escuchado canciones por tu cuenta.</p> : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}
