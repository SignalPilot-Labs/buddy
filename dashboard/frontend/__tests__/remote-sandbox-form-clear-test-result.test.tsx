/**
 * Regression tests for RemoteSandboxForm stale test result/error (BUG 6).
 *
 * Root cause: The `update` function only called onChange({ ...data, ...patch }).
 * It never cleared testResult or testError. After running a connection test,
 * editing any field left stale "Connected" or error text visible, misleading
 * the user into thinking the (now-edited) config was tested and passed/failed.
 *
 * Fix: update() now calls setTestResult(null) and setTestError(null) before
 * calling onChange so stale feedback is cleared on any form field change.
 */

import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { RemoteSandboxForm } from "@/components/settings/RemoteSandboxForm";
import type { SandboxFormData } from "@/components/settings/RemoteSandboxes";
import type { TestSandboxResult } from "@/lib/api";

const FORM_DATA: SandboxFormData = {
  name: "my-cluster",
  ssh_target: "user@gpu1",
  type: "docker",
  default_start_cmd: "docker run -it ubuntu",
  queue_timeout: 300,
  heartbeat_timeout: 60,
  work_dir: "",
};

const PASSING_RESULT: TestSandboxResult = {
  ok: true,
  checks: [{ name: "ssh", ok: true, detail: "connected" }],
};

const FAILING_RESULT: TestSandboxResult = {
  ok: false,
  checks: [{ name: "ssh", ok: false, detail: "Connection refused" }],
};

function renderForm(overrides: Partial<{
  data: SandboxFormData;
  onTest: (() => Promise<TestSandboxResult>) | null;
  onChange: (d: SandboxFormData) => void;
}> = {}) {
  const data = overrides.data ?? { ...FORM_DATA };
  const onChange = overrides.onChange ?? vi.fn();
  const onTest = overrides.onTest !== undefined ? overrides.onTest : vi.fn().mockResolvedValue(PASSING_RESULT);

  render(
    <RemoteSandboxForm
      data={data}
      onChange={onChange}
      onSave={vi.fn().mockResolvedValue(undefined)}
      onTest={onTest}
      onCancel={vi.fn()}
      saving={false}
      isEdit={false}
    />,
  );

  return { onChange };
}

describe("RemoteSandboxForm: stale test result cleared on edit (BUG 6)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("source code: update() calls setTestResult(null) and setTestError(null)", () => {
    const fs = require("fs") as typeof import("fs");
    const path = require("path") as typeof import("path");
    const src = fs.readFileSync(
      path.resolve(__dirname, "../components/settings/RemoteSandboxForm.tsx"),
      "utf-8",
    );

    const fnStart = src.indexOf("const update = ");
    const fnBody = src.slice(fnStart, src.indexOf("\n  };", fnStart));

    expect(fnBody).toContain("setTestResult(null)");
    expect(fnBody).toContain("setTestError(null)");

    // Both clears must happen before onChange is called
    const resultClearPos = fnBody.indexOf("setTestResult(null)");
    const errorClearPos = fnBody.indexOf("setTestError(null)");
    const onChangePos = fnBody.indexOf("onChange(");

    expect(resultClearPos).toBeGreaterThan(0);
    expect(errorClearPos).toBeGreaterThan(0);
    expect(resultClearPos).toBeLessThan(onChangePos);
    expect(errorClearPos).toBeLessThan(onChangePos);
  });

  it("behavioral: after test passes, typing in Name field clears 'Connected' message", async () => {
    // We need a controlled data state to simulate a field change triggering update().
    // Use a stateful wrapper so onChange feeds back into data.
    let currentData = { ...FORM_DATA };
    const onTest = vi.fn().mockResolvedValue(PASSING_RESULT);

    const { rerender } = render(
      <RemoteSandboxForm
        data={currentData}
        onChange={(d) => { currentData = d; }}
        onSave={vi.fn().mockResolvedValue(undefined)}
        onTest={onTest}
        onCancel={vi.fn()}
        saving={false}
        isEdit={false}
      />,
    );

    // Run the test
    const testBtn = screen.getByRole("button", { name: /test/i });
    await userEvent.click(testBtn);

    // Wait for "Connected" to appear
    await waitFor(() => {
      expect(screen.getByText("Connected")).toBeInTheDocument();
    });

    // Now rerender with new data (simulating onChange propagating back)
    currentData = { ...currentData, name: "renamed-cluster" };
    await act(async () => {
      rerender(
        <RemoteSandboxForm
          data={currentData}
          onChange={(d) => { currentData = d; }}
          onSave={vi.fn().mockResolvedValue(undefined)}
          onTest={onTest}
          onCancel={vi.fn()}
          saving={false}
          isEdit={false}
        />,
      );
    });

    // Type in the Name field — this triggers update() which should clear testResult
    const nameInput = screen.getByPlaceholderText("gpu-cluster-1");
    await userEvent.type(nameInput, "x");

    // "Connected" must be gone
    expect(screen.queryByText("Connected")).not.toBeInTheDocument();
  });

  it("behavioral: after test fails, editing SSH target clears the error message", async () => {
    let currentData = { ...FORM_DATA };
    const onTest = vi.fn().mockResolvedValue(FAILING_RESULT);

    const { rerender } = render(
      <RemoteSandboxForm
        data={currentData}
        onChange={(d) => { currentData = d; }}
        onSave={vi.fn().mockResolvedValue(undefined)}
        onTest={onTest}
        onCancel={vi.fn()}
        saving={false}
        isEdit={false}
      />,
    );

    // Run the test
    const testBtn = screen.getByRole("button", { name: /test/i });
    await userEvent.click(testBtn);

    // Wait for the failure detail to appear
    await waitFor(() => {
      expect(screen.getByText(/Connection refused/)).toBeInTheDocument();
    });

    // Type in the SSH target field
    const sshInput = screen.getByPlaceholderText("user@hostname");
    await userEvent.type(sshInput, "x");

    // Error message must be cleared
    expect(screen.queryByText(/Connection refused/)).not.toBeInTheDocument();
  });
});
