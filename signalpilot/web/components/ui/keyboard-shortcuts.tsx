"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

/**
 * Global keyboard shortcuts:
 *   Ctrl/Cmd + K  — Focus search / quick nav
 *   Ctrl/Cmd + 1  — Dashboard
 *   Ctrl/Cmd + 2  — Query Explorer
 *   Ctrl/Cmd + 3  — Schema Explorer
 *   Ctrl/Cmd + 4  — Sandboxes
 *   Ctrl/Cmd + 5  — Connections
 *   Ctrl/Cmd + 6  — Audit Log
 *   ?             — Show shortcuts help
 */

const SHORTCUTS = [
  { key: "1", label: "Dashboard", path: "/dashboard" },
  { key: "2", label: "Query Explorer", path: "/query" },
  { key: "3", label: "Schema Explorer", path: "/schema" },
  { key: "4", label: "Sandboxes", path: "/sandboxes" },
  { key: "5", label: "Connections", path: "/connections" },
  { key: "6", label: "System Health", path: "/health" },
  { key: "7", label: "Audit Log", path: "/audit" },
  { key: "8", label: "Settings", path: "/settings" },
];

export function KeyboardShortcuts() {
  const router = useRouter();
  const [showHelp, setShowHelp] = useState(false);

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Ignore if user is typing in an input/textarea
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT") {
        return;
      }

      // ? — show help
      if (e.key === "?" && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        setShowHelp((prev) => !prev);
        return;
      }

      // Escape — close help
      if (e.key === "Escape" && showHelp) {
        setShowHelp(false);
        return;
      }

      // Ctrl/Cmd + number — navigate
      if (e.ctrlKey || e.metaKey) {
        const shortcut = SHORTCUTS.find((s) => s.key === e.key);
        if (shortcut) {
          e.preventDefault();
          router.push(shortcut.path);
        }
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [router, showHelp]);

  if (!showHelp) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm"
      onClick={() => setShowHelp(false)}
    >
      <div
        className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl p-6 shadow-2xl w-96"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-sm font-semibold mb-4">Keyboard Shortcuts</h2>
        <div className="space-y-2">
          {SHORTCUTS.map((s) => (
            <div key={s.key} className="flex items-center justify-between">
              <span className="text-sm text-[var(--color-text-muted)]">{s.label}</span>
              <kbd className="px-2 py-0.5 rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-xs font-mono">
                Ctrl+{s.key}
              </kbd>
            </div>
          ))}
          <div className="border-t border-[var(--color-border)] pt-2 mt-2">
            <div className="flex items-center justify-between">
              <span className="text-sm text-[var(--color-text-muted)]">Execute query</span>
              <kbd className="px-2 py-0.5 rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-xs font-mono">
                Ctrl+Enter
              </kbd>
            </div>
            <div className="flex items-center justify-between mt-2">
              <span className="text-sm text-[var(--color-text-muted)]">Show shortcuts</span>
              <kbd className="px-2 py-0.5 rounded bg-[var(--color-bg)] border border-[var(--color-border)] text-xs font-mono">
                ?
              </kbd>
            </div>
          </div>
        </div>
        <p className="text-[10px] text-[var(--color-text-dim)] mt-4 text-center">
          Press Escape or ? to close
        </p>
      </div>
    </div>
  );
}
