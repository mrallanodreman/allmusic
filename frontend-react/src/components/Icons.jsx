export function Icon({ name, className = '' }) {
  const paths = {
    play: <path d="M8 5v14l11-7z" />,
    pause: <path d="M6 5h4v14H6zM14 5h4v14h-4z" />,
    bolt: <path d="M13 2 4 14h7l-1 8 9-12h-7z" />,
    search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m15.4 15.4 5.1 5.1" /></>,
    radio: <path d="M12 3a9 9 0 0 0-9 9 9 9 0 0 0 9 9 9 9 0 0 0 9-9 9 9 0 0 0-9-9Zm0 5a4 4 0 0 1 4 4 4 4 0 0 1-4 4 4 4 0 0 1-4-4 4 4 0 0 1 4-4Zm-7 4a7 7 0 0 1 3-5.8M19 12a7 7 0 0 1-3 5.8" />,
    list: <path d="M4 6h16M4 12h16M4 18h10" />,
    clock: <path d="M12 7v5l4 2M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z" />,
    star: <path d="m12 3 2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.8 6.2 20.9l1.1-6.5L2.6 9.8l6.5-.9z" />,
    mic: <path d="M12 15a4 4 0 0 0 4-4V6a4 4 0 0 0-8 0v5a4 4 0 0 0 4 4Zm7-4a7 7 0 0 1-6 6.9V21h-2v-3.1A7 7 0 0 1 5 11" />,
    skip: <path d="M5 5v14l9-7zm10 0h4v14h-4z" />,
    volume: <path d="M11 5 6 9H2v6h4l5 4zM15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13" />,
    mute: <path d="M11 5 6 9H2v6h4l5 4zM22 9l-6 6m0-6 6 6" />,
  };
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      {paths[name] || paths.radio}
    </svg>
  );
}
