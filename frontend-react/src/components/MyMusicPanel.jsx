import { useCallback, useEffect, useRef, useState } from 'react';
import { Icon } from './Icons.jsx';
import { normalizeText } from '../lib/safe.js';
import {
  getArtistToken, saveArtistToken, loginArtist, registerArtist,
  getArtistProfile, updateArtistProfile, uploadArtistPhoto,
  createArtistAlbum, removeArtistAlbum, uploadArtistFile, removeArtistFile,
  uploadOwnTrack, updateOwnTrack, deleteOwnTrack, activatePremium,
  getArtistEarnings, mediaUrl, toPersonalTrack, countTrackPlay,
} from '../lib/libraryApi.js';

/**
 * Tu Música: migración de las cuentas y uploads del panel clásico.
 * Usa los mismos tokens y rutas: no hay migración de datos ni usuarios.
 * "Premium" mantiene la lógica de activación del backend existente.
 */
export function MyMusicPanel({ onPlay }) {
  const [token, setToken] = useState(getArtistToken);
  const [profile, setProfile] = useState(null);
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [artistName, setArtistName] = useState('');
  const [password, setPassword] = useState('');
  const [form, setForm] = useState({ title: '', genre: '', is_public: true, rights_declared: false });
  const [file, setFile] = useState(null);
  const [albumName, setAlbumName] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [profileEdit, setProfileEdit] = useState(null);
  const [earnings, setEarnings] = useState(null);
  const inputFile = useRef(null);

  const refresh = useCallback(async (activeToken = token) => {
    if (!activeToken) { setProfile(null); return; }
    try {
      const payload = await getArtistProfile(activeToken);
      const artist = payload.artist || payload;
      if (!artist?.id) throw new Error('No se pudo recuperar el perfil.');
      setProfile(artist);
      setProfileEdit({
        artist_name: artist.artist_name || '',
        bio: artist.bio || '',
        genre: artist.genre || '',
        instagram: artist.social?.instagram || '',
        spotify: artist.social?.spotify || '',
        youtube: artist.social?.youtube || '',
      });
      if (artist.is_premium) {
        try { setEarnings(await getArtistEarnings(activeToken)); }
        catch { setEarnings(null); }
      }
    } catch (err) {
      if (err.status === 401 || err.status === 403) {
        saveArtistToken('');
        setToken('');
        setProfile(null);
      } else { setMessage(err.message); }
    }
  }, [token]);

  useEffect(() => {
    if (token) void refresh(token);
  }, [token, refresh]);

  const run = async (fn) => {
    setBusy(true);
    setMessage('');
    try { await fn(); }
    catch (err) { setMessage(err.message || 'No se pudo completar la operación.'); }
    finally { setBusy(false); }
  };

  const authenticate = (event) => {
    event.preventDefault();
    if (!email.trim() || password.length < 8 || (mode === 'register' && !artistName.trim())) {
      setMessage('Ingresá un correo, una contraseña de 8 caracteres como mínimo y el nombre artístico si vas a registrarte.');
      return;
    }
    void run(async () => {
      const result = mode === 'register'
        ? await registerArtist(email, password, artistName)
        : await loginArtist(email, password);
      if (!result.token) throw new Error('El servidor no devolvió una sesión.');
      saveArtistToken(result.token);
      setPassword('');
      setToken(result.token);
      setMessage('Sesión iniciada.');
    });
  };

  const logout = () => {
    saveArtistToken('');
    setToken('');
    setProfile(null);
    setPassword('');
    setEarnings(null);
    setMessage('Sesión cerrada.');
  };

  const submitTrack = (event) => {
    event.preventDefault();
    if (!file) { setMessage('Seleccioná un archivo de audio.'); return; }
    if (!form.title.trim() || !form.rights_declared) {
      setMessage('El título y la declaración de derechos son obligatorios.');
      return;
    }
    if (file.size > 200 * 1024 * 1024) {
      setMessage('Máximo 200 MB por archivo.');
      return;
    }
    void run(async () => {
      await uploadOwnTrack(token, { ...form, file });
      setForm({ title: '', genre: '', is_public: true, rights_declared: false });
      setFile(null);
      if (inputFile.current) inputFile.current.value = '';
      await refresh();
      setMessage('La canción se subió correctamente.');
    });
  };

  const updateVisibility = (track, publicFlag) => void run(async () => {
    await updateOwnTrack(token, track.id, { is_public: publicFlag });
    await refresh();
    setMessage(publicFlag ? 'Canción publicada.' : 'Canción retirada de la vista pública.');
  });

  const editTrack = (track) => {
    const title = window.prompt('Título de la canción', track.title || '');
    if (title === null || !title.trim()) return;
    const genre = window.prompt('Género', track.genre || '');
    if (genre === null) return;
    void run(async () => {
      await updateOwnTrack(token, track.id, { title: title.trim(), genre: genre.trim() });
      await refresh();
      setMessage('Datos de la canción actualizados.');
    });
  };

  const deleteTrack = (track) => {
    if (!window.confirm(`¿Eliminar definitivamente "${track.title}" y su archivo de audio?`)) return;
    void run(async () => {
      await deleteOwnTrack(token, track.id);
      await refresh();
      setMessage('Canción eliminada.');
    });
  };

  const saveProfile = (event) => {
    event.preventDefault();
    if (!profileEdit) return;
    void run(async () => {
      await updateArtistProfile(token, {
        artist_name: normalizeText(profileEdit.artist_name, 80),
        bio: profileEdit.bio.slice(0, 1000),
        genre: normalizeText(profileEdit.genre, 60),
        social: {
          instagram: profileEdit.instagram.slice(0, 200),
          spotify: profileEdit.spotify.slice(0, 200),
          youtube: profileEdit.youtube.slice(0, 200),
        },
      });
      await refresh();
      setMessage('Perfil artístico guardado.');
    });
  };

  const uploadImage = (kind, fileValue) => {
    if (!fileValue) return;
    if (!/^image\/(png|jpeg|webp)$/.test(fileValue.type)) {
      setMessage('Solo imágenes JPG, PNG o WEBP.');
      return;
    }
    void run(async () => {
      await uploadArtistPhoto(token, kind, fileValue);
      await refresh();
      setMessage(kind === 'avatar' ? 'Avatar actualizado.' : 'Portada del artista actualizada.');
    });
  };

  const createAlbum = (event) => {
    event.preventDefault();
    if (!albumName.trim()) return;
    void run(async () => {
      await createArtistAlbum(token, { title: albumName.trim(), year: new Date().getFullYear() });
      setAlbumName('');
      await refresh();
      setMessage('Álbum creado.');
    });
  };

  const deleteAlbum = (album) => {
    if (!window.confirm(`¿Eliminar el álbum "${album.title}"?`)) return;
    void run(async () => {
      await removeArtistAlbum(token, album.id);
      await refresh();
      setMessage('Álbum eliminado.');
    });
  };

  const uploadFile = (picked) => {
    if (!picked) return;
    void run(async () => {
      await uploadArtistFile(token, picked);
      await refresh();
      setMessage('Archivo añadido a tu biblioteca.');
    });
  };

  const deleteFile = (record) => {
    if (!window.confirm(`¿Eliminar "${record.name}"?`)) return;
    void run(async () => {
      await removeArtistFile(token, record.name);
      await refresh();
      setMessage('Archivo eliminado.');
    });
  };

  const enablePremium = () => {
    if (!window.confirm('¿Activar el estado Premium de tu cuenta? La plataforma gestionará las condiciones vigentes.')) return;
    void run(async () => {
      await activatePremium(token);
      await refresh();
      setMessage('Premium activado.');
    });
  };

  const playOwn = (track) => {
    if (!track.is_public) {
      setMessage('Publicá la canción para poder escucharla desde el reproductor público.');
      return;
    }
    const candidate = toPersonalTrack({ ...track, artist_name: profile.artist_name });
    if (!candidate) { setMessage('Archivo no disponible para reproducción.'); return; }
    onPlay(candidate);
    void countTrackPlay(track.id).catch(() => {});
  };

  return (
    <section className="music-workspace artist-workspace" id="mymusic" aria-labelledby="mymusic-heading">
      <header className="music-workspace__header">
        <span className="music-workspace__edition">MFMOOD / EDICIÓN ARTISTAS</span>
        <h2 id="mymusic-heading">TU <em>MÚSICA</em></h2>
        <p>Tu discografía, tus archivos y tu identidad artística. Recuperamos las mismas cuentas del archivo clásico.</p>
      </header>

      {message ? <p className="music-workspace__notice" role="status">{message}</p> : null}
      {!token ? (
        <div className="artist-workspace__auth">
          <div className="artist-workspace__auth-visual">
            <span>C24 / BACKSTAGE</span>
            <strong>EL ESCENARIO ES TUYO.</strong>
            <p>Publicá música original y administrá tus lanzamientos.</p>
          </div>
          <form className="music-workspace__sheet artist-workspace__auth-form" onSubmit={authenticate}>
            <div className="music-workspace__tabs" role="group" aria-label="Acceso de artista">
              <button type="button" className={mode === 'login' ? 'is-active' : ''} onClick={() => setMode('login')}>ENTRAR</button>
              <button type="button" className={mode === 'register' ? 'is-active' : ''} onClick={() => setMode('register')}>CREAR CUENTA</button>
            </div>
            <label htmlFor="artist-email">CORREO ELECTRÓNICO</label>
            <input id="artist-email" type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} />
            {mode === 'register' ? (
              <><label htmlFor="artist-name">NOMBRE ARTÍSTICO</label>
              <input id="artist-name" required maxLength={80} value={artistName} onChange={e => setArtistName(e.target.value)} /></>
            ) : null}
            <label htmlFor="artist-password">CONTRASEÑA</label>
            <input id="artist-password" type="password" minLength={8} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required value={password} onChange={e => setPassword(e.target.value)} />
            <button type="submit" className="music-workspace__primary" disabled={busy}>{busy ? 'CONECTANDO…' : mode === 'login' ? 'ABRIR CABINA' : 'CREAR MI PERFIL'}</button>
          </form>
        </div>
      ) : !profile ? (
        <div className="music-workspace__sheet">
          <p>Cargando tu biblioteca…</p>
          <button type="button" onClick={() => refresh()} disabled={busy}>REINTENTAR</button>
          <button type="button" onClick={logout}>CERRAR SESIÓN</button>
        </div>
      ) : (
        <>
          <div className="artist-workspace__profile">
            <div className="artist-workspace__banner" style={profile.header_image ? { backgroundImage: `url("${mediaUrl(profile.header_image)}")` } : undefined}>
              <label>CAMBIAR PORTADA <input type="file" accept="image/png,image/jpeg,image/webp" onChange={e => uploadImage('header', e.target.files?.[0])} disabled={busy} /></label>
            </div>
            <div className="artist-workspace__profile-info">
              {profile.avatar ? <img src={mediaUrl(profile.avatar)} alt="" /> : <span className="artist-workspace__avatar-fallback"><Icon name="star" className="icon" /></span>}
              <div>
                <span>{profile.is_premium ? 'ARTISTA PREMIUM' : 'ARTISTA INDEPENDIENTE'}</span>
                <h3>{normalizeText(profile.artist_name, 80)}</h3>
                <p>{normalizeText(profile.genre, 60) || 'Sin género definido'} · {(profile.tracks || []).length} canciones</p>
              </div>
              <div className="artist-workspace__profile-actions">
                <label>AVATAR <input type="file" accept="image/png,image/jpeg,image/webp" onChange={e => uploadImage('avatar', e.target.files?.[0])} disabled={busy}/></label>
                <button type="button" onClick={logout}>SALIR</button>
              </div>
            </div>
          </div>

          <div className="artist-workspace__grid">
            <form className="music-workspace__sheet artist-workspace__upload" onSubmit={submitTrack}>
              <h3>SUBIR CANCIÓN</h3>
              <p className="music-workspace__caption">MP3, WAV, FLAC, OGG, AAC, M4A o WMA · hasta 200 MB · sujeto a validación del servidor.</p>
              <label htmlFor="artist-song-file">ARCHIVO DE AUDIO</label>
              <input ref={inputFile} id="artist-song-file" type="file" required accept=".mp3,.wav,.flac,.ogg,.aac,.m4a,.wma" onChange={e => {
                const chosen = e.target.files?.[0] || null;
                setFile(chosen);
                if (chosen && !form.title) setForm(f => ({ ...f, title: chosen.name.replace(/\.[^.]+$/, '') }));
              }} />
              <label htmlFor="artist-song-title">TÍTULO</label>
              <input id="artist-song-title" required maxLength={200} value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} />
              <label htmlFor="artist-song-genre">GÉNERO</label>
              <input id="artist-song-genre" maxLength={60} value={form.genre} onChange={e => setForm(f => ({ ...f, genre: e.target.value }))} />
              <label className="artist-workspace__check">
                <input type="checkbox" checked={form.is_public} onChange={e => setForm(f => ({ ...f, is_public: e.target.checked }))} />
                <span>Mostrar esta canción públicamente</span>
              </label>
              <label className="artist-workspace__check">
                <input type="checkbox" required checked={form.rights_declared} onChange={e => setForm(f => ({ ...f, rights_declared: e.target.checked }))} />
                <span>Declaro que poseo los derechos necesarios sobre este audio y autorizo su publicación.</span>
              </label>
              <button type="submit" disabled={busy || !file || !form.rights_declared} className="music-workspace__primary">{busy ? 'PROCESANDO…' : 'PUBLICAR CANCIÓN'}</button>
            </form>

            <form className="music-workspace__sheet artist-workspace__details" onSubmit={saveProfile}>
              <h3>EDITAR PERFIL</h3>
              {profileEdit ? (
                <>
                  <label htmlFor="artist-profile-name">NOMBRE ARTÍSTICO</label>
                  <input id="artist-profile-name" required value={profileEdit.artist_name} maxLength={80} onChange={e => setProfileEdit(p => ({ ...p, artist_name: e.target.value }))} />
                  <label htmlFor="artist-profile-genre">GÉNERO</label>
                  <input id="artist-profile-genre" maxLength={60} value={profileEdit.genre} onChange={e => setProfileEdit(p => ({ ...p, genre: e.target.value }))} />
                  <label htmlFor="artist-profile-bio">BIOGRAFÍA</label>
                  <textarea id="artist-profile-bio" maxLength={1000} value={profileEdit.bio} onChange={e => setProfileEdit(p => ({ ...p, bio: e.target.value }))} rows={4} />
                  {['instagram', 'spotify', 'youtube'].map(network => (
                    <label key={network} className="artist-workspace__social">{network.toUpperCase()}
                      <input type="url" placeholder="https://" maxLength={200} value={profileEdit[network]} onChange={e => setProfileEdit(p => ({ ...p, [network]: e.target.value }))}/>
                    </label>
                  ))}
                  <button type="submit" className="music-workspace__primary" disabled={busy}>GUARDAR PERFIL</button>
                </>
              ) : null}
            </form>
          </div>

          <div className="music-workspace__sheet">
            <div className="music-workspace__sheet-head">
              <h3>MI DISCOGRAFÍA</h3>
              <span>{(profile.tracks || []).length} TEMAS</span>
            </div>
            <div className="music-workspace__track-list">
              {(profile.tracks || []).map(track => (
                <div className="music-workspace__track artist-workspace__track" key={track.id}>
                  <span className="music-workspace__index"><Icon name="music" className="icon" /></span>
                  <div><strong>{normalizeText(track.title, 160)}</strong><small>{normalizeText(track.genre, 60)} · {track.is_public ? 'PUBLICADA' : 'PRIVADA'} · {track.plays_count || 0} reproducciones</small></div>
                  <label className="artist-workspace__visibility">
                    <input type="checkbox" checked={Boolean(track.is_public)} disabled={busy} onChange={e => updateVisibility(track, e.target.checked)} />
                    <span>{track.is_public ? 'VISIBLE' : 'OCULTA'}</span>
                  </label>
                  <button type="button" disabled={!track.is_public || busy} onClick={() => playOwn(track)} aria-label={`Escuchar ${track.title}`}>▶</button>
                  <button type="button" disabled={busy} onClick={() => editTrack(track)} aria-label={`Editar ${track.title}`}>EDITAR</button>
                  <button type="button" disabled={busy} onClick={() => deleteTrack(track)} aria-label={`Borrar ${track.title}`}>×</button>
                </div>
              ))}
              {!(profile.tracks || []).length ? <p className="music-workspace__empty">Tu primera publicación comienza aquí.</p> : null}
            </div>
          </div>

          <div className="artist-workspace__grid">
            <div className="music-workspace__sheet">
              <h3>ÁLBUMES</h3>
              <form className="music-workspace__form" onSubmit={createAlbum}>
                <input value={albumName} onChange={e => setAlbumName(e.target.value)} maxLength={120} aria-label="Nombre del álbum" placeholder="Nuevo álbum" />
                <button type="submit" disabled={busy || !albumName.trim()}>AÑADIR</button>
              </form>
              <div className="artist-workspace__entries">
                {(profile.albums || []).map(album => (
                  <div key={album.id}><strong>{normalizeText(album.title, 120)}</strong><small>{album.year}</small>
                    <button type="button" disabled={busy} onClick={() => deleteAlbum(album)}>ELIMINAR</button>
                  </div>
                ))}
                {!(profile.albums || []).length ? <p className="music-workspace__empty">Aún no has creado álbumes.</p> : null}
              </div>
            </div>
            <div className="music-workspace__sheet">
              <h3>ARCHIVOS DEL ARTISTA</h3>
              <label className="artist-workspace__file">
                SUBIR ARCHIVO
                <input type="file" disabled={busy} onChange={e => { uploadFile(e.target.files?.[0]); e.target.value = ''; }} />
              </label>
              <div className="artist-workspace__entries">
                {(profile.files || []).map(entry => (
                  <div key={entry.name}><a href={mediaUrl(entry.url)} target="_blank" rel="noreferrer">{normalizeText(entry.name, 110)}</a>
                    <small>{Math.round((Number(entry.size) || 0) / 1024)} KB</small>
                    <button type="button" disabled={busy} onClick={() => deleteFile(entry)}>ELIMINAR</button>
                  </div>
                ))}
                {!(profile.files || []).length ? <p className="music-workspace__empty">Aún no hay archivos adicionales.</p> : null}
              </div>
            </div>
          </div>

          <div className="music-workspace__sheet artist-workspace__premium">
            <div>
              <span className="music-workspace__edition">ESTUDIO / PREMIUM</span>
              <h3>ESTADO DE MONETIZACIÓN</h3>
              <p>{profile.is_premium ? 'Cuenta Premium activa' : 'Cuenta gratuita'}</p>
              {profile.is_premium ? (
                <p>Ganancias registradas: <strong>${Number(earnings?.total ?? profile.earnings ?? 0).toFixed(2)}</strong></p>
              ) : <p>La monetización depende de las condiciones operativas del sistema.</p>}
            </div>
            {!profile.is_premium ? <button type="button" disabled={busy} onClick={enablePremium}>ACTIVAR PREMIUM</button> : null}
          </div>
        </>
      )}
    </section>
  );
}
