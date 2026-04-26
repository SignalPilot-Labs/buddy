/**
 * Regression test: GroupCards must track expansion state by tool ID, not array index.
 *
 * Before the fix, both `ReadGroupCard` and `EditGroupCard` used the loop index `i`
 * from `.map((item, i) => ...)` as the expansion key. When new tool calls arrived
 * via SSE and the `tools` prop grew, the index-to-item mapping shifted, causing the
 * wrong item to appear expanded or the expanded state to collapse unexpectedly.
 *
 * The fix uses `tools[i].id` (stable DB primary key) instead of `i` for all
 * expansion toggle and comparison expressions in both card components.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/feed/GroupCards.tsx"),
  "utf-8",
);

describe("GroupCards: expansion state keyed by tool ID", () => {
  it("ReadGroupCard toggle sets previewIdx to tools[i].id", () => {
    // Should use tools[i].id in the toggle, not bare i
    expect(SRC).toContain("setPreviewIdx(previewIdx === tools[i].id ? null : tools[i].id)");
  });

  it("ReadGroupCard chevron comparison uses tools[i].id", () => {
    expect(SRC).toContain("open={previewIdx === tools[i].id}");
  });

  it("ReadGroupCard content visibility check uses tools[i].id", () => {
    expect(SRC).toContain("previewIdx === tools[i].id && !!fileObj?.content");
  });

  it("EditGroupCard toggle sets expandedFile to tools[i].id", () => {
    expect(SRC).toContain("setExpandedFile(expandedFile === tools[i].id ? null : tools[i].id)");
  });

  it("EditGroupCard chevron comparison uses tools[i].id", () => {
    expect(SRC).toContain("open={expandedFile === tools[i].id}");
  });

  it("EditGroupCard content block uses tools[i].id", () => {
    expect(SRC).toContain("expandedFile === tools[i].id && (() => {");
  });

  it("no bare index comparison for previewIdx remains", () => {
    // Must not contain the old pattern: previewIdx === i (where i is the loop var)
    // We check there's no setPreviewIdx(... === i ? null : i)
    expect(SRC).not.toContain("setPreviewIdx(previewIdx === i ? null : i)");
  });

  it("no bare index comparison for expandedFile remains", () => {
    expect(SRC).not.toContain("setExpandedFile(expandedFile === i ? null : i)");
  });
});
