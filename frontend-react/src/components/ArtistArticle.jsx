import { useCallback, useEffect, useState } from 'react';

// Cache en memoria: abrir y cerrar la misma ficha no repite la petición.
const articleCache = new Map();

export function ArtistArticle({ slug, onClose }) {
  const [article, setArticle] = useState(() => (slug ? articleCache.get(slug) || null : null));
  const [error, setError] = useState('');

  useEffect(() => {
    if (!slug) return undefined;
    let alive = true;
    setError('');
    if (articleCache.has(slug)) {
      setArticle(articleCache.get(slug));
      return undefined;
    }
    setArticle(null);
    fetch('/blog/artists.json')
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.json();
      })
      .then((data) => {
        const found = (data.articles || []).find((item) => item.slug === slug);
        if (!found) throw new Error('Artículo no encontrado');
        articleCache.set(slug, found);
        if (alive) setArticle(found);
      })
      .catch((cause) => {
        if (alive) setError(cause?.message || 'error desconocido');
      });
    return () => { alive = false; };
  }, [slug]);

  useEffect(() => {
    if (!slug) return;
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    document.getElementById('artist-article')?.scrollIntoView({
      behavior: reduce ? 'auto' : 'smooth',
      block: 'start',
    });
  }, [slug]);

  const close = useCallback(() => {
    onClose?.();
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    document.getElementById('reproductor')?.scrollIntoView({
      behavior: reduce ? 'auto' : 'smooth',
      block: 'center',
    });
  }, [onClose]);

  if (!slug) return null;

  return (
    <section className="artist-article panel" id="artist-article" aria-label={`Artículo de ${slug}`}>
      <div className="artist-article__head">
        <p className="artist-article__kicker">
          {article ? `${article.tag} · ${article.readingMinutes} min de lectura` : 'NEWSHIT · FICHA DE ARTISTA'}
        </p>
        <button type="button" className="artist-article__close" onClick={close} aria-label="Cerrar artículo">
          ✕
        </button>
      </div>

      {error ? (
        <p className="artist-article__error" role="alert">
          No se pudo abrir la ficha ({error}).{' '}
          <a href={`/blog/${slug}/`}>Abrir artículo permanente ↗</a>
        </p>
      ) : null}
      {!article && !error ? (
        <p className="artist-article__loading" role="status">Abriendo ficha…</p>
      ) : null}

      {article ? (
        <article className="artist-article__body">
          <h2 className="artist-article__title">{article.title}</h2>
          <p className="artist-article__lede">{article.description}</p>

          <div className="artist-article__layout">
            <img
              className="artist-article__image"
              src={article.image}
              alt={article.imageAlt}
              width="400"
              height="400"
              loading="lazy"
            />
            <div className="artist-article__intro">
              <p>{article.intro}</p>
              <dl className="artist-article__facts">
                {(article.facts || []).map((fact) => (
                  <div key={fact.label}>
                    <dt>{fact.label}</dt>
                    <dd>{fact.value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </div>

          {(article.sections || []).map((section) => (
            <section className="artist-article__section" key={section.heading}>
              <h3>{section.heading}</h3>
              {(section.paragraphs || []).map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
            </section>
          ))}

          <aside className="artist-article__listen">
            <h3>Escuchar ahora</h3>
            {article.trackHref ? (
              <a
                className="artist-article__track"
                href={article.trackHref}
                {...(article.trackHref.startsWith('http')
                  ? { target: '_blank', rel: 'noopener noreferrer' }
                  : {})}
              >
                ▶ Escuchar {article.trackTitle}
              </a>
            ) : null}
            <ul>
              {(article.listen || []).map((link) => (
                <li key={link.url}>
                  <a href={link.url} target="_blank" rel="noopener noreferrer">{link.label}</a>
                </li>
              ))}
            </ul>
          </aside>

          <p className="artist-article__credit">{article.credit}</p>
          <a className="artist-article__permalink" href={`/blog/${slug}/`}>
            Ver artículo permanente y compartir ↗
          </a>
        </article>
      ) : null}
    </section>
  );
}
