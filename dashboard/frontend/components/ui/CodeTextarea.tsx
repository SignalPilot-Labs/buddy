/**Editable textarea with bash syntax highlighting overlay and copy button.*/

"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { getHighlighter } from "@/components/ui/shikiHighlighter";

interface CodeTextareaProps {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  rows: number;
  className?: string;
}

const SHARED =
  "w-full rounded border px-3 py-2.5 font-mono text-content leading-normal whitespace-pre-wrap break-words";

export default function CodeTextarea({ value, onChange, placeholder, rows, className }: CodeTextareaProps) {
  const [html, setHtml] = useState("");
  const [copied, setCopied] = useState(false);
  const preRef = useRef<HTMLPreElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!value.trim()) {
      setHtml("");
      return;
    }
    let cancelled = false;
    getHighlighter()
      .then((h) => {
        if (cancelled) return;
        const result = h.codeToHtml(value, { lang: "bash", theme: "github-dark" });
        setHtml(result);
      })
      .catch(() => setHtml(""));
    return () => { cancelled = true; };
  }, [value]);

  const syncScroll = useCallback(() => {
    if (preRef.current && textareaRef.current) {
      preRef.current.scrollTop = textareaRef.current.scrollTop;
      preRef.current.scrollLeft = textareaRef.current.scrollLeft;
    }
  }, []);

  const handleCopy = useCallback(() => {
    void navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [value]);

  return (
    <div className={`relative group ${className ?? ""}`}>
      {/* Highlighted layer — scrolls in sync with textarea, no pointer events */}
      <pre
        ref={preRef}
        aria-hidden
        dangerouslySetInnerHTML={{ __html: html }}
        className={`absolute inset-0 overflow-hidden pointer-events-none border-transparent no-scrollbar ${SHARED} [&_pre]:!bg-transparent [&_pre]:!m-0 [&_pre]:!p-0 [&_pre]:!whitespace-pre-wrap [&_pre]:!break-words [&_code]:!bg-transparent [&_code]:!font-mono [&_code]:!text-[length:inherit] [&_code]:!leading-[inherit] [&_code]:!p-0 [&_code]:!m-0`}
      />
      {/* Editable textarea — transparent text so highlight shows through, visible caret */}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onScroll={syncScroll}
        placeholder={placeholder}
        rows={rows}
        spellCheck={false}
        className={`relative bg-black/20 border-border placeholder:text-text-secondary resize-none focus-visible:outline-none focus-visible:border-[#00ff88]/30 focus-visible:ring-1 focus-visible:ring-[#00ff88]/40 transition-all selection:bg-[#00ff88]/20 ${SHARED}`}
        style={{ color: html ? "transparent" : undefined, caretColor: "#00ff88" }}
      />
      {/* Copy icon — top right, visible on hover */}
      {value.trim() && (
        <button
          type="button"
          onClick={handleCopy}
          title="Copy to clipboard"
          aria-label="Copy to clipboard"
          className="absolute top-1.5 right-1.5 p-1 rounded hover:bg-white/[0.04] text-text-secondary hover:text-accent-hover opacity-0 group-hover:opacity-100 transition-all"
        >
          {copied ? (
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#00ff88" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          ) : (
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="9" y="9" width="13" height="13" rx="2" />
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
            </svg>
          )}
        </button>
      )}
    </div>
  );
}
