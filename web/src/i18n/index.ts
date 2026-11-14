import { en } from './en';
import { id, type Messages } from './id';

export type Lang = 'id' | 'en';
export type MessageKey = keyof Messages;

export const dictionaries: Record<Lang, Messages> = { id, en };

export const defaultLang: Lang = import.meta.env.VITE_DEFAULT_LANG === 'en' ? 'en' : 'id';

export function translate(lang: Lang, key: MessageKey, vars?: Record<string, string | number>) {
  let text: string = dictionaries[lang][key] ?? dictionaries.id[key] ?? key;
  for (const [k, v] of Object.entries(vars ?? {})) text = text.replaceAll(`{${k}}`, String(v));
  return text;
}

/** Translator bound to the current language (language switcher arrives with T-40). */
export function useT() {
  const lang = defaultLang;
  return {
    lang,
    t: (key: MessageKey, vars?: Record<string, string | number>) => translate(lang, key, vars),
  };
}
