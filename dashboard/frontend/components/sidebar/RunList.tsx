"use client";

import { AnimatePresence } from "framer-motion";
import type { Run } from "@/lib/types";
import { RunItem } from "./RunItem";
import { EmptyRuns } from "@/components/ui/EmptyStates";

export function RunList({
  runs,
  activeId,
  onSelect,
  loading,
  mobile,
  collapsed,
}: {
  runs: Run[];
  activeId: string | null;
  onSelect: (id: string) => void;
  loading: boolean;
  mobile?: boolean;
  collapsed?: boolean;
}) {
  const isCollapsed = !mobile && collapsed;

  return (
    <aside className={
      mobile
        ? "flex-1 flex flex-col bg-sidebar"
        : `flex-shrink-0 flex flex-col border-r border-border bg-sidebar ${isCollapsed ? "w-[48px]" : "w-[260px]"}`
    }>
      {!isCollapsed && (
        <div className="px-4 py-3 border-b border-border shrink-0">
          <div className="flex items-center gap-2">
            <h2 className="text-[13px] font-bold text-text-muted">
              Runs
            </h2>
            <span className="text-[11px] text-text-secondary tabular-nums ml-auto">{runs.length}</span>
          </div>
        </div>
      )}

      <div className="flex-1 overflow-y-auto sidebar-scroll">
        {loading && runs.length === 0 ? (
          <div className="p-6 text-center">
            <div className="inline-flex h-5 w-5 rounded-full border-2 border-border-subtle border-t-[#00ff88]" style={{ animation: "spin 1s linear infinite" }} />
          </div>
        ) : runs.length === 0 ? (
          isCollapsed ? null : <EmptyRuns />
        ) : (
          <AnimatePresence mode="popLayout">
            {runs.map((run) => (
              <RunItem
                key={run.id}
                run={run}
                active={run.id === activeId}
                onClick={() => onSelect(run.id)}
                collapsed={isCollapsed}
              />
            ))}
          </AnimatePresence>
        )}
      </div>
    </aside>
  );
}
