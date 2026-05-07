"use client";

import { useState, useRef, useEffect } from "react";
import { PANEL_WIDTH_STORAGE_PREFIX } from "@/lib/constants";

export interface UsePanelResizeOptions {
  storageKey: string;
  defaultWidth: number;
  minWidth: number;
  maxWidth: number;
  // If set, effective max = min(maxWidth, window.innerWidth * maxWidthRatio).
  // Re-clamped on window resize so the panel can never exceed the viewport.
  maxWidthRatio: number | null;
  direction: "left" | "right";
}

export interface UsePanelResizeResult {
  width: number;
  isDragging: boolean;
  handleMouseDown: (e: React.MouseEvent) => void;
  panelRef: React.RefObject<HTMLDivElement | null>;
}

function effectiveMax(maxWidth: number, ratio: number | null): number {
  if (ratio === null || typeof window === "undefined") return maxWidth;
  return Math.min(maxWidth, Math.floor(window.innerWidth * ratio));
}

export function usePanelResize({
  storageKey,
  defaultWidth,
  minWidth,
  maxWidth,
  maxWidthRatio,
  direction,
}: UsePanelResizeOptions): UsePanelResizeResult {
  const [width, setWidth] = useState<number>(() => {
    if (typeof window === "undefined") return defaultWidth;
    const max = effectiveMax(maxWidth, maxWidthRatio);
    const stored = localStorage.getItem(
      PANEL_WIDTH_STORAGE_PREFIX + storageKey,
    );
    if (stored !== null) {
      const parsed = parseInt(stored, 10);
      if (!isNaN(parsed)) return Math.min(max, Math.max(minWidth, parsed));
    }
    return defaultWidth;
  });

  // Re-clamp when the viewport shrinks so a stored wide panel never exceeds it.
  useEffect(() => {
    if (maxWidthRatio === null) return;
    const onResize = (): void => {
      const max = effectiveMax(maxWidth, maxWidthRatio);
      setWidth((w) => Math.min(w, max));
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [maxWidth, maxWidthRatio]);

  const [isDragging, setIsDragging] = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const startXRef = useRef(0);
  const startWidthRef = useRef(0);
  const currentWidthRef = useRef(width);
  // Cached once on mousedown — viewport can't change mid-drag, so we avoid
  // re-reading window.innerWidth on every mousemove event.
  const dragMaxRef = useRef(0);

  // Keep ref in sync with state (for mouseUp to persist correct value).
  useEffect(() => {
    currentWidthRef.current = width;
  }, [width]);

  // Stable handler refs — never recreated, no stale closure issues.
  const moveRef = useRef<(e: MouseEvent) => void>(null);
  const upRef = useRef<() => void>(null);

  // Track whether document listeners are currently attached so the unmount
  // cleanup can remove them even if mouseup never fired.
  const listenersAttachedRef = useRef(false);

  const stableMoveRef = useRef((e: MouseEvent) => {
    moveRef.current?.(e);
  });
  const stableUpRef = useRef(() => {
    upRef.current?.();
  });
  const stableMove = stableMoveRef.current;
  const stableUp = stableUpRef.current;

  moveRef.current = (e: MouseEvent): void => {
    const delta = e.clientX - startXRef.current;
    const raw =
      direction === "left"
        ? startWidthRef.current + delta
        : startWidthRef.current - delta;
    const clamped = Math.min(dragMaxRef.current, Math.max(minWidth, raw));
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
    listenersAttachedRef.current = false;
    setWidth(currentWidthRef.current);
    setIsDragging(false);
    localStorage.setItem(
      PANEL_WIDTH_STORAGE_PREFIX + storageKey,
      String(currentWidthRef.current),
    );
  };

  // Unmount cleanup: remove listeners and restore body styles if we unmount
  // mid-drag (before mouseup fires). Safe to call when listeners are not
  // attached — removeEventListener is a no-op for listeners that were never
  // added, and resetting empty styles is harmless.
  useEffect(() => {
    return () => {
      if (listenersAttachedRef.current) {
        document.removeEventListener("mousemove", stableMove);
        document.removeEventListener("mouseup", stableUp);
        document.body.style.userSelect = "";
        document.body.style.cursor = "";
        listenersAttachedRef.current = false;
      }
    };
    // stableMove/stableUp are stable refs — never change after mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleMouseDown = (e: React.MouseEvent): void => {
    e.preventDefault();
    startXRef.current = e.clientX;
    startWidthRef.current = currentWidthRef.current;
    dragMaxRef.current = effectiveMax(maxWidth, maxWidthRatio);
    if (panelRef.current) {
      panelRef.current.style.transition = "none";
    }
    setIsDragging(true);
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";
    listenersAttachedRef.current = true;
    document.addEventListener("mousemove", stableMove);
    document.addEventListener("mouseup", stableUp);
  };

  return { width, isDragging, handleMouseDown, panelRef };
}
