/**
 * Regression test: CodeTextarea highlight overlay must stay in sync
 * with the textarea — matching line-height, word-break, and tracking
 * resize via ResizeObserver.
 *
 * Before the fix, the highlighted pre overlay had different line-height
 * and word-break rules, causing text to overlap or drift on long lines.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/ui/CodeTextarea.tsx"),
  "utf-8",
);

describe("CodeTextarea: highlight and textarea must stay in sync", () => {
  it("uses ResizeObserver to track textarea size", () => {
    expect(SRC).toContain("ResizeObserver");
    expect(SRC).toContain("observer.observe(textarea)");
    expect(SRC).toContain("observer.disconnect");
  });

  it("pre and textarea share the same leading value", () => {
    // Both must use leading-[1.5] for identical line height
    const preSection = SRC.slice(SRC.indexOf("<pre"), SRC.indexOf("</pre>") || SRC.indexOf("/>", SRC.indexOf("<pre")) + 2);
    const textareaSection = SRC.slice(SRC.indexOf("<textarea"), SRC.indexOf("</textarea>") || SRC.indexOf("/>", SRC.indexOf("<textarea")) + 2);
    expect(preSection).toContain("leading-[1.5]");
    expect(textareaSection).toContain("leading-[1.5]");
  });

  it("pre and textarea share the same word-break rule", () => {
    const preSection = SRC.slice(SRC.indexOf("<pre"), SRC.indexOf("dangerouslySetInnerHTML"));
    const textareaSection = SRC.slice(SRC.indexOf("<textarea"), SRC.length);
    expect(preSection).toContain("[word-break:break-all]");
    expect(textareaSection).toContain("[word-break:break-all]");
  });

  it("pre and textarea both use whitespace-pre-wrap", () => {
    const preSection = SRC.slice(SRC.indexOf("<pre"), SRC.indexOf("dangerouslySetInnerHTML"));
    const textareaSection = SRC.slice(SRC.indexOf("<textarea"), SRC.length);
    expect(preSection).toContain("whitespace-pre-wrap");
    expect(textareaSection).toContain("whitespace-pre-wrap");
  });

  it("shiki inner elements also get matching wrap/break rules", () => {
    // The [&_pre] selectors must propagate the same rules to shiki's inner <pre>
    expect(SRC).toContain("[&_pre]:!whitespace-pre-wrap");
    expect(SRC).toContain("[&_pre]:![word-break:break-all]");
    expect(SRC).toContain("[&_code]:!leading-[1.5]");
  });

  it("uses shared getHighlighter from shikiHighlighter module", () => {
    expect(SRC).toContain('from "@/components/ui/shikiHighlighter"');
    expect(SRC).not.toContain("createHighlighter");
  });
});
