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

export default function CodeTextarea({ value, onChange, placeholder, rows, className }: CodeTextareaProps) {
  const [html, setHtml] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
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
        setHtml(h.codeToHtml(value, { lang: "bash", theme: "github-dark" }));
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

  // Keep pre height in sync when textarea is resized (drag handle)
  useEffect(() => {
    const textarea = textareaRef.current;
    const pre = preRef.current;
    if (!textarea || !pre) return;
    const observer = new ResizeObserver(() => {
      pre.style.height = `${textarea.offsetHeight}px`;
    });
    observer.observe(textarea);
    return () => observer.disconnect();
  }, []);

  return (
    <div ref={containerRef} className={`relative ${className ?? ""}`}>
      <pre
        ref={preRef}
        aria-hidden
        className="absolute inset-x-0 top-0 overflow-hidden pointer-events-none rounded border border-transparent px-3 py-2.5 font-mono text-[length:inherit] leading-[1.5] whitespace-pre-wrap break-words [word-break:break-all] [&_pre]:!bg-transparent [&_pre]:!m-0 [&_pre]:!p-0 [&_pre]:!whitespace-pre-wrap [&_pre]:!break-words [&_pre]:![word-break:break-all] [&_pre]:!leading-[1.5] [&_code]:!bg-transparent [&_code]:!font-mono [&_code]:!text-[length:inherit] [&_code]:!leading-[1.5]"
        dangerouslySetInnerHTML={{ __html: html }}
      />
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onScroll={syncScroll}
        placeholder={placeholder}
        rows={rows}
        spellCheck={false}
        className="relative w-full bg-black/30 border border-border rounded px-3 py-2.5 font-mono text-content leading-[1.5] whitespace-pre-wrap [word-break:break-all] placeholder:text-text-secondary resize-y focus-visible:outline-none focus-visible:border-[#00ff88]/30 focus-visible:ring-1 focus-visible:ring-[#00ff88]/40 transition-all"
        style={{ color: html ? "transparent" : undefined, caretColor: "#00ff88" }}
      />
    </div>
  );
}
