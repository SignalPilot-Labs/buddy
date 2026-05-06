/**
 * Regression tests for DefaultModelSetting optimistic update with no rollback (BUG 12).
 *
 * Root cause: handleSelect in DefaultModelSetting performed an optimistic update
 * (setSelectedModel + saveStoredModel) then called updateSettings. On failure,
 * it set the error message but did NOT roll back selectedModel or localStorage.
 * After a failed save, the UI showed the new model, localStorage had the new
 * model, but the server retained the old model. This divergence persisted across
 * page reloads since localStorage was never reverted.
 *
 * Fix: Capture previousModel before the update. On catch, call
 * setSelectedModel(previousModel) and saveStoredModel(previousModel) to revert
 * both UI state and localStorage.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const SRC = fs.readFileSync(
  path.resolve(__dirname, "../app/settings/page.tsx"),
  "utf-8",
);

describe("DefaultModelSetting: rollback optimistic update on API failure (BUG 12)", () => {
  it("handleSelect captures previousModel before making changes", () => {
    const fnStart = SRC.indexOf("const handleSelect");
    expect(fnStart).toBeGreaterThan(-1);
    const fnEnd = SRC.indexOf("\n  };", fnStart);
    const fnBody = SRC.slice(fnStart, fnEnd + 5);

    expect(fnBody).toContain("const previousModel");

    // previousModel must be captured before setSelectedModel(id)
    const capturePos = fnBody.indexOf("const previousModel");
    const setModelPos = fnBody.indexOf("setSelectedModel(id)");
    expect(capturePos).toBeLessThan(setModelPos);
  });

  it("handleSelect rollbacks setSelectedModel to previousModel in catch block", () => {
    const fnStart = SRC.indexOf("const handleSelect");
    const fnEnd = SRC.indexOf("\n  };", fnStart);
    const fnBody = SRC.slice(fnStart, fnEnd + 5);

    const catchPos = fnBody.indexOf("catch");
    expect(catchPos).toBeGreaterThan(-1);

    const catchBlock = fnBody.slice(catchPos);
    expect(catchBlock).toContain("setSelectedModel(previousModel)");
  });

  it("handleSelect rollbacks saveStoredModel to previousModel in catch block", () => {
    const fnStart = SRC.indexOf("const handleSelect");
    const fnEnd = SRC.indexOf("\n  };", fnStart);
    const fnBody = SRC.slice(fnStart, fnEnd + 5);

    const catchPos = fnBody.indexOf("catch");
    const catchBlock = fnBody.slice(catchPos);

    expect(catchBlock).toContain("saveStoredModel(previousModel)");
  });

  it("handleSelect still sets error message in catch block", () => {
    const fnStart = SRC.indexOf("const handleSelect");
    const fnEnd = SRC.indexOf("\n  };", fnStart);
    const fnBody = SRC.slice(fnStart, fnEnd + 5);

    const catchPos = fnBody.indexOf("catch");
    const catchBlock = fnBody.slice(catchPos);

    expect(catchBlock).toContain("setModelSaveError");
  });

  it("optimistic update writes to both state and localStorage before the try block", () => {
    const fnStart = SRC.indexOf("const handleSelect");
    const fnEnd = SRC.indexOf("\n  };", fnStart);
    const fnBody = SRC.slice(fnStart, fnEnd + 5);

    const tryPos = fnBody.indexOf("try {");
    const setModelPos = fnBody.indexOf("setSelectedModel(id)");
    const saveStoredPos = fnBody.indexOf("saveStoredModel(id)");

    // Both optimistic writes happen before the try block
    expect(setModelPos).toBeGreaterThan(0);
    expect(saveStoredPos).toBeGreaterThan(0);
    expect(setModelPos).toBeLessThan(tryPos);
    expect(saveStoredPos).toBeLessThan(tryPos);
  });

  it("rollback writes come before error message in catch block", () => {
    const fnStart = SRC.indexOf("const handleSelect");
    const fnEnd = SRC.indexOf("\n  };", fnStart);
    const fnBody = SRC.slice(fnStart, fnEnd + 5);

    const catchPos = fnBody.indexOf("catch");
    const catchBlock = fnBody.slice(catchPos);

    const setModelRollbackPos = catchBlock.indexOf("setSelectedModel(previousModel)");
    const saveStoredRollbackPos = catchBlock.indexOf("saveStoredModel(previousModel)");
    const errorMsgPos = catchBlock.indexOf("setModelSaveError");

    expect(setModelRollbackPos).toBeGreaterThan(0);
    expect(saveStoredRollbackPos).toBeGreaterThan(0);
    expect(setModelRollbackPos).toBeLessThan(errorMsgPos);
    expect(saveStoredRollbackPos).toBeLessThan(errorMsgPos);
  });
});
