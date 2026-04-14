"use client";

import { useState, useRef, useEffect } from "react";
import { PANEL_WIDTH_STORAGE_PREFIX } from "@/lib/constants";

export interface UsePanelResizeOptions {
  storageKey: string;
  defaultWidth: number;
  minWidth: number;
  maxWidth: number;
  direction: "left" | "right";
}

export interface UsePanelResizeResult {
  width: number;
  isDragging: boolean;
  handleMouseDown: (e: React.MouseEvent) => void;
  panelRef: React.RefObject<HTMLDivElement | null>;
}

export function usePanelResize({
  storageKey,
  defaultWidth,
  minWidth,
  maxWidth,
  direction,
}: UsePanelResizeOptions): UsePanelResizeResult {
  const [width, setWidth] = useState<number>(() => {
    if (typeof window === "undefined") return defaultWidth;
    const stored = localStorage.getItem(
      PANEL_WIDTH_STORAGE_PREFIX + storageKey,
    );
    if (stored !== null) {
      const parsed = parseInt(stored, 10);
      if (!isNaN(parsed)) return Math.min(maxWidth, Math.max(minWidth, parsed));
    }
    return defaultWidth;
  });

  const [isDragging, setIsDragging] = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const startXRef = useRef(0);
  const startWidthRef = useRef(0);
  const currentWidthRef = useRef(width);

  // Keep ref in sync with state (for mouseUp to persist correct value).
  useEffect(() => {
    currentWidthRef.current = width;
  }, [width]);

  // Stable handler refs — never recreated, no stale closure issues.
  const moveRef = useRef<(e: MouseEvent) => void>(null);
  const upRef = useRef<() => void>(null);

  moveRef.current = (e: MouseEvent): void => {
    const delta = e.clientX - startXRef.current;
    const raw =
      direction === "left"
        ? startWidthRef.current + delta
        : startWidthRef.current - delta;
    const clamped = Math.min(maxWidth, Math.max(minWidth, raw));
    currentWidthRef.current = clamped;
    if (panelRef.current) {
      panelRef.current.style.width = `${clamped}px`;
    }
  };

  upRef.current = (): void => {
    document.body.style.userSelect = "";
    document.body.style.cursor = "";
    if (panelRef.current) {
      panelRef.current.style.transition = "";
    }
    document.removeEventListener("mousemove", stableMove);
    document.removeEventListener("mouseup", stableUp);
    setWidth(currentWidthRef.current);
    setIsDragging(false);
    localStorage.setItem(
      PANEL_WIDTH_STORAGE_PREFIX + storageKey,
      String(currentWidthRef.current),
    );
  };

  const stableMoveRef = useRef((e: MouseEvent) => {
    moveRef.current?.(e);
  });
  const stableUpRef = useRef(() => {
    upRef.current?.();
  });
  const stableMove = stableMoveRef.current;
  const stableUp = stableUpRef.current;

  const handleMouseDown = (e: React.MouseEvent): void => {
    e.preventDefault();
    startXRef.current = e.clientX;
    startWidthRef.current = currentWidthRef.current;
    if (panelRef.current) {
      panelRef.current.style.transition = "none";
    }
    setIsDragging(true);
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
    document.addEventListener("mousemove", stableMove);
    document.addEventListener("mouseup", stableUp);
  };

  return { width, isDragging, handleMouseDown, panelRef };
}
