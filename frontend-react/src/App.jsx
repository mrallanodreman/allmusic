import { useCallback, useEffect, useState } from 'react';
import { useRadioData } from './hooks/useRadioData.js';
import { useAudioStream } from './hooks/useAudioStream.js';
import { useAudioAnalyser } from './hooks/useAudioAnalyser.js';
import { moodSlug, normalizeText } from './lib/safe.js';
import { DecorLayer } from './components/DecorLayer.jsx';
import { HeaderBanner } from './components/HeaderBanner.jsx';
import { Sidebar } from './components/Sidebar.jsx';
import { PlayerStage } from './components/PlayerStage.jsx';
import { TrackSearchPanel } from './components/TrackSearchPanel.jsx';
import { EventBillboard } from './components/EventBillboard.jsx';
import { LibraryPanel } from './components/LibraryPanel.jsx';
import { MyMusicPanel } from './components/MyMusicPanel.jsx';
import { toPersonalTrack } from './lib/libraryApi.js';
import { RequestBar } from './components/RequestBar.jsx';
import { MoodBoard } from './components/MoodBoard.jsx';
import { NewShit } from './components/NewShit.jsx';
import { CommunityCarousel } from './components/CommunityCarousel.jsx';
import { TopRequested } from './components/TopRequested.jsx';
import { QueuePanel } from './components/QueuePanel.jsx';
import { HistoryPanel } from './components/HistoryPanel.jsx';
import { NowPlayingBar } from './components/NowPlayingBar.jsx';

export default function App() {
  const data = useRadioData();
  const audio = useAudioStream(data.now?.stream_url);
  const meter = useAudioAnalyser(audio.audioRef);

  // El contexto se habilita en un gesto: PLAY/PAUSA, RADIO o canción.
  const handleToggleAudio = useCallback(() => {
    meter.activate();
    audio.toggle();
  }, [meter.activate, audio.toggle]);
  const handleReturnRadio = useCallback(() => {
    meter.activate();
    audio.switchToRadio();
  }, [meter.activate, audio.switchToRadio]);
  const [personalQueue, setPersonalQueue] = useState([]);
  const [personalIndex, setPersonalIndex] = useState(0);
  const [historyVersion, setHistoryVersion] = useState(0);

  const playOne = useCallback((item) => {
    const track = toPersonalTrack(item);
    if (!track) return false;
    meter.activate();
    const ok = audio.playTrack(track);
    if (ok) {
      // Reutilizar las escuchadas del reproductor clásico (am_played).
      try {
        const existing = JSON.parse(window.localStorage.getItem('am_played') || '[]');
        const items = Array.isArray(existing) ? existing : [];
        const src = track.directSrc || (track.id ? `stream/${track.id}` : '');
        const next = [{
          title: track.title,
          artist: track.artist,
          thumb: track.thumbnail || '',
          src, videoId: track.id || null,
          id: track.localTrackId || track.id,
          ts: Date.now(),
        }, ...items.filter(x => !(x.title === track.title && x.artist === track.artist))].slice(0, 50);
        window.localStorage.setItem('am_played', JSON.stringify(next));
        setHistoryVersion(v => v + 1);
      } catch { /* audio funciona sin localStorage */ }
    }
    return ok;
  }, [meter.activate, audio.playTrack]);

  const handlePlaySelection = useCallback((track) => {
    setPersonalQueue([]);
    setPersonalIndex(0);
    return playOne(track);
  }, [playOne]);

  const handlePlayQueue = useCallback((tracks, index = 0) => {
    const queue = (Array.isArray(tracks) ? tracks : []).map(toPersonalTrack).filter(Boolean);
    if (!queue.length) return false;
    const pos = Math.min(queue.length - 1, Math.max(0, Number(index) || 0));
    setPersonalQueue(queue);
    setPersonalIndex(pos);
    return playOne(queue[pos]);
  }, [playOne]);

  const handleNextPersonal = useCallback(() => {
    if (audio.mode !== 'personal' || personalQueue.length < 2) return false;
    const next = (personalIndex + 1) % personalQueue.length;
    setPersonalIndex(next);
    return playOne(personalQueue[next]);
  }, [audio.mode, personalQueue, personalIndex, playOne]);

  useEffect(() => {
    const node = audio.audioRef.current;
    if (!node) return undefined;
    const onEnd = () => {
      if (audio.mode === 'personal' && personalQueue.length > 1) handleNextPersonal();
    };
    node.addEventListener('ended', onEnd);
    return () => node.removeEventListener('ended', onEnd);
  }, [audio.audioRef, audio.mode, personalQueue, handleNextPersonal]);
  const [activeMood, setActiveMood] = useState('');
  const [libraryView, setLibraryView] = useState(() => {
    const section = typeof window === 'undefined' ? '' : window.location.hash.slice(1);
    return ['playlists', 'mymusic'].includes(section) ? section : null;
  });
  const [searchOpen, setSearchOpen] = useState(false);
  const [carteleraOpen, setCarteleraOpen] = useState(
    () => typeof window !== 'undefined' && window.location.hash === '#cartelera'
  );

  useEffect(() => {
    const syncCartelera = () => {
      const hash = window.location.hash.slice(1);
      setCarteleraOpen(hash === 'cartelera');
      setLibraryView(['playlists', 'mymusic'].includes(hash) ? hash : null);
    };
    window.addEventListener('hashchange', syncCartelera);
    window.addEventListener('popstate', syncCartelera);
    return () => {
      window.removeEventListener('hashchange', syncCartelera);
      window.removeEventListener('popstate', syncCartelera);
    };
  }, []);

  const openCartelera = useCallback(() => {
    setLibraryView(null);
    setSearchOpen(false);
    setCarteleraOpen(true);
    if (window.location.hash !== '#cartelera') {
      window.history.pushState(null, '', '#cartelera');
    }
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        document.getElementById('cartelera')?.scrollIntoView({
          behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
            ? 'auto' : 'smooth',
          block: 'start',
        });
      });
    });
  }, []);

  const closeCartelera = useCallback((returnToPlayer = false) => {
    setCarteleraOpen(false);
    if (window.location.hash === '#cartelera') {
      window.history.replaceState(
        null, '', window.location.pathname + window.location.search
      );
    }
    if (returnToPlayer) {
      window.requestAnimationFrame(() => {
        document.getElementById('reproductor')?.scrollIntoView({
          behavior: 'smooth',
          block: 'start',
        });
      });
    }
  }, []);

  const openSearch = useCallback(() => {
    setLibraryView(null);
    setCarteleraOpen(false);
    setSearchOpen(true);
    // La sección se monta debajo del reproductor, no dentro del formulario
    // de pedidos a la radio. Dos frames garantizan que el DOM ya exista.
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        document.getElementById('buscar-musica')?.scrollIntoView({
          behavior: 'smooth',
          block: 'nearest',
        });
      });
    });
  }, []);

  const toggleSearch = useCallback(() => {
    if (searchOpen) setSearchOpen(false);
    else openSearch();
  }, [openSearch, searchOpen]);

  const closeSearch = useCallback(() => setSearchOpen(false), []);

  const openLibrary = useCallback((view) => {
    if (!['playlists', 'mymusic'].includes(view)) return;
    setCarteleraOpen(false);
    setSearchOpen(false);
    setLibraryView(view);
    if (window.location.hash !== `#${view}`) {
      window.history.pushState(null, '', `#${view}`);
    }
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        document.getElementById(view)?.scrollIntoView({
          behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
          block: 'start',
        });
      });
    });
  }, []);

  const radioHome = useCallback(() => {
    setLibraryView(null);
    setCarteleraOpen(false);
    setSearchOpen(false);
    if (window.location.hash) {
      window.history.replaceState(null, '', window.location.pathname + window.location.search);
    }
    document.getElementById('reproductor')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  const handleMood = useCallback(
    (label) => {
      const clean = normalizeText(label, 40);
      if (!clean) return;
      setActiveMood(moodSlug(clean));
      // El mood se activa usando el endpoint real de pedidos: no se inventa lógica de tickets
      // en el cliente; el contador de la sidebar es solo un reflejo visual de la sesión.
      data.submit(clean, 'mood-web');
    },
    [data.submit]
  );

  return (
    <div className="app" data-mood={activeMood || 'default'}>
      <a className="skip-link" href="#contenido">Saltar al contenido</a>
      <DecorLayer />
      <HeaderBanner live={Boolean(data.now?.playing)}>
        <RequestBar pending={data.pending} notice={data.notice} onSubmit={data.submit} />
      </HeaderBanner>

      <div className="layout">
        <Sidebar
          ticketsUsed={data.ticketsUsed}
          onAir={Boolean(data.now?.playing)}
          elapsed={data.now?.track?.elapsed}
          onOpenSearch={openSearch}
          onOpenCartelera={openCartelera}
          onCloseCartelera={closeCartelera}
          carteleraOpen={carteleraOpen}
          activeLibrary={libraryView}
          onOpenLibrary={openLibrary}
          onRadioHome={radioHome}
          analyserRef={meter.analyserRef}
          listening={audio.listening}
        />
        <main className="content" id="contenido">
          {data.error ? (
            <div className="alert" role="alert">
              {data.error}
              <button type="button" onClick={data.refresh}>Reintentar</button>
            </div>
          ) : null}

          <PlayerStage
            now={data.now}
            playing={audio.listening}
            onToggle={handleToggleAudio}
            volume={audio.volume}
            onVolume={audio.setVolume}
            onSkip={data.advance}
            advancing={data.advancing}
            audioError={audio.error}
            hasStream={audio.hasStream}
            hasPlayable={audio.hasPlayable}
            mode={audio.mode}
            selectedTrack={audio.selectedTrack}
            personalElapsed={audio.elapsed}
            personalDuration={audio.duration}
            searchOpen={searchOpen}
            analyserRef={meter.analyserRef}
            onSearch={toggleSearch}
            onRadio={handleReturnRadio}
            onNextPersonal={handleNextPersonal}
            onSeek={audio.seek}
            canNextPersonal={personalQueue.length > 1}
          />

          {searchOpen ? (
            <TrackSearchPanel
              onClose={closeSearch}
              onSelect={handlePlaySelection}
              onRadio={handleReturnRadio}
              mode={audio.mode}
              selectedTrack={audio.selectedTrack}
            />
          ) : null}

          {carteleraOpen ? (
            <EventBillboard onClose={() => closeCartelera(true)} />
          ) : null}

          {libraryView === 'playlists' ? (
            <LibraryPanel
              onPlay={handlePlaySelection}
              onPlayQueue={handlePlayQueue}
              selectedTrack={audio.selectedTrack}
              historyVersion={historyVersion}
            />
          ) : null}

          {libraryView === 'mymusic' ? (
            <MyMusicPanel onPlay={handlePlaySelection} />
          ) : null}

          {!libraryView && !carteleraOpen ? (
            <div className="content__grid">
              <QueuePanel items={data.queue} nextMood={data.nextMood} />
              <HistoryPanel items={data.history} />
            </div>
          ) : null}

          {data.loading ? <p className="loading" role="status">Sintonizando señal…</p> : null}
        </main>

        <aside className="rail" aria-label="Ranking, moods y recomendados">
          <TopRequested items={data.topRequested} />
          <MoodBoard
            moods={data.moods}
            activeMood={activeMood}
            onSelect={handleMood}
            pending={data.pending}
          />
          <NewShit
            playing={audio.listening}
            mode={audio.mode}
            selectedTrack={audio.selectedTrack}
            onToggle={handleToggleAudio}
            onPlayTrack={handlePlaySelection}
            onRadio={handleReturnRadio}
            audioError={audio.error}
            analyserRef={meter.analyserRef}
          />
          <CommunityCarousel />
        </aside>
      </div>

      <NowPlayingBar
        now={data.now}
        playing={audio.listening}
        onToggle={handleToggleAudio}
        volume={audio.volume}
        onVolume={audio.setVolume}
        onSkip={data.advance}
        advancing={data.advancing}
        activeMood={activeMood}
        hasStream={audio.hasStream}
        hasPlayable={audio.hasPlayable}
        mode={audio.mode}
        selectedTrack={audio.selectedTrack}
        personalElapsed={audio.elapsed}
        personalDuration={audio.duration}
        searchOpen={searchOpen}
        analyserRef={meter.analyserRef}
        onSearch={toggleSearch}
        onRadio={handleReturnRadio}
        onNextPersonal={handleNextPersonal}
        canNextPersonal={personalQueue.length > 1}
      />
      <audio ref={audio.audioRef} preload="none" />
    </div>
  );
}
