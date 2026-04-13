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
    const stored = localStorage.getItem(PANEL_WIDTH_STORAGE_PREFIX + storageKey);
    if (stored !== null) {
      const parsed = parseInt(stored, 10);
      if (!isNaN(parsed)) return Math.min(maxWidth, Math.max(minWidth, parsed));
    }
    return defaultWidth;
  });

  const [isDragging, setIsDragging] = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);

  const startXRef = useRef<number>(0);
  const startWidthRef = useRef<number>(0);
  const currentWidthRef = useRef<number>(width);

  useEffect(() => {
    currentWidthRef.current = width;
  }, [width]);

  const clamp = useCallback(
    (v: number): number => Math.min(maxWidth, Math.max(minWidth, v)),
    [minWidth, maxWidth],
  );

  const handleMouseMove = useCallback(
    (e: MouseEvent): void => {
      const delta = e.clientX - startXRef.current;
      const newWidth =
        direction === "left"
          ? startWidthRef.current + delta
          : startWidthRef.current - delta;
      const clamped = clamp(newWidth);
      currentWidthRef.current = clamped;
      if (panelRef.current) {
        panelRef.current.style.width = `${clamped}px`;
      }
    },
    [direction, clamp],
  );

  const handleMouseUp = useCallback((): void => {
    document.body.style.userSelect = "";
    document.body.style.cursor = "";
    // Restore transition before committing final width.
    if (panelRef.current) {
      panelRef.current.style.transition = "";
    }
    document.removeEventListener("mousemove", handleMouseMove);
    document.removeEventListener("mouseup", handleMouseUp);
    setWidth(currentWidthRef.current);
    setIsDragging(false);
    localStorage.setItem(
      PANEL_WIDTH_STORAGE_PREFIX + storageKey,
      String(currentWidthRef.current),
    );
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
      // Kill transition immediately — don't wait for React re-render.
      if (panelRef.current) {
        panelRef.current.style.transition = "none";
      }
      setIsDragging(true);
      document.body.style.userSelect = "none";
      document.body.style.cursor = "col-resize";
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
    },
    [handleMouseMove, handleMouseUp],
  );

  return { width, isDragging, handleMouseDown, panelRef };
}
