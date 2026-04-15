/**
 * Message card consistency tests.
 *
 * LLMMessageCard and ControlMessage share the same card layout pattern.
 * If one changes structure, the other must match. These tests catch
 * style drift between the two cards.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/feed/MessageCards.tsx"),
  "utf-8",
);

describe("message card consistency", () => {
  it("both cards use rounded-lg p-4 border-l-2 layout", () => {
    // Both LLMMessageCard and ControlMessage must use the same card frame
    const matches = SRC.match(/rounded-lg p-4 border-l-2/g);
    expect(matches).not.toBeNull();
    expect(matches!.length).toBeGreaterThanOrEqual(2);
  });

  it("both cards use text-title font-semibold for header", () => {
    const matches = SRC.match(/text-title font-semibold/g);
    expect(matches).not.toBeNull();
    expect(matches!.length).toBeGreaterThanOrEqual(2);
  });

  it("both cards use text-caption for timestamp", () => {
    const matches = SRC.match(/text-caption text-text-dim tabular-nums/g);
    expect(matches).not.toBeNull();
    expect(matches!.length).toBeGreaterThanOrEqual(2);
  });

  it("both cards use h-6 w-6 icon container", () => {
    const matches = SRC.match(/h-6 w-6 rounded-md/g);
    expect(matches).not.toBeNull();
    expect(matches!.length).toBeGreaterThanOrEqual(2);
  });
});
