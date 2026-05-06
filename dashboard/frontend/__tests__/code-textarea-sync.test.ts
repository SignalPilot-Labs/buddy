/**
 * Regression test: CodeTextarea highlight overlay must stay in sync
 * with the textarea — matching font, padding, line-height, and wrap.
 *
 * Both layers reference the same SHARED constant for text styling,
 * so we verify that constant contains the required classes and both
 * elements use it.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/ui/CodeTextarea.tsx"),
  "utf-8",
);

describe("CodeTextarea: highlight and textarea must stay in sync", () => {
  it("shared constant contains all required text styling classes", () => {
    const sharedLine = SRC.slice(SRC.indexOf("SHARED"), SRC.indexOf("export default"));
    expect(sharedLine).toContain("font-mono");
    expect(sharedLine).toContain("text-content");
    expect(sharedLine).toContain("leading-normal");
    expect(sharedLine).toContain("px-3 py-2.5");
    expect(sharedLine).toContain("whitespace-pre-wrap");
    expect(sharedLine).toContain("break-words");
  });

  it("pre and textarea both reference the shared style constant", () => {
    const preSection = SRC.slice(SRC.indexOf("<pre"), SRC.indexOf("</pre>"));
    const taSection = SRC.slice(SRC.indexOf("<textarea"), SRC.indexOf("</textarea>"));
    expect(preSection).toContain("${SHARED}");
    expect(taSection).toContain("${SHARED}");
  });

  it("pre uses overflow-auto for scroll sync", () => {
    const preSection = SRC.slice(SRC.indexOf("<pre"), SRC.indexOf("</pre>"));
    expect(preSection).toContain("overflow-auto");
  });

  it("shiki inner pre also gets whitespace-pre-wrap", () => {
    expect(SRC).toContain("[&_pre]:!whitespace-pre-wrap");
    expect(SRC).toContain("[&_pre]:!break-words");
  });

  it("does not force text color on code spans (lets shiki inline styles work)", () => {
    expect(SRC).not.toContain("[&_code]:!text-content");
  });

  it("uses shared getHighlighter from shikiHighlighter module", () => {
    expect(SRC).toContain('from "@/components/ui/shikiHighlighter"');
    expect(SRC).not.toContain("createHighlighter");
  });

  it("syncScroll handler updates pre scroll position", () => {
    expect(SRC).toContain("preRef.current.scrollTop = textareaRef.current.scrollTop");
    expect(SRC).toContain("preRef.current.scrollLeft = textareaRef.current.scrollLeft");
  });
});
