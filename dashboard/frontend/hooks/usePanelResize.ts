"use client";

import { useState, useRef, useCallback, useEffect } from "react";
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
}

export function usePanelResize({
  storageKey,
  defaultWidth,
  minWidth,
  maxWidth,
  direction,
}: UsePanelResizeOptions): UsePanelResizeResult {
  const [width, setWidth] = useState<number>(() => {
    try {
      const stored = localStorage.getItem(PANEL_WIDTH_STORAGE_PREFIX + storageKey);
      if (stored !== null) {
        const parsed = parseInt(stored, 10);
        if (!isNaN(parsed)) return Math.min(maxWidth, Math.max(minWidth, parsed));
      }
    } catch {
      // localStorage unavailable (SSR or restricted context)
    }
    return defaultWidth;
  });

  const [isDragging, setIsDragging] = useState(false);

  // Refs avoid stale closures in event listeners registered once on mousedown.
  const startXRef = useRef<number>(0);
  const startWidthRef = useRef<number>(0);
  const currentWidthRef = useRef<number>(width);

  // Keep currentWidthRef in sync so handleMouseUp can persist the latest value.
  useEffect(() => {
    currentWidthRef.current = width;
  }, [width]);

  const handleMouseMove = useCallback(
    (e: MouseEvent): void => {
      const delta = e.clientX - startXRef.current;
      const newWidth =
        direction === "left"
          ? startWidthRef.current + delta
          : startWidthRef.current - delta;
      const clamped = Math.min(maxWidth, Math.max(minWidth, newWidth));
      currentWidthRef.current = clamped;
      setWidth(clamped);
    },
    [direction, minWidth, maxWidth],
  );

  const handleMouseUp = useCallback((): void => {
    setIsDragging(false);
    document.body.style.userSelect = "";
    document.body.style.cursor = "";
    try {
      localStorage.setItem(
        PANEL_WIDTH_STORAGE_PREFIX + storageKey,
        String(currentWidthRef.current),
      );
    } catch {
      // ignore write failures
    }
    document.removeEventListener("mousemove", handleMouseMove);
    document.removeEventListener("mouseup", handleMouseUp);
  }, [storageKey, handleMouseMove]);

  useEffect(() => {
    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [handleMouseMove, handleMouseUp]);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent): void => {
      e.preventDefault();
      startXRef.current = e.clientX;
      startWidthRef.current = currentWidthRef.current;
      setIsDragging(true);
      document.body.style.userSelect = "none";
      document.body.style.cursor = "col-resize";
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
    },
    [handleMouseMove, handleMouseUp],
  );

  return { width, isDragging, handleMouseDown };
}
