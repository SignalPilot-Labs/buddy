/**Read-only code block with bash syntax highlighting and copy button.*/

"use client";

import { useState, useEffect, useCallback } from "react";
import { getHighlighter } from "@/components/ui/shikiHighlighter";

interface CodeBlockProps {
  code: string;
  className?: string;
}

export default function CodeBlock({ code, className }: CodeBlockProps) {
  const [html, setHtml] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!code.trim()) {
      setHtml("");
      return;
    }
    let cancelled = false;
    getHighlighter()
      .then((h) => {
        if (cancelled) return;
        const result = h.codeToHtml(code, { lang: "bash", theme: "github-dark" });
        setHtml(result);
      })
      .catch(() => setHtml(""));
    return () => { cancelled = true; };
  }, [code]);

  const handleCopy = useCallback(() => {
    void navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [code]);

  return (
    <div className={`relative group ${className ?? ""}`}>
      <div
        className="px-3 py-2 bg-black/30 rounded border border-border font-mono text-content leading-normal whitespace-pre-wrap break-words overflow-x-auto [&_pre]:!bg-transparent [&_pre]:!m-0 [&_pre]:!p-0 [&_pre]:!whitespace-pre-wrap [&_pre]:!break-words [&_code]:!bg-transparent [&_code]:!font-mono [&_code]:!text-[length:inherit] [&_code]:!leading-[inherit]"
        dangerouslySetInnerHTML={html ? { __html: html } : undefined}
      >
        {!html ? <span className="text-text-secondary">{code}</span> : undefined}
      </div>
      <button
        onClick={handleCopy}
        className="absolute top-1.5 right-1.5 px-1.5 py-0.5 rounded text-caption bg-white/5 border border-border text-text-dim opacity-0 group-hover:opacity-100 hover:bg-white/10 transition-all"
      >
        {copied ? "Copied!" : "Copy"}
      </button>
    </div>
  );
}
