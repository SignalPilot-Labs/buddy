"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import type { ParallelRunSlot } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { elapsed } from "@/lib/format";

export interface SlotCardProps {
  slot: ParallelRunSlot;
  onStop: () => void;
  onKill: () => void;
  onPause: () => void;
  onUnlock: () => void;
  onInject?: (prompt: string) => void;
  onHealthCheck?: () => void;
  health?: "ok" | "degraded" | "unknown";
}

const STATUS_COLORS: Record<string, string> = {
  starting: "text-[#ffaa00]",
  running: "text-[#00ff88]",
  completed: "text-[#888]",
  stopped: "text-[#888]",
  error: "text-[#ff4444]",
  killed: "text-[#ff4444]",
};

export function SlotCard({
  slot,
  onStop,
  onKill,
  onPause,
  onUnlock,
  onInject,
  onHealthCheck,
  health = "unknown",
}: SlotCardProps) {
  const [time, setTime] = useState(() => elapsed(slot.started_at));
  const [confirmKill, setConfirmKill] = useState(false);
  const [injectOpen, setInjectOpen] = useState(false);
  const [injectText, setInjectText] = useState("");
  const [detailsOpen, setDetailsOpen] = useState(false);
  const killTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!["starting", "running"].includes(slot.status)) return;
    const id = setInterval(() => setTime(elapsed(slot.started_at)), 60000);
    return () => clearInterval(id);
  }, [slot.started_at, slot.status]);

  const handleKill = useCallback(() => {
    if (confirmKill) {
      onKill();
      setConfirmKill(false);
      if (killTimer.current) clearTimeout(killTimer.current);
    } else {
      setConfirmKill(true);
      killTimer.current = setTimeout(() => setConfirmKill(false), 3000);
    }
  }, [confirmKill, onKill]);

  const handleInject = useCallback(() => {
    if (injectText.trim() && onInject) {
      onInject(injectText.trim());
      setInjectText("");
      setInjectOpen(false);
    }
  }, [injectText, onInject]);

  const isActive = ["starting", "running"].includes(slot.status);
  const healthDot =
    health === "ok" ? "bg-[#00ff88]" : health === "degraded" ? "bg-[#ffaa00]" : "bg-[#555]";

  return (
    <div className="rounded-lg border border-[#1a1a1a] bg-[#0d0d0d] p-3 space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span
            className={`h-2 w-2 rounded-full ${
              slot.status === "running" ? "bg-[#00ff88] animate-pulse" : "bg-[#555]"
            }`}
          />
          <span className="text-[11px] font-mono text-[#ccc]">
            {slot.run_id ? slot.run_id.slice(0, 8) : slot.container_name.replace("buddy-worker-", "")}
          </span>
          <span className={`text-[9px] uppercase font-semibold ${STATUS_COLORS[slot.status] ?? "text-[#888]"}`}>
            {slot.status}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[9px] text-[#666] tabular-nums">{time}</span>
          {onHealthCheck && (
            <button
              onClick={onHealthCheck}
              aria-label="Check health"
              className="p-0.5 rounded hover:bg-white/[0.04]"
            >
              <span className={`block h-1.5 w-1.5 rounded-full ${healthDot}`} />
            </button>
          )}
        </div>
      </div>

      {/* Prompt preview */}
      {slot.prompt && (
        <p className="text-[9px] text-[#666] line-clamp-2 leading-relaxed">
          {slot.prompt}
        </p>
      )}

      {/* Error */}
      {slot.error_message && (
        <p className="text-[9px] text-[#ff4444] line-clamp-2">{slot.error_message}</p>
      )}

      {/* Controls */}
      {isActive && (
        <div className="flex items-center gap-1.5 pt-1">
          {slot.status === "running" && (
            <>
              <Button variant="ghost" onClick={onPause}>Pause</Button>
              <Button variant="ghost" onClick={onUnlock}>Unlock</Button>
              <Button variant="ghost" onClick={onStop}>Stop</Button>
              {onInject && (
                <Button variant="ghost" onClick={() => setInjectOpen(!injectOpen)}>Inject</Button>
              )}
            </>
          )}
          {slot.status === "starting" && (
            <span className="text-[9px] text-[#ffaa00]">Starting...</span>
          )}
          <div className="flex-1" />
          <Button
            variant={confirmKill ? "danger" : "ghost"}
            onClick={handleKill}
          >
            {confirmKill ? "Confirm Kill" : "Kill"}
          </Button>
        </div>
      )}

      {/* Inject textarea */}
      {injectOpen && (
        <div className="space-y-1.5">
          <textarea
            value={injectText}
            onChange={(e) => setInjectText(e.target.value)}
            placeholder="Prompt to inject..."
            rows={2}
            className="w-full bg-black/30 border border-[#1a1a1a] rounded px-2 py-1.5 text-[10px] text-[#ccc] placeholder-[#666] resize-y focus:outline-none focus:border-[#00ff88]/30"
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                handleInject();
              }
              if (e.key === "Escape") setInjectOpen(false);
            }}
          />
          <div className="flex justify-end gap-1">
            <Button variant="ghost" onClick={() => setInjectOpen(false)}>Cancel</Button>
            <Button variant="primary" onClick={handleInject}>Send</Button>
          </div>
        </div>
      )}

      {/* Details toggle */}
      <button
        onClick={() => setDetailsOpen(!detailsOpen)}
        className="text-[8px] text-[#555] hover:text-[#888] transition-colors"
      >
        {detailsOpen ? "Hide details" : "Details"}
      </button>
      {detailsOpen && (
        <div className="text-[8px] text-[#555] space-y-0.5 font-mono">
          <div>Branch: {slot.base_branch}</div>
          <div>Budget: {slot.max_budget_usd > 0 ? `$${slot.max_budget_usd}` : "unlimited"}</div>
          <div>Duration: {slot.duration_minutes > 0 ? `${slot.duration_minutes}m` : "no lock"}</div>
          {slot.volume_name && <div>Volume: {slot.volume_name}</div>}
          {slot.container_id && <div>Container: {slot.container_id}</div>}
        </div>
      )}
    </div>
  );
}
