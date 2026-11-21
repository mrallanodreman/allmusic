import { useState } from 'react';
import { Icon } from './Icons.jsx';
import { isSafeRequestText } from '../lib/safe.js';

const MAX = 120;

export function RequestBar({ pending, notice, onSubmit, disabled }) {
  const [value, setValue] = useState('');
  const valid = isSafeRequestText(value, MAX);
  const blocked = pending || disabled;

  function handleSubmit(event) {
    event.preventDefault();
    if (!valid || blocked) return;
    onSubmit(value);
    setValue('');
  }

  return (
    <section className="request panel" aria-labelledby="request-title">
      <img
        className="request__tape"
        src={`${import.meta.env.BASE_URL}assets/radio-ui/tape_request_line.png`}
        alt=""
        aria-hidden="true"
      />
      <h2 className="sr-only" id="request-title">Pedir una canción o un mood</h2>
      <form className="request__form" onSubmit={handleSubmit}>
        <label className="sr-only" htmlFor="request-input">Pedí una canción o un mood</label>
        <input
          id="request-input"
          className="request__input"
          type="text"
          inputMode="text"
          autoComplete="off"
          maxLength={MAX}
          placeholder="PIDE UNA CANCIÓN O UN MOOD..."
          value={value}
          onChange={(event) => setValue(event.target.value)}
          disabled={blocked}
          aria-describedby="request-help"
        />
        <button className="request__button" type="submit" disabled={!valid || blocked}>
          <Icon name="mic" className="icon" />
          <span>{pending ? 'ENVIANDO…' : 'PEDIR'}</span>
        </button>
      </form>
      <p className="request__help" id="request-help" aria-live="polite">
        {notice || `${value.length}/${MAX} · El pedido se envía a la cola real de la radio.`}
      </p>
    </section>
  );
}
