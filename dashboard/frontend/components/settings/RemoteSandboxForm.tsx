"use client";

/**Inline form for creating or editing a remote sandbox configuration.*/

import { useState } from "react";
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

const START_CMD_PLACEHOLDERS: Record<string, string> = {
  docker: "source /etc/profile && docker run --rm -p 127.0.0.1:8923:8923 ghcr.io/signalpilot-labs/autofyn-sandbox:stable",
  slurm: "source /etc/profile && module load apptainer && srun --job-name=autofyn -p PARTITION -n 1 --cpus-per-task=4 --mem=16G bash -c 'W=~/scratch/autofyn_runs/$AF_RUN_KEY && mkdir -p $W && apptainer exec --overlay $W --pwd /opt/autofyn -B $HOME ~/.autofyn/sandbox.sif python3 -m server; rm -rf $W'",
};

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
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <div>
      <label className="text-content uppercase tracking-[0.15em] text-text-muted font-semibold mb-1 block">
        {props.label}
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

  const update = (patch: Partial<SandboxFormData>): void => {
    onChange({ ...data, ...patch });
  };

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
        <FormField label="Name">
          <input
            type="text"
            value={data.name}
            onChange={(e) => update({ name: e.target.value })}
            placeholder="gpu-cluster-1"
            className={INPUT_CLASS}
          />
        </FormField>
        <FormField label="SSH">
          <input
            type="text"
            value={data.ssh_target}
            onChange={(e) => update({ ssh_target: e.target.value })}
            placeholder="ssh user@hostname"
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
              onClick={() => update({ type: t.value })}
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

      <FormField label="Start Command">
        <CodeTextarea
          value={data.default_start_cmd}
          onChange={(v) => update({ default_start_cmd: v })}
          placeholder={START_CMD_PLACEHOLDERS[data.type]}
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
