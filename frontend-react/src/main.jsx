import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './styles.css';

/**
 * Protección frente a fallos de renderizado.
 * El usuario debe ver una salida recuperable, nunca una página blanca.
 * No expone el stacktrace al navegador del visitante.
 */
class MfMoodErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidMount() {
    // El HTML tiene un estado inicial sin JS; ocultarlo solo tras montar React.
    document.getElementById('allmusic-boot')?.remove();
  }

  componentDidCatch(error, info) {
    console.error('[MfMood] Error al iniciar la interfaz:', error, info.componentStack);
    document.getElementById('allmusic-boot')?.remove();
  }

  render() {
    if (this.state.hasError) {
      return (
        <main style={{
          minHeight: '100vh', display: 'grid', placeItems: 'center',
          background: '#090a0c', color: '#f7f1e8',
          padding: '28px', fontFamily: 'Arial, sans-serif', textAlign: 'center',
        }}>
          <section style={{ maxWidth: 530, display: 'grid', gap: 17 }}>
            <h1 style={{ fontSize: 42, margin: 0, fontWeight: 900 }}>
              CANAL <span style={{ color: '#fa168e' }}>24</span>
            </h1>
            <p style={{ margin: 0, lineHeight: 1.6 }}>
              La cabina tuvo un problema al abrirse. Podés reintentar sin perder
              tu biblioteca o entrar temporalmente al reproductor anterior.
            </p>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 12, flexWrap: 'wrap' }}>
              <button onClick={() => window.location.reload()}
                style={{ background: '#f4d500', color: '#090a0c', border: 0, padding: 13, fontWeight: 900 }}>
                REINTENTAR
              </button>
              <a href="/classic"
                style={{ background: '#f7f1e8', color: '#090a0c', padding: 13, textDecoration: 'none', fontWeight: 900 }}>
                SITIO CLÁSICO
              </a>
            </div>
          </section>
        </main>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <MfMoodErrorBoundary>
      <App />
    </MfMoodErrorBoundary>
  </React.StrictMode>
);
