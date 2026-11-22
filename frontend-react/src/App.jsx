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
import { RequestBar } from './components/RequestBar.jsx';
import { MoodBoard } from './components/MoodBoard.jsx';
import { NewShit } from './components/NewShit.jsx';
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
  const handlePlaySelection = useCallback((track) => {
    meter.activate();
    return audio.playTrack(track);
  }, [meter.activate, audio.playTrack]);
  const [activeMood, setActiveMood] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [carteleraOpen, setCarteleraOpen] = useState(
    () => typeof window !== 'undefined' && window.location.hash === '#cartelera'
  );

  useEffect(() => {
    const syncCartelera = () => {
      setCarteleraOpen(window.location.hash === '#cartelera');
    };
    window.addEventListener('hashchange', syncCartelera);
    window.addEventListener('popstate', syncCartelera);
    return () => {
      window.removeEventListener('hashchange', syncCartelera);
      window.removeEventListener('popstate', syncCartelera);
    };
  }, []);

  const openCartelera = useCallback(() => {
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

          <div className="content__grid">
            <QueuePanel items={data.queue} />
            <HistoryPanel items={data.history} />
          </div>

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
      />
      <audio ref={audio.audioRef} preload="none" />
    </div>
  );
}
