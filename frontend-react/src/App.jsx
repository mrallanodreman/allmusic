import { useCallback, useRef, useState } from 'react';
import { useRadioData } from './hooks/useRadioData.js';
import { useAudioStream } from './hooks/useAudioStream.js';
import { Artboard } from './components/artboard/Artboard.jsx';

export default function App() {
  const data = useRadioData();
  const audio = useAudioStream(data.now?.stream_url);
  const [requestText, setRequestText] = useState('');
  const [hint, setHint] = useState('');
  const [legacyDecor, setLegacyDecor] = useState(true);
  const requestRef = useRef(null);

  // Igual que el panel histórico: el chip prepara el pedido, no lo envía.
  const handleMood = useCallback((query) => {
    setRequestText(String(query || ''));
    setHint('Mood listo para encolar');
    requestRef.current?.focus();
  }, []);

  const handleRequest = useCallback(
    async (text) => {
      const result = await data.submit(text);
      if (result?.ok !== false) {
        setRequestText('');
        setHint('');
      }
      return result;
    },
    [data.submit]
  );

  const toast = audio.error || data.notice || hint;

  return (
    <Artboard
      data={data}
      requestText={requestText}
      requestRef={requestRef}
      onRequestText={setRequestText}
      onMood={handleMood}
      onRequest={handleRequest}
      onListen={audio.toggle}
      onAdvance={data.advance}
      onRefresh={data.refresh}
      legacyDecor={legacyDecor}
      onToggleDecor={() => setLegacyDecor((value) => !value)}
      listening={audio.listening}
      advancing={data.advancing}
      audioRef={audio.audioRef}
      toast={toast}
    />
  );
}
