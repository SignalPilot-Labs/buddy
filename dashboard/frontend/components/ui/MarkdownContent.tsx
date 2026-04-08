"use client";

import Markdown from "react-markdown";
import { clsx } from "clsx";
import type { Components } from "react-markdown";

interface MarkdownContentProps {
  content: string;
  className?: string;
}

const MARKDOWN_COMPONENTS: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  h1: ({ children }) => <h1 className="font-semibold mb-1.5 mt-3 first:mt-0 text-[14px]">{children}</h1>,
  h2: ({ children }) => <h2 className="font-semibold mb-1.5 mt-3 first:mt-0 text-[13px]">{children}</h2>,
  h3: ({ children }) => <h3 className="font-semibold mb-1.5 mt-3 first:mt-0 text-[12px]">{children}</h3>,
  h4: ({ children }) => <h4 className="font-semibold mb-1.5 mt-3 first:mt-0 text-[11px]">{children}</h4>,
  strong: ({ children }) => <strong className="font-semibold text-[#ddd]">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  a: ({ children, href }) => (
    <a
      href={href}
      className="underline underline-offset-2 hover:text-[#eee] transition-colors"
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
    <pre className="bg-black/40 rounded border border-white/[0.05] p-2.5 my-2 overflow-x-auto whitespace-pre-wrap break-all [&>code]:bg-transparent [&>code]:p-0 [&>code]:rounded-none">
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
};

export function MarkdownContent({ content, className }: MarkdownContentProps): React.ReactElement {
  return (
    <div className={clsx("break-words leading-[1.7]", className)}>
      <Markdown components={MARKDOWN_COMPONENTS}>{content}</Markdown>
    </div>
  );
}
