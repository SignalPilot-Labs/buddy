"use client";

import { useEffect } from "react";
import { useTranslation } from "@/hooks/useTranslation";

export function HtmlLangSetter(): null {
  const { locale } = useTranslation();

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  return null;
}
