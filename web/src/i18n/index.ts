import { messages } from './en';

export type MessageKey = keyof typeof messages;

/** Locale used for date and number formatting (the interface is English-only). */
export const LOCALE = 'en-GB';

export function translate(key: MessageKey, vars?: Record<string, string | number>): string {
  let text: string = messages[key];
  for (const [k, v] of Object.entries(vars ?? {})) text = text.replaceAll(`{${k}}`, String(v));
  return text;
}

/** Translator for components; `lang` is the formatting locale. */
export function useT() {
  return { lang: LOCALE, t: translate };
}
