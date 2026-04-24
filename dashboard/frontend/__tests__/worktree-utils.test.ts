import { describe, it, expect } from "vitest";
import {
  norm,
  extractFileChanges,
  buildTreeFromDiff,
  buildTreeFromChanges,
  mergeTrees,
  parseTmpDiffStats,
  resolveSessionTree,
} from "@/lib/worktree-utils";

describe("norm", () => {
  it("strips /home/agentuser/repo/ prefix", () => {
    expect(norm("/home/agentuser/repo/src/main.ts")).toBe("src/main.ts");
  });
  it("strips /workspace/ prefix", () => {
    expect(norm("/workspace/foo.py")).toBe("foo.py");
  });
  it("converts /home/agentuser/ to ~/", () => {
    expect(norm("/home/agentuser/.config/file")).toBe("~/.config/file");
  });
  it("returns unchanged if no prefix match", () => {
    expect(norm("relative/path.ts")).toBe("relative/path.ts");
  });
  it("strips /tmp/ prefix to tmp/", () => {
    expect(norm("/tmp/run_state.md")).toBe("tmp/run_state.md");
  });
  it("strips /tmp/round-N prefix to tmp/round-N", () => {
    expect(norm("/tmp/round-1/architect.md")).toBe("tmp/round-1/architect.md");
  });
});

describe("buildTreeFromDiff", () => {
  it("returns empty root for empty input", () => {
    const root = buildTreeFromDiff([]);
    expect(root.children.size).toBe(0);
  });
  it("builds nested tree from file paths", () => {
    const root = buildTreeFromDiff([
      { path: "src/index.ts", added: 10, removed: 2, status: "modified" },
      { path: "src/utils/helper.ts", added: 5, removed: 0, status: "added" },
    ]);
    expect(root.children.has("src")).toBe(true);
    const src = root.children.get("src")!;
    expect(src.isDir).toBe(true);
    expect(src.children.has("index.ts")).toBe(true);
    expect(src.children.get("index.ts")!.added).toBe(10);
    expect(src.children.has("utils")).toBe(true);
  });
  it("marks leaf nodes with status", () => {
    const root = buildTreeFromDiff([
      { path: "deleted.py", added: 0, removed: 50, status: "deleted" },
    ]);
    const leaf = root.children.get("deleted.py")!;
    expect(leaf.status).toBe("deleted");
    expect(leaf.removed).toBe(50);
  });
});

describe("buildTreeFromChanges", () => {
  it("skips read-only changes", () => {
    const root = buildTreeFromChanges([
      { path: "src/file.ts", action: "read", timestamp: "t1", toolCallId: 1, toolName: "Read" },
    ], null);
    expect(root.children.size).toBe(0);
  });
  it("aggregates edits to same file", () => {
    const root = buildTreeFromChanges([
      { path: "src/file.ts", action: "edit", linesAdded: 3, linesRemoved: 1, timestamp: "t1", toolCallId: 1, toolName: "Edit" },
      { path: "src/file.ts", action: "edit", linesAdded: 2, linesRemoved: 0, timestamp: "t2", toolCallId: 2, toolName: "Edit" },
    ], null);
    const leaf = root.children.get("src")!.children.get("file.ts")!;
    expect(leaf.added).toBe(5);
    expect(leaf.removed).toBe(1);
  });
});

describe("extractFileChanges", () => {
  it("returns empty for no events", () => {
    expect(extractFileChanges([])).toEqual([]);
  });
  it("extracts read action from tool event", () => {
    const changes = extractFileChanges([{
      _kind: "tool",
      data: {
        id: 1, tool_name: "Read", ts: "t1",
        input_data: { file_path: "/home/agentuser/repo/src/main.ts" },
        output_data: {},
      },
    } as any]);
    expect(changes).toHaveLength(1);
    expect(changes[0].action).toBe("read");
    expect(changes[0].path).toBe("src/main.ts");
  });
  it("extracts edit with line counts", () => {
    const changes = extractFileChanges([{
      _kind: "tool",
      data: {
        id: 2, tool_name: "Edit", ts: "t2",
        input_data: { file_path: "/workspace/foo.py" },
        output_data: {
          structuredPatch: [{ lines: ["+added", "-removed", " context", "+another"] }],
        },
      },
    } as any]);
    expect(changes).toHaveLength(1);
    expect(changes[0].action).toBe("edit");
    expect(changes[0].linesAdded).toBe(2);
    expect(changes[0].linesRemoved).toBe(1);
  });

  it("write with structuredPatch counts actual + lines", () => {
    const changes = extractFileChanges([{
      _kind: "tool",
      data: {
        id: 3, tool_name: "Write", ts: "t3",
        input_data: { file_path: "/workspace/new-file.ts" },
        output_data: {
          structuredPatch: [{ lines: ["+new", " ctx", "+added", "-old"] }],
        },
      },
    } as any]);
    expect(changes).toHaveLength(1);
    expect(changes[0].action).toBe("write");
    expect(changes[0].linesAdded).toBe(2);
    expect(changes[0].linesRemoved).toBe(1);
  });

  it("write without structuredPatch has undefined line counts", () => {
    const changes = extractFileChanges([{
      _kind: "tool",
      data: {
        id: 4, tool_name: "Write", ts: "t4",
        input_data: { file_path: "/workspace/new-file.ts" },
        output_data: {},
      },
    } as any]);
    expect(changes).toHaveLength(1);
    expect(changes[0].action).toBe("write");
    expect(changes[0].linesAdded).toBeUndefined();
    expect(changes[0].linesRemoved).toBeUndefined();
  });

  it("write with both + and - lines counts both", () => {
    const changes = extractFileChanges([{
      _kind: "tool",
      data: {
        id: 5, tool_name: "Write", ts: "t5",
        input_data: { file_path: "/workspace/rewritten.ts" },
        output_data: {
          structuredPatch: [
            { lines: ["+++ b/rewritten.ts", "+line1", "+line2", "-old1", " ctx"] },
            { lines: ["+line3", "-old2", "-old3"] },
          ],
        },
      },
    } as any]);
    expect(changes).toHaveLength(1);
    expect(changes[0].linesAdded).toBe(3);
    expect(changes[0].linesRemoved).toBe(3);
  });

  it("edit still works after refactor to shared helper", () => {
    const changes = extractFileChanges([{
      _kind: "tool",
      data: {
        id: 6, tool_name: "Edit", ts: "t6",
        input_data: { file_path: "/workspace/existing.ts" },
        output_data: {
          structuredPatch: [
            { lines: ["--- a/existing.ts", "+++ b/existing.ts", "+added1", "-removed1", " unchanged"] },
            { lines: ["+added2", "+added3"] },
          ],
        },
      },
    } as any]);
    expect(changes).toHaveLength(1);
    expect(changes[0].action).toBe("edit");
    expect(changes[0].linesAdded).toBe(3);
    expect(changes[0].linesRemoved).toBe(1);
  });
});

describe("mergeTrees", () => {
  it("includes files from both trees", () => {
    const git = buildTreeFromDiff([
      { path: "src/a.py", added: 5, removed: 0, status: "added" },
    ]);
    const session = buildTreeFromChanges([
      { path: "tmp/report.md", action: "edit", linesAdded: 10, linesRemoved: 0, timestamp: "t", toolCallId: 1, toolName: "Write" },
    ], null);
    const merged = mergeTrees(git, session);
    expect(merged.children.has("src")).toBe(true);
    expect(merged.children.has("tmp")).toBe(true);
  });

  it("session wins on file conflict", () => {
    const git = buildTreeFromDiff([
      { path: "src/main.py", added: 5, removed: 2, status: "modified" },
    ]);
    const session = buildTreeFromChanges([
      { path: "src/main.py", action: "edit", linesAdded: 99, linesRemoved: 0, timestamp: "t", toolCallId: 1, toolName: "Edit" },
    ], null);
    const merged = mergeTrees(git, session);
    const file = merged.children.get("src")!.children.get("main.py")!;
    expect(file.added).toBe(99);
  });

  it("merges directories recursively", () => {
    const git = buildTreeFromDiff([
      { path: "src/a.py", added: 1, removed: 0, status: "added" },
    ]);
    const session = buildTreeFromChanges([
      { path: "src/b.py", action: "edit", linesAdded: 2, linesRemoved: 0, timestamp: "t", toolCallId: 1, toolName: "Write" },
    ], null);
    const merged = mergeTrees(git, session);
    const src = merged.children.get("src")!;
    expect(src.children.has("a.py")).toBe(true);
    expect(src.children.has("b.py")).toBe(true);
  });

  it("handles empty git tree", () => {
    const git = buildTreeFromDiff([]);
    const session = buildTreeFromChanges([
      { path: "tmp/x.md", action: "edit", linesAdded: 1, linesRemoved: 0, timestamp: "t", toolCallId: 1, toolName: "Write" },
    ], null);
    const merged = mergeTrees(git, session);
    expect(merged.children.has("tmp")).toBe(true);
  });

  it("handles empty session tree", () => {
    const git = buildTreeFromDiff([
      { path: "src/a.py", added: 1, removed: 0, status: "added" },
    ]);
    const session = buildTreeFromChanges([], null);
    const merged = mergeTrees(git, session);
    expect(merged.children.has("src")).toBe(true);
  });
});

describe("mergeTrees tmpTree vs liveTree status preservation", () => {
  // Regression for the bug where Write tool-call events populated liveTree
  // with status "modified" for tmp/round-N files and clobbered the "added"
  // classification that tmpTree assigned via forcedStatus.
  it("preserves 'added' status from tmpTree when liveTree has same path as 'modified'", () => {
    const liveTree = buildTreeFromChanges([
      { path: "tmp/round-1/architect.md", action: "write", linesAdded: 10, linesRemoved: 0, timestamp: "t1", toolCallId: 1, toolName: "Write" },
    ], null);
    const tmpTree = buildTreeFromChanges([
      { path: "tmp/round-1/architect.md", action: "edit", linesAdded: 10, linesRemoved: 0, timestamp: "t", toolCallId: 0, toolName: "Archive" },
    ], "added");

    const merged = mergeTrees(liveTree, tmpTree);
    const leaf = merged.children.get("tmp")!.children.get("round-1")!.children.get("architect.md")!;
    expect(leaf.status).toBe("added");
  });

  it("keeps liveTree entries that are not in tmpTree", () => {
    const liveTree = buildTreeFromChanges([
      { path: "src/code.ts", action: "edit", linesAdded: 3, linesRemoved: 1, timestamp: "t1", toolCallId: 1, toolName: "Edit" },
    ], null);
    const tmpTree = buildTreeFromChanges([
      { path: "tmp/round-1/plan.md", action: "edit", linesAdded: 5, linesRemoved: 0, timestamp: "t", toolCallId: 0, toolName: "Archive" },
    ], "added");

    const merged = mergeTrees(liveTree, tmpTree);
    expect(merged.children.has("src")).toBe(true);
    expect(merged.children.has("tmp")).toBe(true);
  });
});

describe("liveTree + tmpTree forced-status partitioning", () => {
  // Mirrors the partition WorkTree.tsx does: tmp/round-N changes go into a
  // tree forced to "added", everything else into a tree with default status.
  // Pins that if /diff/tmp fetch is racing, the user still sees 'A' on tmp
  // files because the liveTree half already classified them correctly.
  it("forces 'added' on tmp/round-N live writes even without tmpTree", () => {
    const changes = [
      { path: "src/main.ts", action: "edit" as const, linesAdded: 1, linesRemoved: 0, timestamp: "t1", toolCallId: 1, toolName: "Edit" },
      { path: "tmp/round-1/plan.md", action: "write" as const, linesAdded: 5, linesRemoved: 0, timestamp: "t2", toolCallId: 2, toolName: "Write" },
    ];
    const tmpLive = changes.filter(c => c.path.startsWith("tmp/round-"));
    const repoLive = changes.filter(c => !c.path.startsWith("tmp/round-"));
    const liveTree = mergeTrees(
      buildTreeFromChanges(repoLive, null),
      buildTreeFromChanges(tmpLive, "added"),
    );
    const srcLeaf = liveTree.children.get("src")!.children.get("main.ts")!;
    const tmpLeaf = liveTree.children.get("tmp")!.children.get("round-1")!.children.get("plan.md")!;
    expect(srcLeaf.status).toBe("modified");
    expect(tmpLeaf.status).toBe("added");
  });
});

describe("resolveSessionTree", () => {
  const emptyRoot = () =>
    buildTreeFromChanges([], null);

  const singleLive = () =>
    buildTreeFromChanges([
      { path: "src/a.ts", action: "edit", linesAdded: 1, linesRemoved: 0, timestamp: "t", toolCallId: 1, toolName: "Edit" },
    ], null);

  const singleTmp = () =>
    buildTreeFromChanges([
      { path: "tmp/round-1/plan.md", action: "edit", linesAdded: 2, linesRemoved: 0, timestamp: "t", toolCallId: 0, toolName: "Archive" },
    ], "added");

  it("returns null when both sides empty", () => {
    expect(resolveSessionTree(emptyRoot(), null)).toBeNull();
  });

  it("returns liveTree when tmpTree is null", () => {
    const live = singleLive();
    expect(resolveSessionTree(live, null)).toBe(live);
  });

  it("returns tmpTree when liveTree has no children", () => {
    const tmp = singleTmp();
    expect(resolveSessionTree(emptyRoot(), tmp)).toBe(tmp);
  });

  it("merges so tmpTree wins on path conflict", () => {
    const live = buildTreeFromChanges([
      { path: "tmp/round-1/plan.md", action: "write", linesAdded: 2, linesRemoved: 0, timestamp: "t1", toolCallId: 1, toolName: "Write" },
    ], null);
    const tmp = singleTmp();
    const merged = resolveSessionTree(live, tmp);
    const leaf = merged!.children.get("tmp")!.children.get("round-1")!.children.get("plan.md")!;
    expect(leaf.status).toBe("added");
  });
});

describe("buildTreeFromChanges forcedStatus", () => {
  it("applies 'added' status to every leaf when forced", () => {
    const root = buildTreeFromChanges([
      { path: "tmp/round-1/debugger.md", action: "edit", linesAdded: 12, linesRemoved: 0, timestamp: "t", toolCallId: 1, toolName: "Archive" },
      { path: "tmp/round-1/planner.md", action: "edit", linesAdded: 5, linesRemoved: 0, timestamp: "t", toolCallId: 2, toolName: "Archive" },
    ], "added");
    const round1 = root.children.get("tmp")!.children.get("round-1")!;
    expect(round1.children.get("debugger.md")!.status).toBe("added");
    expect(round1.children.get("planner.md")!.status).toBe("added");
  });

  it("defaults to 'modified' when forcedStatus is null", () => {
    const root = buildTreeFromChanges([
      { path: "src/file.ts", action: "edit", linesAdded: 1, linesRemoved: 0, timestamp: "t", toolCallId: 1, toolName: "Edit" },
    ], null);
    expect(root.children.get("src")!.children.get("file.ts")!.status).toBe("modified");
  });
});

describe("parseTmpDiffStats", () => {
  const makeDiff = (path: string, body: string[]): string => {
    const header = [
      `diff --git a/${path} b/${path}`,
      "new file mode 100644",
      "--- /dev/null",
      `+++ b/${path}`,
      `@@ -0,0 +1,${body.length} @@`,
    ].join("\n");
    return `${header}\n${body.map(l => `+${l}`).join("\n")}`;
  };

  it("returns empty for an empty diff", () => {
    expect(parseTmpDiffStats("")).toEqual([]);
  });

  it("extracts path and correct line count from a single new file", () => {
    const diff = makeDiff("tmp/round-1/debugger.md", ["line a", "line b", "line c"]);
    expect(parseTmpDiffStats(diff)).toEqual([
      { path: "tmp/round-1/debugger.md", linesAdded: 3 },
    ]);
  });

  it("handles multiple files in one combined diff", () => {
    const diff = [
      makeDiff("tmp/round-1/a.md", ["x", "y"]),
      makeDiff("tmp/round-2/b.md", ["p", "q", "r", "s"]),
    ].join("\n");
    expect(parseTmpDiffStats(diff)).toEqual([
      { path: "tmp/round-1/a.md", linesAdded: 2 },
      { path: "tmp/round-2/b.md", linesAdded: 4 },
    ]);
  });

  it("does not count the '+++ b/...' file header as an added line", () => {
    const diff = makeDiff("tmp/round-1/x.md", ["only one"]);
    expect(parseTmpDiffStats(diff)).toEqual([
      { path: "tmp/round-1/x.md", linesAdded: 1 },
    ]);
  });

  it("ignores non-tmp paths (git-tracked files mixed into combined diff)", () => {
    const diff = [
      makeDiff("src/main.py", ["code"]),
      makeDiff("tmp/round-1/report.md", ["a", "b"]),
    ].join("\n");
    expect(parseTmpDiffStats(diff)).toEqual([
      { path: "tmp/round-1/report.md", linesAdded: 2 },
    ]);
  });

  it("includes tmp/run_state.md (not just tmp/round-N files)", () => {
    const diff = [
      makeDiff("tmp/run_state.md", ["line1", "line2", "line3"]),
      makeDiff("tmp/round-1/plan.md", ["a", "b"]),
    ].join("\n");
    const result = parseTmpDiffStats(diff);
    expect(result).toContainEqual({ path: "tmp/run_state.md", linesAdded: 3 });
    expect(result).toContainEqual({ path: "tmp/round-1/plan.md", linesAdded: 2 });
  });
});

describe("tmp/ partition logic (mirrors WorkTree.tsx liveTree split)", () => {
  it("tmp/ files (including run_state.md) partition into tmpLive, not repoLive", () => {
    const changes = [
      { path: "tmp/run_state.md", action: "write" as const, linesAdded: 5, linesRemoved: 0, timestamp: "t1", toolCallId: 1, toolName: "Write" },
      { path: "tmp/round-1/plan.md", action: "write" as const, linesAdded: 3, linesRemoved: 0, timestamp: "t2", toolCallId: 2, toolName: "Write" },
      { path: "src/main.ts", action: "edit" as const, linesAdded: 1, linesRemoved: 0, timestamp: "t3", toolCallId: 3, toolName: "Edit" },
    ];
    const tmpLive = changes.filter(c => c.path.startsWith("tmp/"));
    const repoLive = changes.filter(c => !c.path.startsWith("tmp/"));
    expect(tmpLive.map(c => c.path)).toContain("tmp/run_state.md");
    expect(tmpLive.map(c => c.path)).toContain("tmp/round-1/plan.md");
    expect(repoLive.map(c => c.path)).toContain("src/main.ts");
    expect(repoLive.map(c => c.path)).not.toContain("tmp/run_state.md");

    const liveTree = mergeTrees(
      buildTreeFromChanges(repoLive, null),
      buildTreeFromChanges(tmpLive, "added"),
    );
    const runStateLeaf = liveTree.children.get("tmp")!.children.get("run_state.md")!;
    const plan = liveTree.children.get("tmp")!.children.get("round-1")!.children.get("plan.md")!;
    const src = liveTree.children.get("src")!.children.get("main.ts")!;
    expect(runStateLeaf.status).toBe("added");
    expect(plan.status).toBe("added");
    expect(src.status).toBe("modified");
  });
});
