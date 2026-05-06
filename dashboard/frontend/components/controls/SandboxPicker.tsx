/**Sandbox selector: local Docker or remote, with start command editor.*/

"use client";

import { clsx } from "clsx";
import CodeTextarea from "@/components/ui/CodeTextarea";
import { SlurmFieldsCard } from "@/components/ui/SlurmFieldsCard";
import { DEFAULT_DOCKER_START_CMD } from "@/lib/constants";
import type { RemoteSandboxConfig } from "@/lib/api";
import { fetchLastStartCmd } from "@/lib/api";

interface SandboxPickerProps {
  sandboxes: RemoteSandboxConfig[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  startCmd: string;
  onStartCmdChange: (cmd: string) => void;
  activeRepo: string | null;
}

export function SandboxPicker({ sandboxes, selectedId, onSelect, startCmd, onStartCmdChange, activeRepo }: SandboxPickerProps) {
  const selectedSandbox = sandboxes.find((s) => s.id === selectedId) ?? null;
  const isSlurm = selectedSandbox?.type === "slurm";

  return (
    <div className="space-y-2">
      <div className="flex gap-1.5 flex-wrap">
        <button
          onClick={() => { onSelect(null); onStartCmdChange(DEFAULT_DOCKER_START_CMD); }}
          className={clsx(
            "text-content px-3 py-2 rounded border transition-all",
            selectedId === null
              ? "border-[#00ff88]/30 bg-[#00ff88]/[0.06] text-[#00ff88] font-medium"
              : "border-border bg-white/[0.01] text-text-dim hover:bg-white/[0.03]"
          )}
        >
          Docker (local)
        </button>
        {sandboxes.map((s) => (
          <button
            key={s.id}
            onClick={async () => {
              onSelect(s.id);
              if (activeRepo) {
                const lastCmd = await fetchLastStartCmd(s.id, activeRepo).catch((err) => {
                  console.warn("Failed to fetch last start cmd:", err);
                  return null;
                });
                onStartCmdChange(lastCmd ?? s.default_start_cmd);
              } else {
                onStartCmdChange(s.default_start_cmd);
              }
            }}
            className={clsx(
              "text-content px-3 py-2 rounded border transition-all",
              selectedId === s.id
                ? "border-[#00ff88]/30 bg-[#00ff88]/[0.06] text-[#00ff88] font-medium"
                : "border-border bg-white/[0.01] text-text-dim hover:bg-white/[0.03]"
            )}
          >
            {s.name} <span className="opacity-60">({s.type})</span>
          </button>
        ))}
      </div>
      {isSlurm ? (
        <SlurmFieldsCard
          key={selectedId}
          startCmd={startCmd}
          onStartCmdChange={onStartCmdChange}
        />
      ) : (
        <div>
          <label className="text-content uppercase tracking-[0.15em] text-text-muted font-semibold mb-1 block">Start Command</label>
          <CodeTextarea
            value={startCmd}
            onChange={onStartCmdChange}
            placeholder=""
            rows={5}
          />
        </div>
      )}
    </div>
  );
}
