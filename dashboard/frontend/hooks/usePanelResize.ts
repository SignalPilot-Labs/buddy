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

  const handleMouseMove = useCallback(
    (e: MouseEvent): void => {
      const delta = e.clientX - startXRef.current;
      const newWidth =
        direction === "left"
          ? startWidthRef.current + delta
          : startWidthRef.current - delta;
      const clamped = Math.min(maxWidth, Math.max(minWidth, newWidth));
      currentWidthRef.current = clamped;
      // Direct DOM mutation — skip React re-render during drag.
      if (panelRef.current) {
        panelRef.current.style.width = `${clamped}px`;
      }
    },
    [direction, minWidth, maxWidth],
  );

  const handleMouseUp = useCallback((): void => {
    document.body.style.userSelect = "";
    document.body.style.cursor = "";
    document.removeEventListener("mousemove", handleMouseMove);
    document.removeEventListener("mouseup", handleMouseUp);
    // Commit final width to React state (single re-render).
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
