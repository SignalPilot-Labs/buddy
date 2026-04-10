"use client";

import { useContext } from "react";
import { ToastContext } from "@/components/ui/Toast";
import type { ToastContextValue } from "@/components/ui/Toast";

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}
