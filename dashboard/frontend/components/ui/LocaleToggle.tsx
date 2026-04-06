"use client";

import { useTranslation } from "@/hooks/useTranslation";

export function LocaleToggle() {
  const { locale, setLocale, t } = useTranslation();

  const handleToggle = () => {
    setLocale(locale === "en" ? "bn" : "en");
  };

  return (
    <button
      onClick={handleToggle}
      className="flex items-center gap-1 px-2 py-1 rounded text-[9px] font-medium text-[#888] hover:text-[#ccc] hover:bg-white/[0.04] transition-colors border border-transparent hover:border-[#1a1a1a]"
      title={locale === "en" ? t.localeToggle.switchToBengali : t.localeToggle.switchToEnglish}
    >
      <span className={locale === "en" ? "text-[#e8e8e8]" : "text-[#555]"}>EN</span>
      <span className="text-[#333]">|</span>
      <span className={locale === "bn" ? "text-[#e8e8e8]" : "text-[#555]"}>বাং</span>
    </button>
  );
}
