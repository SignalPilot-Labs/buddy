"use client";

import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { updateSettings, fetchSettings } from "@/lib/settings-api";
import type { Settings } from "@/lib/types";
import { Button } from "@/components/ui/Button";

const MASK_VALUE = "****";

interface EnvVarsSectionProps {
  settings: Settings;
  onSettingsChange: (settings: Settings) => void;
}

function parseEnvVarsText(text: string): Record<string, string> {
  const result: Record<string, string> = {};
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || !trimmed.includes("=")) continue;
    const eqIndex = trimmed.indexOf("=");
    const key = trimmed.slice(0, eqIndex).trim();
    const value = trimmed.slice(eqIndex + 1);
    if (key) {
      result[key] = value;
    }
  }
  return result;
}

function maskedDictToDisplayText(dict: Record<string, string>): string {
  return Object.entries(dict)
    .map(([key, value]) => {
      const displayValue = value === MASK_VALUE ? "" : value;
      return `${key}=${displayValue}`;
    })
    .join("\n");
}

function isMaskedDict(dict: Record<string, string>): boolean {
  return Object.values(dict).every((v) => v === MASK_VALUE);
}

export function EnvVarsSection({ settings, onSettingsChange }: EnvVarsSectionProps) {
  const [envVarsText, setEnvVarsText] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDirty, setIsDirty] = useState(false);

  useEffect(() => {
    if (settings.repo_env_vars && Object.keys(settings.repo_env_vars).length > 0) {
      setEnvVarsText(maskedDictToDisplayText(settings.repo_env_vars));
    } else {
      setEnvVarsText("");
    }
    setIsDirty(false);
  }, [settings.repo_env_vars]);

  const handleChange = (text: string) => {
    setEnvVarsText(text);
    setIsDirty(true);
    setError(null);
  };

  const handleSave = async () => {
    const parsed = parseEnvVarsText(envVarsText);

    // Filter out keys with empty values that came from masked display (unchanged)
    const toSave: Record<string, string> = {};
    const currentKeys = settings.repo_env_vars
      ? Object.keys(settings.repo_env_vars)
      : [];

    for (const [key, value] of Object.entries(parsed)) {
      if (value === "" && currentKeys.includes(key) && isMaskedDict(settings.repo_env_vars ?? {})) {
        // Key was shown from masked dict and user left value empty — skip (don't overwrite)
        continue;
      }
      toSave[key] = value;
    }

    setSaving(true);
    setError(null);
    try {
      await updateSettings({ repo_env_vars: toSave });
      const updated = await fetchSettings();
      onSettingsChange(updated);
      setSaved(true);
      setIsDirty(false);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  };

  const keyCount = Object.keys(
    settings.repo_env_vars ?? {}
  ).length;

  return (
    <div className="p-4 bg-white/[0.01] border border-[#1a1a1a] rounded-lg">
      <div className="flex items-center justify-between mb-3">
        <label className="text-[10px] font-semibold text-[#ccc]">
          Environment Variables
        </label>
        {keyCount > 0 && (
          <span className="text-[9px] text-[#666]">
            {keyCount} key{keyCount !== 1 ? "s" : ""} stored
          </span>
        )}
      </div>

      <textarea
        value={envVarsText}
        onChange={(e) => handleChange(e.target.value)}
        placeholder={"API_KEY=your-value\nANOTHER_VAR=another-value"}
        rows={5}
        className="w-full bg-black/30 border border-[#1a1a1a] rounded px-3 py-2 text-[11px] text-[#ccc] font-mono placeholder-[#555] focus:outline-none focus:border-[#00ff88]/30 transition-all resize-y min-h-[80px]"
        autoComplete="off"
        spellCheck={false}
      />

      <div className="mt-2 flex items-center justify-between gap-3">
        <p className="text-[9px] text-[#999] leading-relaxed flex-1">
          One <code className="text-[#88ccff] bg-[#88ccff]/[0.06] px-1 py-0.5 rounded text-[9px]">KEY=value</code> per
          line. Values are encrypted at rest and injected into the sandbox container environment on each run.
          Existing keys show with empty values — leave blank to keep current value, or enter a new value to update.
        </p>
        <div className="flex items-center gap-2 shrink-0">
          {saved && (
            <motion.span
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-[9px] text-[#00ff88]"
            >
              Saved
            </motion.span>
          )}
          {error && (
            <span className="text-[9px] text-[#ff4444]">{error}</span>
          )}
          <Button
            variant="success"
            size="md"
            onClick={handleSave}
            disabled={saving || !isDirty}
          >
            {saving ? "Saving..." : "Save Vars"}
          </Button>
        </div>
      </div>
    </div>
  );
}
