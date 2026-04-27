"use client";

/**JSON textarea editor for MCP server configurations, matching the env-vars pattern.*/

import { useState } from "react";

const MCP_PLACEHOLDER = `{
  "my-server": {
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-github"],
    "env": { "GITHUB_TOKEN": "your-token" }
  },
  "my-sse-server": {
    "type": "sse",
    "url": "http://localhost:3000/sse"
  }
}`;

export interface McpServersEditorProps {
  value: string;
  onChange: (text: string) => void;
}

export function McpServersEditor({
  value,
  onChange,
}: McpServersEditorProps): React.ReactElement {
  const [parseError, setParseError] = useState<string | null>(null);

  function handleChange(text: string): void {
    onChange(text);
    if (!text.trim()) {
      setParseError(null);
      return;
    }
    try {
      const parsed = JSON.parse(text);
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
        setParseError("Must be a JSON object");
      } else {
        setParseError(null);
      }
    } catch {
      setParseError("Invalid JSON");
    }
  }

  return (
    <div>
      <textarea
        value={value}
        onChange={(e) => handleChange(e.target.value)}
        placeholder={MCP_PLACEHOLDER}
        rows={5}
        className="w-full bg-black/30 border border-border rounded px-3 py-2.5 text-content text-accent-hover font-mono placeholder:text-text-secondary resize-y focus-visible:outline-none focus-visible:border-[#00ff88]/30 focus-visible:ring-1 focus-visible:ring-[#00ff88]/40 transition-all"
        autoComplete="off"
        spellCheck={false}
        aria-label="MCP servers JSON"
      />
      {parseError && <p className="mt-1 text-content text-[#ff4444]">{parseError}</p>}
    </div>
  );
}
