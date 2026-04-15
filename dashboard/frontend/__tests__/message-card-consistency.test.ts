/**
 * Message card structure tests.
 *
 * LLMMessageCard and ControlMessage both compose a shared MessageCard
 * base. These tests verify the base exists and both cards use it,
 * preventing duplication regressions.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/feed/MessageCards.tsx"),
  "utf-8",
);

describe("message card structure", () => {
  it("MessageCard base component exists", () => {
    expect(SRC).toContain("function MessageCard(");
  });

  it("LLMMessageCard composes MessageCard", () => {
    expect(SRC).toContain("<MessageCard");
    // Must appear in LLMMessageCard function body
    const llmBlock = SRC.slice(SRC.indexOf("function LLMMessageCard"), SRC.indexOf("function ControlMessage"));
    expect(llmBlock).toContain("<MessageCard");
  });

  it("ControlMessage composes MessageCard", () => {
    const ctrlBlock = SRC.slice(SRC.indexOf("function ControlMessage"));
    expect(ctrlBlock).toContain("<MessageCard");
  });

  it("layout classes exist only in MessageCard base, not in LLM or Control", () => {
    const llmBlock = SRC.slice(SRC.indexOf("function LLMMessageCard"), SRC.indexOf("function ControlMessage"));
    const ctrlBlock = SRC.slice(SRC.indexOf("function ControlMessage"), SRC.indexOf("function UserPromptCard"));

    // These structural classes must NOT appear in LLM or Control — only in the base
    for (const block of [llmBlock, ctrlBlock]) {
      expect(block).not.toContain("rounded-lg p-4 border-l-2");
      expect(block).not.toContain("h-6 w-6 rounded-md");
    }
  });
});
