import type { RunStatus } from "@/lib/types";
import { TERMINAL_STATUSES } from "@/lib/constants";

export type ButtonVariant = "ghost" | "primary" | "success" | "warning" | "danger";
export type ButtonIcon = "pause" | "send";

export interface ButtonState {
  label: string;
  variant: ButtonVariant;
  disabled: boolean;
  icon: ButtonIcon;
}

export function getButtonState(
  status: RunStatus | null,
  hasText: boolean,
): ButtonState {
  if (status === null || status === "starting") {
    return { label: "Send", variant: "ghost", disabled: true, icon: "send" };
  }

  if (status === "running") {
    if (hasText) {
      return { label: "Send", variant: "primary", disabled: false, icon: "send" };
    }
    return { label: "Pause", variant: "warning", disabled: false, icon: "pause" };
  }

  if (status === "paused") {
    if (hasText) {
      return { label: "Resume & Send", variant: "primary", disabled: false, icon: "send" };
    }
    return { label: "Resume", variant: "success", disabled: false, icon: "send" };
  }

  if (status === "rate_limited") {
    if (hasText) {
      return { label: "Send", variant: "primary", disabled: false, icon: "send" };
    }
    return { label: "Rate limited", variant: "warning", disabled: true, icon: "send" };
  }

  if (TERMINAL_STATUSES.has(status)) {
    return { label: "Send", variant: "success", disabled: !hasText, icon: "send" };
  }

  return { label: "Send", variant: "ghost", disabled: true, icon: "send" };
}
