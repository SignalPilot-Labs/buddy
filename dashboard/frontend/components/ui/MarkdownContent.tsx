"use client";

import { memo } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { clsx } from "clsx";
import type { Components } from "react-markdown";

interface MarkdownContentProps {
  content: string;
  className?: string;
}

const MARKDOWN_COMPONENTS: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  h1: ({ children }) => <h1 className="font-semibold leading-tight mb-1.5 mt-3 first:mt-0 text-[18px]">{children}</h1>,
  h2: ({ children }) => <h2 className="font-medium leading-tight mb-1.5 mt-3 first:mt-0 text-[15px]">{children}</h2>,
  h3: ({ children }) => <h3 className="font-semibold leading-tight mb-1.5 mt-3 first:mt-0 text-[14px]">{children}</h3>,
  h4: ({ children }) => <h4 className="font-semibold leading-tight mb-1.5 mt-3 first:mt-0 text-[13px]">{children}</h4>,
  strong: ({ children }) => <strong className="font-semibold text-text">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  del: ({ children }) => <del className="opacity-60">{children}</del>,
  a: ({ children, href }) => (
    <a
      href={href}
      className="underline underline-offset-2 hover:text-text transition-colors"
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  ),
  ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-0.5">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-0.5">{children}</ol>,
  li: ({ children }) => <li>{children}</li>,
  pre: ({ children }) => (
    <pre className="bg-black/40 rounded border border-white/[0.05] p-2.5 my-2 overflow-x-auto whitespace-pre-wrap break-words [&>code]:bg-transparent [&>code]:p-0 [&>code]:rounded-none">
      {children}
    </pre>
  ),
  code: ({ children }) => (
    <code className="bg-white/10 rounded px-1 py-0.5 text-[0.9em] font-mono">
      {children}
    </code>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-white/10 pl-3 my-2 opacity-80">{children}</blockquote>
  ),
  hr: () => <hr className="border-white/10 my-3" />,
  table: ({ children }) => (
    <div className="overflow-x-auto my-2">
      <table className="text-[0.9em] border-collapse">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border border-white/10 px-2 py-1 text-left font-semibold">{children}</th>,
  td: ({ children }) => <td className="border border-white/10 px-2 py-1">{children}</td>,
};

export const MarkdownContent = memo(function MarkdownContent({ content, className }: MarkdownContentProps): React.ReactElement | null {
  if (!content) return null;
  return (
    <div className={clsx("break-words leading-[1.7]", className)}>
      <Markdown remarkPlugins={[remarkGfm]} components={MARKDOWN_COMPONENTS}>{content}</Markdown>
    </div>
  );
});
