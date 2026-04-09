"use client";

import type { ButtonState, ButtonIcon } from "@/lib/commandState";

function ButtonIconSvg({ icon }: { icon: ButtonIcon }): React.ReactElement {
  if (icon === "pause") {
    return (
      <svg width="14" height="14" viewBox="0 0 14 14" fill="currentColor">
        <rect x="3" y="2" width="3" height="10" rx="1" />
        <rect x="8" y="2" width="3" height="10" rx="1" />
      </svg>
    );
  }
  // "send" — arrow up
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 12V3" />
      <path d="M3 7l4-4 4 4" />
    </svg>
  );
}

interface SmartButtonProps {
  state: ButtonState;
  onClick: () => void;
  className?: string;
}

export function SmartButton({ state, onClick, className }: SmartButtonProps): React.ReactElement {
  return (
    <button
      type="button"
      disabled={state.disabled}
      onClick={onClick}
      className={`h-9 w-9 flex items-center justify-center rounded-lg border transition-all duration-150 disabled:opacity-30 disabled:cursor-not-allowed focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 ${
        state.icon === "pause"
          ? "text-[#ffcc44] border-[#ffcc44]/20 hover:bg-[#ffcc44]/10 focus-visible:outline-[#ffcc44]/50"
          : "text-[#00ff88] border-[#00ff88]/20 hover:bg-[#00ff88]/10 focus-visible:outline-[#00ff88]/50"
      } ${className ?? ""}`}
      title={state.label}
    >
      <ButtonIconSvg icon={state.icon} />
    </button>
  );
}
