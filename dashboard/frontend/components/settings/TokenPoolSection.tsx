/**Settings section for Claude OAuth token pool management.*/

"use client";

import { AnimatePresence } from "framer-motion";
import type { PoolToken } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { ListRow } from "@/components/ui/ListRow";
import { IconLock, IconCheck, IconPlus } from "@/components/ui/icons";

interface TokenPoolSectionProps {
  tokens: PoolToken[];
  newToken: string;
  addingToken: boolean;
  tokenError: string | null;
  onNewTokenChange: (value: string) => void;
  onAddToken: () => void;
  onRemoveToken: (index: number) => void;
}

export function TokenPoolSection({
  tokens,
  newToken,
  addingToken,
  tokenError,
  onNewTokenChange,
  onAddToken,
  onRemoveToken,
}: TokenPoolSectionProps) {
  return (
    <div className="p-4 bg-white/[0.01] border border-border rounded-lg">
      <div className="flex items-center justify-between mb-3">
        <label className="text-content font-semibold text-accent-hover">
          Claude Tokens
        </label>
        <span className="text-content text-text-secondary">
          {tokens.length} key{tokens.length !== 1 ? "s" : ""} · round-robin
        </span>
      </div>

      <div className="space-y-1.5 mb-3">
        <AnimatePresence>
          {tokens.map((t) => (
            <ListRow key={t.masked} layoutId={t.masked} onDelete={() => onRemoveToken(t.index)} deleteTitle="Remove token">
              <IconLock className="text-text-secondary shrink-0" />
              <span className="text-content font-mono text-accent-hover flex-1 min-w-0 truncate">
                {t.masked}
              </span>
              {t.active && (
                <span className="flex items-center gap-1 text-content text-[#00ff88]/60 shrink-0">
                  <IconCheck />
                  Next
                </span>
              )}
            </ListRow>
          ))}
        </AnimatePresence>

        {tokens.length === 0 && (
          <div className="px-2.5 py-3 text-content text-text-secondary text-center">
            No tokens yet
          </div>
        )}
      </div>

      <div className="flex gap-2">
        <input
          type="password"
          value={newToken}
          onChange={(e) => { onNewTokenChange(e.target.value); }}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); onAddToken(); } }}
          placeholder="sk-ant-oat01-..."
          className="flex-1 bg-black/30 border border-border rounded px-3 py-2 text-content text-accent-hover font-mono placeholder:text-text-secondary focus-visible:outline-none focus-visible:border-[#00ff88]/30 focus-visible:ring-1 focus-visible:ring-[#00ff88]/40 transition-all"
          autoComplete="off"
          spellCheck={false}
        />
        <Button
          variant="success"
          size="md"
          icon={<IconPlus size={10} />}
          onClick={onAddToken}
          disabled={addingToken || !newToken.trim()}
        >
          {addingToken ? "Adding..." : "Add"}
        </Button>
      </div>

      {tokenError && (
        <p className="mt-1.5 text-content text-[#ff4444]">{tokenError}</p>
      )}

      <p className="mt-2 text-caption text-text-dim">
        Run <code className="text-[#88ccff] bg-[#88ccff]/[0.06] px-1 py-0.5 rounded">claude setup-token</code> to generate tokens. Multiple keys rotate on rate limit.
      </p>
    </div>
  );
}
