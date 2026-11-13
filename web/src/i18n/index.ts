import { en } from './en';
import { id, type Messages } from './id';

export type Lang = 'id' | 'en';
export type MessageKey = keyof Messages;

const dictionaries: Record<Lang, Messages> = { id, en };

const defaultLang: Lang = import.meta.env.VITE_DEFAULT_LANG === 'en' ? 'en' : 'id';

/** Minimal translator; a language switcher arrives with T-40. */
export function useT(lang: Lang = defaultLang) {
  const dict = dictionaries[lang];
  return (key: MessageKey) => dict[key];
}
