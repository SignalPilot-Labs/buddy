/**
 * Regression tests for StartRunModal state management bugs.
 *
 * Bug 1: Double-start race — rapid clicks could invoke onStart multiple times
 *   before the button became disabled on first click.
 *   Fix: local `submitting` state + `submittingRef` ref set at handleStart entry,
 *   button disabled when `busy || submitting`.
 *
 * Bug 2: Stale form state — values entered in a previous open cycle persisted
 *   when the modal was reopened.
 *   Fix: useEffect resets all form state when `open` transitions false -> true.
 */

import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { StartRunModal } from "@/components/controls/StartRunModal";
import { DEFAULT_BASE_BRANCH, DEFAULT_EFFORT } from "@/lib/constants";

function renderModal(overrides: Partial<{
  open: boolean;
  onClose: () => void;
  onStart: (...args: unknown[]) => void;
  busy: boolean;
  branches: string[];
  activeRepo: string | null;
}> = {}) {
  const defaults = {
    open: true,
    onClose: vi.fn(),
    onStart: vi.fn(),
    busy: false,
    branches: ["main"],
    activeRepo: null,
  };
  const props = { ...defaults, ...overrides };
  return { ...render(<StartRunModal {...props} />), props };
}

function findStartBtn(): HTMLButtonElement | undefined {
  return Array.from(document.querySelectorAll("button")).find(
    (b) => b.textContent?.trim() === "New Run" || b.textContent?.trim() === "Starting...",
  ) as HTMLButtonElement | undefined;
}

describe("StartRunModal: double-start prevention (Bug 1)", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("start button is disabled while busy=true", () => {
    renderModal({ busy: true });
    const btn = findStartBtn();
    expect(btn?.disabled).toBe(true);
    expect(btn?.textContent?.trim()).toBe("Starting...");
  });

  it("clicking start button when disabled (busy=true) does not invoke onStart", async () => {
    const onStart = vi.fn();
    renderModal({ busy: true, onStart });
    const btn = findStartBtn();
    if (btn) await userEvent.click(btn);
    expect(onStart).not.toHaveBeenCalled();
  });

  it("submittingRef guards prevent re-entry during handleStart execution", () => {
    // Verify that the source code uses both a ref guard and state guard.
    // This is a structural test — the ref guard is synchronous and prevents
    // re-entry even before React re-renders the disabled button.
    const fs = require("fs") as typeof import("fs");
    const path = require("path") as typeof import("path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../components/controls/StartRunModal.tsx"),
      "utf-8",
    );

    // submittingRef must exist
    expect(src).toContain("submittingRef");
    expect(src).toContain("submittingRef.current = true");
    // Guard must be at the start of handleStart
    const fnStart = src.indexOf("const handleStart");
    const fnBody = src.slice(fnStart, src.indexOf("\n  };", fnStart));
    // The ref guard must come before the first real async work
    const guardPos = fnBody.indexOf("if (submittingRef.current) return");
    expect(guardPos).toBeGreaterThan(0);
    // Must be reset in finally
    const finallyPos = fnBody.indexOf("finally");
    const refResetPos = fnBody.indexOf("submittingRef.current = false", finallyPos);
    expect(refResetPos).toBeGreaterThan(finallyPos);
  });

  it("handleKeyDown guard blocks key submission when busy", async () => {
    const onStart = vi.fn();
    const { container } = renderModal({ busy: true, onStart });
    const textarea = container.querySelector("textarea");
    if (textarea) {
      textarea.focus();
      await userEvent.keyboard("{Control>}{Enter}{/Control}");
    }
    expect(onStart).not.toHaveBeenCalled();
  });
});

describe("StartRunModal: state reset on open (Bug 2)", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("prompt textarea is cleared when modal is reopened", async () => {
    const { rerender } = renderModal({ open: true });

    // Type a custom prompt
    const textarea = document.querySelector("textarea")!;
    await userEvent.type(textarea, "my stale prompt");
    expect(textarea.value).toBe("my stale prompt");

    // Close the modal (open=false)
    rerender(
      <StartRunModal
        open={false}
        onClose={vi.fn()}
        onStart={vi.fn()}
        busy={false}
        branches={["main"]}
        activeRepo={null}
      />,
    );

    // Reopen the modal (open=true)
    rerender(
      <StartRunModal
        open={true}
        onClose={vi.fn()}
        onStart={vi.fn()}
        busy={false}
        branches={["main"]}
        activeRepo={null}
      />,
    );

    // Prompt textarea must be cleared
    const freshTextarea = document.querySelector("textarea")!;
    expect(freshTextarea.value).toBe("");
  });

  it("onStart receives default values after modal is reopened without changes", async () => {
    const onStart = vi.fn();
    const { rerender } = renderModal({ open: true, onStart });

    // Make some changes
    const textarea = document.querySelector("textarea")!;
    await userEvent.type(textarea, "previous prompt");

    // Close and reopen
    rerender(
      <StartRunModal
        open={false}
        onClose={vi.fn()}
        onStart={onStart}
        busy={false}
        branches={["main"]}
        activeRepo={null}
      />,
    );
    rerender(
      <StartRunModal
        open={true}
        onClose={vi.fn()}
        onStart={onStart}
        busy={false}
        branches={["main"]}
        activeRepo={null}
      />,
    );

    // Click start without typing anything — onStart should get default values
    const startBtn = findStartBtn();
    await userEvent.click(startBtn!);

    expect(onStart).toHaveBeenCalledOnce();
    const [prompt, preset, budget, duration, baseBranch, , effort, sandboxId] =
      onStart.mock.calls[0] as [
        string | undefined,
        string | undefined,
        number,
        number,
        string,
        string,
        string,
        string | null,
      ];

    // prompt is undefined (no text typed) or empty string — either represents "no input"
    expect(prompt === undefined || prompt === "").toBe(true);
    expect(preset).toBeUndefined();
    expect(budget).toBe(0);
    expect(duration).toBe(0);
    expect(baseBranch).toBe(DEFAULT_BASE_BRANCH);
    expect(effort).toBe(DEFAULT_EFFORT);
    expect(sandboxId).toBeNull();
  });
});

describe("StartRunModal: source code structural checks", () => {
  it("handleStart sets submitting=true and submittingRef.current=true at entry", () => {
    const fs = require("fs") as typeof import("fs");
    const path = require("path") as typeof import("path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../components/controls/StartRunModal.tsx"),
      "utf-8",
    );

    const fnStart = src.indexOf("const handleStart");
    const fnBody = src.slice(fnStart, src.indexOf("\n  };", fnStart));

    // Both ref and state guards must be set before any await
    const refSetPos = fnBody.indexOf("submittingRef.current = true");
    const stateSetPos = fnBody.indexOf("setSubmitting(true)");
    const firstAwait = fnBody.indexOf("await ");

    expect(refSetPos).toBeGreaterThan(0);
    expect(stateSetPos).toBeGreaterThan(0);
    expect(refSetPos).toBeLessThan(firstAwait > 0 ? firstAwait : Infinity);
    expect(stateSetPos).toBeLessThan(firstAwait > 0 ? firstAwait : Infinity);
  });

  it("handleStart resets both submittingRef and submitting in finally block", () => {
    const fs = require("fs") as typeof import("fs");
    const path = require("path") as typeof import("path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../components/controls/StartRunModal.tsx"),
      "utf-8",
    );

    const fnStart = src.indexOf("const handleStart");
    const fnBody = src.slice(fnStart, src.indexOf("\n  };", fnStart));

    expect(fnBody).toContain("finally");
    const finallyPos = fnBody.indexOf("finally");
    const refResetPos = fnBody.indexOf("submittingRef.current = false", finallyPos);
    const stateResetPos = fnBody.indexOf("setSubmitting(false)", finallyPos);
    expect(refResetPos).toBeGreaterThan(finallyPos);
    expect(stateResetPos).toBeGreaterThan(finallyPos);
  });

  it("button disabled condition includes submitting state", () => {
    const fs = require("fs") as typeof import("fs");
    const path = require("path") as typeof import("path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../components/controls/StartRunModal.tsx"),
      "utf-8",
    );

    const buttonIdx = src.indexOf('variant="success"');
    const buttonSnippet = src.slice(buttonIdx, src.indexOf(">", buttonIdx + 100));
    expect(buttonSnippet).toContain("submitting");
    expect(buttonSnippet).toContain("busy");
  });

  it("reset effect runs on false-to-true transition of open", () => {
    const fs = require("fs") as typeof import("fs");
    const path = require("path") as typeof import("path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../components/controls/StartRunModal.tsx"),
      "utf-8",
    );

    // prevOpenRef must be present for transition tracking
    expect(src).toContain("prevOpenRef");
    // The effect must guard on !wasOpen && open
    expect(src).toContain("!wasOpen && open");
    // Default values must be restored
    expect(src).toContain("setBaseBranch(DEFAULT_BASE_BRANCH)");
    expect(src).toContain("setEffort(DEFAULT_EFFORT)");
    expect(src).toContain("setStartCmd(DEFAULT_DOCKER_START_CMD)");
    // All error states must be cleared
    expect(src).toContain("setEnvError(null)");
    expect(src).toContain("setMountError(null)");
    expect(src).toContain("setMcpError(null)");
    expect(src).toContain("setMountsLoading(false)");
  });

  it("handleKeyDown checks submittingRef before proceeding", () => {
    const fs = require("fs") as typeof import("fs");
    const path = require("path") as typeof import("path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../components/controls/StartRunModal.tsx"),
      "utf-8",
    );

    const fnStart = src.indexOf("const handleKeyDown");
    const fnBody = src.slice(fnStart, src.indexOf("\n  };", fnStart));
    expect(fnBody).toContain("submittingRef.current");
  });
});
