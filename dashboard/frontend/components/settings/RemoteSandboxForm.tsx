"use client";

/**Inline form for creating or editing a remote sandbox configuration.*/

import { clsx } from "clsx";
import { Button } from "@/components/ui/Button";
import type { SandboxFormData } from "@/components/settings/RemoteSandboxes";

const SANDBOX_TYPES: readonly ("docker" | "slurm")[] = ["docker", "slurm"];

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
  children: React.ReactNode;
}): React.ReactElement {
  return (
    <div>
      <label className="text-caption uppercase tracking-wider text-text-dim mb-1 block">
        {props.label}
      </label>
      {props.children}
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
        <FormField label="SSH Target">
          <input
            type="text"
            value={data.ssh_target}
            onChange={(e) => update({ ssh_target: e.target.value })}
            placeholder="user@host"
            className={INPUT_CLASS}
          />
        </FormField>
      </div>

      <FormField label="Type">
        <div className="flex items-center bg-black/30 border border-border rounded-full p-0.5 w-fit">
          {SANDBOX_TYPES.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => update({ type: t })}
              className={clsx(
                "px-3 py-1 rounded-full text-content capitalize transition-all",
                data.type === t
                  ? "bg-[#00ff88]/[0.12] text-[#00ff88] font-medium"
                  : "text-text-dim hover:text-text-secondary",
              )}
            >
              {t}
            </button>
          ))}
        </div>
      </FormField>

      <FormField label="Default Start Command">
        <textarea
          value={data.default_start_cmd}
          onChange={(e) => update({ default_start_cmd: e.target.value })}
          placeholder="docker run --rm -it my-sandbox:latest"
          rows={2}
          className={`${INPUT_CLASS} resize-y`}
        />
      </FormField>

      <FormField label="Secret Dir">
        <input
          type="text"
          value={data.secret_dir}
          onChange={(e) => update({ secret_dir: e.target.value })}
          placeholder="~/.autofyn/secrets"
          className={INPUT_CLASS}
        />
      </FormField>

      <div className="grid grid-cols-2 gap-3">
        <FormField label="Queue Timeout (s)">
          <input
            type="number"
            value={data.queue_timeout}
            onChange={(e) => update({ queue_timeout: Number(e.target.value) })}
            className={INPUT_CLASS}
          />
        </FormField>
        <FormField label="Heartbeat Timeout (s)">
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
