"use client";

import Image from "next/image";
import Link from "next/link";
import { clsx } from "clsx";
import { useTranslation } from "@/hooks/useTranslation";
import { LocaleToggle } from "@/components/ui/LocaleToggle";
import type { SettingsStatus } from "@/lib/types";

interface SettingsHeaderProps {
  status: SettingsStatus | null;
}

export function SettingsHeader({ status }: SettingsHeaderProps): React.ReactElement {
  const { t } = useTranslation();

  return (
    <div className="border-b border-[#1a1a1a]">
      <div className="max-w-2xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-2 text-[#999] hover:text-[#888] transition-colors"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
              <polyline points="8 2 4 6 8 10" />
            </svg>
            <span className="text-[10px]">{t.settings.dashboard}</span>
          </Link>
          <span className="text-[#1a1a1a]">/</span>
          <div className="flex items-center gap-2">
            <div className="flex items-center justify-center h-6 w-6 rounded bg-white/[0.04] border border-white/[0.08]">
              <Image src="/logo.svg" alt="AutoFyn" width={14} height={14} />
            </div>
            <h1 className="text-[12px] font-semibold">{t.settings.title}</h1>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <LocaleToggle />
          {status && (
            <div
              className={clsx(
                "flex items-center gap-1.5 px-2 py-1 rounded text-[9px] font-medium",
                status.configured
                  ? "bg-[#00ff88]/[0.06] text-[#00ff88]"
                  : "bg-[#ffaa00]/[0.06] text-[#ffaa00]"
              )}
            >
              <div
                className={clsx(
                  "w-1.5 h-1.5 rounded-full",
                  status.configured ? "bg-[#00ff88]" : "bg-[#ffaa00]"
                )}
              />
              {status.configured ? t.settings.configured : t.settings.setupRequired}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
