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
  Download,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { getAudit, getAuditExportUrl } from "@/lib/api";
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
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

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

  function exportCSV() {
    const headers = ["timestamp", "event_type", "connection_name", "sql", "tables", "rows_returned", "duration_ms", "blocked", "block_reason"];
    const rows = filtered.map((e) =>
      headers.map((h) => {
        const val = e[h as keyof AuditEntry];
        if (h === "timestamp") return new Date((val as number) * 1000).toISOString();
        if (h === "tables") return (val as string[])?.join(";") || "";
        if (val === null || val === undefined) return "";
        return String(val).replace(/"/g, '""');
      })
    );
    const csv = [headers.join(","), ...rows.map((r) => r.map((v) => `"${v}"`).join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `signalpilot-audit-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

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
        <div className="flex items-center gap-2">
          <button
            onClick={exportCSV}
            disabled={filtered.length === 0}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-hover)] transition-colors disabled:opacity-40"
          >
            <Download className="w-4 h-4" />
            Export CSV
          </button>
          <a
            href={getAuditExportUrl("json", typeFilter || undefined)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-hover)] transition-colors"
          >
            <Download className="w-4 h-4" />
            Compliance Export
          </a>
          <button
            onClick={refresh}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-hover)] transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
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
        {!loading && (
          <span className="text-xs text-[var(--color-text-dim)] tabular-nums whitespace-nowrap">
            {filtered.length} entries
          </span>
        )}
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
                const isExpanded = expandedRow === entry.id;
                return (
                  <tr
                    key={entry.id}
                    onClick={() => setExpandedRow(isExpanded ? null : entry.id)}
                    className="hover:bg-[var(--color-bg-hover)] transition-colors cursor-pointer group"
                  >
                    <td className="px-4 py-3 text-xs text-[var(--color-text-muted)] tabular-nums whitespace-nowrap">
                      <div className="flex items-center gap-1.5">
                        {isExpanded ? (
                          <ChevronDown className="w-3 h-3 text-[var(--color-text-dim)]" />
                        ) : (
                          <ChevronRight className="w-3 h-3 text-[var(--color-text-dim)] opacity-0 group-hover:opacity-100 transition-opacity" />
                        )}
                        {new Date(entry.timestamp * 1000).toLocaleString()}
                      </div>
                      {isExpanded && entry.sql && (
                        <div className="mt-3 ml-4">
                          <p className="text-[10px] uppercase tracking-wider text-[var(--color-text-dim)] mb-1">Full SQL</p>
                          <pre className="whitespace-pre-wrap text-xs text-[var(--color-text)] bg-[var(--color-bg)] p-3 rounded-lg border border-[var(--color-border)] max-h-40 overflow-auto">
                            {entry.sql}
                          </pre>
                          {entry.rows_returned != null && (
                            <p className="text-[10px] text-[var(--color-text-dim)] mt-2">
                              Rows returned: <span className="text-[var(--color-text-muted)]">{entry.rows_returned.toLocaleString()}</span>
                            </p>
                          )}
                          {entry.metadata && Object.keys(entry.metadata).length > 0 && (
                            <div className="mt-2">
                              <p className="text-[10px] uppercase tracking-wider text-[var(--color-text-dim)] mb-1">Metadata</p>
                              <pre className="text-[10px] text-[var(--color-text-dim)] bg-[var(--color-bg)] p-2 rounded border border-[var(--color-border)]">
                                {JSON.stringify(entry.metadata, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 align-top">
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
                    <td className="px-4 py-3 text-xs text-[var(--color-text-muted)] align-top">
                      {entry.connection_name || "—"}
                    </td>
                    <td className="px-4 py-3 max-w-md align-top">
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
                        <div className="flex gap-1 mt-1 flex-wrap">
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
                    <td className="px-4 py-3 text-xs text-right tabular-nums text-[var(--color-text-dim)] whitespace-nowrap align-top">
                      {entry.duration_ms != null
                        ? `${entry.duration_ms.toFixed(0)}ms`
                        : "—"}
                      {entry.rows_returned != null && (
                        <div className="text-[10px] text-[var(--color-text-dim)] mt-0.5">
                          {entry.rows_returned} rows
                        </div>
                      )}
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
