"use client";

import { useRef } from "react";
import { clsx } from "clsx";
import { MODELS, MODEL_IDS, saveStoredModel } from "@/lib/constants";
import type { ModelId } from "@/lib/constants";

export interface ModelSelectorProps {
  value: ModelId;
  onChange: (id: ModelId) => void;
}

export function ModelSelector({ value, onChange }: ModelSelectorProps): React.ReactElement {
  const buttonsRef = useRef<Array<HTMLButtonElement | null>>([]);

  const selectById = (id: ModelId): void => {
    onChange(id);
    saveStoredModel(id);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>, idx: number): void => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft" && e.key !== "Home" && e.key !== "End") return;
    e.preventDefault();
    const last = MODEL_IDS.length - 1;
    let next = idx;
    if (e.key === "ArrowRight") next = idx === last ? 0 : idx + 1;
    else if (e.key === "ArrowLeft") next = idx === 0 ? last : idx - 1;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = last;
    selectById(MODEL_IDS[next]);
    buttonsRef.current[next]?.focus();
  };

  return (
    <div role="radiogroup" aria-label="Model" className="grid grid-cols-3 gap-2">
      {MODEL_IDS.map((id, idx) => {
        const spec = MODELS[id];
        const selected = value === id;
        return (
          <button
            key={id}
            ref={(el) => { buttonsRef.current[idx] = el; }}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => selectById(id)}
            onKeyDown={(e) => handleKeyDown(e, idx)}
            className={clsx(
              "text-left p-3 rounded border transition-all focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#00ff88]/60",
              selected
                ? "border-[#00ff88]/30 bg-[#00ff88]/[0.04]"
                : "border-border bg-white/[0.01] hover:bg-white/[0.03]"
            )}
          >
            <div
              className={clsx(
                "text-[10px] font-medium leading-tight",
                selected ? "text-text" : "text-accent-hover"
              )}
            >
              {spec.label}
            </div>
            <div className="text-[10px] text-text-muted mt-0.5 leading-tight">
              {spec.description}
            </div>
            <div
              className={clsx(
                "text-[10px] mt-1.5 font-mono",
                selected ? "text-[#00ff88]/70" : "text-text-dim"
              )}
            >
              {spec.context}
            </div>
          </button>
        );
      })}
    </div>
  );
}
