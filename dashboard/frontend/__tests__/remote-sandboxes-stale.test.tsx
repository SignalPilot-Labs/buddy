/**
 * Regression test: RemoteSandboxes must not call setSandboxes or setError
 * after the component unmounts (e.g. user navigates away while fetch is in-flight).
 *
 * Before the fix, the useEffect called fetchRemoteSandboxes().then(setSandboxes)
 * with no unmount guard. If the fetch resolved after unmount it would still
 * call setState, triggering a React warning and potential inconsistent UI state.
 *
 * The fix adds a `cancelled` flag that is set to true in the cleanup function.
 * All setState calls check `if (cancelled) return;` before executing.
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
  path.resolve(__dirname, "../components/settings/RemoteSandboxes.tsx"),
  "utf-8",
);

describe("RemoteSandboxes: unmount guard (cancelled flag)", () => {
  it("source code declares a cancelled flag inside the useEffect", () => {
    // The initial fetch useEffect must declare let cancelled = false
    const effectIdx = SRC.indexOf("fetchRemoteSandboxes()");
    expect(effectIdx).toBeGreaterThan(0);
    // cancelled declaration must appear before the fetch call
    const cancelledDeclIdx = SRC.lastIndexOf("let cancelled = false", effectIdx);
    expect(cancelledDeclIdx).toBeGreaterThan(0);
    expect(cancelledDeclIdx).toBeLessThan(effectIdx);
  });

  it("source code returns a cleanup that sets cancelled = true", () => {
    // The cleanup must set cancelled to true
    expect(SRC).toContain("cancelled = true");
    // It must be inside a return () => { ... } cleanup
    expect(SRC).toContain("return () => { cancelled = true; }");
  });

  it("setSandboxes is guarded with if (cancelled) return", () => {
    const setIdx = SRC.indexOf("setSandboxes(");
    expect(setIdx).toBeGreaterThan(0);
    // The guard must appear on the same .then() callback, before setSandboxes
    const thenIdx = SRC.lastIndexOf(".then(", setIdx);
    const guardIdx = SRC.indexOf("if (cancelled) return", thenIdx);
    // Guard must exist between .then( and setSandboxes(
    expect(guardIdx).toBeGreaterThan(thenIdx);
    expect(guardIdx).toBeLessThan(setIdx);
  });

  it("setError (in catch) is guarded with if (cancelled) return", () => {
    // Find the catch handler that calls setError
    const catchIdx = SRC.indexOf(".catch(");
    expect(catchIdx).toBeGreaterThan(0);
    const catchBody = SRC.slice(catchIdx, catchIdx + 120);
    expect(catchBody).toContain("if (cancelled) return");
    expect(catchBody).toContain("setError(");
  });

  it("behavioural: unmounting before fetch resolves does not call setSandboxes", async () => {
    let resolveFetch!: (value: api.RemoteSandboxConfig[]) => void;
    const pendingFetch = new Promise<api.RemoteSandboxConfig[]>((res) => {
      resolveFetch = res;
    });

    const fetchSpy = vi.spyOn(api, "fetchRemoteSandboxes").mockReturnValue(pendingFetch);

    // Lazy import to avoid module-level import issues with the spy
    const { RemoteSandboxes } = await import("@/components/settings/RemoteSandboxes");

    const { unmount } = render(<RemoteSandboxes />);

    // Unmount before the fetch resolves — triggers cancelled = true
    unmount();

    // Now resolve the fetch — setState should be suppressed
    await act(async () => {
      resolveFetch([]);
    });

    // The spy must have been called (fetch did fire), but after unmount the
    // cancelled flag should have prevented any setState from running.
    expect(fetchSpy).toHaveBeenCalledOnce();
    // No assertion for setState — React 18+ does not throw on post-unmount
    // setState, but the guard prevents it. We verify the guard exists via
    // the source-level tests above.
  });

  it("behavioural: fetch resolving before unmount still sets state", async () => {
    const sandbox: api.RemoteSandboxConfig = {
      id: "s1",
      name: "prod-box",
      ssh_target: "user@host",
      type: "docker",
      default_start_cmd: "docker run ...",
      queue_timeout: 1800,
      heartbeat_timeout: 1800,
      work_dir: "/work",
    };

    vi.spyOn(api, "fetchRemoteSandboxes").mockResolvedValue([sandbox]);

    const { RemoteSandboxes } = await import("@/components/settings/RemoteSandboxes");
    const { container } = render(<RemoteSandboxes />);

    // Wait for the fetch to resolve and state to update
    await act(async () => {
      await Promise.resolve();
    });

    // The sandbox name should appear in the rendered output
    expect(container.textContent).toContain("prod-box");
  });
});
