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
    id: 'karol-g',
    title: 'KAROL G',
    subtitle: 'Viajando Por El Mundo · Tropitour',
    organizer: 'OUTPUT',
    category: 'REGUETÓN / POP URBANO',
    dateLabel: '15, 16 Y 17 ENE 2027',
    day: '15–17',
    month: 'ENE',
    year: '2027',
    hour: '20:00',
    location: 'Estadio Olímpico Atahualpa · Quito',
    price: null,
    status: 'soldout',
    statusNote: 'TRES FECHAS AGOTADAS',
    theme: 'holo',
    image: 'https://assets.lahora.com.ec/__export/1777518347845/sites/lahora/img/2026/04/29/whatsapp_image_2026-04-29_at_10_03_04_pm.jpeg_172237755.jpeg',
    imageCredit: 'Afiche de gira publicado por La Hora · Output',
    url: 'https://www.ticketshow.com.ec/evento/KAROL-G-QUITO-2027',
    ticketPlatform: 'TicketShow',
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
    id: 'santa-grifa',
    title: 'LA SANTA GRIFA',
    subtitle: 'Provenca Hip Hop 2027',
    organizer: 'PROVENCA PRODUCCIONES',
    category: 'RAP MEXICANO / HIP-HOP',
    dateLabel: 'SÁB 03 ABR 2027',
    day: '03',
    month: 'ABR',
    year: '2027',
    hour: '18:30',
    location: 'Centro de Exposiciones Quito · Pabellón Simón Bolívar',
    price: '20',
    taxNote: '+ $3 IVA en preventa general',
    theme: 'neon',
    image: 'https://www.jambase.com/wp-content/uploads/2024/08/la-santa-grifa-1480x832.png',
    imageCredit: 'Fotografía promocional del artista · JamBase (no es el afiche del evento)',
    url: 'https://www.buenplan.com.ec/event/provenca-hip-hop-2027',
    ticketPlatform: 'BuenPlan',
  },
  {
    id: 'jay-wheeler',
    title: 'JAY WHEELER',
    subtitle: 'La Voz Favorita World Tour',
    organizer: 'OUTPUT',
    category: 'REGUETÓN / URBANO',
    dateLabel: 'JUE 29 ABR 2027',
    day: '29',
    month: 'ABR',
    year: '2027',
    hour: 'HORA EN BOLETERÍA',
    location: 'Coliseo General Rumiñahui · Quito',
    price: '40',
    taxNote: '+ IVA y cargos de servicio',
    theme: 'holo',
    image: 'https://confirmado.net/wp-content/uploads/2026/10/jay_wheeler1.png',
    imageCredit: 'Imagen de campaña de La Voz Favorita difundida por Output',
    url: 'https://www.ticketshow.com.ec/evento/JAY-WHEELER-QUITO-2027',
    ticketPlatform: 'TicketShow',
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
  },  {
    id: 'nsqk',
    title: 'NSQK',
    subtitle: 'Mosca World Tour · Quito',
    organizer: 'CAÑA PRODUCCIONES + CROSSOVER',
    category: 'HIP-HOP / POP ALTERNATIVO',
    dateLabel: 'VIE 13 AGO 2027',
    day: '13',
    month: 'AGO',
    year: '2027',
    hour: '20:00',
    location: 'Quito · recinto por confirmar',
    venueNote: 'BuenPlan: SoundGarden UIO · sitio de gira: Ágora de la Casa de la Cultura',
    price: '35',
    taxNote: '+ $5,25 IVA (VIP)',
    theme: 'paper',
    image: 'https://yqueplanhoy.com/media/public/events/event-480.webp',
    imageCredit: 'Afiche MOSCA de Quito · Crossover / BuenPlan, difundido por ¿Y Qué Plan Hoy?',
    url: 'https://www.buenplan.com.ec/event/nsqk-2027-quito',
    ticketPlatform: 'BuenPlan',
  },
  {
    id: 'don-omar',
    title: 'DON OMAR',
    subtitle: 'The Last King World Tour',
    organizer: 'JM PRODUCTIONS',
    category: 'REGUETÓN / CLÁSICOS',
    dateLabel: 'SÁB 30 OCT 2027',
    day: '30',
    month: 'OCT',
    year: '2027',
    hour: 'HORA EN WEB OFICIAL',
    location: 'Estadio Olímpico Atahualpa · Quito',
    price: null,
    status: 'soldout',
    statusNote: 'AGOTADO EN PREVENTA · 19 NOV 2026',
    theme: 'neon',
    image: 'https://donomar.com/cdn/shop/files/last-king-world-tour_1200x630.jpg?v=1779215556',
    imageCredit: 'Arte oficial The Last King World Tour · Don Omar',
    url: 'https://donomar.com/pages/preventa',
    ticketPlatform: 'Gira oficial',
  },

];

export const EVENT_COUNT = EVENTS.length;

function EventTicket({ event, index }) {
  return (
    <article className={`billboard__ticket billboard__ticket--${event.theme}`} style={{ '--ticket-index': index }}>
      <div className="billboard__ticket-core">
        <div className="billboard__art">
          <span className="billboard__art-fallback" aria-hidden="true">{event.title}</span>
          <img
            src={event.image}
            alt={event.imageCredit || `Arte del evento ${event.title}: ${event.subtitle}`}
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={(event) => { event.currentTarget.style.display = 'none'; }}
          />
          <span className="billboard__art-mark">C24 / AGENDA</span>
          {event.status === 'soldout' ? (
            <span className="billboard__art-soldout">SOLD OUT</span>
          ) : null}
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
          {event.venueNote ? (
            <p className="billboard__venue-warning">{event.venueNote}</p>
          ) : null}

          <div className="billboard__purchase">
            <div className={`billboard__price${event.status === 'soldout' ? ' billboard__price--soldout' : ''}`}>
              <small>{event.status === 'soldout' ? 'ESTADO DE BOLETERÍA' : 'ENTRADAS DESDE'}</small>
              {event.status === 'soldout' ? (
                <strong>AGOTADO</strong>
              ) : (
                <strong><span>$</span>{event.price}<span>.00</span></strong>
              )}
              {event.statusNote ? <small>{event.statusNote}</small> : null}
              {event.taxNote ? <small>{event.taxNote}</small> : null}
            </div>
            <a
              href={event.url}
              className={`billboard__purchase-link${event.status === 'soldout' ? ' billboard__purchase-link--soldout' : ''}`}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`Ver ${event.status === 'soldout' ? 'información oficial del concierto' : 'disponibilidad y entradas'} de ${event.title} en ${event.ticketPlatform || 'BuenPlan'}`}
            >
              {event.status === 'soldout' ? 'VER ANUNCIO' : 'VER ENTRADAS'}
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
        <span>{String(EVENT_COUNT).padStart(2, '0')} EVENTOS EN AGENDA</span>
      </div>

      <div className="billboard__grid">
        {EVENTS.map((event, index) => (
          <EventTicket key={event.id} event={event} index={index} />
        ))}
      </div>
      <footer className="billboard__foot">
        <span>CARTELES DE PROMOCIÓN · NO SON ENTRADAS EMITIDAS</span>
        <span>ENLACES OFICIALES Y DE PRENSA · FECHAS, RECINTOS Y DISPONIBILIDAD SUJETOS A CONFIRMACIÓN</span>
      </footer>
    </section>
  );
}
