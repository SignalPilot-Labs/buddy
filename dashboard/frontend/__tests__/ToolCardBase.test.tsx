/**
 * Regression tests for ToolCardBase typography.
 * Ensures tool card font sizes stay within the design-system scale.
 */

import { render, screen } from "@testing-library/react";
import { ToolCardBase } from "@/components/feed/ToolCardBase";
import { makeToolCall } from "./testFactories";

describe("ToolCardBase", () => {
  it("card variant button uses text-body (13px), not browser default", () => {
    render(
      <ToolCardBase
        tool={makeToolCall({ tool_name: "Write", input_data: { file_path: "/tmp/foo.ts" } })}
        variant="card"
      />,
    );
    const button = screen.getByRole("button");
    expect(button.className).toContain("text-body");
  });

  it("inline variant button uses text-content (12px)", () => {
    render(
      <ToolCardBase
        tool={makeToolCall({ tool_name: "Read", output_data: { content: "x" } })}
        variant="inline"
      />,
    );
    const button = screen.getByRole("button");
    expect(button.className).toContain("text-content");
  });
});
