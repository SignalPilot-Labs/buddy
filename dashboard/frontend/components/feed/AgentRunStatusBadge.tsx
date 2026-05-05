"use client";

import type { ReactElement } from "react";
import { clsx } from "clsx";
import {
  CheckmarkIcon,
  CrossIcon,
  WarningTriangleIcon,
  PauseIcon,
} from "@/components/ui/StatusIcons";

export interface AgentRunStatusBadgeProps {
  isPending: boolean;
  isPaused: boolean;
  isIdle: boolean;
  isThinking: boolean;
  isCompleted: boolean;
  isFailed: boolean;
  idleSec: number;
  phaseColor: string;
}

export interface IdleWarningBannerProps {
  idleSec: number;
}

export function AgentRunStatusBadge({
  isPending,
  isPaused,
  isIdle,
  isThinking,
  isCompleted,
  isFailed,
  phaseColor,
}: AgentRunStatusBadgeProps): ReactElement | null {
  if (isPending && !isIdle) {
    return (
      <span
        className={clsx(
          "flex items-center gap-1.5 text-content font-semibold",
          isThinking ? "text-[#cc88ff]" : "text-[#ffaa00]"
        )}
      >
        <span className="relative flex h-1.5 w-1.5">
          <span
            className={clsx(
              "absolute inline-flex h-full w-full rounded-full animate-ping opacity-50",
              isThinking ? "bg-[#cc88ff]" : "bg-[#ffaa00]"
            )}
          />
          <span
            className={clsx(
              "relative inline-flex h-1.5 w-1.5 rounded-full",
              isThinking ? "bg-[#cc88ff]" : "bg-[#ffaa00]"
            )}
            style={{
              boxShadow: isThinking
                ? "0 0 4px rgba(204, 136, 255, 0.5)"
                : "0 0 4px rgba(255, 170, 0, 0.5)",
            }}
          />
        </span>
        {isThinking ? "thinking" : "running"}
      </span>
    );
  }

  if (isIdle) {
    return (
      <span className="flex items-center gap-1.5 text-content font-semibold text-[#ff4444]">
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full rounded-full bg-[#ff4444] animate-ping opacity-50" />
          <span
            className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[#ff4444]"
            style={{ boxShadow: "0 0 4px rgba(255, 68, 68, 0.5)" }}
          />
        </span>
        stuck
      </span>
    );
  }

  if (isPaused) {
    return (
      <span className="flex items-center gap-1 text-content font-semibold" style={{ color: "rgba(255, 170, 0, 0.7)" }}>
        <PauseIcon color="rgba(255, 170, 0, 0.7)" />
        paused
      </span>
    );
  }

  if (isCompleted) {
    return (
      <span className="flex items-center gap-1 text-content font-semibold" style={{ color: phaseColor }}>
        <CheckmarkIcon color={phaseColor} />
        done
      </span>
    );
  }

  if (isFailed) {
    return (
      <span className="flex items-center gap-1 text-content font-semibold text-[#ff4444]">
        <CrossIcon color="#ff4444" />
        failed
      </span>
    );
  }

  return null;
}

export function IdleWarningBanner({ idleSec }: IdleWarningBannerProps): ReactElement {
  return (
    <div className="border-t border-[#ff4444]/20 bg-[#ff4444]/[0.06] px-4 py-2">
      <div className="flex items-center gap-2.5">
        <WarningTriangleIcon color="#ff4444" />
        <span className="text-content text-[#ff4444]">
          Agent idle for{" "}
          <span className="font-semibold tabular-nums">
            {idleSec >= 60
              ? `${Math.floor(idleSec / 60)}m ${idleSec % 60}s`
              : `${idleSec}s`}
          </span>{" "}
          &mdash; auto-recovery at 10m
        </span>
      </div>
    </div>
  );
}
