"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { RepoInfo } from "@/lib/types";
import { Button } from "@/components/ui/Button";

interface RepoListSectionProps {
  repos: RepoInfo[];
  activeRepo: string;
  newRepo: string;
  addingRepo: boolean;
  repoError: string | null;
  onNewRepoChange: (value: string) => void;
  onAddRepo: () => void;
  onRemoveRepo: (slug: string) => void;
  onSetActive: (slug: string) => void;
}

export function RepoListSection({
  repos,
  activeRepo,
  newRepo,
  addingRepo,
  repoError,
  onNewRepoChange,
  onAddRepo,
  onRemoveRepo,
  onSetActive,
}: RepoListSectionProps) {
  return (
    <div className="p-4 bg-white/[0.01] border border-border rounded-lg">
      <div className="flex items-center justify-between mb-3">
        <label className="text-[12px] font-semibold text-accent-hover">
          Repositories
        </label>
        <span className="text-[11px] text-text-secondary">
          {repos.length} configured
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
                className="flex items-center gap-2 px-2.5 py-2 bg-black/30 rounded border border-border group"
              >
                <svg
                  width="12" height="12" viewBox="0 0 16 16" fill="currentColor"
                  className="text-text-secondary shrink-0"
                >
                  <path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z" />
                </svg>

                <span className="text-[11px] font-mono text-accent-hover flex-1 min-w-0 truncate">
                  {r.repo}
                </span>

                <span className="text-[11px] text-text-secondary shrink-0">
                  {r.run_count} run{r.run_count !== 1 ? "s" : ""}
                </span>

                {isActive ? (
                  <span className="flex items-center gap-1 text-[11px] text-[#00ff88]/60 shrink-0">
                    <svg width="8" height="8" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <polyline points="2 5 4 7 8 3" />
                    </svg>
                    Active
                  </span>
                ) : (
                  <button
                    onClick={() => onSetActive(r.repo)}
                    className="text-[11px] text-text-secondary hover:text-[#00ff88] transition-colors opacity-0 group-hover:opacity-100 focus-visible:opacity-100 shrink-0 focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-1 focus-visible:outline-[#00ff88]"
                  >
                    Set Active
                  </button>
                )}

                <button
                  onClick={() => onRemoveRepo(r.repo)}
                  className="text-text-secondary hover:text-[#ff4444] transition-colors opacity-0 group-hover:opacity-100 focus-visible:opacity-100 shrink-0 focus-visible:outline focus-visible:outline-1 focus-visible:outline-offset-1 focus-visible:outline-[#ff4444]"
                  title="Remove repository"
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
          <div className="px-2.5 py-3 text-[11px] text-text-secondary text-center">
            No repositories configured yet
          </div>
        )}
      </div>

      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            type="text"
            value={newRepo}
            onChange={(e) => { onNewRepoChange(e.target.value); }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                onAddRepo();
              }
            }}
            placeholder="owner/repo"
            className="w-full bg-black/30 border border-border rounded px-3 py-2 text-[11px] text-accent-hover font-mono placeholder:text-text-secondary focus-visible:outline-none focus-visible:border-[#00ff88]/30 focus-visible:ring-1 focus-visible:ring-[#00ff88]/40 transition-all"
            autoComplete="off"
            spellCheck={false}
          />
        </div>
        <Button
          variant="success"
          size="md"
          onClick={onAddRepo}
          disabled={addingRepo || !newRepo.trim()}
        >
          {addingRepo ? "Adding..." : "Add Repo"}
        </Button>
      </div>

      {repoError && (
        <p className="mt-1.5 text-[11px] text-[#ff4444]">{repoError}</p>
      )}

      <p className="mt-2 text-[11px] text-text-muted leading-relaxed">
        Add repositories in <code className="text-[#88ccff] bg-[#88ccff]/[0.06] px-1 py-0.5 rounded text-[11px]">owner/repo</code> format.
        The active repo is used when starting new runs. Switch between repos using the selector in the dashboard header.
      </p>
    </div>
  );
}
