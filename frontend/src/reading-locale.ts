import { locale } from './locale';

/** UI copy only. Collected article content is deliberately never translated here. */
export function tx(zh: string, en: string) { return locale.value === 'en' ? en : zh; }
