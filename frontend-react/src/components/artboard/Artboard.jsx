import clsx from 'clsx';
import { normalizeText } from '../../lib/safe.js';
import { inferMood } from '../../lib/mood.js';
import { BackgroundLayers, MoodArtStack } from './Layers.jsx';
import { LegacyDecorLayer, DecorToggle } from './LegacyDecor.jsx';
import { ArtboardNav, BroadcastRuntime, Toast } from './Chrome.jsx';
import {
  NowPanel,
  RequestPanel,
  MoodPanel,
  TopPanel,
  QueuePanel,
  HistoryPanel,
} from './Panels.jsx';

export function Artboard({
  data,
  requestText,
  requestRef,
  onRequestText,
  onMood,
  onRequest,
  onListen,
  onAdvance,
  onRefresh,
  legacyDecor,
  onToggleDecor,
  listening,
  advancing,
  audioRef,
  toast,
}) {
  const live = Boolean(data.now?.playing);
  const mood = inferMood(data.now);
  const track = data.now?.track;
  const title = normalizeText(track?.title, 120);
  const artist = normalizeText(track?.artist || track?.uploader, 120) || 'C24';
  const ticker = live && title ? `${title} // ${artist}` : 'SEÑAL EN ESPERA // CANAL 24 RADIO 24/7';

  return (
    <main
      className={clsx(
        'radio-artboard',
        live && 'is-live',
        data.topRequested.length > 0 && 'has-request-data',
        data.queue.length > 0 && 'has-queue-data',
        data.history.length > 0 && 'has-history-data',
        mood.label !== 'ROCK SIGNAL' && 'mood-has-overlay'
      )}
      data-mood={mood.key || 'default'}
      aria-label="C24 Radio 24/7"
    >
      <BackgroundLayers />
      <LegacyDecorLayer enabled={legacyDecor} live={live} />

      <ArtboardNav
        onListen={onListen}
        onAdvance={onAdvance}
        onRefresh={onRefresh}
        listening={listening}
        advancing={advancing}
      />
      <DecorToggle enabled={legacyDecor} onToggle={onToggleDecor} />

      <NowPanel now={data.now} live={live} />
      <RequestPanel
        value={requestText}
        inputRef={requestRef}
        onChange={onRequestText}
        pending={data.pending}
        disabled={advancing}
        notice={data.notice}
        onSubmit={onRequest}
      />

      <MoodArtStack />
      <MoodPanel mood={mood} pending={data.pending} onSelect={onMood} />

      <TopPanel items={data.topRequested} />
      <QueuePanel items={data.queue} />
      <HistoryPanel items={data.history} />

      <BroadcastRuntime ticker={ticker} live={live} />

      <audio className="radio-audio" ref={audioRef} preload="none" aria-hidden="true" />
      <Toast message={toast} />

      {data.error ? (
        <p className="artboard-alert" role="alert">{data.error}</p>
      ) : null}
      {data.loading ? (
        <span className="artboard-loading" role="status">Sintonizando…</span>
      ) : null}
    </main>
  );
}
