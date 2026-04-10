"use client";

import { useRef } from "react";
import { clsx } from "clsx";
import { MODEL_OPTIONS, LOCALSTORAGE_MODEL_KEY } from "@/lib/constants";
import type { ModelId } from "@/lib/constants";

export interface ModelSelectorProps {
  value: ModelId;
  onChange: (id: ModelId) => void;
}

export function ModelSelector({ value, onChange }: ModelSelectorProps): React.ReactElement {
  const buttonsRef = useRef<Array<HTMLButtonElement | null>>([]);

  const selectById = (id: ModelId): void => {
    onChange(id);
    try {
      localStorage.setItem(LOCALSTORAGE_MODEL_KEY, id);
    } catch {
      // localStorage may be unavailable in some environments
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>, idx: number): void => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft" && e.key !== "Home" && e.key !== "End") return;
    e.preventDefault();
    const last = MODEL_OPTIONS.length - 1;
    let next = idx;
    if (e.key === "ArrowRight") next = idx === last ? 0 : idx + 1;
    else if (e.key === "ArrowLeft") next = idx === 0 ? last : idx - 1;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = last;
    selectById(MODEL_OPTIONS[next].id);
    buttonsRef.current[next]?.focus();
  };

  return (
    <div role="radiogroup" aria-label="Model" className="grid grid-cols-3 gap-2">
      {MODEL_OPTIONS.map((opt, idx) => {
        const selected = value === opt.id;
        return (
          <button
            key={opt.id}
            ref={(el) => { buttonsRef.current[idx] = el; }}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => selectById(opt.id)}
            onKeyDown={(e) => handleKeyDown(e, idx)}
            className={clsx(
              "text-left p-3 rounded border transition-all focus:outline-none focus-visible:ring-1 focus-visible:ring-[#00ff88]/60",
              selected
                ? "border-[#00ff88]/30 bg-[#00ff88]/[0.04]"
                : "border-[#1a1a1a] bg-white/[0.01] hover:bg-white/[0.03]"
            )}
          >
            <div
              className={clsx(
                "text-[10px] font-medium leading-tight",
                selected ? "text-[#e8e8e8]" : "text-[#ccc]"
              )}
            >
              {opt.label}
            </div>
            <div className="text-[9px] text-[#999] mt-0.5 leading-tight">
              {opt.description}
            </div>
            <div
              className={clsx(
                "text-[8px] mt-1.5 font-mono",
                selected ? "text-[#00ff88]/70" : "text-[#555]"
              )}
            >
              {opt.context}
            </div>
          </button>
        );
      })}
    </div>
  );
}
