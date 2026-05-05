"use client";

import { clsx } from "clsx";
import type { HostMount } from "@/lib/api";

interface HostMountsEditorProps {
  mounts: HostMount[];
  onChange: (mounts: HostMount[]) => void;
  loading: boolean;
  error: string | null;
}

export function HostMountsEditor({ mounts, onChange, loading, error }: HostMountsEditorProps) {
  if (loading) return <p className="text-content text-text-secondary">Loading mounts...</p>;

  return (
    <div className="space-y-2">
      <p className="text-content text-text-secondary mb-2">Repo is at /home/agentuser/repo inside the sandbox.</p>
      {mounts.map((m, i) => (
        <div key={i} className="space-y-1.5 mb-3">
          <div className="flex items-center gap-2">
            <span className="text-caption uppercase tracking-wider text-text-dim w-16 shrink-0">Host</span>
            <input
              type="text"
              value={m.host_path}
              onChange={(e) => {
                const next = [...mounts];
                next[i] = { ...m, host_path: e.target.value };
                onChange(next);
              }}
              placeholder="/Users/you/datasets"
              className="flex-1 bg-black/30 border border-border rounded px-2.5 py-1.5 text-content font-mono text-accent-hover placeholder:text-text-secondary focus-visible:outline-none focus-visible:border-[#00ff88]/30"
            />
            <button
              type="button"
              onClick={() => onChange(mounts.filter((_, j) => j !== i))}
              className="p-1 text-text-dim hover:text-[#ff4444] transition-colors"
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                <line x1="2" y1="2" x2="8" y2="8" /><line x1="8" y1="2" x2="2" y2="8" />
              </svg>
            </button>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-caption uppercase tracking-wider text-text-dim w-16 shrink-0">Sandbox</span>
            <input
              type="text"
              value={m.container_path}
              onChange={(e) => {
                const next = [...mounts];
                next[i] = { ...m, container_path: e.target.value };
                onChange(next);
              }}
              placeholder="/home/agentuser/datasets"
              className="flex-1 bg-black/30 border border-border rounded px-2.5 py-1.5 text-content font-mono text-accent-hover placeholder:text-text-secondary focus-visible:outline-none focus-visible:border-[#00ff88]/30"
            />
            <span className="w-[26px]" />
          </div>
          <div className="flex items-center gap-2 pl-[72px]">
            <div className="flex items-center bg-black/30 border border-border rounded-full p-0.5">
              {(["ro", "rw"] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => {
                    const next = [...mounts];
                    next[i] = { ...m, mode };
                    onChange(next);
                  }}
                  className={clsx(
                    "px-2.5 py-0.5 rounded-full text-content transition-all",
                    m.mode === mode
                      ? "bg-[#00ff88]/[0.12] text-[#00ff88] font-medium"
                      : "text-text-dim hover:text-text-secondary"
                  )}
                >
                  {mode === "ro" ? "Read only" : "Read & write"}
                </button>
              ))}
            </div>
          </div>
        </div>
      ))}
      <button
        type="button"
        onClick={() => onChange([...mounts, { host_path: "", container_path: "", mode: "ro" }])}
        className="text-content text-text-secondary hover:text-accent-hover transition-colors"
      >
        + Add mount
      </button>
      {error && <p className="mt-1 text-content text-[#ff4444]">{error}</p>}
    </div>
  );
}
