"use client";

import { useContext } from "react";
import { ToastContext } from "@/components/ui/Toast";
import type { ToastContextValue } from "@/components/ui/Toast";

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context;
}
