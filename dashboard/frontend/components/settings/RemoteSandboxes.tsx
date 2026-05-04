"use client";

/**Settings section for managing remote sandbox configurations.*/

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/Button";
import { fetchRemoteSandboxes, createRemoteSandbox, updateRemoteSandbox, deleteRemoteSandbox } from "@/lib/api";
import type { RemoteSandboxConfig } from "@/lib/api";
import { RemoteSandboxForm } from "@/components/settings/RemoteSandboxForm";

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
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"));
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
      <div className="flex items-center justify-between mb-1">
        <label className="text-content font-semibold text-accent-hover">
          Remote Sandboxes
        </label>
        <span className="text-content text-text-secondary">
          {sandboxes.length} configured
        </span>
      </div>

      <p className="text-body text-text-muted mb-3">
        Run on remote machines via SSH.{" "}
        <a
          href="https://github.com/SignalPilot-Labs/AutoFyn#remote-sandboxes"
          target="_blank"
          rel="noopener noreferrer"
          className="text-[#88ccff] hover:underline"
        >
          Setup guide
        </a>
      </p>

      <div className="space-y-1.5 mb-3">
        <AnimatePresence>
          {sandboxes.map((s) => (
            <motion.div
              key={s.id}
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="flex items-center gap-2 px-2.5 py-2 bg-black/30 rounded border border-border group"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-text-secondary shrink-0">
                <rect x="2" y="3" width="20" height="14" rx="2" />
                <line x1="8" y1="21" x2="16" y2="21" />
                <line x1="12" y1="17" x2="12" y2="21" />
              </svg>
              <span className="text-content font-mono text-accent-hover flex-1 min-w-0 truncate">
                {s.name}
              </span>
              <span className="text-content text-text-secondary shrink-0">
                {s.ssh_target}
              </span>
              <span className="text-caption uppercase tracking-wider px-1.5 py-0.5 rounded bg-[#88ccff]/[0.08] text-[#88ccff] shrink-0">
                {s.type}
              </span>
              <button
                onClick={() => handleEdit(s)}
                className="text-content text-text-secondary hover:text-[#00ff88] transition-colors opacity-0 group-hover:opacity-100 focus-visible:opacity-100 shrink-0"
              >
                Edit
              </button>
              <button
                onClick={() => void handleDelete(s)}
                className="text-text-secondary hover:text-[#ff4444] transition-colors opacity-0 group-hover:opacity-100 focus-visible:opacity-100 shrink-0"
                title="Delete sandbox"
              >
                <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <line x1="2" y1="2" x2="8" y2="8" /><line x1="8" y1="2" x2="2" y2="8" />
                </svg>
              </button>
            </motion.div>
          ))}
        </AnimatePresence>

        {sandboxes.length === 0 && !showForm && (
          <div className="px-2.5 py-3 text-content text-text-secondary text-center">
            No remote sandboxes configured.
          </div>
        )}
      </div>

      {showForm && (
        <RemoteSandboxForm
          data={formData}
          onChange={setFormData}
          onSave={handleSave}
          onCancel={handleCancel}
          saving={saving}
          isEdit={editingId !== null}
        />
      )}

      {!showForm && (
        <Button variant="success" size="md" onClick={handleAdd}>
          Add Sandbox
        </Button>
      )}

      {error && (
        <p className="mt-1.5 text-content text-[#ff4444]">{error}</p>
      )}
    </div>
  );
}
