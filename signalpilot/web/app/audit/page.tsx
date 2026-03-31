"use client";

import { useEffect, useState, useCallback } from "react";
import {
  ScrollText,
  Filter,
  RefreshCw,
  ShieldAlert,
  Terminal,
  Database as DbIcon,
  Loader2,
} from "lucide-react";
import { getAudit } from "@/lib/api";
import type { AuditEntry } from "@/lib/types";

const typeColors: Record<string, string> = {
  query: "text-[var(--color-success)]",
  execute: "text-[var(--color-accent)]",
  connect: "text-blue-400",
  block: "text-[var(--color-error)]",
};

const typeIcons: Record<string, React.ElementType> = {
  query: DbIcon,
  execute: Terminal,
  connect: DbIcon,
  block: ShieldAlert,
};

export default function AuditPage() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("");

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { limit: 200 };
      if (typeFilter) params.event_type = typeFilter;
      const res = await getAudit(params);
      setEntries(res.entries);
    } catch {} finally {
      setLoading(false);
    }
  }, [typeFilter]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const filtered = entries.filter((e) => {
    if (!filter) return true;
    const lower = filter.toLowerCase();
    return (
      e.sql?.toLowerCase().includes(lower) ||
      e.connection_name?.toLowerCase().includes(lower) ||
      e.event_type.includes(lower) ||
      e.block_reason?.toLowerCase().includes(lower)
    );
  });

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold mb-1">Audit Log</h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            Full-chain audit trail of all governed operations
          </p>
        </div>
        <button
          onClick={refresh}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-hover)] transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-6">
        <div className="flex items-center gap-2 flex-1">
          <Filter className="w-4 h-4 text-[var(--color-text-dim)]" />
          <input
            type="text"
            placeholder="Search by SQL, connection, or reason..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="flex-1 px-3 py-2 rounded-lg bg-[var(--color-bg-input)] border border-[var(--color-border)] text-sm focus:outline-none focus:border-[var(--color-accent)]"
          />
        </div>
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="px-3 py-2 rounded-lg bg-[var(--color-bg-input)] border border-[var(--color-border)] text-sm focus:outline-none focus:border-[var(--color-accent)]"
        >
          <option value="">All types</option>
          <option value="query">Queries</option>
          <option value="execute">Executions</option>
          <option value="connect">Connections</option>
          <option value="block">Blocked</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border)]">
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
                Time
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
                Type
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
                Connection
              </th>
              <th className="text-left px-4 py-3 text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
                Detail
              </th>
              <th className="text-right px-4 py-3 text-xs font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
                Duration
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-border)]">
            {loading && filtered.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center">
                  <Loader2 className="w-5 h-5 animate-spin mx-auto text-[var(--color-text-muted)]" />
                </td>
              </tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-12 text-center text-[var(--color-text-dim)]"
                >
                  <ScrollText className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  No audit entries found
                </td>
              </tr>
            ) : (
              filtered.map((entry) => {
                const Icon = typeIcons[entry.event_type] || ScrollText;
                return (
                  <tr
                    key={entry.id}
                    className="hover:bg-[var(--color-bg-hover)] transition-colors"
                  >
                    <td className="px-4 py-3 text-xs text-[var(--color-text-muted)] tabular-nums whitespace-nowrap">
                      {new Date(entry.timestamp * 1000).toLocaleString()}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`flex items-center gap-1.5 text-xs font-medium ${typeColors[entry.event_type] || ""}`}
                      >
                        <Icon className="w-3.5 h-3.5" />
                        {entry.event_type}
                        {entry.blocked && (
                          <span className="px-1.5 py-0.5 rounded bg-[var(--color-error)]/10 text-[var(--color-error)] text-[10px] uppercase">
                            blocked
                          </span>
                        )}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--color-text-muted)]">
                      {entry.connection_name || "—"}
                    </td>
                    <td className="px-4 py-3 max-w-md">
                      {entry.sql ? (
                        <code className="text-xs text-[var(--color-text)] bg-[var(--color-bg)] px-2 py-0.5 rounded block truncate">
                          {entry.sql}
                        </code>
                      ) : entry.block_reason ? (
                        <span className="text-xs text-[var(--color-error)]">
                          {entry.block_reason}
                        </span>
                      ) : (
                        <span className="text-xs text-[var(--color-text-dim)]">
                          {entry.metadata?.code_preview
                            ? String(entry.metadata.code_preview).slice(0, 60)
                            : "—"}
                        </span>
                      )}
                      {entry.tables.length > 0 && (
                        <div className="flex gap-1 mt-1">
                          {entry.tables.map((t) => (
                            <span
                              key={t}
                              className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-bg)] text-[var(--color-text-muted)]"
                            >
                              {t}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-xs text-right tabular-nums text-[var(--color-text-dim)] whitespace-nowrap">
                      {entry.duration_ms != null
                        ? `${entry.duration_ms.toFixed(0)}ms`
                        : "—"}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
