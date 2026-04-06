import type { en } from "@/lib/i18n/en";

export type Locale = "en" | "bn";

type Stringify<T> = T extends string
  ? string
  : { [K in keyof T]: Stringify<T[K]> };

export type LocaleDict = Stringify<typeof en>;

export const LOCALE_STORAGE_KEY = "autofyn_locale";
