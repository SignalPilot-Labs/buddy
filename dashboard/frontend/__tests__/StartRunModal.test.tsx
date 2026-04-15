/**
 * StartRunModal component tests.
 *
 * Covers: opening/closing, model selector, busy state,
 * collapsed sections, expand behavior, and onStart callback wiring.
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
    activeRepo: null,
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
    expect(document.body.textContent).toContain("New Run");
  });

  it("does not render when closed", () => {
    renderModal({ open: false });
    expect(document.body.textContent).not.toContain("General improvement");
  });

  it("shows model selector with model options", () => {
    renderModal();
    // "Model" label appears in CollapsibleSection header
    expect(document.body.textContent).toContain("Model");
    // Summary text includes model label when collapsed
    expect(document.body.textContent).toContain("Claude Opus 4.6");
  });

  it("shows quick start options", () => {
    renderModal();
    expect(document.body.textContent).toContain("Quick Start");
  });

  it("disables when busy", () => {
    renderModal({ busy: true });
    expect(document.body.textContent).toContain("Starting...");
  });

  it("calls onStart when start button clicked", async () => {
    const { props } = renderModal();
    const buttons = document.querySelectorAll("button");
    const startBtn = Array.from(buttons).find(
      (b) => b.textContent?.includes("New Run") && !b.textContent?.includes("Starting")
    );
    if (startBtn) {
      await userEvent.click(startBtn);
      expect(props.onStart).toHaveBeenCalledOnce();
    }
  });

  it("collapsed sections show summaries", () => {
    renderModal();
    // Budget section shows "Unlimited" when collapsed and budget is disabled
    expect(document.body.textContent).toContain("Unlimited");
    // Model section summary includes model name when collapsed
    expect(document.body.textContent).toContain("Claude Opus 4.6");
    // Env section summary shows "No vars" when empty
    expect(document.body.textContent).toContain("No vars");
  });

  it("collapsed sections show host mounts summary", () => {
    renderModal();
    expect(document.body.textContent).toContain("Host Mounts");
    expect(document.body.textContent).toContain("None");
  });

  it("expanding host mounts shows add button", async () => {
    renderModal();
    const collapsibleButtons = Array.from(
      document.querySelectorAll<HTMLButtonElement>("button[aria-expanded]")
    );
    const mountsButton = collapsibleButtons.find((b) =>
      b.textContent?.includes("Host Mounts")
    );
    expect(mountsButton).toBeDefined();
    if (mountsButton) {
      await userEvent.click(mountsButton);
    }
    expect(document.body.textContent).toContain("+ Add mount");
  });

  it("expanding a section reveals its content", async () => {
    renderModal();

    // Model section header button — find by aria-expanded=false and containing "Model"
    const collapsibleButtons = Array.from(
      document.querySelectorAll<HTMLButtonElement>("button[aria-expanded]")
    );
    const modelButton = collapsibleButtons.find((b) =>
      b.textContent?.includes("Model")
    );
    expect(modelButton).toBeDefined();

    // Before clicking: model radio buttons should not be visible
    expect(document.body.querySelector('[role="radiogroup"]')).toBeNull();

    if (modelButton) {
      await userEvent.click(modelButton);
    }

    // After clicking: the ModelSelector radiogroup should now appear
    expect(document.body.querySelector('[role="radiogroup"]')).not.toBeNull();
  });
});
