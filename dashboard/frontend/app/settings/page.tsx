"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { fetchSettings, fetchSettingsStatus, updateSettings, fetchPoolTokens, addPoolToken, removePoolToken } from "@/lib/settings-api";
import { fetchRepos } from "@/lib/api";
import type { Settings, SettingsStatus, RepoInfo, PoolToken } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { getApiBase } from "@/lib/constants";
import { useTranslation } from "@/hooks/useTranslation";
import { SettingsHeader } from "@/components/settings/SettingsHeader";
import { SecurityInfoPanel } from "@/components/settings/SecurityInfoPanel";
import { TokenPoolPanel } from "@/components/settings/TokenPoolPanel";
import { RepositoriesPanel } from "@/components/settings/RepositoriesPanel";
import { CredentialFieldCard, FIELDS } from "@/components/settings/CredentialFieldCard";
import type { FieldConfig } from "@/components/settings/CredentialFieldCard";

export default function SettingsPage(): React.ReactElement {
  const [status, setStatus] = useState<SettingsStatus | null>(null);
  const [settings, setSettings] = useState<Settings>({});
  const [edits, setEdits] = useState<Partial<Settings>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});
  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const [tokens, setTokens] = useState<PoolToken[]>([]);
  const { t } = useTranslation();

  useEffect(() => {
    void Promise.all([fetchSettingsStatus(), fetchSettings(), fetchRepos(), fetchPoolTokens()]).then(
      ([s, cfg, r, tok]) => {
        setStatus(s);
        setSettings(cfg);
        setRepos(r);
        setTokens(tok);
      }
    );
  }, []);

  const handleSave = async (): Promise<void> => {
    const updates: Partial<Settings> = {};
    for (const [k, v] of Object.entries(edits)) {
      if (v && v.trim()) {
        updates[k as keyof Settings] = v.trim();
      }
    }
    if (Object.keys(updates).length === 0) return;
    setSaving(true);
    setError(null);
    try {
      await updateSettings(updates);
      const [s, cfg] = await Promise.all([fetchSettingsStatus(), fetchSettings()]);
      setStatus(s);
      setSettings(cfg);
      setEdits({});
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : t.settings.failedToSave);
    } finally {
      setSaving(false);
    }
  };

  const handleAddRepo = async (slug: string): Promise<void> => {
    await updateSettings({ github_repo: slug });
    const r = await fetchRepos();
    setRepos(r);
    const [s, cfg] = await Promise.all([fetchSettingsStatus(), fetchSettings()]);
    setStatus(s);
    setSettings(cfg);
  };

  const handleRemoveRepo = async (slug: string): Promise<void> => {
    const res = await fetch(`${getApiBase()}/api/repos/${encodeURIComponent(slug)}`, {
      method: "DELETE",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const r = await fetchRepos();
    setRepos(r);
  };

  const handleSetActive = async (slug: string): Promise<void> => {
    const res = await fetch(`${getApiBase()}/api/repos/active`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo: slug }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const [s, cfg] = await Promise.all([fetchSettingsStatus(), fetchSettings()]);
    setStatus(s);
    setSettings(cfg);
  };

  const handleAddToken = async (token: string): Promise<void> => {
    await addPoolToken(token);
    setTokens(await fetchPoolTokens());
  };

  const handleRemoveToken = async (index: number): Promise<void> => {
    await removePoolToken(index);
    setTokens(await fetchPoolTokens());
  };

  const handleEditChange = (key: keyof Settings, value: string): void => {
    setEdits({ ...edits, [key]: value });
  };

  const handleCancelEdit = (key: keyof Settings): void => {
    const next = { ...edits };
    delete next[key];
    setEdits(next);
  };

  const handleToggleShow = (key: keyof Settings): void => {
    setShowSecrets({ ...showSecrets, [key]: !showSecrets[key] });
  };

  const hasEdits = Object.values(edits).some((v) => v && v.trim());
  const activeRepo = settings.github_repo || "";

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-[#e8e8e8]">
      <SettingsHeader status={status} />
      <div className="max-w-2xl mx-auto px-6 py-8">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-6"
        >
          <SecurityInfoPanel />
          <TokenPoolPanel tokens={tokens} onAdd={handleAddToken} onRemove={handleRemoveToken} />
          <RepositoriesPanel
            repos={repos}
            activeRepo={activeRepo}
            onAdd={handleAddRepo}
            onRemove={handleRemoveRepo}
            onSetActive={handleSetActive}
          />
          {FIELDS.map((field: FieldConfig) => (
            <CredentialFieldCard
              key={field.key}
              field={field}
              currentValue={settings[field.key] || ""}
              editValue={edits[field.key]}
              isSet={field.statusKey ? (status?.[field.statusKey] ?? false) : false}
              show={showSecrets[field.key] || false}
              onEditChange={handleEditChange}
              onCancelEdit={handleCancelEdit}
              onToggleShow={handleToggleShow}
            />
          ))}
          <div className="flex items-center justify-between pt-2">
            <div>
              {error && (
                <p className="text-[10px] text-[#ff4444]">{error}</p>
              )}
              {saved && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-[10px] text-[#00ff88]"
                >
                  {t.settings.settingsSaved}
                </motion.p>
              )}
            </div>
            <Button
              variant="success"
              size="md"
              onClick={() => void handleSave()}
              disabled={saving || !hasEdits}
            >
              {saving ? t.settings.saving : t.settings.saveChanges}
            </Button>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
