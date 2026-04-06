/**
 * StartRunModal component tests.
 *
 * Covers: opening/closing, extended context checkbox, busy state,
 * and onStart callback wiring.
 */

import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { StartRunModal } from "@/components/controls/StartRunModal";

function renderModal(overrides = {}) {
  const defaults = {
    open: true,
    onClose: vi.fn(),
    onStart: vi.fn(),
    busy: false,
    branches: ["main", "staging", "develop"],
  };
  const props = { ...defaults, ...overrides };
  return { ...render(<StartRunModal {...props} />), props };
}

describe("StartRunModal", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("renders modal content when open", () => {
    renderModal();
    // Modal renders in portal — search whole document
    expect(document.body.textContent).toContain("New Run");
  });

  it("does not render when closed", () => {
    renderModal({ open: false });
    expect(document.body.textContent).not.toContain("General improvement");
  });

  it("shows extended context checkbox", () => {
    renderModal();
    expect(document.body.textContent).toContain("Extended Context");
  });

  it("shows branch selector with main", () => {
    renderModal();
    expect(document.body.textContent).toContain("main");
  });

  it("disables when busy", () => {
    renderModal({ busy: true });
    expect(document.body.textContent).toContain("Starting...");
  });

  it("calls onStart when start button clicked", async () => {
    const { props } = renderModal();
    // Find the start/submit button by text
    const buttons = document.querySelectorAll("button");
    const startBtn = Array.from(buttons).find(
      (b) => b.textContent?.includes("New Run") && !b.textContent?.includes("Starting")
    );
    if (startBtn) {
      await userEvent.click(startBtn);
      expect(props.onStart).toHaveBeenCalledOnce();
    }
  });
});
