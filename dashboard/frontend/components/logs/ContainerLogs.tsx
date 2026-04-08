"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { clsx } from "clsx";
import { fetchContainerLogs } from "@/lib/api";
import { CONTAINER_LOGS_POLL_MS, CONTAINER_LOGS_DEFAULT_TAIL } from "@/lib/constants";

export function ContainerLogs({ runId }: { runId: string | null }) {
  const [lines, setLines] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filter, setFilter] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    const data = await fetchContainerLogs(CONTAINER_LOGS_DEFAULT_TAIL);
    setLines(data.lines ?? []);
  }, []);

  // Initial load
  useEffect(() => {
    if (!runId) { setLines([]); return; }
    setLoading(true);
    setLines([]);
    refresh().finally(() => setLoading(false));
  }, [runId, refresh]);

  // Auto-poll while a run is selected
  useEffect(() => {
    if (!runId) return;
    const id = setInterval(refresh, CONTAINER_LOGS_POLL_MS);
    return () => clearInterval(id);
  }, [runId, refresh]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [lines, autoScroll]);

  // Detect manual scroll to disable auto-scroll
  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;
    const el = containerRef.current;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setAutoScroll(atBottom);
  }, []);

  const filtered = filter
    ? lines.filter((l) => l.toLowerCase().includes(filter.toLowerCase()))
    : lines;

  if (!runId) {
    return (
      <div className="flex items-center justify-center h-full text-[11px] text-[#555]">
        Select a run to view logs
      </div>
    );
  }

  return (
    <div className="relative flex flex-col h-full bg-[#030303]">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-[#1a1a1a]">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#888" strokeWidth="1.5" strokeLinecap="round">
          <rect x="1" y="1" width="10" height="10" rx="1" />
          <path d="M3 4l2 2-2 2" />
          <line x1="6" y1="8" x2="9" y2="8" />
        </svg>
        <span className="text-[11px] font-bold uppercase tracking-[0.15em] text-[#999]">
          Sandbox Logs
        </span>
        <span className="text-[10px] text-[#555] tabular-nums ml-auto">
          {filtered.length} lines
        </span>
      </div>

      {/* Filter bar */}
      <div className="px-3 py-1.5 border-b border-[#1a1a1a]/60">
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter logs..."
          className="w-full bg-transparent text-[10px] text-[#ccc] placeholder-[#444] outline-none"
        />
      </div>

      {/* Log content */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto font-mono text-[10px] leading-[16px] px-2 py-1"
      >
        {loading && lines.length === 0 && (
          <div className="flex items-center justify-center py-8">
            <div
              className="h-4 w-4 rounded-full border-2 border-[#333] border-t-[#00ff88]"
              style={{ animation: "spin 1s linear infinite" }}
            />
          </div>
        )}

        {filtered.map((line, i) => (
          <LogLine key={i} line={line} />
        ))}

        {!loading && lines.length === 0 && (
          <div className="text-[10px] text-[#555] px-2 py-6 text-center">
            No logs available
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Scroll indicator */}
      {!autoScroll && (
        <button
          onClick={() => {
            setAutoScroll(true);
            bottomRef.current?.scrollIntoView({ behavior: "smooth" });
          }}
          className="absolute bottom-2 right-4 px-2 py-1 rounded bg-[#1a1a1a] border border-[#333] text-[9px] text-[#888] hover:text-[#ccc] transition-colors"
        >
          Scroll to bottom
        </button>
      )}
    </div>
  );
}

function LogLine({ line }: { line: string }) {
  const level = getLogLevel(line);
  return (
    <div
      className={clsx(
        "px-1 py-[1px] rounded whitespace-pre-wrap break-all hover:bg-white/[0.02]",
        level === "error" && "text-[#ff6666]",
        level === "warning" && "text-[#ffaa44]",
        level === "info" && "text-[#999]",
        level === "debug" && "text-[#666]",
        !level && "text-[#888]",
      )}
    >
      {line}
    </div>
  );
}

function getLogLevel(line: string): "error" | "warning" | "info" | "debug" | null {
  const lower = line.toLowerCase();
  if (lower.includes("error") || lower.includes("traceback") || lower.includes("exception")) return "error";
  if (lower.includes("warning") || lower.includes("warn")) return "warning";
  if (lower.includes("debug")) return "debug";
  if (lower.includes("info")) return "info";
  return null;
}
