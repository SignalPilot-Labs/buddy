"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Plus,
  Database,
  Trash2,
  CheckCircle2,
  XCircle,
  Loader2,
  TestTube,
  ChevronDown,
  ChevronRight,
  Table2,
  Activity,
  AlertTriangle,
  Clock,
} from "lucide-react";
import {
  getConnections,
  createConnection,
  deleteConnection,
  testConnection,
  getConnectionSchema,
  getConnectionsHealth,
} from "@/lib/api";
import type { ConnectionInfo, ConnectionHealthStats } from "@/lib/types";

const dbTypeIcons: Record<string, string> = {
  postgres: "🐘",
  duckdb: "🦆",
  mysql: "🐬",
  snowflake: "❄️",
};

const healthStatusColors: Record<string, string> = {
  healthy: "text-[var(--color-success)]",
  warning: "text-yellow-500",
  degraded: "text-orange-500",
  unhealthy: "text-[var(--color-error)]",
  unknown: "text-[var(--color-text-dim)]",
};

const healthStatusBg: Record<string, string> = {
  healthy: "bg-[var(--color-success)]",
  warning: "bg-yellow-500",
  degraded: "bg-orange-500",
  unhealthy: "bg-[var(--color-error)]",
  unknown: "bg-[var(--color-text-dim)]",
};

export default function ConnectionsPage() {
  const [connections, setConnections] = useState<ConnectionInfo[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<Record<string, { status: string; message: string }>>({});
  const [saving, setSaving] = useState(false);
  const [expandedConn, setExpandedConn] = useState<string | null>(null);
  const [schemaData, setSchemaData] = useState<Record<string, { tables: Record<string, { schema: string; name: string; columns: { name: string; type: string; nullable: boolean; primary_key?: boolean }[] }> }>>({});
  const [schemaLoading, setSchemaLoading] = useState<string | null>(null);
  const [healthData, setHealthData] = useState<Record<string, ConnectionHealthStats>>({});
  const [form, setForm] = useState({
    name: "",
    db_type: "postgres" as const,
    host: "localhost",
    port: "5432",
    database: "",
    username: "",
    password: "",
    description: "",
  });

  const refresh = useCallback(() => {
    getConnections().then(setConnections).catch(() => {});
    getConnectionsHealth()
      .then((res) => {
        const map: Record<string, ConnectionHealthStats> = {};
        for (const h of res.connections) {
          map[h.connection_name] = h;
        }
        setHealthData(map);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleCreate() {
    setSaving(true);
    try {
      await createConnection({
        name: form.name,
        db_type: form.db_type,
        host: form.host,
        port: parseInt(form.port) || 5432,
        database: form.database,
        username: form.username,
        password: form.password,
        description: form.description,
      });
      setShowForm(false);
      setForm({
        name: "",
        db_type: "postgres",
        host: "localhost",
        port: "5432",
        database: "",
        username: "",
        password: "",
        description: "",
      });
      refresh();
    } catch (e) {
      alert(String(e));
    } finally {
      setSaving(false);
    }
  }

  async function handleTest(name: string) {
    setTesting(name);
    try {
      const result = await testConnection(name);
      setTestResult((prev) => ({ ...prev, [name]: result }));
    } catch (e) {
      setTestResult((prev) => ({
        ...prev,
        [name]: { status: "error", message: String(e) },
      }));
    } finally {
      setTesting(null);
    }
  }

  async function handleDelete(name: string) {
    if (!confirm(`Delete connection "${name}"?`)) return;
    await deleteConnection(name);
    refresh();
  }

  async function handleToggleSchema(name: string) {
    if (expandedConn === name) {
      setExpandedConn(null);
      return;
    }
    setExpandedConn(name);
    if (!schemaData[name]) {
      setSchemaLoading(name);
      try {
        const data = await getConnectionSchema(name);
        setSchemaData((prev) => ({ ...prev, [name]: { tables: data.tables } }));
      } catch (e) {
        setSchemaData((prev) => ({ ...prev, [name]: { tables: {} } }));
      } finally {
        setSchemaLoading(null);
      }
    }
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold mb-1">Connections</h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            Manage database connections for governed AI access
          </p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white text-sm font-medium transition-colors"
        >
          <Plus className="w-4 h-4" /> Add Connection
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="mb-6 p-6 bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl">
          <h3 className="text-sm font-medium mb-4">New Connection</h3>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Name</label>
              <input
                type="text"
                placeholder="prod-analytics"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-input)] border border-[var(--color-border)] text-sm focus:outline-none focus:border-[var(--color-accent)]"
              />
            </div>
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Type</label>
              <select
                value={form.db_type}
                onChange={(e) =>
                  setForm({
                    ...form,
                    db_type: e.target.value as typeof form.db_type,
                    port: e.target.value === "postgres" ? "5432" : e.target.value === "mysql" ? "3306" : form.port,
                  })
                }
                className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-input)] border border-[var(--color-border)] text-sm focus:outline-none focus:border-[var(--color-accent)]"
              >
                <option value="postgres">PostgreSQL</option>
                <option value="duckdb">DuckDB</option>
                <option value="mysql">MySQL</option>
                <option value="snowflake">Snowflake</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Host</label>
              <input type="text" placeholder="localhost" value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-input)] border border-[var(--color-border)] text-sm focus:outline-none focus:border-[var(--color-accent)]" />
            </div>
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Port</label>
              <input type="text" placeholder="5432" value={form.port} onChange={(e) => setForm({ ...form, port: e.target.value })} className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-input)] border border-[var(--color-border)] text-sm focus:outline-none focus:border-[var(--color-accent)]" />
            </div>
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Database</label>
              <input type="text" placeholder="mydb" value={form.database} onChange={(e) => setForm({ ...form, database: e.target.value })} className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-input)] border border-[var(--color-border)] text-sm focus:outline-none focus:border-[var(--color-accent)]" />
            </div>
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Username</label>
              <input type="text" placeholder="postgres" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-input)] border border-[var(--color-border)] text-sm focus:outline-none focus:border-[var(--color-accent)]" />
            </div>
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Password</label>
              <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-input)] border border-[var(--color-border)] text-sm focus:outline-none focus:border-[var(--color-accent)]" />
            </div>
            <div>
              <label className="block text-xs text-[var(--color-text-muted)] mb-1">Description</label>
              <input type="text" placeholder="Production analytics DB" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-input)] border border-[var(--color-border)] text-sm focus:outline-none focus:border-[var(--color-accent)]" />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={handleCreate} disabled={saving || !form.name} className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-accent)] hover:bg-[var(--color-accent-hover)] text-white text-sm font-medium transition-colors disabled:opacity-50">
              {saving && <Loader2 className="w-4 h-4 animate-spin" />}
              Save
            </button>
            <button onClick={() => setShowForm(false)} className="px-4 py-2 rounded-lg text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors">
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Connections list */}
      {connections.length === 0 && !showForm ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <Database className="w-12 h-12 text-[var(--color-text-dim)] mb-4" />
          <p className="text-sm text-[var(--color-text-muted)] mb-2">No connections configured</p>
          <p className="text-xs text-[var(--color-text-dim)]">Add a database connection to enable governed SQL queries</p>
        </div>
      ) : (
        <div className="space-y-3">
          {connections.map((conn) => {
            const health = healthData[conn.name];
            const isExpanded = expandedConn === conn.name;
            const tables = schemaData[conn.name]?.tables;

            return (
              <div key={conn.id} className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl hover:border-[var(--color-border-hover)] transition-colors">
                {/* Connection header row */}
                <div className="flex items-center gap-4 p-4">
                  <div className="text-2xl w-10 text-center">{dbTypeIcons[conn.db_type] || "🗄️"}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm">{conn.name}</span>
                      <span className="text-xs px-2 py-0.5 rounded bg-[var(--color-bg)] text-[var(--color-text-muted)]">{conn.db_type}</span>
                      {/* Health status badge */}
                      {health && (
                        <span className={`flex items-center gap-1 text-xs ${healthStatusColors[health.status]}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${healthStatusBg[health.status]}`} />
                          {health.status}
                          {health.latency_p50_ms != null && (
                            <span className="text-[var(--color-text-dim)] ml-1">
                              p50: {health.latency_p50_ms.toFixed(0)}ms
                            </span>
                          )}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-[var(--color-text-muted)] mt-0.5">
                      {conn.host}:{conn.port}/{conn.database}
                      {conn.description && (
                        <span className="ml-2 text-[var(--color-text-dim)]">&mdash; {conn.description}</span>
                      )}
                    </div>
                    {/* Health details inline */}
                    {health && health.sample_count > 0 && (
                      <div className="flex items-center gap-4 mt-1.5 text-[10px] text-[var(--color-text-dim)]">
                        <span className="flex items-center gap-1">
                          <Activity className="w-3 h-3" />
                          {health.sample_count} queries
                        </span>
                        {health.error_rate != null && health.error_rate > 0 && (
                          <span className="flex items-center gap-1 text-[var(--color-error)]">
                            <AlertTriangle className="w-3 h-3" />
                            {(health.error_rate * 100).toFixed(1)}% error rate
                          </span>
                        )}
                        {health.latency_p95_ms != null && (
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            p95: {health.latency_p95_ms.toFixed(0)}ms
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Test result */}
                  {testResult[conn.name] && (
                    <span className={`flex items-center gap-1 text-xs ${testResult[conn.name].status === "healthy" ? "text-[var(--color-success)]" : "text-[var(--color-error)]"}`}>
                      {testResult[conn.name].status === "healthy" ? <CheckCircle2 className="w-3.5 h-3.5" /> : <XCircle className="w-3.5 h-3.5" />}
                      {testResult[conn.name].message.slice(0, 40)}
                    </span>
                  )}

                  {/* Schema browse button */}
                  <button
                    onClick={(e) => { e.stopPropagation(); handleToggleSchema(conn.name); }}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-hover)] transition-colors"
                  >
                    {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                    <Table2 className="w-3.5 h-3.5" />
                    Schema
                  </button>

                  <button
                    onClick={() => handleTest(conn.name)}
                    disabled={testing === conn.name}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-hover)] transition-colors"
                  >
                    {testing === conn.name ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <TestTube className="w-3.5 h-3.5" />}
                    Test
                  </button>
                  <button
                    onClick={() => handleDelete(conn.name)}
                    className="p-1.5 rounded hover:bg-[var(--color-error)]/10 text-[var(--color-text-dim)] hover:text-[var(--color-error)] transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Inline schema browser */}
                {isExpanded && (
                  <div className="border-t border-[var(--color-border)] px-4 py-4">
                    {schemaLoading === conn.name ? (
                      <div className="flex items-center gap-2 py-4 justify-center text-sm text-[var(--color-text-muted)]">
                        <Loader2 className="w-4 h-4 animate-spin" /> Loading schema...
                      </div>
                    ) : tables && Object.keys(tables).length > 0 ? (
                      <div className="space-y-2">
                        <p className="text-xs text-[var(--color-text-dim)] mb-3">
                          {Object.keys(tables).length} tables
                        </p>
                        <div className="grid grid-cols-2 gap-2 max-h-80 overflow-auto">
                          {Object.values(tables).map((t) => (
                            <div key={t.name} className="p-3 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)]">
                              <div className="flex items-center gap-2 mb-2">
                                <Table2 className="w-3.5 h-3.5 text-[var(--color-accent)]" />
                                <span className="text-xs font-medium">{t.schema}.{t.name}</span>
                                <span className="text-[10px] text-[var(--color-text-dim)]">{t.columns.length} cols</span>
                              </div>
                              <div className="space-y-0.5">
                                {t.columns.slice(0, 8).map((col) => (
                                  <div key={col.name} className="flex items-center gap-2 text-[10px]">
                                    <span className={`${col.primary_key ? "text-yellow-500 font-semibold" : "text-[var(--color-text-muted)]"}`}>
                                      {col.name}
                                    </span>
                                    <span className="text-[var(--color-text-dim)]">{col.type}</span>
                                    {!col.nullable && <span className="text-[var(--color-text-dim)] opacity-50">NOT NULL</span>}
                                    {col.primary_key && <span className="text-yellow-500 text-[9px]">PK</span>}
                                  </div>
                                ))}
                                {t.columns.length > 8 && (
                                  <p className="text-[10px] text-[var(--color-text-dim)]">
                                    + {t.columns.length - 8} more columns
                                  </p>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <p className="text-xs text-[var(--color-text-dim)] py-4 text-center">
                        No schema available. Test the connection first.
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
