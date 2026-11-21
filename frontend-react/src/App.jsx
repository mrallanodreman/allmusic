import { useCallback, useState } from 'react';
import { useRadioData } from './hooks/useRadioData.js';
import { moodSlug, normalizeText } from './lib/safe.js';
import { DecorLayer } from './components/DecorLayer.jsx';
import { HeaderBanner } from './components/HeaderBanner.jsx';
import { Sidebar } from './components/Sidebar.jsx';
import { PlayerStage } from './components/PlayerStage.jsx';
import { RequestBar } from './components/RequestBar.jsx';
import { MoodBoard } from './components/MoodBoard.jsx';
import { TopRequested } from './components/TopRequested.jsx';
import { QueuePanel } from './components/QueuePanel.jsx';
import { HistoryPanel } from './components/HistoryPanel.jsx';
import { NowPlayingBar } from './components/NowPlayingBar.jsx';

export default function App() {
  const data = useRadioData();
  const [activeMood, setActiveMood] = useState('');
  const [playing, setPlaying] = useState(true);

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

  const togglePlay = useCallback(() => setPlaying((value) => !value), []);

  return (
    <div className="app" data-mood={activeMood || 'default'}>
      <DecorLayer />
      <HeaderBanner live={Boolean(data.now?.playing)} />

      <div className="layout">
        <Sidebar ticketsUsed={data.ticketsUsed} />
        <main className="content">
          {data.error ? (
            <div className="alert" role="alert">
              {data.error}
              <button type="button" onClick={data.refresh}>Reintentar</button>
            </div>
          ) : null}

          <PlayerStage now={data.now} playing={playing} onToggle={togglePlay} />
          <RequestBar pending={data.pending} notice={data.notice} onSubmit={data.submit} />
          <MoodBoard
            moods={data.moods}
            activeMood={activeMood}
            onSelect={handleMood}
            pending={data.pending}
          />

          <div className="content__grid">
            <TopRequested items={data.topRequested} />
            <QueuePanel items={data.queue} />
            <HistoryPanel items={data.history} />
          </div>

          {data.loading ? <p className="loading" role="status">Sintonizando señal…</p> : null}
        </main>
      </div>

      <NowPlayingBar
        now={data.now}
        playing={playing}
        onToggle={togglePlay}
        activeMood={activeMood}
      />
    </div>
  );
}
