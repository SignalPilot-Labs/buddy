import { describe, it, expect } from "vitest";
import { getButtonState } from "@/lib/commandState";

describe("getButtonState", () => {
  it("returns disabled Send when no run selected", () => {
    const state = getButtonState(null, false);
    expect(state.label).toBe("Send");
    expect(state.disabled).toBe(true);
    expect(state.icon).toBe("send");
  });

  it("returns disabled Send when starting", () => {
    const state = getButtonState("starting", false);
    expect(state.disabled).toBe(true);
  });

  it("returns Pause when running with no text", () => {
    const state = getButtonState("running", false);
    expect(state.label).toBe("Pause");
    expect(state.variant).toBe("warning");
    expect(state.icon).toBe("pause");
    expect(state.disabled).toBe(false);
  });

  it("returns Send when running with text", () => {
    const state = getButtonState("running", true);
    expect(state.label).toBe("Send");
    expect(state.variant).toBe("primary");
    expect(state.icon).toBe("send");
    expect(state.disabled).toBe(false);
  });

  it("returns disabled Send when paused with no text", () => {
    const state = getButtonState("paused", false);
    expect(state.label).toBe("Send");
    expect(state.disabled).toBe(true);
  });

  it("returns Send when paused with text", () => {
    const state = getButtonState("paused", true);
    expect(state.label).toBe("Send");
    expect(state.variant).toBe("primary");
    expect(state.disabled).toBe(false);
  });

  it("returns disabled Rate limited when rate limited with no text", () => {
    const state = getButtonState("rate_limited", false);
    expect(state.label).toBe("Rate limited");
    expect(state.disabled).toBe(true);
  });

  it("returns Send when rate limited with text", () => {
    const state = getButtonState("rate_limited", true);
    expect(state.label).toBe("Send");
    expect(state.disabled).toBe(false);
  });

  const terminalStatuses = ["completed", "stopped", "error", "crashed", "killed", "completed_no_changes"] as const;

  terminalStatuses.forEach((status) => {
    it(`returns disabled Send when ${status} with no text`, () => {
      const state = getButtonState(status, false);
      expect(state.label).toBe("Send");
      expect(state.disabled).toBe(true);
    });

    it(`returns Send when ${status} with text`, () => {
      const state = getButtonState(status, true);
      expect(state.label).toBe("Send");
      expect(state.variant).toBe("success");
      expect(state.disabled).toBe(false);
    });
  });
});
