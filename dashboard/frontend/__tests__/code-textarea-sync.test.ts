/**
 * Regression test: CodeTextarea highlight overlay must stay in sync
 * with the textarea — matching font, padding, line-height, and wrap.
 *
 * The pre overlay sits absolutely on top of the textarea with
 * transparent text. Both layers must use identical text styling.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/ui/CodeTextarea.tsx"),
  "utf-8",
);

describe("CodeTextarea: highlight and textarea must stay in sync", () => {
  it("pre and textarea both use font-mono", () => {
    const preClass = SRC.slice(SRC.indexOf("className=\"absolute"), SRC.indexOf("dangerouslySetInnerHTML"));
    const taClass = SRC.slice(SRC.indexOf("className=\"relative w-full"), SRC.indexOf("style={{"));
    expect(preClass).toContain("font-mono");
    expect(taClass).toContain("font-mono");
  });

  it("pre and textarea both use text-content for font size", () => {
    const preClass = SRC.slice(SRC.indexOf("className=\"absolute"), SRC.indexOf("dangerouslySetInnerHTML"));
    const taClass = SRC.slice(SRC.indexOf("className=\"relative w-full"), SRC.indexOf("style={{"));
    expect(preClass).toContain("text-content");
    expect(taClass).toContain("text-content");
  });

  it("pre and textarea both use leading-normal for line height", () => {
    const preClass = SRC.slice(SRC.indexOf("className=\"absolute"), SRC.indexOf("dangerouslySetInnerHTML"));
    const taClass = SRC.slice(SRC.indexOf("className=\"relative w-full"), SRC.indexOf("style={{"));
    expect(preClass).toContain("leading-normal");
    expect(taClass).toContain("leading-normal");
  });

  it("pre and textarea both use matching padding", () => {
    const preClass = SRC.slice(SRC.indexOf("className=\"absolute"), SRC.indexOf("dangerouslySetInnerHTML"));
    const taClass = SRC.slice(SRC.indexOf("className=\"relative w-full"), SRC.indexOf("style={{"));
    expect(preClass).toContain("px-3 py-2.5");
    expect(taClass).toContain("px-3 py-2.5");
  });

  it("pre uses whitespace-pre-wrap and break-words for wrapping", () => {
    const preClass = SRC.slice(SRC.indexOf("className=\"absolute"), SRC.indexOf("dangerouslySetInnerHTML"));
    expect(preClass).toContain("whitespace-pre-wrap");
    expect(preClass).toContain("break-words");
  });

  it("shiki inner pre also gets whitespace-pre-wrap", () => {
    expect(SRC).toContain("[&_pre]:!whitespace-pre-wrap");
    expect(SRC).toContain("[&_pre]:!break-words");
  });

  it("does not force text color on code spans (lets shiki inline styles work)", () => {
    // This was the original bug — [&_code]:!text-content overrode shiki colors
    expect(SRC).not.toContain("[&_code]:!text-content");
  });

  it("uses shared getHighlighter from shikiHighlighter module", () => {
    expect(SRC).toContain('from "@/components/ui/shikiHighlighter"');
    expect(SRC).not.toContain("createHighlighter");
  });
});
