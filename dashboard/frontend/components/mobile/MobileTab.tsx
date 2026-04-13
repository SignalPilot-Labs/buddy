"use client";

import { clsx } from "clsx";

interface MobileTabProps {
  icon: React.ReactNode;
  label: string;
  active: boolean;
  onClick: () => void;
  badge?: number | null;
}

export function MobileTab({ icon, label, active, onClick, badge }: MobileTabProps) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        "mobile-tab-btn flex flex-col items-center justify-center gap-0.5 flex-1 h-full relative transition-colors duration-150",
        active ? "text-[#00ff88]" : "text-text-secondary",
      )}
    >
      {/* Active indicator bar */}
      {active && (
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-6 h-[2px] bg-[#00ff88] rounded-b" />
      )}

      <div className="relative">
        {icon}
        {badge != null && badge > 0 && (
          <span
            className="absolute -top-1.5 -right-2.5 min-w-[16px] h-[16px] leading-none flex items-center justify-center rounded-full bg-[#00ff88]/20 text-[#00ff88] text-caption font-bold px-0.5"
            aria-label={`${badge > 99 ? "99+" : badge} new items`}
          >
            {badge > 99 ? "99+" : badge}
          </span>
        )}
      </div>

      <span className="text-content font-medium">{label}</span>
    </button>
  );
}
