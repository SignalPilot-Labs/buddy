/**Settings section for managing remote sandbox configurations.*/

"use client";

import { useState, useEffect } from "react";
import { AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/Button";
import { ListRow } from "@/components/ui/ListRow";
import { IconServer, IconPencil, IconPlus } from "@/components/ui/icons";
import { fetchRemoteSandboxes, createRemoteSandbox, updateRemoteSandbox, deleteRemoteSandbox, testRemoteSandbox } from "@/lib/api";
import type { RemoteSandboxConfig } from "@/lib/api";
import { RemoteSandboxForm } from "@/components/settings/RemoteSandboxForm";
import CodeBlock from "@/components/ui/CodeBlock";

export interface SandboxFormData {
  name: string;
  ssh_target: string;
  type: "slurm" | "docker";
  default_start_cmd: string;
  queue_timeout: number;
  heartbeat_timeout: number;
}

const EMPTY_FORM: SandboxFormData = {
  name: "",
  ssh_target: "",
  type: "docker",
  default_start_cmd: "",
  queue_timeout: 1800,
  heartbeat_timeout: 1800,
};

function formFromConfig(s: RemoteSandboxConfig): SandboxFormData {
  return {
    name: s.name,
    ssh_target: s.ssh_target,
    type: s.type,
    default_start_cmd: s.default_start_cmd,
    queue_timeout: s.queue_timeout,
    heartbeat_timeout: s.heartbeat_timeout,
  };
}

export function RemoteSandboxes(): React.ReactElement {
  const [sandboxes, setSandboxes] = useState<RemoteSandboxConfig[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<SandboxFormData>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchRemoteSandboxes()
      .then(setSandboxes)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"));
  }, []);

  const handleAdd = (): void => {
    setFormData(EMPTY_FORM);
    setEditingId(null);
    setShowForm(true);
    setError(null);
  };

  const handleEdit = (s: RemoteSandboxConfig): void => {
    setFormData(formFromConfig(s));
    setEditingId(s.id);
    setShowForm(true);
    setError(null);
  };

  const handleDelete = async (s: RemoteSandboxConfig): Promise<void> => {
    setError(null);
    try {
      await deleteRemoteSandbox(s.id);
      setSandboxes(await fetchRemoteSandboxes());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete");
    }
  };

  const handleCancel = (): void => {
    setShowForm(false);
    setEditingId(null);
    setError(null);
  };

  const handleSave = async (data: SandboxFormData): Promise<void> => {
    setSaving(true);
    setError(null);
    try {
      if (editingId !== null) {
        await updateRemoteSandbox(editingId, data);
      } else {
        await createRemoteSandbox(data);
      }
      setSandboxes(await fetchRemoteSandboxes());
      setShowForm(false);
      setEditingId(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-4 bg-white/[0.01] border border-border rounded-lg">
      <div className="flex items-center justify-between mb-3">
        <label className="text-content font-semibold text-accent-hover">
          Remote Sandboxes
        </label>
        <span className="text-content text-text-secondary">
          {sandboxes.length} configured
        </span>
      </div>

      <div className="space-y-1.5 mb-3">
        <AnimatePresence>
          {sandboxes.map((s) => (
            <ListRow key={s.id} layoutId={s.id} onDelete={() => void handleDelete(s)} deleteTitle="Delete sandbox">
              <IconServer className="text-text-secondary shrink-0" />
              <span className="text-content font-mono text-accent-hover flex-1 min-w-0 truncate">
                {s.name}
              </span>
              <span className="text-content text-text-secondary shrink-0">
                {s.ssh_target}
              </span>
              <span className="text-content uppercase tracking-wider px-1.5 py-0.5 rounded bg-[#88ccff]/[0.08] text-[#88ccff] shrink-0">
                {s.type}
              </span>
              <button
                onClick={() => handleEdit(s)}
                className="text-text-secondary hover:text-[#00ff88] transition-colors shrink-0"
                title="Edit sandbox"
              >
                <IconPencil size={11} />
              </button>
            </ListRow>
          ))}
        </AnimatePresence>

        {sandboxes.length === 0 && !showForm && (
          <div className="px-2.5 py-3 text-content text-text-secondary text-center">
            No remote sandboxes yet
          </div>
        )}
      </div>

      {showForm && (
        <RemoteSandboxForm
          data={formData}
          onChange={setFormData}
          onSave={handleSave}
          onTest={editingId !== null ? () => testRemoteSandbox(editingId) : null}
          onCancel={handleCancel}
          saving={saving}
          isEdit={editingId !== null}
        />
      )}

      <Button variant="success" size="md" icon={<IconPlus size={10} />} onClick={handleAdd}>
        Add Sandbox
      </Button>

      {error && (
        <p className="mt-1.5 text-content text-[#ff4444]">{error}</p>
      )}

      <p className="mt-2 text-content text-text-dim">
        Setup (run once on the remote):
      </p>
      <CodeBlock
        code="source /etc/profile && module load apptainer && mkdir -p ~/.autofyn && apptainer pull ~/.autofyn/sandbox.sif docker://ghcr.io/signalpilot-labs/autofyn-sandbox:stable"
        className="mt-1"
      />
    </div>
  );
}
