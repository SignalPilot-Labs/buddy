/**Sandbox selector: local Docker or remote, with start command editor.*/

"use client";

import { useRef, useCallback } from "react";
import { clsx } from "clsx";
import CodeTextarea from "@/components/ui/CodeTextarea";
import { SlurmFieldsCard } from "@/components/ui/SlurmFieldsCard";
import { DEFAULT_DOCKER_START_CMD } from "@/lib/constants";
import type { RemoteSandboxConfig } from "@/lib/api";
import { fetchLastStartCmd } from "@/lib/api";

/** Key for local Docker in the command cache. */
const LOCAL_KEY = "__local__";

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

  // Cache start commands per sandbox so switching back restores edits.
  const cmdCache = useRef<Map<string, string>>(new Map());

  /** Save current command, then switch to a new sandbox with the given command. */
  const switchTo = useCallback((nextId: string | null, nextCmd: string) => {
    const currentKey = selectedId ?? LOCAL_KEY;
    cmdCache.current.set(currentKey, startCmd);
    // Set command FIRST so the remounted SlurmFieldsCard sees it.
    onStartCmdChange(nextCmd);
    onSelect(nextId);
  }, [selectedId, startCmd, onSelect, onStartCmdChange]);

  const handleLocalClick = useCallback(() => {
    switchTo(null, DEFAULT_DOCKER_START_CMD);
  }, [switchTo]);

  const handleRemoteClick = useCallback(async (s: RemoteSandboxConfig) => {
    const currentKey = selectedId ?? LOCAL_KEY;
    cmdCache.current.set(currentKey, startCmd);

    const cached = cmdCache.current.get(s.id);
    if (cached) {
      // Synchronous: cached command available, set before select for correct remount.
      onStartCmdChange(cached);
      onSelect(s.id);
    } else {
      // First time selecting this sandbox — fetch last-used or use default.
      let cmd = s.default_start_cmd;
      if (activeRepo) {
        const lastCmd = await fetchLastStartCmd(s.id, activeRepo).catch(() => null);
        cmd = lastCmd ?? s.default_start_cmd;
      }
      onStartCmdChange(cmd);
      onSelect(s.id);
    }
  }, [selectedId, startCmd, activeRepo, onSelect, onStartCmdChange]);

  return (
    <div className="space-y-2">
      <div className="flex gap-1.5 flex-wrap">
        <button
          onClick={handleLocalClick}
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
            onClick={() => void handleRemoteClick(s)}
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
