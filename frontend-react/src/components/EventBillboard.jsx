import { useEffect, useRef } from 'react';
import { Icon } from './Icons.jsx';

/**
 * Cartelera promocional de Canal 24.
 * Artes oficiales referenciados directamente desde las fichas de BuenPlan,
 * sin emitir entradas, códigos QR, comprobantes o reservas.
 *
 * Diseño de tickets: adaptación visual de las tarjetas MIT de Uiverse:
 * - dexter-st / slippery-bird-76 (holographic ticket)
 * - zeeshan_2112 / shy-rattlesnake-3 (dark futuristic ticket)
 * Consultar BILLBOARD_CREDITS.md para licencias y enlaces de atribución.
 */
const EVENTS = [
  {
    id: 'jondo',
    title: 'JONDO',
    subtitle: 'Del alma al cuerpo',
    organizer: 'LOLA BAILA EC',
    category: 'DANZA / CULTURA',
    dateLabel: 'JUE 17 DIC 2026',
    day: '17',
    month: 'DIC',
    year: '2026',
    hour: '19:00',
    location: 'Teatro Demetrio Aguilera Malta · Casa de la Cultura, Quito',
    price: '18',
    taxNote: '',
    theme: 'paper',
    image: 'https://cdn.buenplan.com.ec/pictures/e5b3de59-695f-4be5-bd2a-8d7b57c9bfb2.jpeg',
    url: 'https://www.buenplan.com.ec/event/jondo-2026',
  },
  {
    id: 'one-shot',
    title: 'ONE SHOT TOUR',
    subtitle: 'Leeroy · Féfé · Bubaseta',
    organizer: 'STAR PRODUCCIONES',
    category: 'HIP-HOP / CONCIERTO',
    dateLabel: 'SÁB 27 FEB 2027',
    day: '27',
    month: 'FEB',
    year: '2027',
    hour: '20:00',
    location: 'Centro de Exposiciones Quito',
    price: '30',
    taxNote: '',
    theme: 'neon',
    image: 'https://cdn.buenplan.com.ec/pictures/331e0c4d-d959-4da1-b6c6-07273e750bbe.jpeg',
    url: 'https://www.buenplan.com.ec/event/one-shot-2027-quito',
  },
  {
    id: 'kaseo',
    title: 'KASE.O',
    subtitle: 'Camisa de Fuerza · Quito 2027',
    organizer: 'G3 + HYBE',
    category: 'RAP / CONCIERTO',
    dateLabel: 'SÁB 15 MAY 2027',
    day: '15',
    month: 'MAY',
    year: '2027',
    hour: '18:00',
    location: 'Coliseo General Rumiñahui · Quito',
    price: '40',
    taxNote: '+ IVA (según localidad)',
    theme: 'holo',
    image: 'https://cdn.buenplan.com.ec/pictures/1a570916-01f3-4606-b542-de6d37a6e63f.png',
    url: 'https://www.buenplan.com.ec/event/kaseo-2027-quito',
  },
];

function EventTicket({ event, index }) {
  return (
    <article className={`billboard__ticket billboard__ticket--${event.theme}`} style={{ '--ticket-index': index }}>
      <div className="billboard__ticket-core">
        <div className="billboard__art">
          <img
            src={event.image}
            alt={`Afiche oficial de ${event.title}: ${event.subtitle}`}
            loading="lazy"
            referrerPolicy="no-referrer"
          />
          <span className="billboard__art-mark">C24 / AGENDA</span>
        </div>

        <div className="billboard__details">
          <div className="billboard__eyebrow">
            <span>{event.category}</span>
            <span className="billboard__ticket-number">EVENTO 0{index + 1}</span>
          </div>

          <h3>{event.title}</h3>
          <p className="billboard__subtitle">{event.subtitle}</p>
          <p className="billboard__organizer">PRODUCE / {event.organizer}</p>

          <div className="billboard__facts">
            <div>
              <span>FECHA</span>
              <strong>{event.dateLabel}</strong>
            </div>
            <div>
              <span>HORA</span>
              <strong>{event.hour}</strong>
            </div>
          </div>
          <div className="billboard__venue">
            <Icon name="pin" className="icon" />
            <span>{event.location}</span>
          </div>

          <div className="billboard__purchase">
            <div className="billboard__price">
              <small>ENTRADAS DESDE</small>
              <strong><span>$</span>{event.price}<span>.00</span></strong>
              {event.taxNote ? <small>{event.taxNote}</small> : null}
            </div>
            <a
              href={event.url}
              className="billboard__purchase-link"
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Consultar y comprar entradas para ${event.title} en BuenPlan`}
            >
              VER ENTRADAS
              <Icon name="arrow-up-right" className="icon" />
            </a>
          </div>
        </div>
      </div>

      <div className="billboard__stub" aria-hidden="true">
        <span className="billboard__stub-side">CANAL 24 · CARTELERA</span>
        <span className="billboard__stub-date">
          <strong>{event.day}</strong>
          <span>{event.month} / {event.year}</span>
        </span>
        <span className="billboard__stub-label">PROMOCIONAL<br />NO VÁLIDO PARA INGRESO</span>
        <span className="billboard__stub-cut">✂</span>
      </div>
    </article>
  );
}

export function EventBillboard({ onClose }) {
  const headingRef = useRef(null);

  useEffect(() => {
    // El foco solo se desplaza al abrir una sección solicitada por el usuario.
    headingRef.current?.focus({ preventScroll: true });
  }, []);

  return (
    <section className="billboard" id="cartelera" aria-labelledby="billboard-title">
      <header className="billboard__header">
        <div className="billboard__heading">
          <span className="billboard__prefix">CANAL 24 / EDICIÓN 001 · QUITO</span>
          <h2 ref={headingRef} tabIndex={-1} id="billboard-title">CARTE<span>LE</span>RA</h2>
          <p>LA MÚSICA NO TERMINA EN LA RADIO. NOS VEMOS EN VIVO.</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="billboard__close"
          aria-label="Cerrar cartelera y volver al reproductor"
        >
          <Icon name="x" className="icon" />
          CERRAR
        </button>
      </header>

      <div className="billboard__intro">
        <span>CONCIERTOS / CULTURA / ESCENARIO</span>
        <span>03 EVENTOS SELECCIONADOS</span>
      </div>

      <div className="billboard__grid">
        {EVENTS.map((event, index) => (
          <EventTicket key={event.id} event={event} index={index} />
        ))}
      </div>
      <footer className="billboard__foot">
        <span>CARTELES DE PROMOCIÓN · NO SON ENTRADAS EMITIDAS</span>
        <span>ARTE Y COMPRA: BUENPLAN · FECHAS Y PRECIOS SUJETOS A ACTUALIZACIÓN POR EL ORGANIZADOR</span>
      </footer>
    </section>
  );
}
