import type { FeedEvent, FileChange } from "@/lib/types";
import { getToolCategory } from "@/lib/types";
import { norm } from "@/components/worktree/tree-builders";

export function extractFileChanges(events: FeedEvent[]): FileChange[] {
  const changes: FileChange[] = [];
  for (const ev of events) {
    if (ev._kind !== "tool") continue;
    const tc = ev.data;
    const cat = getToolCategory(tc.tool_name);
    const input = tc.input_data || {};
    const output = tc.output_data || {};

    switch (cat) {
      case "read": {
        const fileObj = (output as Record<string, unknown>)?.file as Record<string, unknown> | undefined;
        const fp = (input.file_path as string) || (fileObj?.filePath as string) || "";
        if (fp) {
          changes.push({
            path: norm(fp),
            action: "read",
            timestamp: tc.ts,
            toolCallId: tc.id,
            toolName: tc.tool_name,
          });
        }
        break;
      }
      case "write": {
        const fp = (input.file_path as string) || (output.filePath as string) || "";
        if (fp) {
          const patch = output.structuredPatch as Array<Record<string, unknown>> | undefined;
          let added = 0;
          if (patch) for (const h of patch) added += (h.newLines as number) || 0;
          changes.push({
            path: norm(fp),
            action: "write",
            linesAdded: added || undefined,
            timestamp: tc.ts,
            toolCallId: tc.id,
            toolName: tc.tool_name,
          });
        }
        break;
      }
      case "edit": {
        const fp = (input.file_path as string) || (output.filePath as string) || "";
        if (fp) {
          const patch = output.structuredPatch as Array<Record<string, unknown>> | undefined;
          let added = 0;
          let removed = 0;
          if (patch) {
            for (const h of patch) {
              for (const l of ((h.lines as string[]) || [])) {
                if (l.startsWith("+") && !l.startsWith("+++")) added++;
                if (l.startsWith("-") && !l.startsWith("---")) removed++;
              }
            }
          }
          changes.push({
            path: norm(fp),
            action: "edit",
            linesAdded: added || undefined,
            linesRemoved: removed || undefined,
            timestamp: tc.ts,
            toolCallId: tc.id,
            toolName: tc.tool_name,
          });
        }
        break;
      }
    }
  }
  return changes;
}
