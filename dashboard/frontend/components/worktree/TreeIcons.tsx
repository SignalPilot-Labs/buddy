"use client";

export function FileIcon({ name, status }: { name: string; status?: string }) {
  const ext = name.split(".").pop()?.toLowerCase() || "";
  let color = "#555";
  if (status === "added") color = "#00ff88";
  else if (status === "deleted") color = "#ff4444";
  else if (status === "modified") color = "#ffcc44";
  else if (ext === "tsx" || ext === "ts") color = "#3178c6";
  else if (ext === "css") color = "#264de4";
  else if (ext === "py") color = "#3776ab";
  else if (ext === "sql") color = "#e38c00";

  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke={color} strokeWidth="1" strokeLinecap="round">
      <path d="M3 1.5h4.5l2.5 2.5v6.5a1 1 0 01-1 1H3a1 1 0 01-1-1v-8a1 1 0 011-1z" />
      <polyline points="7.5 1.5 7.5 4 10 4" />
    </svg>
  );
}

export function DirIcon({ open }: { open: boolean }) {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#555" strokeWidth="1" strokeLinecap="round">
      {open ? (
        <>
          <path d="M1 3.5h3l1-1h4.5a1 1 0 011 1V4H2.5L1 9V3.5z" />
          <path d="M2.5 4L1 9h8.5l1.5-5H2.5z" />
        </>
      ) : (
        <path d="M1 3h3l1 1h5a1 1 0 011 1v5a1 1 0 01-1 1H2a1 1 0 01-1-1V3z" />
      )}
    </svg>
  );
}
