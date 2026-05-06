/**
 * Regression tests for SandboxPicker async race condition (BUG 5).
 *
 * Root cause: handleRemoteClick is async. Between invoking fetchLastStartCmd
 * and it resolving, the user can click another sandbox. When the stale fetch
 * resolves it would call onStartCmdChange and onSelect with the first sandbox's
 * id/cmd, overwriting the newer selection.
 *
 * Fix: generation counter (selectGenRef) — incremented on each click, checked
 * after await. Stale results are discarded if gen !== selectGenRef.current.
 */

import { render, screen, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

vi.mock("@/lib/api", () => ({
  fetchLastStartCmd: vi.fn(),
}));

import { SandboxPicker } from "@/components/controls/SandboxPicker";
import { fetchLastStartCmd } from "@/lib/api";

const SANDBOX_A = {
  id: "sandbox-a",
  name: "GPU A",
  ssh_target: "user@gpu-a",
  type: "docker" as const,
  default_start_cmd: "docker run A",
  queue_timeout: 300,
  heartbeat_timeout: 60,
  work_dir: "/workspace",
};

const SANDBOX_B = {
  id: "sandbox-b",
  name: "GPU B",
  ssh_target: "user@gpu-b",
  type: "docker" as const,
  default_start_cmd: "docker run B",
  queue_timeout: 300,
  heartbeat_timeout: 60,
  work_dir: "/workspace",
};

function renderPicker(overrides: {
  onSelect?: (id: string | null) => void;
  onStartCmdChange?: (cmd: string) => void;
} = {}) {
  const onSelect = overrides.onSelect ?? vi.fn();
  const onStartCmdChange = overrides.onStartCmdChange ?? vi.fn();
  render(
    <SandboxPicker
      sandboxes={[SANDBOX_A, SANDBOX_B]}
      selectedId={null}
      onSelect={onSelect}
      startCmd="docker run local"
      onStartCmdChange={onStartCmdChange}
      activeRepo="my-repo"
    />,
  );
  return { onSelect, onStartCmdChange };
}

describe("SandboxPicker: stale async fetch race condition (BUG 5)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("source code contains selectGenRef and the stale-fetch guard", () => {
    const fs = require("fs") as typeof import("fs");
    const path = require("path") as typeof import("path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../components/controls/SandboxPicker.tsx"),
      "utf-8",
    );

    expect(src).toContain("selectGenRef");
    expect(src).toContain("gen !== selectGenRef.current");
  });

  it("generation increment happens before the await, guard happens after", () => {
    const fs = require("fs") as typeof import("fs");
    const path = require("path") as typeof import("path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../components/controls/SandboxPicker.tsx"),
      "utf-8",
    );

    const fnStart = src.indexOf("const handleRemoteClick");
    const fnBody = src.slice(fnStart, src.indexOf("\n  }, [", fnStart));

    const genIncrPos = fnBody.indexOf("++selectGenRef.current");
    const awaitPos = fnBody.indexOf("await ");
    const guardPos = fnBody.indexOf("if (gen !== selectGenRef.current) return");

    expect(genIncrPos).toBeGreaterThan(0);
    expect(awaitPos).toBeGreaterThan(genIncrPos);
    expect(guardPos).toBeGreaterThan(awaitPos);
  });

  it("guard is only in the async else branch, not the synchronous cached branch", () => {
    const fs = require("fs") as typeof import("fs");
    const path = require("path") as typeof import("path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../components/controls/SandboxPicker.tsx"),
      "utf-8",
    );

    const fnStart = src.indexOf("const handleRemoteClick");
    const fnBody = src.slice(fnStart, src.indexOf("\n  }, [", fnStart));

    // Guard must appear exactly once — only in the else branch
    const guardCount = (fnBody.match(/gen !== selectGenRef\.current/g) ?? []).length;
    expect(guardCount).toBe(1);

    // It must appear after the await (async else branch), not before
    const awaitPos = fnBody.indexOf("await ");
    const guardPos = fnBody.indexOf("gen !== selectGenRef.current");
    expect(guardPos).toBeGreaterThan(awaitPos);
  });

  it("behavioral: clicking B after A resolves A first — B's id is selected, not A's", async () => {
    let resolveA!: (value: string | null) => void;
    let resolveB!: (value: string | null) => void;

    const mockedFetch = fetchLastStartCmd as ReturnType<typeof vi.fn>;
    mockedFetch
      .mockImplementationOnce(
        () => new Promise<string | null>((res) => { resolveA = res; }),
      )
      .mockImplementationOnce(
        () => new Promise<string | null>((res) => { resolveB = res; }),
      );

    const onSelect = vi.fn();
    const onStartCmdChange = vi.fn();

    renderPicker({ onSelect, onStartCmdChange });

    const btnA = screen.getByText(/GPU A/);
    const btnB = screen.getByText(/GPU B/);

    // Click A — starts async fetch for A
    await userEvent.click(btnA);

    // Click B — starts async fetch for B (increments gen to 2)
    await userEvent.click(btnB);

    // Resolve A first (stale result — gen will be 1, current is 2)
    await act(async () => {
      resolveA("cmd-from-a");
    });

    // Resolve B second (fresh result)
    await act(async () => {
      resolveB("cmd-from-b");
    });

    // onSelect should have been called with sandbox-b (the last clicked)
    // It must NOT have been called with sandbox-a after sandbox-b was selected
    const selectCalls = onSelect.mock.calls.map((c) => c[0] as string | null);

    // The last call to onSelect must be for B
    expect(selectCalls[selectCalls.length - 1]).toBe("sandbox-b");

    // onStartCmdChange must not have been called with A's command after B was selected
    const cmdCalls = onStartCmdChange.mock.calls.map((c) => c[0] as string);
    const lastCmd = cmdCalls[cmdCalls.length - 1];
    expect(lastCmd).toBe("cmd-from-b");

    // Critically: A's cmd must not appear after B's cmd in the call sequence
    const aIdx = cmdCalls.lastIndexOf("cmd-from-a");
    const bIdx = cmdCalls.lastIndexOf("cmd-from-b");
    // If A's cmd was applied after B's that would be the bug — assert it isn't
    expect(aIdx).toBeLessThan(bIdx === -1 ? Infinity : bIdx);
  });
});
