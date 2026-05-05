/**Settings section for managing configured repositories.*/

"use client";

import { AnimatePresence } from "framer-motion";
import type { RepoInfo } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ListRow } from "@/components/ui/ListRow";
import { IconRepo, IconCheck, IconPlus } from "@/components/ui/icons";

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
        <label className="text-content font-semibold text-accent-hover">
          Repositories
        </label>
        <span className="text-caption text-text-secondary">
          {repos.length} configured
        </span>
      </div>

      <div className="space-y-1.5 mb-3">
        <AnimatePresence>
          {repos.map((r) => {
            const isActive = r.repo === activeRepo;
            return (
              <ListRow key={r.repo} layoutId={r.repo} onDelete={() => onRemoveRepo(r.repo)} deleteTitle="Remove repository">
                <IconRepo className="text-text-secondary shrink-0" />
                <span className="text-content font-mono text-accent-hover flex-1 min-w-0 truncate">
                  {r.repo}
                </span>
                <span className="text-caption text-text-secondary shrink-0">
                  {r.run_count} run{r.run_count !== 1 ? "s" : ""}
                </span>
                {isActive ? (
                  <span className="flex items-center gap-1 text-content text-[#00ff88]/60 shrink-0">
                    <IconCheck />
                    Active
                  </span>
                ) : (
                  <button
                    onClick={() => onSetActive(r.repo)}
                    className="text-caption text-text-secondary hover:text-[#00ff88] transition-colors shrink-0"
                  >
                    Set Active
                  </button>
                )}
              </ListRow>
            );
          })}
        </AnimatePresence>

        {repos.length === 0 && (
          <div className="px-2.5 py-3 text-content text-text-secondary text-center">
            No repositories yet
          </div>
        )}
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          value={newRepo}
          onChange={(e) => { onNewRepoChange(e.target.value); }}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); onAddRepo(); } }}
          placeholder="owner/repo"
          className="flex-1 bg-black/30 border border-border rounded px-3 py-2 text-content text-accent-hover font-mono placeholder:text-text-secondary focus-visible:outline-none focus-visible:border-[#00ff88]/30 focus-visible:ring-1 focus-visible:ring-[#00ff88]/40 transition-all"
          autoComplete="off"
          spellCheck={false}
        />
        <Button
          variant="success"
          size="md"
          icon={<IconPlus size={10} />}
          onClick={onAddRepo}
          disabled={addingRepo || !newRepo.trim()}
        >
          {addingRepo ? "Adding..." : "Add"}
        </Button>
      </div>

      {repoError && (
        <p className="mt-1.5 text-content text-[#ff4444]">{repoError}</p>
      )}
    </div>
  );
}
