// Small inline stroke icons (24×24). Inline SVG keeps the bundle free of icon libraries and
// lets icons inherit the surrounding text colour.
const PATHS = {
  menu: ["M4 7h16", "M4 12h16", "M4 17h16"],
  x: ["M6 6l12 12", "M18 6L6 18"],
  plus: ["M12 5v14", "M5 12h14"],
  arrowRight: ["M5 12h14", "M13 6l6 6-6 6"],
  check: ["M5 12.5l4.5 4.5L19 7.5"],
  alert: ["M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z", "M12 7.5v6", "M12 16.5v.5"],
  info: ["M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18z", "M12 11v5.5", "M12 7.5v.5"],
  download: ["M12 4v11", "M7 10l5 5 5-5", "M5 20h14"],
  upload: ["M12 20V9", "M7 14l5-5 5 5", "M5 4h14"],
  trash: ["M4 7h16", "M9 7V4h6v3", "M6 7l1 13h10l1-13", "M10 11v6", "M14 11v6"],
  file: ["M7 3h7l5 5v13H7z", "M14 3v5h5"],
  image: ["M4 5h16v14H4z", "M4 17l5-5 4 4 2.5-2.5L20 18", "M15.5 7.5a1.5 1.5 0 1 1 0 3a1.5 1.5 0 1 1 0-3z"],
  logout: ["M10 5H5v14h5", "M14 8l4 4-4 4", "M18 12H9"],
  user: ["M12 4a4 4 0 1 1 0 8a4 4 0 1 1 0-8z", "M4 20c1.5-4 4.5-6 8-6s6.5 2 8 6"],
  list: ["M9 6h11", "M9 12h11", "M9 18h11", "M4.5 6h.01", "M4.5 12h.01", "M4.5 18h.01"],
  sparkle: ["M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"],
  cloud: ["M7 18h10a4 4 0 0 0 .5-8A6 6 0 0 0 6 9.5 4.3 4.3 0 0 0 7 18z"],
  database: [
    "M5 6c0-1.7 3.1-3 7-3s7 1.3 7 3-3.1 3-7 3-7-1.3-7-3z",
    "M5 6v12c0 1.7 3.1 3 7 3s7-1.3 7-3V6",
    "M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3",
  ],
  bucket: ["M4 6h16l-2 14H6z", "M4 6c0-1.1 3.6-2 8-2s8 .9 8 2"],
  printer: ["M7 9V4h10v5", "M7 17H4v-7h16v7h-3", "M7 14h10v6H7z"],
  drop: ["M12 3c3.5 4.2 6 7.6 6 10.5A6 6 0 0 1 6 13.5C6 10.6 8.5 7.2 12 3z"],
  refresh: ["M20 11a8 8 0 1 0-2.3 5.7", "M20 5v6h-6"],
  server: ["M4 4h16v7H4z", "M4 13h16v7H4z", "M8 7.5h.01", "M8 16.5h.01"],
  browser: ["M3 5h18v14H3z", "M3 9h18", "M6 7h.01", "M8.5 7h.01"],
};

export default function Icon({ name, size = 20, className = "", title }) {
  const paths = PATHS[name] ?? [];
  return (
    <svg
      className={`icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={title ? undefined : true}
      role={title ? "img" : undefined}
      focusable="false"
    >
      {title && <title>{title}</title>}
      {paths.map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}
