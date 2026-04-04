"use client";

import type { RunStatus } from "@/lib/types";
import { Button } from "@/components/ui/Button";

interface ControlBarProps {
  status: RunStatus | null;
  onPause: () => void;
  onOpenInject: () => void;
  busy: boolean;
}

export function ControlBar({ status, onPause, onOpenInject, busy }: ControlBarProps) {
  if (status === null) return null;

  if (status === "running") {
    return (
      <Button
        variant="warning"
        disabled={busy}
        onClick={onPause}
        icon={
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="2" y="2" width="2" height="6" rx="0.5" />
            <rect x="6" y="2" width="2" height="6" rx="0.5" />
          </svg>
        }
      >
        Pause
      </Button>
    );
  }

  return (
    <Button
      variant="success"
      disabled={busy}
      onClick={onOpenInject}
      icon={
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
          <polygon points="3 2 8 5 3 8" />
        </svg>
      }
    >
      Resume
    </Button>
  );
}
