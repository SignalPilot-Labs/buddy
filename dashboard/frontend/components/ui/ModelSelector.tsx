"use client";

import { clsx } from "clsx";
import { MODEL_OPTIONS, LOCALSTORAGE_MODEL_KEY } from "@/lib/constants";
import type { ModelId } from "@/lib/constants";

export interface ModelSelectorProps {
  value: ModelId;
  onChange: (id: ModelId) => void;
}

export function ModelSelector({ value, onChange }: ModelSelectorProps): React.ReactElement {
  const handleClick = (id: ModelId): void => {
    onChange(id);
    try {
      localStorage.setItem(LOCALSTORAGE_MODEL_KEY, id);
    } catch {
      // localStorage may be unavailable in some environments
    }
  };

  return (
    <div className="grid grid-cols-3 gap-2">
      {MODEL_OPTIONS.map((opt) => (
        <button
          key={opt.id}
          onClick={() => handleClick(opt.id)}
          className={clsx(
            "text-left p-3 rounded border transition-all",
            value === opt.id
              ? "border-[#00ff88]/30 bg-[#00ff88]/[0.04]"
              : "border-[#1a1a1a] bg-white/[0.01] hover:bg-white/[0.03]"
          )}
        >
          <div
            className={clsx(
              "text-[10px] font-medium leading-tight",
              value === opt.id ? "text-[#e8e8e8]" : "text-[#ccc]"
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
              value === opt.id ? "text-[#00ff88]/70" : "text-[#555]"
            )}
          >
            {opt.context}
          </div>
        </button>
      ))}
    </div>
  );
}
