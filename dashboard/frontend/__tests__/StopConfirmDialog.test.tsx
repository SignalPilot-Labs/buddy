/**
 * StopConfirmDialog component tests.
 *
 * Covers: renders when open, hidden when closed, button callbacks,
 * ESC key cancel, backdrop click cancel.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { StopConfirmDialog } from "@/components/ui/StopConfirmDialog";

function renderDialog(overrides: Partial<{ open: boolean; onConfirm: (openPr: boolean) => void; onCancel: () => void }> = {}) {
  const defaults = {
    open: true,
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
  };
  const props = { ...defaults, ...overrides };
  return { ...render(<StopConfirmDialog {...props} />), props };
}

describe("StopConfirmDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders dialog content when open", () => {
    renderDialog();
    expect(screen.getByText("Stop this run?")).toBeTruthy();
    expect(screen.getByText("Open a Pull Request?")).toBeTruthy();
    expect(screen.getByText("Yes, open PR")).toBeTruthy();
    expect(screen.getByText("No, just stop")).toBeTruthy();
  });

  it("does not render when closed", () => {
    renderDialog({ open: false });
    expect(document.body.textContent).not.toContain("Stop this run?");
  });

  it("calls onConfirm(true) when 'Yes, open PR' is clicked", async () => {
    const onConfirm = vi.fn();
    renderDialog({ onConfirm });
    await userEvent.click(screen.getByText("Yes, open PR"));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onConfirm).toHaveBeenCalledWith(true);
  });

  it("calls onConfirm(false) when 'No, just stop' is clicked", async () => {
    const onConfirm = vi.fn();
    renderDialog({ onConfirm });
    await userEvent.click(screen.getByText("No, just stop"));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onConfirm).toHaveBeenCalledWith(false);
  });

  it("calls onCancel when ESC key is pressed", async () => {
    const onCancel = vi.fn();
    renderDialog({ onCancel });
    await userEvent.keyboard("{Escape}");
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel when backdrop is clicked", async () => {
    const onCancel = vi.fn();
    renderDialog({ onCancel });
    const dialog = screen.getByRole("dialog");
    await userEvent.click(dialog);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("does not call onCancel when dialog panel content is clicked", async () => {
    const onCancel = vi.fn();
    renderDialog({ onCancel });
    await userEvent.click(screen.getByText("Stop this run?"));
    expect(onCancel).not.toHaveBeenCalled();
  });
});
