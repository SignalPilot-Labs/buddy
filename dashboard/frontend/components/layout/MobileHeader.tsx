"use client";

import Link from "next/link";
import type { RunStatus, Run } from "@/lib/types";
import type { LocaleDict } from "@/lib/i18n/types";
import { LogoMark } from "@/components/ui/LogoMark";
import { StatusBadge } from "@/components/ui/Badge";
import { MobileAccessPopover } from "@/components/ui/MobileAccessPopover";
import { LocaleToggle } from "@/components/ui/LocaleToggle";

interface MobileHeaderProps {
  runStatus: RunStatus | null;
  agentReachable: boolean;
  agentIdle: boolean;
  selectedRun: Run | null;
  t: LocaleDict;
}

export function MobileHeader({
  runStatus,
  agentReachable,
  agentIdle,
  selectedRun,
  t,
}: MobileHeaderProps): React.ReactElement {
  const healthDotClass = agentReachable
    ? agentIdle
      ? "bg-[#00ff88]/60"
      : "bg-[#00ff88]"
    : "bg-[#ff4444]/60";
  const healthDotStyle: React.CSSProperties | undefined =
    !agentIdle && agentReachable
      ? { boxShadow: "0 0 4px rgba(0,255,136,0.3)" }
      : undefined;

  return (
    <header className="mobile-top-bar items-center gap-2 px-3 py-2 border-b border-[#1a1a1a] bg-[#0a0a0a] header-glow safe-area-top">
      <LogoMark runStatus={runStatus} />

      <div>
        <h1 className="text-[12px] font-bold text-[#e8e8e8] tracking-tight">
          AutoFyn
        </h1>
        <p className="text-[8px] text-[#777] tracking-[0.1em] uppercase -mt-0.5">
          {t.monitor}
        </p>
      </div>

      <div className="flex-1" />

      <span
        className={`h-2 w-2 rounded-full ${healthDotClass}`}
        style={healthDotStyle}
      />

      <MobileAccessPopover />

      {selectedRun && (
        <StatusBadge status={selectedRun.status as RunStatus} size="md" />
      )}

      <LocaleToggle />

      <Link
        href="/settings"
        className="p-2 rounded hover:bg-white/[0.04] text-[#888] hover:text-[#ccc] transition-colors"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      </Link>
    </header>
  );
}
