/**
 * Sync test: DEFAULT_DOCKER_START_CMD in constants.ts must contain
 * the same key fragments as the Python DEFAULT_DOCKER_START_CMD
 * in local_backend.py.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";
import { DEFAULT_DOCKER_START_CMD } from "../lib/constants";

describe("DEFAULT_DOCKER_START_CMD sync", () => {
  it("TypeScript constant contains all required docker run fragments", () => {
    const fragments = [
      "docker run",
      "--name autofyn-sandbox-$AF_RUN_KEY",
      "--hostname autofyn-sandbox-$AF_RUN_KEY",
      "--network autofyn_default",
      "--cap-add SYS_PTRACE",
      "--cap-add SYS_ADMIN",
      "--security-opt apparmor:unconfined",
      "autofyn-repo-$AF_RUN_KEY:/home/agentuser/repo:rw",
      "$AF_DOCKER_EXTRA_VOLUMES",
      "$AF_DOCKER_EXTRA_ENV",
      "ghcr.io/signalpilot-labs/autofyn-sandbox:$AF_IMAGE_TAG",
    ];

    for (const frag of fragments) {
      expect(DEFAULT_DOCKER_START_CMD).toContain(frag);
    }
  });

  it("Python constant contains the same fragments", () => {
    const PY_SRC = fs.readFileSync(
      path.resolve(__dirname, "../../../autofyn/sandbox_client/backends/local_backend.py"),
      "utf-8",
    );
    expect(PY_SRC).toContain("DEFAULT_DOCKER_START_CMD");
    // Python uses f-strings that resolve SANDBOX_POOL_IMAGE_BASE and SANDBOX_POOL_NETWORK,
    // so verify the variable references exist in source
    expect(PY_SRC).toContain("SANDBOX_POOL_IMAGE_BASE");
    expect(PY_SRC).toContain("SANDBOX_POOL_NETWORK");
    expect(PY_SRC).toContain("$AF_RUN_KEY");
    expect(PY_SRC).toContain("$AF_IMAGE_TAG");
    expect(PY_SRC).toContain("$AF_DOCKER_EXTRA_VOLUMES");
    expect(PY_SRC).toContain("$AF_DOCKER_EXTRA_ENV");
  });
});
