import { describe, it, expect } from "vitest";
import {
  norm,
  extractFileChanges,
  buildTreeFromDiff,
  buildTreeFromChanges,
  mergeTrees,
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
    ]);
    expect(root.children.size).toBe(0);
  });
  it("aggregates edits to same file", () => {
    const root = buildTreeFromChanges([
      { path: "src/file.ts", action: "edit", linesAdded: 3, linesRemoved: 1, timestamp: "t1", toolCallId: 1, toolName: "Edit" },
      { path: "src/file.ts", action: "edit", linesAdded: 2, linesRemoved: 0, timestamp: "t2", toolCallId: 2, toolName: "Edit" },
    ]);
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
    ]);
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
    ]);
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
    ]);
    const merged = mergeTrees(git, session);
    const src = merged.children.get("src")!;
    expect(src.children.has("a.py")).toBe(true);
    expect(src.children.has("b.py")).toBe(true);
  });

  it("handles empty git tree", () => {
    const git = buildTreeFromDiff([]);
    const session = buildTreeFromChanges([
      { path: "tmp/x.md", action: "edit", linesAdded: 1, linesRemoved: 0, timestamp: "t", toolCallId: 1, toolName: "Write" },
    ]);
    const merged = mergeTrees(git, session);
    expect(merged.children.has("tmp")).toBe(true);
  });

  it("handles empty session tree", () => {
    const git = buildTreeFromDiff([
      { path: "src/a.py", added: 1, removed: 0, status: "added" },
    ]);
    const session = buildTreeFromChanges([]);
    const merged = mergeTrees(git, session);
    expect(merged.children.has("src")).toBe(true);
  });
});
