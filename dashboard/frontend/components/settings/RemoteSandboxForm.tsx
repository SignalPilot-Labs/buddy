"use client";

/**Inline form for creating or editing a remote sandbox configuration.*/

import { clsx } from "clsx";
import { Button } from "@/components/ui/Button";
import type { SandboxFormData } from "@/components/settings/RemoteSandboxes";

const RUNTIME_TYPES: readonly { value: "docker" | "slurm"; label: string }[] = [
  { value: "docker", label: "Docker" },
  { value: "slurm", label: "Slurm" },
];

const START_CMD_PLACEHOLDERS: Record<string, string> = {
  docker: "docker run --rm -v $HOME:$HOME ghcr.io/signalpilot-labs/autofyn-sandbox:stable python3 -m sandbox.server",
  slurm: "srun -p PARTITION --mem=4G singularity exec -B $HOME ~/.autofyn/sandbox.sif python3 -m sandbox.server",
};

interface RemoteSandboxFormProps {
  data: SandboxFormData;
  onChange: (data: SandboxFormData) => void;
  onSave: (data: SandboxFormData) => Promise<void>;
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
        <p className="text-body text-text-dim mt-0.5">{props.hint}</p>
      )}
    </div>
  );
}

const INPUT_CLASS =
  "w-full bg-black/30 border border-border rounded px-2.5 py-1.5 text-content font-mono text-accent-hover placeholder:text-text-secondary focus-visible:outline-none focus-visible:border-[#00ff88]/30";

export function RemoteSandboxForm({
  data,
  onChange,
  onSave,
  onCancel,
  saving,
  isEdit,
}: RemoteSandboxFormProps): React.ReactElement {
  const update = (patch: Partial<SandboxFormData>): void => {
    onChange({ ...data, ...patch });
  };

  const handleSubmit = (): void => {
    void onSave(data);
  };

  return (
    <div className="p-3 bg-white/[0.02] border border-border rounded-lg space-y-3 mb-3">
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
        <textarea
          value={data.default_start_cmd}
          onChange={(e) => update({ default_start_cmd: e.target.value })}
          placeholder={START_CMD_PLACEHOLDERS[data.type]}
          rows={2}
          className={`${INPUT_CLASS} resize-y`}
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

      <div className="flex gap-2 pt-1">
        <Button variant="ghost" size="md" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          variant="success"
          size="md"
          onClick={handleSubmit}
          disabled={saving || !data.name.trim() || !data.ssh_target.trim()}
        >
          {saving ? "Saving..." : isEdit ? "Update" : "Create"}
        </Button>
      </div>
    </div>
  );
}
