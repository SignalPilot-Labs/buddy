/**
 * Regression test: StartRunModal must not call setState on async fetch callbacks
 * after the modal closes (open transitions to false) while fetches are in-flight.
 *
 * Before the fix, three useEffects had unguarded async fetches:
 *   1. fetchRemoteSandboxes().then(setRemoteSandboxes) — no cancelled guard
 *   2. fetchRepoEnv / fetchRepoMcpServers — no cancelled guard
 *   3. fetchLastStartCmd in restore-sandbox effect — no cancelled guard
 *
 * The fix adds a `cancelled` flag in each effect. The cleanup sets cancelled = true
 * and all setState calls check `if (cancelled) return;` before executing.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, act } from "@testing-library/react";
import * as fs from "fs";
import * as path from "path";
import * as api from "@/lib/api";

afterEach(() => {
  vi.restoreAllMocks();
});

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../components/controls/StartRunModal.tsx"),
  "utf-8",
);

describe("StartRunModal: cancelled flag guard — fetchRemoteSandboxes effect", () => {
  it("the fetchRemoteSandboxes useEffect has a cancelled flag", () => {
    // Find the effect block containing fetchRemoteSandboxes
    const effectIdx = SRC.indexOf("fetchRemoteSandboxes()");
    expect(effectIdx).toBeGreaterThan(0);
    // cancelled must be declared before the fetch
    const cancelledIdx = SRC.lastIndexOf("let cancelled = false", effectIdx);
    expect(cancelledIdx).toBeGreaterThan(0);
    expect(cancelledIdx).toBeLessThan(effectIdx);
  });

  it("setRemoteSandboxes in the .then() handler is guarded", () => {
    // Find setRemoteSandboxes call inside the .then() of the fetchRemoteSandboxes effect
    const effectIdx = SRC.indexOf("fetchRemoteSandboxes()");
    const thenIdx = SRC.indexOf(".then(", effectIdx);
    const setIdx = SRC.indexOf("setRemoteSandboxes(", thenIdx);
    const guardIdx = SRC.indexOf("if (cancelled) return", thenIdx);

    expect(thenIdx).toBeGreaterThan(effectIdx);
    expect(guardIdx).toBeGreaterThan(thenIdx);
    expect(guardIdx).toBeLessThan(setIdx);
  });

  it("the fetchRemoteSandboxes effect returns a cleanup that sets cancelled = true", () => {
    const effectIdx = SRC.indexOf("fetchRemoteSandboxes()");
    // Find the closing of the effect — look for the dep array [open]
    const depArrayIdx = SRC.indexOf("}, [open]);", effectIdx);
    expect(depArrayIdx).toBeGreaterThan(0);
    const effectBody = SRC.slice(effectIdx - 100, depArrayIdx);
    expect(effectBody).toContain("return () => { cancelled = true; }");
  });
});

describe("StartRunModal: cancelled flag guard — fetchRepoEnv / fetchRepoMcpServers effect", () => {
  it("the env+mcp useEffect has a cancelled flag", () => {
    const envIdx = SRC.indexOf("fetchRepoEnv(");
    expect(envIdx).toBeGreaterThan(0);
    const cancelledIdx = SRC.lastIndexOf("let cancelled = false", envIdx);
    expect(cancelledIdx).toBeGreaterThan(0);
    expect(cancelledIdx).toBeLessThan(envIdx);
  });

  it("setEnvText is guarded with if (cancelled) return", () => {
    const envIdx = SRC.indexOf("fetchRepoEnv(");
    const thenIdx = SRC.indexOf(".then(", envIdx);
    const setEnvIdx = SRC.indexOf("setEnvText(", thenIdx);
    const guardIdx = SRC.indexOf("if (cancelled) return", thenIdx);

    expect(thenIdx).toBeGreaterThan(0);
    expect(guardIdx).toBeGreaterThan(thenIdx);
    expect(guardIdx).toBeLessThan(setEnvIdx);
  });

  it("setMcpText is guarded with if (cancelled) return", () => {
    const mcpIdx = SRC.indexOf("fetchRepoMcpServers(");
    expect(mcpIdx).toBeGreaterThan(0);
    const thenIdx = SRC.indexOf(".then(", mcpIdx);
    const setMcpIdx = SRC.indexOf("setMcpText(", thenIdx);
    const guardIdx = SRC.indexOf("if (cancelled) return", thenIdx);

    expect(thenIdx).toBeGreaterThan(mcpIdx);
    expect(guardIdx).toBeGreaterThan(thenIdx);
    expect(guardIdx).toBeLessThan(setMcpIdx);
  });

  it("the env+mcp effect returns a cleanup that sets cancelled = true", () => {
    const envIdx = SRC.indexOf("fetchRepoEnv(");
    const depArrayIdx = SRC.indexOf("}, [open, activeRepo]);", envIdx);
    expect(depArrayIdx).toBeGreaterThan(0);
    const effectBody = SRC.slice(envIdx - 100, depArrayIdx);
    expect(effectBody).toContain("return () => { cancelled = true; }");
  });
});

describe("StartRunModal: cancelled flag guard — fetchLastStartCmd in restore-sandbox effect", () => {
  it("the restore-sandbox effect has a cancelled flag", () => {
    const lastCmdIdx = SRC.indexOf("fetchLastStartCmd(");
    expect(lastCmdIdx).toBeGreaterThan(0);
    const cancelledIdx = SRC.lastIndexOf("let cancelled = false", lastCmdIdx);
    expect(cancelledIdx).toBeGreaterThan(0);
    expect(cancelledIdx).toBeLessThan(lastCmdIdx);
  });

  it("setStartCmd in fetchLastStartCmd callback is guarded", () => {
    const lastCmdIdx = SRC.indexOf("fetchLastStartCmd(");
    const thenIdx = SRC.indexOf(".then(", lastCmdIdx);
    const setStartIdx = SRC.indexOf("setStartCmd(", thenIdx);
    const guardIdx = SRC.indexOf("if (cancelled) return", thenIdx);

    expect(thenIdx).toBeGreaterThan(lastCmdIdx);
    expect(guardIdx).toBeGreaterThan(thenIdx);
    expect(guardIdx).toBeLessThan(setStartIdx);
  });
});

describe("StartRunModal: behavioural stale-fetch tests", () => {
  it("closing modal before fetchRemoteSandboxes resolves does not call setRemoteSandboxes", async () => {
    let resolveRemote!: (val: api.RemoteSandboxConfig[]) => void;
    const pendingRemote = new Promise<api.RemoteSandboxConfig[]>((res) => {
      resolveRemote = res;
    });

    vi.spyOn(api, "fetchRemoteSandboxes").mockReturnValue(pendingRemote);
    vi.spyOn(api, "fetchRepoEnv").mockResolvedValue({});
    vi.spyOn(api, "fetchRepoMcpServers").mockResolvedValue({});

    const { StartRunModal } = await import("@/components/controls/StartRunModal");

    const { rerender } = render(
      <StartRunModal
        open={true}
        onClose={vi.fn()}
        onStart={vi.fn()}
        busy={false}
        branches={["main"]}
        activeRepo={null}
      />,
    );

    // Close modal (triggers cleanup, sets cancelled = true)
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

    // Resolve the fetch after modal is closed
    await act(async () => {
      resolveRemote([]);
    });

    // fetchRemoteSandboxes must have been called (effect ran when open=true)
    expect(api.fetchRemoteSandboxes).toHaveBeenCalled();
    // No error / crash — the cancelled guard prevented setState
  });

  it("closing modal before fetchRepoEnv resolves does not update envText", async () => {
    let resolveEnv!: (val: Record<string, string>) => void;
    const pendingEnv = new Promise<Record<string, string>>((res) => {
      resolveEnv = res;
    });

    vi.spyOn(api, "fetchRemoteSandboxes").mockResolvedValue([]);
    vi.spyOn(api, "fetchRepoEnv").mockReturnValue(pendingEnv);
    vi.spyOn(api, "fetchRepoMcpServers").mockResolvedValue({});

    const { StartRunModal } = await import("@/components/controls/StartRunModal");

    const { rerender } = render(
      <StartRunModal
        open={true}
        onClose={vi.fn()}
        onStart={vi.fn()}
        busy={false}
        branches={["main"]}
        activeRepo="my-repo"
      />,
    );

    // Close modal before env fetch resolves
    rerender(
      <StartRunModal
        open={false}
        onClose={vi.fn()}
        onStart={vi.fn()}
        busy={false}
        branches={["main"]}
        activeRepo="my-repo"
      />,
    );

    // Resolve the fetch — cancelled guard should suppress setEnvText
    await act(async () => {
      resolveEnv({ API_KEY: "secret" });
    });

    expect(api.fetchRepoEnv).toHaveBeenCalledWith("my-repo");
    // No crash — guard prevented setState after close
  });
});
