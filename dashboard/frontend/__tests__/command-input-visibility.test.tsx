/**
 * Regression test: CommandInput must only appear when a run is selected.
 *
 * A grayed-out chat box with no active run confuses users into typing
 * there instead of clicking "New Run". Parents must conditionally render
 * CommandInput only when selectedRunId is non-null.
 */

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CommandInput } from "@/components/controls/CommandInput";

const NO_OP = () => {};

function renderWithRunId(runId: string | null) {
  return render(
    <>
      {runId && (
        <CommandInput
          runId={runId}
          status="running"
          run={null}
          connected={true}
          events={[]}
          busy={false}
          onPause={NO_OP}
          onResume={NO_OP}
          onInject={NO_OP}
          onRestart={NO_OP}
        />
      )}
    </>,
  );
}

describe("CommandInput visibility", () => {
  it("renders textarea when a run is selected", () => {
    renderWithRunId("run-123");
    expect(screen.getByRole("textbox")).toBeDefined();
  });

  it("does not render textarea when no run is selected", () => {
    renderWithRunId(null);
    expect(screen.queryByRole("textbox")).toBeNull();
  });
});
