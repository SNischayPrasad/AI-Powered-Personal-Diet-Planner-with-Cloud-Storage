// Display formatting helpers. All numbers use the same grouping so the UI, the API's text
// exports and the README screenshots agree ("2,060 kcal").

const numberFormat = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export function formatNumber(value) {
  return numberFormat.format(Math.round(Number(value) || 0));
}

export function formatKcal(value, { unit = true } = {}) {
  const number = formatNumber(value);
  return unit ? `${number} kcal` : number;
}

export function formatGrams(value) {
  return `${formatNumber(value)} g`;
}

export function formatPercent(ratio) {
  return `${Math.round((Number(ratio) || 0) * 100)}%`;
}

export function formatBytes(bytes) {
  const value = Number(bytes) || 0;
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

// `timeZone` defaults to the viewer's own zone; tests pass an explicit one.
export function formatDate(iso, { timeZone } = {}) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone,
  }).format(new Date(iso));
}

export function formatDateTime(iso, { timeZone } = {}) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone,
  }).format(new Date(iso));
}
