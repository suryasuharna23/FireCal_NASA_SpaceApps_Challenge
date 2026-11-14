export function monthNames(lang: string, style: 'short' | 'long' | 'narrow' = 'short') {
  const fmt = new Intl.DateTimeFormat(lang === 'en' ? 'en-GB' : 'id-ID', {
    month: style,
    timeZone: 'UTC',
  });
  return Array.from({ length: 12 }, (_, i) => fmt.format(new Date(Date.UTC(2000, i, 1))));
}
