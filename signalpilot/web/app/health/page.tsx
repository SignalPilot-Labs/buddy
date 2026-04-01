"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Activity,
  RefreshCw,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Database,
  TrendingUp,
  Wifi,
  WifiOff,
  Zap,
  BarChart3,
} from "lucide-react";
import {
  getConnectionsHealth,
  getConnectionHealth,
  testConnection,
  getConnections,
  getCacheStats,
  getSchemaCache,
} from "@/lib/api";
import type { ConnectionHealthStats, ConnectionInfo } from "@/lib/types";

const statusConfig: Record<
  string,
  { color: string; bg: string; icon: React.ElementType; label: string }
> = {
  healthy: {
    color: "text-[var(--color-success)]",
    bg: "bg-[var(--color-success)]",
    icon: CheckCircle2,
    label: "Healthy",
  },
  warning: {
    color: "text-[var(--color-warning)]",
    bg: "bg-[var(--color-warning)]",
    icon: AlertTriangle,
    label: "Warning",
  },
  degraded: {
    color: "text-orange-400",
    bg: "bg-orange-400",
    icon: AlertTriangle,
    label: "Degraded",
  },
  unhealthy: {
    color: "text-[var(--color-error)]",
    bg: "bg-[var(--color-error)]",
    icon: XCircle,
    label: "Unhealthy",
  },
  unknown: {
    color: "text-[var(--color-text-dim)]",
    bg: "bg-[var(--color-text-dim)]",
    icon: Activity,
    label: "Unknown",
  },
};

function LatencyBar({
  label,
  value,
  maxMs = 500,
}: {
  label: string;
  value: number | null;
  maxMs?: number;
}) {
  if (value === null) return null;
  const pct = Math.min(100, (value / maxMs) * 100);
  const color =
    value < 50
      ? "bg-[var(--color-success)]"
      : value < 200
        ? "bg-[var(--color-warning)]"
        : "bg-[var(--color-error)]";

  return (
    <div className="flex items-center gap-3">
      <span className="text-[10px] text-[var(--color-text-dim)] w-8 text-right uppercase">
        {label}
      </span>
      <div className="flex-1 h-2 bg-[var(--color-bg)] rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs tabular-nums text-[var(--color-text-muted)] w-16 text-right">
        {value.toFixed(1)}ms
      </span>
    </div>
  );
}

export default function HealthPage() {
  const [healthData, setHealthData] = useState<ConnectionHealthStats[]>([]);
  const [connections, setConnections] = useState<ConnectionInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<
    Record<string, { status: string; message: string }>
  >({});
  const [cacheStats, setCacheStats] = useState<{
    entries: number;
    max_entries: number;
    hits: number;
    misses: number;
    hit_rate: number;
  } | null>(null);
  const [schemaCache, setSchemaCache] = useState<{
    cached_connections: number;
    total_entries: number;
    ttl_seconds: number;
  } | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [health, conns, cache, schema] = await Promise.all([
        getConnectionsHealth().catch(() => ({ connections: [] })),
        getConnections().catch(() => []),
        getCacheStats().catch(() => null),
        getSchemaCache().catch(() => null),
      ]);
      setHealthData(health.connections);
      setConnections(conns);
      setCacheStats(cache);
      setSchemaCache(schema);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    if (!autoRefresh) return;
    const i = setInterval(refresh, 10000);
    return () => clearInterval(i);
  }, [refresh, autoRefresh]);

  async function handleTest(name: string) {
    setTesting(name);
    try {
      const result = await testConnection(name);
      setTestResults((prev) => ({ ...prev, [name]: result }));
      // Refresh health after test
      try {
        const h = await getConnectionHealth(name);
        setHealthData((prev) =>
          prev.map((item) =>
            item.connection_name === name ? h : item
          )
        );
      } catch {}
    } catch (e) {
      setTestResults((prev) => ({
        ...prev,
        [name]: { status: "error", message: String(e) },
      }));
    } finally {
      setTesting(null);
    }
  }

  const overallHealthy = healthData.filter(
    (h) => h.status === "healthy"
  ).length;
  const overallTotal = healthData.length;
  const avgLatency =
    healthData.filter((h) => h.latency_avg_ms != null).length > 0
      ? healthData.reduce((sum, h) => sum + (h.latency_avg_ms || 0), 0) /
        healthData.filter((h) => h.latency_avg_ms != null).length
      : null;

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold mb-1">System Health</h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            Connection health, latency monitoring, and cache performance
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] cursor-pointer">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            Auto-refresh (10s)
          </label>
          <button
            onClick={refresh}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-hover)] transition-colors"
          >
            <RefreshCw
              className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
            />
            Refresh
          </button>
        </div>
      </div>

      {/* Overview cards */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-[var(--color-success)]/10">
              <Wifi className="w-4 h-4 text-[var(--color-success)]" />
            </div>
            <span className="text-sm text-[var(--color-text-muted)]">
              Connections
            </span>
          </div>
          <p className="text-2xl font-semibold tabular-nums">
            {overallHealthy}/{overallTotal}
          </p>
          <p className="text-xs text-[var(--color-text-dim)] mt-1">healthy</p>
        </div>

        <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-[var(--color-accent)]/10">
              <Clock className="w-4 h-4 text-[var(--color-accent)]" />
            </div>
            <span className="text-sm text-[var(--color-text-muted)]">
              Avg Latency
            </span>
          </div>
          <p className="text-2xl font-semibold tabular-nums">
            {avgLatency != null ? `${avgLatency.toFixed(1)}ms` : "--"}
          </p>
          <p className="text-xs text-[var(--color-text-dim)] mt-1">
            across all connections
          </p>
        </div>

        <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-[var(--color-success)]/10">
              <Zap className="w-4 h-4 text-[var(--color-success)]" />
            </div>
            <span className="text-sm text-[var(--color-text-muted)]">
              Query Cache
            </span>
          </div>
          <p className="text-2xl font-semibold tabular-nums">
            {cacheStats ? `${(cacheStats.hit_rate * 100).toFixed(1)}%` : "--"}
          </p>
          <p className="text-xs text-[var(--color-text-dim)] mt-1">
            {cacheStats
              ? `${cacheStats.hits} hits / ${cacheStats.misses} misses`
              : "hit rate"}
          </p>
        </div>

        <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl p-5">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-purple-500/10">
              <Database className="w-4 h-4 text-purple-400" />
            </div>
            <span className="text-sm text-[var(--color-text-muted)]">
              Schema Cache
            </span>
          </div>
          <p className="text-2xl font-semibold tabular-nums">
            {schemaCache ? schemaCache.cached_connections : "--"}
          </p>
          <p className="text-xs text-[var(--color-text-dim)] mt-1">
            {schemaCache
              ? `${schemaCache.total_entries} entries, TTL ${schemaCache.ttl_seconds}s`
              : "cached connections"}
          </p>
        </div>
      </div>

      {/* Connection health cards */}
      {loading && healthData.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24">
          <Loader2 className="w-8 h-8 animate-spin text-[var(--color-accent)] mb-4" />
          <p className="text-sm text-[var(--color-text-muted)]">
            Loading health data...
          </p>
        </div>
      ) : healthData.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <WifiOff className="w-12 h-12 text-[var(--color-text-dim)] mb-4" />
          <p className="text-sm text-[var(--color-text-muted)] mb-2">
            No connection health data available
          </p>
          <p className="text-xs text-[var(--color-text-dim)]">
            Connect a database and run some queries to see health metrics
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <h2 className="text-sm font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
            Connection Health
          </h2>
          <div className="grid grid-cols-2 gap-4">
            {healthData.map((health) => {
              const cfg = statusConfig[health.status] || statusConfig.unknown;
              const StatusIcon = cfg.icon;
              const conn = connections.find(
                (c) => c.name === health.connection_name
              );
              const testResult = testResults[health.connection_name];

              return (
                <div
                  key={health.connection_name}
                  className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl overflow-hidden"
                >
                  {/* Card header */}
                  <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]">
                    <div className="flex items-center gap-3">
                      <div className={`w-2.5 h-2.5 rounded-full ${cfg.bg}`} />
                      <div>
                        <h3 className="text-sm font-medium">
                          {health.connection_name}
                        </h3>
                        <span className="text-xs text-[var(--color-text-dim)]">
                          {health.db_type}
                          {conn ? ` - ${conn.host}:${conn.port}` : ""}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`flex items-center gap-1 text-xs font-medium ${cfg.color}`}
                      >
                        <StatusIcon className="w-3.5 h-3.5" />
                        {cfg.label}
                      </span>
                      <button
                        onClick={() => handleTest(health.connection_name)}
                        disabled={testing === health.connection_name}
                        className="flex items-center gap-1 px-2 py-1 rounded text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-hover)] transition-colors disabled:opacity-50"
                      >
                        {testing === health.connection_name ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Activity className="w-3 h-3" />
                        )}
                        Test
                      </button>
                    </div>
                  </div>

                  {/* Card body */}
                  <div className="px-5 py-4 space-y-4">
                    {/* Latency bars */}
                    <div className="space-y-2">
                      <h4 className="text-[10px] text-[var(--color-text-dim)] uppercase tracking-wider">
                        Latency
                      </h4>
                      <LatencyBar
                        label="p50"
                        value={health.latency_p50_ms}
                      />
                      <LatencyBar
                        label="p95"
                        value={health.latency_p95_ms}
                      />
                      <LatencyBar
                        label="p99"
                        value={health.latency_p99_ms}
                      />
                    </div>

                    {/* Stats grid */}
                    <div className="grid grid-cols-3 gap-3">
                      <div>
                        <p className="text-[10px] text-[var(--color-text-dim)] uppercase">
                          Samples
                        </p>
                        <p className="text-sm font-medium tabular-nums">
                          {health.sample_count}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-[var(--color-text-dim)] uppercase">
                          Success
                        </p>
                        <p className="text-sm font-medium tabular-nums text-[var(--color-success)]">
                          {health.successes ?? "--"}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-[var(--color-text-dim)] uppercase">
                          Failures
                        </p>
                        <p className="text-sm font-medium tabular-nums text-[var(--color-error)]">
                          {health.failures ?? 0}
                        </p>
                      </div>
                      {health.error_rate != null && (
                        <div>
                          <p className="text-[10px] text-[var(--color-text-dim)] uppercase">
                            Error Rate
                          </p>
                          <p
                            className={`text-sm font-medium tabular-nums ${
                              health.error_rate > 0.1
                                ? "text-[var(--color-error)]"
                                : health.error_rate > 0
                                  ? "text-[var(--color-warning)]"
                                  : "text-[var(--color-success)]"
                            }`}
                          >
                            {(health.error_rate * 100).toFixed(1)}%
                          </p>
                        </div>
                      )}
                      {health.consecutive_failures != null &&
                        health.consecutive_failures > 0 && (
                          <div>
                            <p className="text-[10px] text-[var(--color-text-dim)] uppercase">
                              Consecutive Fails
                            </p>
                            <p className="text-sm font-medium tabular-nums text-[var(--color-error)]">
                              {health.consecutive_failures}
                            </p>
                          </div>
                        )}
                    </div>

                    {/* Last error */}
                    {health.last_error && (
                      <div className="p-2.5 rounded-lg bg-[var(--color-error)]/5 border border-[var(--color-error)]/10">
                        <p className="text-[10px] text-[var(--color-error)] font-medium mb-0.5">
                          Last Error
                        </p>
                        <p className="text-xs text-[var(--color-text-muted)] truncate">
                          {health.last_error}
                        </p>
                      </div>
                    )}

                    {/* Test result */}
                    {testResult && (
                      <div
                        className={`p-2.5 rounded-lg border ${
                          testResult.status === "ok"
                            ? "bg-[var(--color-success)]/5 border-[var(--color-success)]/10"
                            : "bg-[var(--color-error)]/5 border-[var(--color-error)]/10"
                        }`}
                      >
                        <p
                          className={`text-xs ${
                            testResult.status === "ok"
                              ? "text-[var(--color-success)]"
                              : "text-[var(--color-error)]"
                          }`}
                        >
                          {testResult.message}
                        </p>
                      </div>
                    )}

                    {/* Last check */}
                    {health.last_check && (
                      <p className="text-[10px] text-[var(--color-text-dim)]">
                        Last check:{" "}
                        {new Date(health.last_check * 1000).toLocaleString()}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Cache Details */}
      {cacheStats && (
        <div className="mt-8">
          <h2 className="text-sm font-medium text-[var(--color-text-muted)] uppercase tracking-wider mb-4">
            Cache Performance
          </h2>
          <div className="bg-[var(--color-bg-card)] border border-[var(--color-border)] rounded-xl p-5">
            <div className="grid grid-cols-2 gap-8">
              {/* Query Cache */}
              <div>
                <h3 className="text-xs font-medium text-[var(--color-text-muted)] mb-3 flex items-center gap-2">
                  <BarChart3 className="w-3.5 h-3.5" />
                  Query Cache
                </h3>
                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-[var(--color-text-dim)]">
                        Hit Rate
                      </span>
                      <span className="font-medium tabular-nums">
                        {(cacheStats.hit_rate * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="w-full h-2.5 bg-[var(--color-bg)] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-[var(--color-success)] rounded-full transition-all"
                        style={{
                          width: `${cacheStats.hit_rate * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                  <div>
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-[var(--color-text-dim)]">
                        Capacity
                      </span>
                      <span className="font-medium tabular-nums">
                        {cacheStats.entries} / {cacheStats.max_entries}
                      </span>
                    </div>
                    <div className="w-full h-2.5 bg-[var(--color-bg)] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-[var(--color-accent)] rounded-full transition-all"
                        style={{
                          width: `${(cacheStats.entries / cacheStats.max_entries) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3 pt-1">
                    <div>
                      <p className="text-[10px] text-[var(--color-text-dim)] uppercase">
                        Hits
                      </p>
                      <p className="text-sm font-medium tabular-nums text-[var(--color-success)]">
                        {cacheStats.hits.toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <p className="text-[10px] text-[var(--color-text-dim)] uppercase">
                        Misses
                      </p>
                      <p className="text-sm font-medium tabular-nums text-[var(--color-text-muted)]">
                        {cacheStats.misses.toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Schema Cache */}
              {schemaCache && (
                <div>
                  <h3 className="text-xs font-medium text-[var(--color-text-muted)] mb-3 flex items-center gap-2">
                    <TrendingUp className="w-3.5 h-3.5" />
                    Schema Cache
                  </h3>
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <p className="text-[10px] text-[var(--color-text-dim)] uppercase">
                          Connections
                        </p>
                        <p className="text-sm font-medium tabular-nums">
                          {schemaCache.cached_connections}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-[var(--color-text-dim)] uppercase">
                          Entries
                        </p>
                        <p className="text-sm font-medium tabular-nums">
                          {schemaCache.total_entries}
                        </p>
                      </div>
                      <div>
                        <p className="text-[10px] text-[var(--color-text-dim)] uppercase">
                          TTL
                        </p>
                        <p className="text-sm font-medium tabular-nums">
                          {schemaCache.ttl_seconds}s
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
