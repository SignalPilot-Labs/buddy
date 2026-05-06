"use client";

/**Shared Slurm parameter fields + start command card, used in settings and run modal.*/

import { useState, useCallback } from "react";
import CodeTextarea from "@/components/ui/CodeTextarea";

export interface SlurmFields {
  partition: string;
  cpus: string;
  memory: string;
  gpu_gres: string;
  work_dir: string;
}

export const EMPTY_SLURM: SlurmFields = {
  partition: "",
  cpus: "",
  memory: "",
  gpu_gres: "",
  work_dir: "",
};

export function buildSlurmCmd(s: SlurmFields): string {
  const gres = s.gpu_gres.trim() ? ` --gres=gpu:${s.gpu_gres.trim()}` : "";
  const nv = s.gpu_gres.trim() ? " --nv" : "";
  const partition = s.partition.trim() || "PARTITION";
  const cpus = s.cpus.trim() || "CPUS";
  const mem = s.memory.trim() || "MEMORY";
  const workDir = s.work_dir.trim() || "WORK_DIR";
  return (
    `source /etc/profile && module load apptainer && ` +
    `srun --job-name=autofyn -p ${partition} -n 1 --cpus-per-task=${cpus} --mem=${mem}${gres} ` +
    `bash -c 'W=${workDir}/autofyn/runs/$AF_RUN_KEY && mkdir -p $W && ` +
    `apptainer exec${nv} --overlay $W --pwd /opt/autofyn -B $HOME $AF_HOST_MOUNTS ${workDir}/autofyn/sandbox.sif python3 -m server; rm -rf $W'`
  );
}

export function parseSlurmCmd(cmd: string): SlurmFields | null {
  if (!cmd.includes("srun") || !cmd.includes("apptainer")) return null;
  const partition = cmd.match(/-p\s+(\S+)/)?.[1] ?? "";
  const cpus = cmd.match(/--cpus-per-task=(\S+)/)?.[1] ?? "";
  const memory = cmd.match(/--mem=(\S+)/)?.[1] ?? "";
  const gresMatch = cmd.match(/--gres=gpu:(\S+)/);
  const gpu_gres = gresMatch?.[1] ?? "";
  const workDirMatch = cmd.match(/W=(\S+?)\/autofyn\/runs/);
  const work_dir = workDirMatch?.[1] ?? "";
  return { partition, cpus, memory, gpu_gres, work_dir };
}

const INPUT_CLASS =
  "w-full bg-black/30 border border-border rounded px-2.5 py-1.5 text-content font-mono text-accent-hover placeholder:text-text-secondary focus-visible:outline-none focus-visible:border-[#00ff88]/30";

function FieldLabel(props: {
  label: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <div>
      <label className="text-content uppercase tracking-[0.15em] text-text-muted font-semibold mb-1 block">
        {props.label}
        {props.required && <span className="text-[#ff4444] ml-0.5">*</span>}
        {props.hint && <span className="normal-case tracking-normal font-normal text-text-dim ml-1.5">{props.hint}</span>}
      </label>
      {props.children}
    </div>
  );
}

interface SlurmFieldsCardProps {
  startCmd: string;
  onStartCmdChange: (cmd: string) => void;
  onWorkDirChange?: (workDir: string) => void;
}

export function SlurmFieldsCard({
  startCmd,
  onStartCmdChange,
  onWorkDirChange,
}: SlurmFieldsCardProps): React.ReactElement {
  const initialSlurm = startCmd
    ? parseSlurmCmd(startCmd) ?? EMPTY_SLURM
    : EMPTY_SLURM;
  const [slurm, setSlurm] = useState<SlurmFields>(initialSlurm);

  const updateSlurm = useCallback((patch: Partial<SlurmFields>): void => {
    setSlurm((prev) => {
      const next = { ...prev, ...patch };
      const cmd = buildSlurmCmd(next);
      onStartCmdChange(cmd);
      if (patch.work_dir !== undefined && onWorkDirChange) {
        onWorkDirChange(next.work_dir);
      }
      return next;
    });
  }, [onStartCmdChange, onWorkDirChange]);

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <FieldLabel label="Partition" required>
          <input
            type="text"
            value={slurm.partition}
            onChange={(e) => updateSlurm({ partition: e.target.value })}
            placeholder="gpu, normal, etc."
            className={INPUT_CLASS}
          />
        </FieldLabel>
        <FieldLabel label="Work Directory" required>
          <input
            type="text"
            value={slurm.work_dir}
            onChange={(e) => updateSlurm({ work_dir: e.target.value })}
            placeholder="~/scratch"
            className={INPUT_CLASS}
          />
        </FieldLabel>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <FieldLabel label="CPUs" required>
          <input
            type="text"
            value={slurm.cpus}
            onChange={(e) => updateSlurm({ cpus: e.target.value })}
            placeholder="4"
            className={INPUT_CLASS}
          />
        </FieldLabel>
        <FieldLabel label="Memory" required>
          <input
            type="text"
            value={slurm.memory}
            onChange={(e) => updateSlurm({ memory: e.target.value })}
            placeholder="16G"
            className={INPUT_CLASS}
          />
        </FieldLabel>
        <FieldLabel label="GPU" hint="Leave blank for no GPU.">
          <input
            type="text"
            value={slurm.gpu_gres}
            onChange={(e) => updateSlurm({ gpu_gres: e.target.value })}
            placeholder="a100:2"
            className={INPUT_CLASS}
          />
        </FieldLabel>
      </div>
      <FieldLabel label="Start Command" hint="Auto-generated from fields above. Edit directly for custom flags.">
        <CodeTextarea
          value={startCmd}
          onChange={onStartCmdChange}
          placeholder=""
          rows={5}
        />
      </FieldLabel>
    </div>
  );
}
