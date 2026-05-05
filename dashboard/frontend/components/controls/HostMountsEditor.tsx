/**Editor for host-to-sandbox bind mount entries in the New Run modal.*/

"use client";

import { clsx } from "clsx";
import { Button } from "@/components/ui/Button";
import { IconTrash, IconPlus } from "@/components/ui/icons";
import type { HostMount } from "@/lib/api";

interface HostMountsEditorProps {
  mounts: HostMount[];
  onChange: (mounts: HostMount[]) => void;
  loading: boolean;
  error: string | null;
}

const INPUT_CLASS =
  "flex-1 bg-black/30 border border-border rounded px-2.5 py-1.5 text-content font-mono text-accent-hover placeholder:text-text-secondary focus-visible:outline-none focus-visible:border-[#00ff88]/30";

export function HostMountsEditor({ mounts, onChange, loading, error }: HostMountsEditorProps) {
  if (loading) return <p className="text-content text-text-secondary">Loading mounts...</p>;

  return (
    <div className="space-y-2">
      <p className="text-content text-text-dim">Bind-mount directories from your machine into the sandbox. Repo is at <code className="text-[#88ccff]">/home/agentuser/repo</code>.</p>
      {mounts.map((m, i) => (
        <div key={i} className="p-2.5 bg-black/20 rounded border border-border space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="text-content uppercase tracking-wider text-text-dim w-16 shrink-0">Host</span>
            <input
              type="text"
              value={m.host_path}
              onChange={(e) => {
                const next = [...mounts];
                next[i] = { ...m, host_path: e.target.value };
                onChange(next);
              }}
              placeholder="/Users/you/datasets"
              className={INPUT_CLASS}
            />
            <button
              type="button"
              onClick={() => onChange(mounts.filter((_, j) => j !== i))}
              className="p-1 text-text-dim hover:text-[#ff4444] transition-colors"
              title="Remove mount"
            >
              <IconTrash size={11} />
            </button>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-content uppercase tracking-wider text-text-dim w-16 shrink-0">Container</span>
            <input
              type="text"
              value={m.container_path}
              onChange={(e) => {
                const next = [...mounts];
                next[i] = { ...m, container_path: e.target.value };
                onChange(next);
              }}
              placeholder="/home/agentuser/datasets"
              className={INPUT_CLASS}
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
      <Button
        variant="success"
        size="sm"
        icon={<IconPlus size={10} />}
        onClick={() => onChange([...mounts, { host_path: "", container_path: "", mode: "ro" }])}
      >
        Add Mount
      </Button>
      {error && <p className="mt-1 text-content text-[#ff4444]">{error}</p>}
    </div>
  );
}
