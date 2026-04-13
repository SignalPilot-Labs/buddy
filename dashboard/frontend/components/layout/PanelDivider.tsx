"use client";

import React from "react";

export interface PanelDividerProps {
  onMouseDown: (e: React.MouseEvent) => void;
  isDragging: boolean;
}

export function PanelDivider({ onMouseDown, isDragging }: PanelDividerProps) {
  return (
    <div
      onMouseDown={onMouseDown}
      className="relative flex-shrink-0 z-10 group"
      style={{ width: 5, cursor: "col-resize" }}
      aria-hidden="true"
    >
      {/* Wider invisible hit area */}
      <div className="absolute inset-y-0 -left-1 -right-1" />
      {/* Visible 1px line in center */}
      <div
        className={`absolute inset-y-0 left-[2px] w-px transition-colors duration-150 ${
          isDragging
            ? "bg-[var(--color-accent)]"
            : "bg-border group-hover:bg-border-hover"
        }`}
      />
    </div>
  );
}
