"use client";

/**Inline form for creating or editing a remote sandbox configuration.*/

import { useState, useCallback } from "react";
import { clsx } from "clsx";
import { Button } from "@/components/ui/Button";
import CodeTextarea from "@/components/ui/CodeTextarea";
import { IconX } from "@/components/ui/icons";
import type { SandboxFormData } from "@/components/settings/RemoteSandboxes";
import type { TestSandboxResult } from "@/lib/api";

const RUNTIME_TYPES: readonly { value: "docker" | "slurm"; label: string }[] = [
  { value: "docker", label: "Docker" },
  { value: "slurm", label: "Slurm" },
];

const DOCKER_PLACEHOLDER =
  "source /etc/profile && docker run --rm -p 127.0.0.1:8923:8923 ghcr.io/signalpilot-labs/autofyn-sandbox:stable";

interface SlurmFields {
  partition: string;
  cpus: string;
  memory: string;
  gpu_gres: string;
  work_dir: string;
}

const EMPTY_SLURM: SlurmFields = {
  partition: "",
  cpus: "",
  memory: "",
  gpu_gres: "",
  work_dir: "",
};

function buildSlurmCmd(s: SlurmFields): string {
  const gres = s.gpu_gres.trim() ? ` --gres=gpu:${s.gpu_gres.trim()}` : "";
  const nv = s.gpu_gres.trim() ? " --nv" : "";
  const partition = s.partition.trim() || "PARTITION";
  const cpus = s.cpus.trim() || "CPUS";
  const mem = s.memory.trim() || "MEMORY";
  const workDir = s.work_dir.trim() || "WORK_DIR";
  return (
    `source /etc/profile && module load apptainer && ` +
    `srun --job-name=autofyn -p ${partition} -n 1 --cpus-per-task=${cpus} --mem=${mem}${gres} ` +
    `bash -c 'W=${workDir}/autofyn_runs/$AF_RUN_KEY && mkdir -p $W && ` +
    `apptainer exec${nv} --overlay $W --pwd /opt/autofyn -B $HOME ~/.autofyn/sandbox.sif python3 -m server; rm -rf $W'`
  );
}

function parseSlurmCmd(cmd: string): SlurmFields | null {
  if (!cmd.includes("srun") || !cmd.includes("apptainer")) return null;
  const partition = cmd.match(/-p\s+(\S+)/)?.[1] ?? "";
  const cpus = cmd.match(/--cpus-per-task=(\S+)/)?.[1] ?? "4";
  const memory = cmd.match(/--mem=(\S+)/)?.[1] ?? "16G";
  const gresMatch = cmd.match(/--gres=gpu:(\S+)/);
  const gpu_gres = gresMatch?.[1] ?? "";
  const workDirMatch = cmd.match(/W=(\S+?)\/autofyn_runs/);
  const work_dir = workDirMatch?.[1] ?? "";
  return { partition, cpus, memory, gpu_gres, work_dir };
}

interface RemoteSandboxFormProps {
  data: SandboxFormData;
  onChange: (data: SandboxFormData) => void;
  onSave: (data: SandboxFormData) => Promise<void>;
  onTest: (() => Promise<TestSandboxResult>) | null;
  onCancel: () => void;
  saving: boolean;
  isEdit: boolean;
}

function FormField(props: {
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
      </label>
      {props.children}
      {props.hint && (
        <p className="text-content text-text-dim mt-0.5">{props.hint}</p>
      )}
    </div>
  );
}

const INPUT_CLASS =
  "w-full bg-black/30 border border-border rounded px-2.5 py-1.5 text-content font-mono text-accent-hover placeholder:text-text-secondary focus-visible:outline-none focus-visible:border-[#00ff88]/30";

function formatTestResult(result: TestSandboxResult): { text: string; ok: boolean } {
  if (result.ok) {
    return { text: "Connected", ok: true };
  }
  const failed = result.checks.filter((c) => !c.ok);
  const messages = failed.map((c) => `${c.name}: ${c.detail}`);
  return { text: messages.join(", "), ok: false };
}

export function RemoteSandboxForm({
  data,
  onChange,
  onSave,
  onTest,
  onCancel,
  saving,
  isEdit,
}: RemoteSandboxFormProps): React.ReactElement {
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestSandboxResult | null>(null);
  const [testError, setTestError] = useState<string | null>(null);

  const initialSlurm = data.type === "slurm" && data.default_start_cmd
    ? parseSlurmCmd(data.default_start_cmd) ?? EMPTY_SLURM
    : EMPTY_SLURM;
  const [slurm, setSlurm] = useState<SlurmFields>(initialSlurm);
  const [cmdManuallyEdited, setCmdManuallyEdited] = useState(false);

  const update = (patch: Partial<SandboxFormData>): void => {
    onChange({ ...data, ...patch });
  };

  const updateSlurm = useCallback((patch: Partial<SlurmFields>): void => {
    const next = { ...slurm, ...patch };
    setSlurm(next);
    setCmdManuallyEdited(false);
    update({ default_start_cmd: buildSlurmCmd(next), work_dir: next.work_dir });
  }, [slurm, data]);

  const handleSubmit = (): void => {
    void onSave(data);
  };

  const handleTest = async (): Promise<void> => {
    if (!onTest) return;
    setTesting(true);
    setTestResult(null);
    setTestError(null);
    try {
      const result = await onTest();
      setTestResult(result);
    } catch (e) {
      setTestError(e instanceof Error ? e.message : "Test failed");
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="p-3 bg-white/[0.02] border border-border rounded-lg space-y-3 mb-3 relative">
      <button
        onClick={onCancel}
        className="absolute top-2.5 right-2.5 text-text-secondary hover:text-[#ff4444] transition-colors"
        title="Close"
      >
        <IconX />
      </button>
      <div className="grid grid-cols-2 gap-3">
        <FormField label="Name" required>
          <input
            type="text"
            value={data.name}
            onChange={(e) => update({ name: e.target.value })}
            placeholder="gpu-cluster-1"
            className={INPUT_CLASS}
          />
        </FormField>
        <FormField label="SSH" required>
          <input
            type="text"
            value={data.ssh_target}
            onChange={(e) => update({ ssh_target: e.target.value })}
            placeholder="user@hostname"
            className={INPUT_CLASS}
          />
        </FormField>
      </div>

      <FormField label="Runtime">
        <div className="flex items-center bg-black/30 border border-border rounded-full p-0.5 w-fit">
          {RUNTIME_TYPES.map((t) => (
            <button
              key={t.value}
              type="button"
              onClick={() => {
                update({ type: t.value });
                if (t.value === "slurm" && !cmdManuallyEdited) {
                  update({ type: t.value, default_start_cmd: buildSlurmCmd(slurm) });
                }
              }}
              className={clsx(
                "px-3 py-1 rounded-full text-content transition-all",
                data.type === t.value
                  ? "bg-[#00ff88]/[0.12] text-[#00ff88] font-medium"
                  : "text-text-dim hover:text-text-secondary",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
      </FormField>

      {data.type === "slurm" && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <FormField label="Partition" required>
              <input
                type="text"
                value={slurm.partition}
                onChange={(e) => updateSlurm({ partition: e.target.value })}
                placeholder="gpu, normal, etc."
                className={INPUT_CLASS}
              />
            </FormField>
            <FormField label="AutoFyn Work Directory" required>
              <input
                type="text"
                value={slurm.work_dir}
                onChange={(e) => updateSlurm({ work_dir: e.target.value })}
                placeholder="~/scratch"
                className={INPUT_CLASS}
              />
            </FormField>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <FormField label="CPUs" required>
              <input
                type="text"
                value={slurm.cpus}
                onChange={(e) => updateSlurm({ cpus: e.target.value })}
                placeholder="4"
                className={INPUT_CLASS}
              />
            </FormField>
            <FormField label="Memory" required>
              <input
                type="text"
                value={slurm.memory}
                onChange={(e) => updateSlurm({ memory: e.target.value })}
                placeholder="16G"
                className={INPUT_CLASS}
              />
            </FormField>
            <FormField label="GPU">
              <input
                type="text"
                value={slurm.gpu_gres}
                onChange={(e) => updateSlurm({ gpu_gres: e.target.value })}
                placeholder="a100:2"
                className={INPUT_CLASS}
              />
            </FormField>
          </div>
        </>
      )}

      <FormField label="Start Command" hint={data.type === "slurm" ? "Auto-generated from fields above. Edit directly for custom flags." : undefined}>
        <CodeTextarea
          value={data.default_start_cmd}
          onChange={(v) => {
            update({ default_start_cmd: v });
            setCmdManuallyEdited(true);
          }}
          placeholder={data.type === "docker" ? DOCKER_PLACEHOLDER : ""}
          rows={3}
        />
      </FormField>

      <div className="grid grid-cols-2 gap-3">
        <FormField label="Startup Timeout (s)" hint="Max wait for sandbox to be ready.">
          <input
            type="number"
            value={data.queue_timeout}
            onChange={(e) => update({ queue_timeout: Number(e.target.value) })}
            className={INPUT_CLASS}
          />
        </FormField>
        <FormField label="Inactivity Timeout (s)" hint="Sandbox exits after this long idle.">
          <input
            type="number"
            value={data.heartbeat_timeout}
            onChange={(e) => update({ heartbeat_timeout: Number(e.target.value) })}
            className={INPUT_CLASS}
          />
        </FormField>
      </div>

      <div className="flex items-center gap-2 pt-1">
        <Button
          variant="success"
          size="md"
          onClick={handleSubmit}
          disabled={saving || !data.name.trim() || !data.ssh_target.trim()}
        >
          {saving ? "Saving..." : isEdit ? "Update" : "Create"}
        </Button>
        {onTest && (
          <Button
            variant="ghost"
            size="md"
            onClick={() => void handleTest()}
            disabled={testing}
          >
            {testing ? "Testing..." : "Test"}
          </Button>
        )}
      </div>
      {testResult && (() => {
        const { text, ok } = formatTestResult(testResult);
        return (
          <p className={clsx("text-content", ok ? "text-[#00ff88]" : "text-[#ff4444]")}>
            {text}
          </p>
        );
      })()}
      {testError && (
        <p className="text-content text-[#ff4444]">{testError}</p>
      )}
    </div>
  );
}
