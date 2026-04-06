"use client";

import { clsx } from "clsx";
import type { RunStatus } from "@/lib/types";
import { STATUS_META } from "@/lib/types";
import { useTranslation } from "@/hooks/useTranslation";
import type { LocaleDict } from "@/lib/i18n/types";

const STATUS_LABEL_KEYS: Record<RunStatus, keyof LocaleDict["statusLabels"]> = {
  running: "running",
  paused: "paused",
  stopped: "stopped",
  completed: "completed",
  completed_no_changes: "completedNoChanges",
  error: "error",
  crashed: "crashed",
  killed: "killed",
  rate_limited: "rateLimited",
};

export function StatusBadge({
  status,
  size = "sm",
}: {
  status: RunStatus;
  size?: "sm" | "md";
}) {
  const { t } = useTranslation();
  const meta = STATUS_META[status] || STATUS_META.error;
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded font-medium tracking-wider uppercase",
        meta.bg,
        meta.color,
        size === "sm" ? "px-1.5 py-0.5 text-[9px]" : "px-2.5 py-1 text-[10px]"
      )}
    >
      {meta.pulse && (
        <span className="relative flex h-1.5 w-1.5">
          <span
            className={clsx(
              "absolute inline-flex h-full w-full animate-ping rounded-full opacity-75",
              meta.dot
            )}
          />
          <span
            className={clsx(
              "relative inline-flex h-1.5 w-1.5 rounded-full",
              meta.dot
            )}
          />
        </span>
      )}
      {!meta.pulse && (
        <span className={clsx("h-1.5 w-1.5 rounded-full", meta.dot)} />
      )}
      {t.statusLabels[STATUS_LABEL_KEYS[status]]}
    </span>
  );
}
