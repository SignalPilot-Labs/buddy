"use client";

import { createContext, useState, useCallback, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";

const TOAST_DURATION_MS = 3000;
const MAX_VISIBLE_TOASTS = 3;

export type ToastVariant = "success" | "error" | "info";

interface ToastItem {
  id: number;
  message: string;
  variant: ToastVariant;
}

export interface ToastContextValue {
  showToast: (message: string, variant: ToastVariant) => void;
}

export const ToastContext = createContext<ToastContextValue | null>(null);

const VARIANT_STYLES: Record<ToastVariant, string> = {
  success: "border-[var(--color-success)]/40 text-[var(--color-success)]",
  error: "border-[var(--color-error)]/40 text-[var(--color-error)]",
  info: "border-[var(--color-info)]/40 text-[var(--color-info)]",
};

const VARIANT_BG: Record<ToastVariant, string> = {
  success: "bg-[var(--color-success)]/[0.06]",
  error: "bg-[var(--color-error)]/[0.06]",
  info: "bg-[var(--color-info)]/[0.06]",
};

function ToastItem({ toast, onDismiss }: { toast: ToastItem; onDismiss: (id: number) => void }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, x: 40, scale: 0.95 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 40, scale: 0.95 }}
      transition={{ duration: 0.2, ease: "easeOut" }}
      className={[
        "flex items-center gap-2 px-3 py-2 rounded border frosted-glass",
        "text-[11px] font-medium cursor-pointer select-none min-w-[160px] max-w-[280px]",
        VARIANT_STYLES[toast.variant],
        VARIANT_BG[toast.variant],
      ].join(" ")}
      onClick={() => onDismiss(toast.id)}
      role="status"
      aria-live="polite"
    >
      <ToastIcon variant={toast.variant} />
      <span className="flex-1">{toast.message}</span>
    </motion.div>
  );
}

function ToastIcon({ variant }: { variant: ToastVariant }) {
  if (variant === "success") {
    return (
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
        <polyline points="2 6 5 9 10 3" />
      </svg>
    );
  }
  if (variant === "error") {
    return (
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" className="shrink-0">
        <circle cx="6" cy="6" r="5" />
        <line x1="4" y1="4" x2="8" y2="8" />
        <line x1="8" y1="4" x2="4" y2="8" />
      </svg>
    );
  }
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" className="shrink-0">
      <circle cx="6" cy="6" r="5" />
      <line x1="6" y1="4" x2="6" y2="6.5" />
      <circle cx="6" cy="8.5" r="0.5" fill="currentColor" />
    </svg>
  );
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const counterRef = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback((message: string, variant: ToastVariant) => {
    const id = ++counterRef.current;
    setToasts((prev) => {
      const next = [...prev, { id, message, variant }];
      return next.slice(-MAX_VISIBLE_TOASTS);
    });
    setTimeout(() => dismiss(id), TOAST_DURATION_MS);
  }, [dismiss]);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div
        className="fixed bottom-4 right-4 z-[9998] flex flex-col gap-2 items-end pointer-events-none"
        aria-label="Notifications"
      >
        <AnimatePresence mode="popLayout">
          {toasts.map((toast) => (
            <div key={toast.id} className="pointer-events-auto">
              <ToastItem toast={toast} onDismiss={dismiss} />
            </div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}
