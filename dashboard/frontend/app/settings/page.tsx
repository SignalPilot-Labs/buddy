"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import Image from "next/image";
import Link from "next/link";
import { fetchSettings, fetchSettingsStatus, updateSettings, fetchPoolTokens, addPoolToken, removePoolToken } from "@/lib/settings-api";
import { fetchRepos } from "@/lib/api";
import type { Settings, SettingsStatus, RepoInfo, PoolToken } from "@/lib/types";
import { LOCALSTORAGE_EXTENDED_CONTEXT_KEY } from "@/lib/constants";
import { Button } from "@/components/ui/Button";
import { TokenPoolSection } from "@/components/settings/TokenPoolSection";
import { RepoListSection } from "@/components/settings/RepoListSection";
import { SecurityBanner } from "@/components/settings/SecurityBanner";
import { CredentialField } from "@/components/settings/CredentialField";
import type { CredentialFieldConfig } from "@/components/settings/CredentialField";
import { clsx } from "clsx";
import { apiFetch } from "@/lib/fetch";

type StringSettingsKey = "claude_token" | "git_token" | "github_repo" | "max_budget_usd";

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

function ExtendedContextSetting() {
  const [enabled, setEnabled] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem(LOCALSTORAGE_EXTENDED_CONTEXT_KEY) === "1";
    }
    return false;
  });

  const toggle = () => {
    const next = !enabled;
    setEnabled(next);
    localStorage.setItem(LOCALSTORAGE_EXTENDED_CONTEXT_KEY, next ? "1" : "0");
  };

  return (
    <div className="p-4 bg-white/[0.01] border border-[#1a1a1a] rounded-lg">
      <label
        className="text-[10px] font-semibold text-[#ccc] flex items-center gap-2 cursor-pointer select-none"
        onClick={toggle}
      >
        <span
          className={clsx(
            "flex items-center justify-center h-3.5 w-3.5 rounded border transition-all",
            enabled ? "bg-[#00ff88] border-[#00ff88]" : "border-[#666] bg-transparent"
          )}
        >
          {enabled && (
            <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="white" strokeWidth="1.5">
              <polyline points="1.5 4 3 5.5 6.5 2" />
            </svg>
          )}
        </span>
        Always Enable Extended Context (1M)
      </label>
      <p className="mt-1.5 text-[10px] text-[#999] leading-relaxed ml-5">
        When enabled, all new runs will use extended 1M context by default.
        This uses more of your daily quota but supports larger context windows.
        You can override this per-run in the launch modal.
      </p>
    </div>
  );
}

export default function SettingsPage() {
  const [status, setStatus] = useState<SettingsStatus | null>(null);
  const [settings, setSettings] = useState<Settings>({});
  const [edits, setEdits] = useState<Partial<Record<StringSettingsKey, string>>>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
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

  useEffect(() => {
    Promise.all([fetchSettingsStatus(), fetchSettings(), fetchRepos(), fetchPoolTokens()]).then(
      ([s, cfg, r, t]) => {
        setStatus(s);
        setSettings(cfg);
        setRepos(r);
        setTokens(t);
      }
    ).catch((e) => { console.error("Settings load failed:", e); setError("Failed to load settings"); });
  }, []);

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
      setTimeout(() => setSaved(false), 2000);
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
    try {
      const res = await apiFetch(`/api/repos/${encodeURIComponent(slug)}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setRepos(await fetchRepos());
    } catch (err) {
      console.error("Failed to remove repo:", err);
    }
  };

  const handleSetActive = async (slug: string) => {
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
      console.error("Failed to set active repo:", err);
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
    <div className="min-h-screen bg-[#0a0a0a] text-[#e8e8e8] overflow-y-auto">
      <div className="border-b border-[#1a1a1a]">
        <div className="max-w-2xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-2 text-[#999] hover:text-[#888] transition-colors">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                <polyline points="8 2 4 6 8 10" />
              </svg>
              <span className="text-[10px]">Dashboard</span>
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
              "flex items-center gap-1.5 px-2 py-1 rounded text-[10px] font-medium",
              status.configured ? "bg-[#00ff88]/[0.06] text-[#00ff88]" : "bg-[#ffaa00]/[0.06] text-[#ffaa00]"
            )}>
              <div className={clsx("w-1.5 h-1.5 rounded-full", status.configured ? "bg-[#00ff88]" : "bg-[#ffaa00]")} />
              {status.configured ? "Configured" : "Setup Required"}
            </div>
          )}
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-6 py-8">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="space-y-6">
          <SecurityBanner />

          <TokenPoolSection
            tokens={tokens}
            newToken={newToken}
            addingToken={addingToken}
            tokenError={tokenError}
            onNewTokenChange={(v) => { setNewToken(v); setTokenError(null); }}
            onAddToken={handleAddToken}
            onRemoveToken={handleRemoveToken}
          />

          <ExtendedContextSetting />

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

          <div className="flex items-center justify-between pt-2">
            <div>
              {error && <p className="text-[10px] text-[#ff4444]">{error}</p>}
              {saved && (
                <motion.p initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-[10px] text-[#00ff88]">
                  Settings saved and encrypted
                </motion.p>
              )}
            </div>
            <Button variant="success" size="md" onClick={handleSave} disabled={saving || !hasEdits}>
              {saving ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
