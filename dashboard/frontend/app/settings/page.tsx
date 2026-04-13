"use client";

import { useState, useEffect, useRef } from "react";
import { motion } from "framer-motion";
import Image from "next/image";
import Link from "next/link";
import { fetchSettings, fetchSettingsStatus, updateSettings, fetchPoolTokens, addPoolToken, removePoolToken } from "@/lib/settings-api";
import { fetchRepos } from "@/lib/api";
import type { Settings, SettingsStatus, RepoInfo, PoolToken } from "@/lib/types";
import { loadStoredModel, saveStoredModel } from "@/lib/constants";
import type { ModelId } from "@/lib/constants";
import { Button } from "@/components/ui/Button";
import { ModelSelector } from "@/components/ui/ModelSelector";
import { TokenPoolSection } from "@/components/settings/TokenPoolSection";
import { RepoListSection } from "@/components/settings/RepoListSection";
import { SecurityBanner } from "@/components/settings/SecurityBanner";
import { CredentialField } from "@/components/settings/CredentialField";
import type { CredentialFieldConfig } from "@/components/settings/CredentialField";
import { clsx } from "clsx";
import { apiFetch } from "@/lib/fetch";

type StringSettingsKey = "git_token" | "github_repo" | "max_budget_usd";

const FIELDS: CredentialFieldConfig[] = [
  {
    key: "git_token",
    label: "GitHub Personal Access Token",
    statusKey: "has_git_token",
    placeholder: "ghp_...",
    secret: true,
    helpText:
      "GitHub Settings > Developer settings > Personal access tokens > Fine-grained tokens. Grant Contents + Pull requests read/write on your repo.",
  },
  {
    key: "max_budget_usd",
    label: "Default Max Budget (USD)",
    placeholder: "50",
    secret: false,
    helpText: "Optional. Default max spend per run. Can be overridden when starting a run.",
  },
];

function DefaultModelSetting(): React.ReactElement {
  const [selectedModel, setSelectedModel] = useState<ModelId>(loadStoredModel);
  const [modelSaveError, setModelSaveError] = useState<string | null>(null);

  const handleSelect = async (id: ModelId): Promise<void> => {
    setSelectedModel(id);
    setModelSaveError(null);
    saveStoredModel(id);
    try {
      await updateSettings({ default_model: id });
    } catch (e) {
      setModelSaveError(e instanceof Error ? e.message : "Failed to save model preference");
    }
  };

  return (
    <div className="p-4 bg-white/[0.01] border border-border rounded-lg">
      <div className="mb-3">
        <h3 className="text-[14px] font-semibold text-accent-hover uppercase tracking-[0.12em]">Default Model</h3>
        <p className="mt-1 text-[13px] text-text-muted leading-relaxed">
          Select the Claude model to use for new runs. Saved as your default preference.
        </p>
      </div>
      <ModelSelector value={selectedModel} onChange={handleSelect} />
      {modelSaveError && (
        <p className="mt-2 text-[12px] text-[#ff4444]">{modelSaveError}</p>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const [status, setStatus] = useState<SettingsStatus | null>(null);
  const [settings, setSettings] = useState<Settings>({});
  const [edits, setEdits] = useState<Partial<Record<StringSettingsKey, string>>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const savedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showSecrets, setShowSecrets] = useState<Record<string, boolean>>({});

  const [repos, setRepos] = useState<RepoInfo[]>([]);
  const [newRepo, setNewRepo] = useState("");
  const [addingRepo, setAddingRepo] = useState(false);
  const [repoError, setRepoError] = useState<string | null>(null);

  const [tokens, setTokens] = useState<PoolToken[]>([]);
  const [newToken, setNewToken] = useState("");
  const [addingToken, setAddingToken] = useState(false);
  const [tokenError, setTokenError] = useState<string | null>(null);

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    Promise.all([fetchSettingsStatus(), fetchSettings(), fetchRepos(), fetchPoolTokens()]).then(
      ([s, cfg, r, t]) => {
        if (cancelled) return;
        setStatus(s);
        setSettings(cfg);
        setRepos(r);
        setTokens(t);
        setLoading(false);
      }
    ).catch((e) => {
      if (cancelled) return;
      console.error("Settings load failed:", e);
      setLoadError(e instanceof Error ? e.message : "Failed to load settings");
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [loadAttempt]);

  const handleSave = async () => {
    const updates: Partial<Record<StringSettingsKey, string>> = {};
    for (const [k, v] of Object.entries(edits)) {
      if (v && v.trim()) updates[k as StringSettingsKey] = v.trim();
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
      if (savedTimerRef.current) clearTimeout(savedTimerRef.current);
      savedTimerRef.current = setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const handleAddRepo = async () => {
    const slug = newRepo.trim();
    if (!slug) return;
    if (!/^[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+$/.test(slug)) {
      setRepoError("Use owner/repo format (e.g. my-org/my-project)");
      return;
    }
    if (repos.some((r) => r.repo === slug)) {
      setRepoError("Repository already added");
      return;
    }
    setAddingRepo(true);
    setRepoError(null);
    try {
      await updateSettings({ github_repo: slug });
      setRepos(await fetchRepos());
      setNewRepo("");
      const [s, cfg] = await Promise.all([fetchSettingsStatus(), fetchSettings()]);
      setStatus(s);
      setSettings(cfg);
    } catch (e) {
      setRepoError(e instanceof Error ? e.message : "Failed to add");
    } finally {
      setAddingRepo(false);
    }
  };

  const handleRemoveRepo = async (slug: string) => {
    setRepoError(null);
    try {
      const res = await apiFetch(`/api/repos/${encodeURIComponent(slug)}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setRepos(await fetchRepos());
    } catch (err) {
      setRepoError(err instanceof Error ? err.message : "Failed to remove repo");
    }
  };

  const handleSetActive = async (slug: string) => {
    setRepoError(null);
    try {
      const res = await apiFetch(`/api/repos/active`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repo: slug }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const [s, cfg] = await Promise.all([fetchSettingsStatus(), fetchSettings()]);
      setStatus(s);
      setSettings(cfg);
    } catch (err) {
      setRepoError(err instanceof Error ? err.message : "Failed to set active repo");
    }
  };

  const handleAddToken = async () => {
    const val = newToken.trim();
    if (!val) return;
    setAddingToken(true);
    setTokenError(null);
    try {
      await addPoolToken(val);
      setTokens(await fetchPoolTokens());
      setNewToken("");
    } catch (e) {
      setTokenError(e instanceof Error ? e.message : "Failed to add token");
    } finally {
      setAddingToken(false);
    }
  };

  const handleRemoveToken = async (index: number) => {
    try {
      await removePoolToken(index);
      setTokens(await fetchPoolTokens());
    } catch (e) {
      setTokenError(e instanceof Error ? e.message : "Failed to remove token");
    }
  };

  const hasEdits = Object.values(edits).some((v) => v && v.trim());
  const activeRepo = settings.github_repo || "";

  return (
    <div className="h-screen bg-bg-card text-text overflow-y-auto [&::-webkit-scrollbar]:w-1.5 [&::-webkit-scrollbar-thumb]:bg-border-subtle [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-track]:bg-transparent">
      <div className="border-b border-border">
        <div className="max-w-2xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2 text-text-secondary hover:text-accent-hover transition-colors">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                <polyline points="8 2 4 6 8 10" />
              </svg>
              <span className="text-[12px]">Dashboard</span>
            </Link>
            <span className="text-[#1a1a1a]">/</span>
            <div className="flex items-center gap-2">
              <div className="flex items-center justify-center h-6 w-6 rounded bg-white/[0.04] border border-white/[0.08]">
                <Image src="/logo.svg" alt="AutoFyn" width={14} height={14} />
              </div>
              <h1 className="text-[12px] font-semibold">Settings</h1>
            </div>
          </div>
          {status && (
            <div className={clsx(
              "flex items-center gap-1.5 px-2 py-1 rounded text-[12px] font-medium",
              status.configured ? "bg-[#00ff88]/[0.06] text-[#00ff88]" : "bg-[#ffaa00]/[0.06] text-[#ffaa00]"
            )}>
              <div className={clsx("w-1.5 h-1.5 rounded-full", status.configured ? "bg-[#00ff88]" : "bg-[#ffaa00]")} />
              {status.configured ? "Configured" : "Setup Required"}
            </div>
          )}
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-6 py-8">
        {loading && (
          <div className="flex items-center justify-center py-16" role="status" aria-live="polite">
            <div className="flex items-center gap-2 text-[11px] text-text-secondary">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="animate-spin">
                <circle cx="6" cy="6" r="5" stroke="#00ff88" strokeWidth="1" strokeDasharray="16 10" />
              </svg>
              Loading settings…
            </div>
          </div>
        )}

        {!loading && loadError && (
          <div className="flex flex-col items-center justify-center py-16 gap-3" role="alert">
            <p className="text-[11px] text-[#ff4444]">{loadError}</p>
            <Button variant="success" size="md" onClick={() => setLoadAttempt((n) => n + 1)}>
              Retry
            </Button>
          </div>
        )}

        {!loading && !loadError && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
            <SecurityBanner />

            {FIELDS.map((field) => (
              <CredentialField
                key={field.key}
                field={field}
                currentValue={settings[field.key] || ""}
                editValue={edits[field.key]}
                isSet={field.statusKey ? !!(status?.[field.statusKey]) : false}
                show={showSecrets[field.key] || false}
                onStartEdit={() => setEdits({ ...edits, [field.key]: "" })}
                onCancelEdit={() => { const next = { ...edits }; delete next[field.key]; setEdits(next); }}
                onEditChange={(v) => setEdits({ ...edits, [field.key]: v })}
                onToggleShow={() => setShowSecrets({ ...showSecrets, [field.key]: !showSecrets[field.key] })}
              />
            ))}

            <RepoListSection
              repos={repos}
              activeRepo={activeRepo}
              newRepo={newRepo}
              addingRepo={addingRepo}
              repoError={repoError}
              onNewRepoChange={(v) => { setNewRepo(v); setRepoError(null); }}
              onAddRepo={handleAddRepo}
              onRemoveRepo={handleRemoveRepo}
              onSetActive={handleSetActive}
            />

            <TokenPoolSection
              tokens={tokens}
              newToken={newToken}
              addingToken={addingToken}
              tokenError={tokenError}
              onNewTokenChange={(v) => { setNewToken(v); setTokenError(null); }}
              onAddToken={handleAddToken}
              onRemoveToken={handleRemoveToken}
            />

            <DefaultModelSetting />

            <div className="flex items-center justify-between pt-2">
              <div>
                {error && <p className="text-[12px] text-[#ff4444]">{error}</p>}
                {saved && (
                  <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-[12px] text-[#00ff88]">
                    Settings saved and encrypted
                  </motion.p>
                )}
              </div>
              <Button variant="success" size="md" onClick={handleSave} disabled={saving || !hasEdits}>
                {saving ? "Saving..." : "Save Changes"}
              </Button>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
