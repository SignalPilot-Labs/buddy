"use client";

import { clsx } from "clsx";
import { MODELS, resolveModelId } from "@/lib/constants";

interface ModelBadgeProps {
  /** Raw model_name from the Run (e.g. "claude-opus-4-6-..."). */
  modelName: string | null | undefined;
  /** Show a small model-icon to the left of the label. */
  showIcon?: boolean;
  className?: string;
}

/**
 * Badge that shows the short model name with its color, derived from a single
 * MODELS record. Returns null if the model cannot be resolved so callers do not
 * need to null-check twice (id + label).
 */
export function ModelBadge({ modelName, showIcon = false, className }: ModelBadgeProps): React.ReactElement | null {
  const id = resolveModelId(modelName);
  if (!id) return null;
  const spec = MODELS[id];
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded text-caption font-medium leading-tight",
        showIcon ? "gap-1 px-1.5 py-0" : "px-1 py-0",
        spec.color,
        className,
      )}
      aria-label={`Model: ${spec.badge}`}
    >
      {showIcon && (
        <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="currentColor" strokeWidth="1.2" aria-hidden="true">
          <circle cx="4" cy="4" r="3" />
          <path d="M2.5 4h3M4 2.5v3" />
        </svg>
      )}
      {spec.badge}
    </span>
  );
}
