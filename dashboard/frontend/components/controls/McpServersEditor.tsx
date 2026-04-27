"use client";

import { useRef } from "react";
import { clsx } from "clsx";
import { MCP_SERVER_TYPES } from "@/lib/constants";
import type { McpServerType } from "@/lib/constants";
import type { McpServerConfig } from "@/lib/api";

export interface McpServersEditorProps {
  servers: Record<string, McpServerConfig>;
  onChange: (servers: Record<string, McpServerConfig>) => void;
  maxServers: number;
}

const REMOVE_ICON = (
  <svg
    width="10"
    height="10"
    viewBox="0 0 10 10"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.5"
  >
    <line x1="2" y1="2" x2="8" y2="8" />
    <line x1="8" y1="2" x2="2" y2="8" />
  </svg>
);

/** Derive the display type from a config shape. Stdio has no `type` field. */
function resolveType(config: McpServerConfig): McpServerType {
  if (config.type === "sse" || config.type === "http") return config.type;
  return "stdio";
}

/** Parse KEY=VALUE lines into a record. Blank lines and comments ignored. */
function parseKvText(text: string): Record<string, string> {
  const result: Record<string, string> = {};
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const eqIdx = trimmed.indexOf("=");
    const key = trimmed.slice(0, eqIdx).trim();
    if (key) result[key] = trimmed.slice(eqIdx + 1);
  }
  return result;
}

/** Serialize a Record<string, string> into KEY=VALUE lines. */
function kvToText(kv: Record<string, string>): string {
  return Object.entries(kv)
    .map(([k, v]) => `${k}=${v}`)
    .join("\n");
}

const INPUT_CLASS =
  "flex-1 bg-black/30 border border-border rounded px-2.5 py-1.5 text-content font-mono text-accent-hover placeholder:text-text-secondary focus-visible:outline-none focus-visible:border-[#00ff88]/30 focus-visible:ring-1 focus-visible:ring-[#00ff88]/40";

const TEXTAREA_CLASS =
  "w-full bg-black/30 border border-border rounded px-2.5 py-1.5 text-content font-mono text-accent-hover placeholder:text-text-secondary resize-y focus-visible:outline-none focus-visible:border-[#00ff88]/30 focus-visible:ring-1 focus-visible:ring-[#00ff88]/40 transition-all";

const LABEL_CLASS =
  "text-caption uppercase tracking-wider text-text-dim w-16 shrink-0";

const LABEL_TEXTAREA_CLASS = `${LABEL_CLASS} pt-2`;

interface ServerRowProps {
  name: string;
  config: McpServerConfig;
  onNameChange: (next: string) => void;
  onConfigChange: (next: McpServerConfig) => void;
  onRemove: () => void;
}

function ServerRow({
  name,
  config,
  onNameChange,
  onConfigChange,
  onRemove,
}: ServerRowProps): React.ReactElement {
  const type = resolveType(config);

  function handleTypeChange(next: McpServerType): void {
    if (next === "stdio") {
      const { type: _t, url: _u, headers: _h, ...rest } = config;
      onConfigChange({ ...rest });
    } else {
      const { command: _c, args: _a, env: _e, ...rest } = config;
      onConfigChange({ ...rest, type: next, url: config.url ?? "" });
    }
  }

  return (
    <div className="space-y-2 mb-4 pb-4 border-b border-border last:border-b-0 last:mb-0 last:pb-0">
      {/* Name + type + remove */}
      <div className="flex items-center gap-2">
        <span className={LABEL_CLASS}>Name</span>
        <input
          type="text"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder="my-server"
          className={INPUT_CLASS}
          autoComplete="off"
          spellCheck={false}
          aria-label="Server name"
        />
        <div className="flex items-center bg-black/30 border border-border rounded-full p-0.5 shrink-0">
          {MCP_SERVER_TYPES.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => handleTypeChange(t)}
              className={clsx(
                "px-2 py-0.5 rounded-full text-caption transition-all",
                type === t
                  ? "bg-[#00ff88]/[0.12] text-[#00ff88] font-medium"
                  : "text-text-dim hover:text-text-secondary",
              )}
            >
              {t}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={onRemove}
          className="p-1 text-text-dim hover:text-[#ff4444] transition-colors shrink-0"
          aria-label="Remove server"
        >
          {REMOVE_ICON}
        </button>
      </div>

      {type === "stdio" && (
        <>
          <div className="flex items-center gap-2">
            <span className={LABEL_CLASS}>Cmd</span>
            <input
              type="text"
              value={config.command ?? ""}
              onChange={(e) =>
                onConfigChange({ ...config, command: e.target.value })
              }
              placeholder="npx"
              className={INPUT_CLASS}
              autoComplete="off"
              spellCheck={false}
              aria-label="Command"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className={LABEL_CLASS}>Args</span>
            <input
              type="text"
              value={(config.args ?? []).join(", ")}
              onChange={(e) =>
                onConfigChange({
                  ...config,
                  args: e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter((s) => s.length > 0),
                })
              }
              placeholder="-y, @modelcontextprotocol/server-github"
              className={INPUT_CLASS}
              autoComplete="off"
              spellCheck={false}
              aria-label="Arguments"
            />
          </div>
          <div className="flex items-start gap-2">
            <span className={LABEL_TEXTAREA_CLASS}>Env</span>
            <textarea
              value={kvToText(config.env ?? {})}
              onChange={(e) =>
                onConfigChange({
                  ...config,
                  env: parseKvText(e.target.value),
                })
              }
              placeholder={"GITHUB_TOKEN=your-token\nOTHER_VAR=value"}
              rows={2}
              className={TEXTAREA_CLASS}
              autoComplete="off"
              spellCheck={false}
              aria-label="Environment variables"
            />
          </div>
        </>
      )}

      {(type === "sse" || type === "http") && (
        <>
          <div className="flex items-center gap-2">
            <span className={LABEL_CLASS}>URL</span>
            <input
              type="text"
              value={config.url ?? ""}
              onChange={(e) =>
                onConfigChange({ ...config, url: e.target.value })
              }
              placeholder="http://localhost:3000/sse"
              className={INPUT_CLASS}
              autoComplete="off"
              spellCheck={false}
              aria-label="Server URL"
            />
          </div>
          <div className="flex items-start gap-2">
            <span className={LABEL_TEXTAREA_CLASS}>Headers</span>
            <textarea
              value={kvToText(config.headers ?? {})}
              onChange={(e) =>
                onConfigChange({
                  ...config,
                  headers: parseKvText(e.target.value),
                })
              }
              placeholder={"Authorization=Bearer your-token"}
              rows={2}
              className={TEXTAREA_CLASS}
              autoComplete="off"
              spellCheck={false}
              aria-label="HTTP headers"
            />
          </div>
        </>
      )}
    </div>
  );
}

export function McpServersEditor({
  servers,
  onChange,
  maxServers,
}: McpServersEditorProps): React.ReactElement {
  const entries = Object.entries(servers);
  const atMax = entries.length >= maxServers;
  const nextId = useRef(0);
  const stableIds = useRef(new Map<string, number>());

  for (const name of Object.keys(servers)) {
    if (!stableIds.current.has(name)) {
      stableIds.current.set(name, nextId.current++);
    }
  }
  for (const name of stableIds.current.keys()) {
    if (!(name in servers)) stableIds.current.delete(name);
  }

  function handleAdd(): void {
    const base = "server";
    let n = entries.length + 1;
    while (servers[`${base}-${n}`] !== undefined) n++;
    onChange({ ...servers, [`${base}-${n}`]: {} });
  }

  function handleRemove(name: string): void {
    const next = { ...servers };
    delete next[name];
    onChange(next);
  }

  function handleNameChange(oldName: string, newName: string): void {
    if (!newName.trim()) return;
    if (newName !== oldName && newName in servers) return;
    const id = stableIds.current.get(oldName);
    if (id !== undefined) {
      stableIds.current.delete(oldName);
      stableIds.current.set(newName, id);
    }
    const next: Record<string, McpServerConfig> = {};
    for (const [k, v] of Object.entries(servers)) {
      next[k === oldName ? newName : k] = v;
    }
    onChange(next);
  }

  function handleConfigChange(name: string, config: McpServerConfig): void {
    onChange({ ...servers, [name]: config });
  }

  return (
    <div className="space-y-1">
      {entries.map(([name, config]) => (
        <ServerRow
          key={stableIds.current.get(name) ?? name}
          name={name}
          config={config}
          onNameChange={(next) => handleNameChange(name, next)}
          onConfigChange={(next) => handleConfigChange(name, next)}
          onRemove={() => handleRemove(name)}
        />
      ))}
      <button
        type="button"
        onClick={handleAdd}
        disabled={atMax}
        title={atMax ? `Maximum of ${maxServers} servers reached` : undefined}
        className={clsx(
          "text-content transition-colors",
          atMax
            ? "text-text-dim cursor-not-allowed"
            : "text-text-secondary hover:text-accent-hover",
        )}
      >
        + Add server
        {atMax && ` (max ${maxServers})`}
      </button>
    </div>
  );
}
