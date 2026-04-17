import { describe, it, expect } from "vitest";
import {
  DEFAULT_MODEL,
  MODEL_IDS,
  MODELS,
  resolveModelId,
  parseStoredModel,
  type ModelId,
} from "@/lib/constants";

describe("Model constants", () => {
  it("DEFAULT_MODEL is claude-opus-4-6", () => {
    expect(DEFAULT_MODEL).toBe("claude-opus-4-6");
  });

  it("exactly 3 models supported", () => {
    expect(MODEL_IDS).toHaveLength(3);
  });

  it("MODEL_IDS matches MODELS keys", () => {
    const keys = Object.keys(MODELS) as ModelId[];
    expect(new Set(MODEL_IDS)).toEqual(new Set(keys));
  });

  it("all model IDs are exact SDK IDs (start with claude-)", () => {
    for (const id of MODEL_IDS) {
      expect(id).toMatch(/^claude-/);
    }
  });

  it("no old aliases in MODEL_IDS", () => {
    for (const id of MODEL_IDS) {
      expect(id).not.toBe("opus");
      expect(id).not.toBe("sonnet");
      expect(id).not.toBe("opus-4-5");
    }
  });
});

describe("resolveModelId", () => {
  it("resolves claude-opus-4-6 from DB string", () => {
    expect(resolveModelId("claude-opus-4-6")).toBe("claude-opus-4-6");
  });

  it("resolves claude-sonnet-4-6 from DB string", () => {
    expect(resolveModelId("claude-sonnet-4-6")).toBe("claude-sonnet-4-6");
  });

  it("resolves claude-opus-4-5 from DB string", () => {
    expect(resolveModelId("claude-opus-4-5")).toBe("claude-opus-4-5");
  });

  it("resolves opus substring to claude-opus-4-6", () => {
    expect(resolveModelId("opus")).toBe("claude-opus-4-6");
  });

  it("resolves sonnet substring to claude-sonnet-4-6", () => {
    expect(resolveModelId("sonnet")).toBe("claude-sonnet-4-6");
  });

  it("returns null for null/undefined", () => {
    expect(resolveModelId(null)).toBeNull();
    expect(resolveModelId(undefined)).toBeNull();
  });

  it("returns null for unknown model", () => {
    expect(resolveModelId("gpt-4")).toBeNull();
  });
});

describe("parseStoredModel", () => {
  it("accepts new SDK IDs directly", () => {
    expect(parseStoredModel("claude-opus-4-6")).toBe("claude-opus-4-6");
    expect(parseStoredModel("claude-sonnet-4-6")).toBe("claude-sonnet-4-6");
    expect(parseStoredModel("claude-opus-4-5")).toBe("claude-opus-4-5");
  });

  it("migrates old opus alias", () => {
    expect(parseStoredModel("opus")).toBe("claude-opus-4-6");
  });

  it("migrates old sonnet alias", () => {
    expect(parseStoredModel("sonnet")).toBe("claude-sonnet-4-6");
  });

  it("migrates old opus-4-5 alias", () => {
    expect(parseStoredModel("opus-4-5")).toBe("claude-opus-4-5");
  });

  it("returns null for unknown string", () => {
    expect(parseStoredModel("gpt-4")).toBeNull();
  });

  it("returns null for null", () => {
    expect(parseStoredModel(null)).toBeNull();
  });
});
