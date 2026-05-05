/**Shared shiki highlighter singleton for bash syntax highlighting.*/

type ShikiHighlighter = Awaited<ReturnType<typeof import("shiki").createHighlighter>>;
let highlighterPromise: Promise<ShikiHighlighter> | null = null;

export function getHighlighter(): Promise<ShikiHighlighter> {
  if (!highlighterPromise) {
    highlighterPromise = import("shiki").then(({ createHighlighter }) =>
      createHighlighter({ themes: ["github-dark"], langs: ["bash"] }),
    );
  }
  return highlighterPromise;
}
