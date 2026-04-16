import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { usePanelResize } from "@/hooks/usePanelResize";
import { PANEL_WIDTH_STORAGE_PREFIX } from "@/lib/constants";

const STORAGE_KEY = "test_panel";
const FULL_KEY = PANEL_WIDTH_STORAGE_PREFIX + STORAGE_KEY;

function setViewport(width: number): void {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    value: width,
  });
}

function fireResize(): void {
  window.dispatchEvent(new Event("resize"));
}

describe("usePanelResize", () => {
  beforeEach(() => {
    localStorage.clear();
    setViewport(1000);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("maxWidthRatio: null (fixed-pixel clamping)", () => {
    it("clamps stored width to maxWidth even on a huge viewport", () => {
      localStorage.setItem(FULL_KEY, "9999");
      setViewport(4000);
      const { result } = renderHook(() =>
        usePanelResize({
          storageKey: STORAGE_KEY,
          defaultWidth: 280,
          minWidth: 200,
          maxWidth: 400,
          maxWidthRatio: null,
          direction: "right",
        }),
      );
      expect(result.current.width).toBe(400);
    });

    it("does not re-clamp on window resize", () => {
      localStorage.setItem(FULL_KEY, "350");
      const { result } = renderHook(() =>
        usePanelResize({
          storageKey: STORAGE_KEY,
          defaultWidth: 280,
          minWidth: 200,
          maxWidth: 400,
          maxWidthRatio: null,
          direction: "right",
        }),
      );
      expect(result.current.width).toBe(350);
      act(() => {
        setViewport(400);
        fireResize();
      });
      // No ratio → resize has no effect; stored width persists.
      expect(result.current.width).toBe(350);
    });
  });

  describe("maxWidthRatio set (viewport-relative clamping)", () => {
    it("clamps to innerWidth * ratio when that is smaller than maxWidth", () => {
      localStorage.setItem(FULL_KEY, "1400");
      setViewport(1000); // 1000 * 0.5 = 500
      const { result } = renderHook(() =>
        usePanelResize({
          storageKey: STORAGE_KEY,
          defaultWidth: 280,
          minWidth: 200,
          maxWidth: 1600,
          maxWidthRatio: 0.5,
          direction: "right",
        }),
      );
      expect(result.current.width).toBe(500);
    });

    it("clamps to maxWidth when the ratio would allow more (ultrawide)", () => {
      localStorage.setItem(FULL_KEY, "2000");
      setViewport(4000); // 4000 * 0.7 = 2800, but maxWidth=1600 wins
      const { result } = renderHook(() =>
        usePanelResize({
          storageKey: STORAGE_KEY,
          defaultWidth: 280,
          minWidth: 200,
          maxWidth: 1600,
          maxWidthRatio: 0.7,
          direction: "right",
        }),
      );
      expect(result.current.width).toBe(1600);
    });

    it("shrinks stored width on window resize when viewport narrows", () => {
      localStorage.setItem(FULL_KEY, "800");
      setViewport(2000); // Initially 2000*0.5=1000, stored 800 fits.
      const { result } = renderHook(() =>
        usePanelResize({
          storageKey: STORAGE_KEY,
          defaultWidth: 280,
          minWidth: 200,
          maxWidth: 1600,
          maxWidthRatio: 0.5,
          direction: "right",
        }),
      );
      expect(result.current.width).toBe(800);
      act(() => {
        setViewport(1000); // 1000*0.5=500 → clamp 800 down to 500
        fireResize();
      });
      expect(result.current.width).toBe(500);
    });

    it("does not grow stored width back up on window resize", () => {
      localStorage.setItem(FULL_KEY, "400");
      setViewport(1000);
      const { result } = renderHook(() =>
        usePanelResize({
          storageKey: STORAGE_KEY,
          defaultWidth: 280,
          minWidth: 200,
          maxWidth: 1600,
          maxWidthRatio: 0.5,
          direction: "right",
        }),
      );
      expect(result.current.width).toBe(400);
      act(() => {
        setViewport(4000); // ratio allows 2000 now, but stored 400 should stay.
        fireResize();
      });
      expect(result.current.width).toBe(400);
    });
  });

  describe("defaults and bounds", () => {
    it("returns defaultWidth when no stored value", () => {
      const { result } = renderHook(() =>
        usePanelResize({
          storageKey: STORAGE_KEY,
          defaultWidth: 280,
          minWidth: 200,
          maxWidth: 1600,
          maxWidthRatio: 0.7,
          direction: "right",
        }),
      );
      expect(result.current.width).toBe(280);
    });

    it("clamps stored value below minWidth up to minWidth", () => {
      localStorage.setItem(FULL_KEY, "50");
      const { result } = renderHook(() =>
        usePanelResize({
          storageKey: STORAGE_KEY,
          defaultWidth: 280,
          minWidth: 200,
          maxWidth: 1600,
          maxWidthRatio: null,
          direction: "right",
        }),
      );
      expect(result.current.width).toBe(200);
    });
  });
});
