/** Minimal unified-diff renderer, grouped by file. */
export function DiffView({ diff }: { diff: string }) {
  const files: { name: string; lines: string[] }[] = [];
  for (const line of diff.split("\n")) {
    if (line.startsWith("diff --git")) {
      const name = line.split(" b/")[1] ?? line;
      files.push({ name, lines: [] });
    } else if (files.length && !line.startsWith("index ") && !line.startsWith("--- ") && !line.startsWith("+++ ")) {
      files[files.length - 1].lines.push(line);
    }
  }
  if (!files.length) return <p className="text-sm text-muted">No diff available.</p>;
  return (
    <div className="grid gap-3">
      {files.map((f) => (
        <details key={f.name} className="overflow-hidden rounded-xl border border-border bg-surface" open={files.length <= 4}>
          <summary className="cursor-pointer bg-surface-2 px-3 py-2 font-mono text-xs">{f.name}</summary>
          <pre className="max-h-96 overflow-auto text-xs leading-5">
            {f.lines.map((l, i) => (
              <div
                key={i}
                className={`px-3 font-mono ${
                  l.startsWith("+") ? "bg-good/10 text-good" : l.startsWith("-") ? "bg-bad/10 text-bad" : l.startsWith("@@") ? "text-accent" : ""
                }`}
              >
                {l || " "}
              </div>
            ))}
          </pre>
        </details>
      ))}
    </div>
  );
}
