"use client";

import { Button } from "@/components/ui/Button";
import type { RunStatus } from "@/lib/types";

export interface RunControlsProps {
  runId: string | null;
  status: RunStatus | null;
  busy: boolean;
  onCancel: (runId: string) => void;
}

/**
 * Renders run action controls that are status-dependent.
 * Currently handles the cancel button shown during sandbox creation
 * (status === "starting").
 */
export function RunControls({ runId, status, busy, onCancel }: RunControlsProps): React.ReactElement | null {
  if (status !== "starting" || !runId) {
    return null;
  }

  return (
    <Button
      variant="warning"
      size="sm"
      disabled={busy}
      onClick={() => onCancel(runId)}
      title="Cancel sandbox creation"
      icon={
        <svg
          width="10"
          height="10"
          viewBox="0 0 10 10"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <line x1="2" y1="2" x2="8" y2="8" />
          <line x1="8" y1="2" x2="2" y2="8" />
        </svg>
      }
    >
      Cancel
    </Button>
  );
}
