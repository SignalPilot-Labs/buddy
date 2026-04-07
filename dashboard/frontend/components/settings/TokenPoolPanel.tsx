"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useTranslation } from "@/hooks/useTranslation";
import { Button } from "@/components/ui/Button";
import type { PoolToken } from "@/lib/types";

interface TokenPoolPanelProps {
  tokens: PoolToken[];
  onAdd: (token: string) => Promise<void>;
  onRemove: (index: number) => Promise<void>;
}

export function TokenPoolPanel({ tokens, onAdd, onRemove }: TokenPoolPanelProps): React.ReactElement {
  const { t } = useTranslation();
  const [newToken, setNewToken] = useState("");
  const [addingToken, setAddingToken] = useState(false);
  const [tokenError, setTokenError] = useState<string | null>(null);

  const handleAdd = async (): Promise<void> => {
    const val = newToken.trim();
    if (!val) return;
    setAddingToken(true);
    setTokenError(null);
    try {
      await onAdd(val);
      setNewToken("");
    } catch (e) {
      setTokenError(e instanceof Error ? e.message : t.settings.failedToSave);
    } finally {
      setAddingToken(false);
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
          {t.settings.claudeTokens}
        </label>
        <span className="text-[9px] text-[#666]">
          {tokens.length} key{tokens.length !== 1 ? "s" : ""} — {t.settings.roundRobin}
        </span>
      </div>

      <div className="space-y-1.5 mb-3">
        <AnimatePresence>
          {tokens.map((tok) => (
            <motion.div
              key={tok.masked}
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="flex items-center gap-2 px-2.5 py-2 bg-black/30 rounded border border-[#1a1a1a] group"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-[#666] shrink-0">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
              <span className="text-[10px] font-mono text-[#ccc] flex-1 min-w-0 truncate">
                {tok.masked}
              </span>
              {tok.active && (
                <span className="flex items-center gap-1 text-[9px] text-[#00ff88]/60 shrink-0">
                  <svg width="8" height="8" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <polyline points="2 5 4 7 8 3" />
                  </svg>
                  {t.settings.next}
                </span>
              )}
              <button
                onClick={() => void onRemove(tok.index)}
                className="text-[#666] hover:text-[#ff4444] transition-colors opacity-0 group-hover:opacity-100 shrink-0"
                title={t.settings.removeToken}
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
          <div className="px-2.5 py-3 text-[10px] text-[#666] text-center">
            {t.settings.noTokens}
          </div>
        )}
      </div>

      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            type="password"
            value={newToken}
            onChange={(e) => { setNewToken(e.target.value); setTokenError(null); }}
            onKeyDown={handleKeyDown}
            placeholder={t.settings.tokenPlaceholder}
            className="w-full bg-black/30 border border-[#1a1a1a] rounded px-3 py-2 text-[11px] text-[#ccc] font-mono placeholder-[#666] focus:outline-none focus:border-[#00ff88]/30 transition-all"
            autoComplete="off"
            spellCheck={false}
          />
        </div>
        <Button
          variant="success"
          size="md"
          onClick={() => void handleAdd()}
          disabled={addingToken || !newToken.trim()}
        >
          {addingToken ? t.settings.addingKey : t.settings.addKey}
        </Button>
      </div>

      {tokenError && (
        <p className="mt-1.5 text-[9px] text-[#ff4444]">{tokenError}</p>
      )}

      <p className="mt-2 text-[9px] text-[#999] leading-relaxed">
        {t.settings.tokenHelp}{" "}
        <code className="text-[#88ccff] bg-[#88ccff]/[0.06] px-1 py-0.5 rounded text-[9px]">claude setup-token</code>{" "}
        {t.settings.tokenHelpSuffix}
      </p>
    </div>
  );
}
