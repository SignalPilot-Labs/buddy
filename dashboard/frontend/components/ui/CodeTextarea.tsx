/**Editable textarea with bash syntax highlighting overlay.*/

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

  return (
    <div className={`relative ${className ?? ""}`}>
      {/* Highlighted layer — scrolls in sync with textarea, no pointer events */}
      <pre
        ref={preRef}
        aria-hidden
        dangerouslySetInnerHTML={{ __html: html }}
        className={`absolute inset-0 overflow-auto pointer-events-none border-transparent no-scrollbar ${SHARED} [&_pre]:!bg-transparent [&_pre]:!m-0 [&_pre]:!p-0 [&_pre]:!whitespace-pre-wrap [&_pre]:!break-words [&_code]:!bg-transparent [&_code]:!font-mono [&_code]:!text-[length:inherit] [&_code]:!leading-[inherit] [&_code]:!p-0 [&_code]:!m-0`}
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
        className={`relative bg-black/20 border-border placeholder:text-text-secondary resize-none focus-visible:outline-none focus-visible:border-[#00ff88]/30 focus-visible:ring-1 focus-visible:ring-[#00ff88]/40 transition-all ${SHARED}`}
        style={{ color: html ? "transparent" : undefined, caretColor: "#00ff88" }}
      />
    </div>
  );
}
