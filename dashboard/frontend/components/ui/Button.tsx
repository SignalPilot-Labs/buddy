"use client";

import { clsx } from "clsx";
import { forwardRef } from "react";

type Variant = "ghost" | "danger" | "success" | "warning" | "primary";
type Size = "sm" | "md" | "pill" | "lg";

const variantStyles: Record<Variant, string> = {
  ghost:
    "bg-white/[0.04] text-[#aaa] hover:bg-white/[0.08] hover:text-white border-[#1a1a1a]",
  primary:
    "bg-[#88ccff]/10 text-[#88ccff] hover:bg-[#88ccff]/20 border-[#88ccff]/20 hover:shadow-[0_0_12px_rgba(136,204,255,0.12)]",
  danger:
    "bg-[#ff4444]/8 text-[#ff4444] hover:bg-[#ff4444]/15 border-[#ff4444]/15",
  success:
    "bg-[#00ff88]/8 text-[#00ff88] hover:bg-[#00ff88]/15 border-[#00ff88]/15 hover:shadow-[0_0_12px_rgba(0,255,136,0.15)]",
  warning:
    "bg-[#ffaa00]/8 text-[#ffaa00] hover:bg-[#ffaa00]/15 border-[#ffaa00]/15",
};

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  icon?: React.ReactNode;
  /**
   * When true, enforce a 44px min touch target regardless of size.
   * Use inside mobile sheets / bottom controls where iOS HIG applies.
   */
  touch?: boolean;
}

const sizeStyles: Record<Size, string> = {
  sm: "px-2.5 py-1.5 text-[11px] min-h-[28px]",
  md: "px-3 py-2 text-[12px] min-h-[32px]",
  pill: "rounded-full px-3 py-1.5 text-[12px] min-h-[28px]",
  lg: "px-4 py-2.5 text-[13px] min-h-[44px]",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "ghost", size = "sm", icon, touch, children, className, ...props }, ref) => (
    <button
      ref={ref}
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 rounded border font-medium transition-all duration-150 shadow-sm",
        "disabled:opacity-30 disabled:pointer-events-none",
        "active:scale-[0.97]",
        variantStyles[variant],
        sizeStyles[size],
        touch && "min-h-[44px] px-4",
        className
      )}
      {...props}
    >
      {icon}
      {children}
    </button>
  )
);

Button.displayName = "Button";
