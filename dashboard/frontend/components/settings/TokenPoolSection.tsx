"use client";

import { motion, AnimatePresence } from "framer-motion";
import type { PoolToken } from "@/lib/types";
import { Button } from "@/components/ui/Button";

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
        <label className="text-[10px] font-semibold text-accent-hover">
          Claude OAuth Tokens
        </label>
        <span className="text-[10px] text-text-secondary">
          {tokens.length} key{tokens.length !== 1 ? "s" : ""} — round-robin on resume
        </span>
      </div>

      <div className="space-y-1.5 mb-3">
        <AnimatePresence>
          {tokens.map((t) => (
            <motion.div
              key={t.masked}
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="flex items-center gap-2 px-2.5 py-2 bg-black/30 rounded border border-border group"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-text-secondary shrink-0">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              <span className="text-[10px] font-mono text-accent-hover flex-1 min-w-0 truncate">
                {t.masked}
              </span>
              {t.active && (
                <span className="flex items-center gap-1 text-[10px] text-[#00ff88]/60 shrink-0">
                  <svg width="8" height="8" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <polyline points="2 5 4 7 8 3" />
                  </svg>
                  Next
                </span>
              )}
              <button
                onClick={() => onRemoveToken(t.index)}
                className="text-text-secondary hover:text-[#ff4444] transition-colors opacity-0 group-hover:opacity-100 shrink-0"
                title="Remove token"
              >
                <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <line x1="2" y1="2" x2="8" y2="8" />
                  <line x1="8" y1="2" x2="2" y2="8" />
                </svg>
              </button>
            </motion.div>
          ))}
        </AnimatePresence>

        {tokens.length === 0 && (
          <div className="px-2.5 py-3 text-[10px] text-text-secondary text-center">
            No tokens configured. Add one to get started.
          </div>
        )}
      </div>

      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            type="password"
            value={newToken}
            onChange={(e) => { onNewTokenChange(e.target.value); }}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); onAddToken(); } }}
            placeholder="sk-ant-oat01-..."
            className="w-full bg-black/30 border border-border rounded px-3 py-2 text-[11px] text-accent-hover font-mono placeholder:text-text-secondary focus-visible:outline-none focus-visible:border-[#00ff88]/30 focus-visible:ring-1 focus-visible:ring-[#00ff88]/40 transition-all"
            autoComplete="off"
            spellCheck={false}
          />
        </div>
        <Button
          variant="success"
          size="md"
          onClick={onAddToken}
          disabled={addingToken || !newToken.trim()}
        >
          {addingToken ? "Adding..." : "Add Key"}
        </Button>
      </div>

      {tokenError && (
        <p className="mt-1.5 text-[10px] text-[#ff4444]">{tokenError}</p>
      )}

      <p className="mt-2 text-[10px] text-text-muted leading-relaxed">
        Add multiple Claude OAuth tokens for automatic rotation. When a run hits a rate limit and is resumed, the next token is used automatically.
        Run <code className="text-[#88ccff] bg-[#88ccff]/[0.06] px-1 py-0.5 rounded text-[10px]">claude setup-token</code> to generate tokens.
      </p>
    </div>
  );
}
