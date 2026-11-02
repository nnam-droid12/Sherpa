/** Unified-diff renderer in a dark, editor-style theme, grouped by file. */
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
  if (!files.length) return <p className="text-sm text-[#8b949e]">No changes.</p>;
  return (
    <div className="grid gap-3">
      {files.map((f) => {
        const added = f.lines.filter((l) => l.startsWith("+")).length;
        const removed = f.lines.filter((l) => l.startsWith("-")).length;
        return (
          <details key={f.name} className="overflow-hidden rounded-xl border border-[#30363d] bg-[#0d1117]" open={files.length <= 4}>
            <summary className="flex cursor-pointer items-center justify-between gap-3 border-b border-[#30363d] bg-[#161b22] px-3 py-2 font-mono text-xs text-[#c9d1d9]">
              <span className="truncate">{f.name}</span>
              <span className="shrink-0">
                <span className="text-[#3fb950]">+{added}</span> <span className="text-[#f85149]">−{removed}</span>
              </span>
            </summary>
            <pre className="max-h-[560px] overflow-auto py-1 text-xs leading-5">
              {f.lines.map((l, i) => {
                const tone = l.startsWith("+")
                  ? "bg-[#2ea04326] text-[#aff5b4]"
                  : l.startsWith("-")
                    ? "bg-[#f8514926] text-[#ffdcd7]"
                    : l.startsWith("@@")
                      ? "bg-[#1f6feb1a] text-[#79c0ff]"
                      : "text-[#c9d1d9]";
                return (
                  <div key={i} className={`whitespace-pre px-3 font-mono ${tone}`}>
                    {l || " "}
                  </div>
                );
              })}
            </pre>
          </details>
        );
      })}
    </div>
  );
}
