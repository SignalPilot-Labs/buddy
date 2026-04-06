"use client";

import { useSyncExternalStore } from "react";
import { en } from "@/lib/i18n/en";
import { bn } from "@/lib/i18n/bn";
import { LOCALE_STORAGE_KEY } from "@/lib/i18n/types";
import type { Locale, LocaleDict } from "@/lib/i18n/types";

const locales: Record<Locale, LocaleDict> = { en, bn };
const listeners = new Set<() => void>();

let currentLocale: Locale = "en";

if (typeof window !== "undefined") {
  const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
  if (stored === "bn") currentLocale = "bn";
}

function subscribe(callback: () => void): () => void {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

function getSnapshot(): Locale {
  return currentLocale;
}

function getServerSnapshot(): Locale {
  return "en";
}

function setLocale(locale: Locale): void {
  currentLocale = locale;
  localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  listeners.forEach((cb) => cb());
}

export function useTranslation(): {
  t: LocaleDict;
  locale: Locale;
  setLocale: (l: Locale) => void;
} {
  const locale = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
  return { t: locales[locale], locale, setLocale };
}
