/**
 * Regression test: usePanelResize must remove document mousemove/mouseup
 * listeners and restore document.body.style on unmount, even when unmount
 * happens mid-drag (before mouseup fires).
 *
 * Before the fix, the only cleanup path was inside the mouseup handler.
 * If the component unmounted between mousedown and mouseup, the listeners
 * leaked and document.body.style.userSelect/cursor were stuck.
 *
 * The fix adds a useEffect (empty deps) whose cleanup function checks
 * listenersAttachedRef and removes the listeners + restores styles.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { usePanelResize } from "@/hooks/usePanelResize";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../hooks/usePanelResize.ts"),
  "utf-8",
);

const HOOK_OPTIONS = {
  storageKey: "cleanup_test_panel",
  defaultWidth: 280,
  minWidth: 200,
  maxWidth: 600,
  maxWidthRatio: null as null,
  direction: "right" as const,
};

function fireMouseDown(handleMouseDown: (e: React.MouseEvent) => void): void {
  const fakeEvent = {
    preventDefault: vi.fn(),
    clientX: 400,
  } as unknown as React.MouseEvent;
  handleMouseDown(fakeEvent);
}

describe("usePanelResize: unmount cleanup (Bug 1)", () => {
  beforeEach(() => {
    localStorage.clear();
    document.body.style.userSelect = "";
    document.body.style.cursor = "";
  });

  afterEach(() => {
    vi.restoreAllMocks();
    document.body.style.userSelect = "";
    document.body.style.cursor = "";
  });

  it("source declares listenersAttachedRef", () => {
    expect(SRC).toContain("listenersAttachedRef = useRef(false)");
  });

  it("source sets listenersAttachedRef.current = true in handleMouseDown", () => {
    const mouseDownStart = SRC.indexOf("const handleMouseDown");
    const mouseDownEnd = SRC.indexOf("};", mouseDownStart);
    const mouseDownBody = SRC.slice(mouseDownStart, mouseDownEnd);
    expect(mouseDownBody).toContain("listenersAttachedRef.current = true");
  });

  it("source sets listenersAttachedRef.current = false in upRef.current", () => {
    const upStart = SRC.indexOf("upRef.current = (): void =>");
    const upEnd = SRC.indexOf("};", upStart);
    const upBody = SRC.slice(upStart, upEnd);
    expect(upBody).toContain("listenersAttachedRef.current = false");
  });

  it("source has a useEffect with empty deps that returns a cleanup function", () => {
    // The cleanup useEffect must have [] as deps and return a cleanup arrow
    expect(SRC).toContain("}, []);");
    // The cleanup function checks listenersAttachedRef and removes listeners
    expect(SRC).toContain('document.removeEventListener("mousemove", stableMove)');
    expect(SRC).toContain('document.removeEventListener("mouseup", stableUp)');
  });

  it("cleanup effect resets body userSelect and cursor", () => {
    // Both style resets appear in cleanup
    const cleanupStart = SRC.indexOf("// Unmount cleanup:");
    const cleanupEnd = SRC.indexOf("}, []);", cleanupStart) + 10;
    const cleanupBody = SRC.slice(cleanupStart, cleanupEnd);
    expect(cleanupBody).toContain('document.body.style.userSelect = ""');
    expect(cleanupBody).toContain('document.body.style.cursor = ""');
  });

  it("removeEventListener is called on unmount after mousedown without mouseup", () => {
    const removeSpy = vi.spyOn(document, "removeEventListener");

    const { result, unmount } = renderHook(() => usePanelResize(HOOK_OPTIONS));

    // Simulate mousedown to attach listeners
    act(() => {
      fireMouseDown(result.current.handleMouseDown);
    });

    // Verify body styles were set during drag
    expect(document.body.style.userSelect).toBe("none");
    expect(document.body.style.cursor).toBe("col-resize");

    // Unmount before mouseup fires
    act(() => {
      unmount();
    });

    // Both listeners must have been removed
    const calls = removeSpy.mock.calls.map((c) => c[0]);
    expect(calls).toContain("mousemove");
    expect(calls).toContain("mouseup");
  });

  it("body styles are restored on unmount mid-drag", () => {
    const { result, unmount } = renderHook(() => usePanelResize(HOOK_OPTIONS));

    act(() => {
      fireMouseDown(result.current.handleMouseDown);
    });

    expect(document.body.style.userSelect).toBe("none");
    expect(document.body.style.cursor).toBe("col-resize");

    act(() => {
      unmount();
    });

    expect(document.body.style.userSelect).toBe("");
    expect(document.body.style.cursor).toBe("");
  });

  it("cleanup is idempotent: unmounting without mousedown does not throw", () => {
    const removeSpy = vi.spyOn(document, "removeEventListener");
    const { unmount } = renderHook(() => usePanelResize(HOOK_OPTIONS));

    // Unmount without ever triggering mousedown
    expect(() => {
      act(() => {
        unmount();
      });
    }).not.toThrow();

    // No removal calls for mousemove/mouseup — listeners were never added
    const calls = removeSpy.mock.calls.map((c) => c[0]);
    expect(calls).not.toContain("mousemove");
    expect(calls).not.toContain("mouseup");
  });

  it("normal drag-to-mouseup still works after the fix", () => {
    const removeSpy = vi.spyOn(document, "removeEventListener");
    const { result } = renderHook(() => usePanelResize(HOOK_OPTIONS));

    act(() => {
      fireMouseDown(result.current.handleMouseDown);
    });

    // Fire mouseup via document
    act(() => {
      document.dispatchEvent(new MouseEvent("mouseup"));
    });

    // Listeners should be removed by the mouseup handler
    const calls = removeSpy.mock.calls.map((c) => c[0]);
    expect(calls).toContain("mousemove");
    expect(calls).toContain("mouseup");

    // Body styles restored
    expect(document.body.style.userSelect).toBe("");
    expect(document.body.style.cursor).toBe("");
  });
});
