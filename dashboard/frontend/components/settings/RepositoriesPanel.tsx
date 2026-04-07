"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useTranslation } from "@/hooks/useTranslation";
import { Button } from "@/components/ui/Button";
import type { RepoInfo } from "@/lib/types";

interface RepositoriesPanelProps {
  repos: RepoInfo[];
  activeRepo: string;
  onAdd: (slug: string) => Promise<void>;
  onRemove: (slug: string) => Promise<void>;
  onSetActive: (slug: string) => Promise<void>;
}

export function RepositoriesPanel({
  repos,
  activeRepo,
  onAdd,
  onRemove,
  onSetActive,
}: RepositoriesPanelProps): React.ReactElement {
  const { t } = useTranslation();
  const [newRepo, setNewRepo] = useState("");
  const [addingRepo, setAddingRepo] = useState(false);
  const [repoError, setRepoError] = useState<string | null>(null);

  const handleAdd = async (): Promise<void> => {
    const slug = newRepo.trim();
    if (!slug) return;
    if (!/^[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+$/.test(slug)) {
      setRepoError(t.settings.repoInvalidFormat);
      return;
    }
    if (repos.some((r) => r.repo === slug)) {
      setRepoError(t.settings.repoAlreadyAdded);
      return;
    }
    setAddingRepo(true);
    setRepoError(null);
    try {
      await onAdd(slug);
      setNewRepo("");
    } catch (e) {
      const msg = e instanceof Error ? e.message : "";
      const mapped: Record<string, string> = {
        "Failed to update settings": t.errors.failedToUpdateSettings,
      };
      setRepoError(mapped[msg] ?? (msg || t.settings.failedToSave));
    } finally {
      setAddingRepo(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === "Enter") {
      e.preventDefault();
      void handleAdd();
    }
  };

  return (
    <div className="p-4 bg-white/[0.01] border border-[#1a1a1a] rounded-lg">
      <div className="flex items-center justify-between mb-3">
        <label className="text-[10px] font-semibold text-[#ccc]">
          {t.settings.repositories}
        </label>
        <span className="text-[9px] text-[#666]">
          {repos.length} {t.settings.configured_count}
        </span>
      </div>

      <div className="space-y-1.5 mb-3">
        <AnimatePresence>
          {repos.map((r) => {
            const isActive = r.repo === activeRepo;
            return (
              <motion.div
                key={r.repo}
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                className="flex items-center gap-2 px-2.5 py-2 bg-black/30 rounded border border-[#1a1a1a] group"
              >
                <svg
                  width="12" height="12" viewBox="0 0 16 16" fill="currentColor"
                  className="text-[#666] shrink-0"
                >
                  <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z" />
                </svg>
                <span className="text-[10px] font-mono text-[#ccc] flex-1 min-w-0 truncate">
                  {r.repo}
                </span>
                <span className="text-[9px] text-[#666] shrink-0">
                  {r.run_count} run{r.run_count !== 1 ? "s" : ""}
                </span>
                {isActive ? (
                  <span className="flex items-center gap-1 text-[9px] text-[#00ff88]/60 shrink-0">
                    <svg width="8" height="8" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <polyline points="2 5 4 7 8 3" />
                    </svg>
                    {t.settings.active}
                  </span>
                ) : (
                  <button
                    onClick={() => void onSetActive(r.repo)}
                    className="text-[9px] text-[#888] hover:text-[#00ff88] transition-colors opacity-0 group-hover:opacity-100 shrink-0"
                  >
                    {t.settings.setActive}
                  </button>
                )}
                <button
                  onClick={() => void onRemove(r.repo)}
                  className="text-[#666] hover:text-[#ff4444] transition-colors opacity-0 group-hover:opacity-100 shrink-0"
                  title={t.settings.removeRepo}
                >
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <line x1="2" y1="2" x2="8" y2="8" />
                    <line x1="8" y1="2" x2="2" y2="8" />
                  </svg>
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>

        {repos.length === 0 && (
          <div className="px-2.5 py-3 text-[10px] text-[#666] text-center">
            {t.settings.noReposConfigured}
          </div>
        )}
      </div>

      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            type="text"
            value={newRepo}
            onChange={(e) => { setNewRepo(e.target.value); setRepoError(null); }}
            onKeyDown={handleKeyDown}
            placeholder={t.settings.repoPlaceholder}
            className="w-full bg-black/30 border border-[#1a1a1a] rounded px-3 py-2 text-[11px] text-[#ccc] font-mono placeholder-[#666] focus:outline-none focus:border-[#00ff88]/30 transition-all"
            autoComplete="off"
            spellCheck={false}
          />
        </div>
        <Button
          variant="success"
          size="md"
          onClick={() => void handleAdd()}
          disabled={addingRepo || !newRepo.trim()}
        >
          {addingRepo ? t.settings.adding : t.settings.addRepo}
        </Button>
      </div>

      {repoError && (
        <p className="mt-1.5 text-[9px] text-[#ff4444]">{repoError}</p>
      )}

      <p className="mt-2 text-[9px] text-[#999] leading-relaxed">
        {t.settings.repoHelp}{" "}
        <code className="text-[#88ccff] bg-[#88ccff]/[0.06] px-1 py-0.5 rounded text-[9px]">owner/repo</code>{" "}
        {t.settings.repoHelpSuffix}
      </p>
    </div>
  );
}
