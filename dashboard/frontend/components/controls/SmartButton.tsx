"use client";

import { Button } from "@/components/ui/Button";
import type { ButtonState, ButtonIcon } from "@/lib/commandState";

function ButtonIconSvg({ icon }: { icon: ButtonIcon }): React.ReactElement {
  if (icon === "pause") {
    return (
      <svg width="12" height="12" viewBox="0 0 10 10" fill="currentColor">
        <rect x="2" y="2" width="2" height="6" rx="0.5" />
        <rect x="6" y="2" width="2" height="6" rx="0.5" />
      </svg>
    );
  }
  // "send"
  return (
    <svg width="12" height="12" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M1 9L5 5 1 1" />
      <path d="M5 9L9 5 5 1" />
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
    <Button
      variant={state.variant}
      size="pill"
      disabled={state.disabled}
      onClick={onClick}
      className={`font-semibold transition-all duration-150 ${className ?? ""}`}
      icon={<ButtonIconSvg icon={state.icon} />}
    >
      {state.label}
    </Button>
  );
}
