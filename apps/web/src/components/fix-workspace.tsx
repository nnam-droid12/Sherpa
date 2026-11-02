"use client";

import { useMemo, useState } from "react";
import type { RunEvent } from "@/lib/types";
import { DiffView } from "./diff-view";

type FileState = {
  path: string;
  action: "read" | "edit" | "create";
  content: string;
  diff: string;
  truncated: boolean;
  seq: number;
};

// Editor palette (GitHub dark), fixed regardless of the site theme.
const BADGE: Record<FileState["action"], string> = {
  read: "bg-[#21262d] text-[#8b949e]",
  edit: "bg-[#bb800926] text-[#e3b341]",
  create: "bg-[#2ea04326] text-[#56d364]",
};

const LABEL: Record<FileState["action"], string> = { read: "read", edit: "edited", create: "new" };

function CodeView({ content, truncated }: { content: string; truncated: boolean }) {
  const lines = content.split("\n");
  return (
    <pre className="max-h-[560px] overflow-auto bg-[#0d1117] py-2 text-xs leading-5 text-[#c9d1d9]">
      {lines.map((l, i) => (
        <div key={i} className="flex font-mono">
          <span className="w-12 shrink-0 select-none pr-4 text-right text-[#6e7681]">{i + 1}</span>
          <span className="whitespace-pre pr-4">{l || " "}</span>
        </div>
      ))}
      {truncated && <div className="px-4 py-2 text-[#8b949e]">… file truncated for display</div>}
    </pre>
  );
}

/** Live view of the repository files the coding agent reads and edits. */
export function FixWorkspace({ events, phase }: { events: RunEvent[]; phase: string }) {
  const [picked, setPicked] = useState<string | null>(null);
  const [mode, setMode] = useState<"diff" | "code">("diff");

  const { files, latest, activity } = useMemo(() => {
    const map = new Map<string, FileState>();
    let latestPath: string | null = null;
    let last: RunEvent | undefined;
    for (const e of events) {
      if (e.phase !== phase) continue;
      if (e.kind === "file" && typeof e.path === "string") {
        const prev = map.get(e.path);
        const action = e.action as FileState["action"];
        map.set(e.path, {
          path: e.path,
          // Once a file has been edited or created it stays marked as such.
          action: prev && prev.action !== "read" && action === "read" ? prev.action : action,
          content: String(e.content ?? ""),
          diff: action === "read" ? prev?.diff ?? "" : String(e.diff ?? ""),
          truncated: Boolean(e.truncated),
          seq: e.seq,
        });
        latestPath = e.path;
      }
      if (e.kind === "tool" || e.kind === "log") last = e;
    }
    const files = [...map.values()].sort((a, b) => a.path.localeCompare(b.path));
    return { files, latest: latestPath, activity: last };
  }, [events, phase]);

  const current = files.find((f) => f.path === (picked ?? latest));
  const changed = files.filter((f) => f.action !== "read").length;
  const showDiff = mode === "diff" && current && current.action !== "read" && current.diff;

  return (
    <div className="grid gap-3">
      {activity && (
        <p className="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm">
          <span className="size-2 shrink-0 animate-pulse rounded-full bg-accent" aria-hidden />
          <span className="truncate">
            {activity.kind === "tool" ? (
              <>
                <span className="font-mono">{String(activity.tool)}</span>
                {activity.target ? <span className="text-muted"> {String(activity.target)}</span> : null}
              </>
            ) : (
              activity.message
            )}
          </span>
        </p>
      )}
      {files.length === 0 ? (
        <p className="text-sm text-muted">Waiting for the coding agent to open the repository…</p>
      ) : (
        <div className="grid overflow-hidden rounded-xl border border-[#30363d] bg-[#0d1117] shadow-lg md:grid-cols-[260px_1fr]">
          <nav aria-label="Files" className="max-h-[600px] overflow-y-auto border-b border-[#30363d] bg-[#010409] md:border-b-0 md:border-r">
            <p className="sticky top-0 flex items-center gap-2 border-b border-[#30363d] bg-[#010409] px-3 py-2 text-xs text-[#8b949e]">
              <span className="flex gap-1" aria-hidden>
                <span className="size-2.5 rounded-full bg-[#ff5f57]" />
                <span className="size-2.5 rounded-full bg-[#febc2e]" />
                <span className="size-2.5 rounded-full bg-[#28c840]" />
              </span>
              {files.length} files · {changed} changed
            </p>
            <ul>
              {files.map((f) => (
                <li key={f.path}>
                  <button
                    onClick={() => setPicked(f.path)}
                    className={`flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left font-mono text-xs transition hover:bg-[#161b22] ${
                      current?.path === f.path ? "bg-[#1f6feb33] text-[#e6edf3]" : "text-[#8b949e]"
                    }`}
                  >
                    <span className="truncate" title={f.path}>
                      {f.path}
                    </span>
                    <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-sans ${BADGE[f.action]}`}>
                      {LABEL[f.action]}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </nav>
          <section className="min-w-0 bg-[#0d1117]">
            {current && (
              <>
                <div className="flex items-center justify-between gap-2 border-b border-[#30363d] bg-[#161b22] px-3 py-2">
                  <span className="truncate font-mono text-xs text-[#e6edf3]">{current.path}</span>
                  {current.action !== "read" && (
                    <div className="flex rounded-md bg-[#0d1117] p-0.5 text-xs" role="tablist" aria-label="View">
                      {(["diff", "code"] as const).map((m) => (
                        <button
                          key={m}
                          role="tab"
                          aria-selected={mode === m}
                          onClick={() => setMode(m)}
                          className={`rounded px-2 py-0.5 capitalize ${mode === m ? "bg-[#21262d] text-[#e6edf3]" : "text-[#8b949e]"}`}
                        >
                          {m === "diff" ? "Changes" : "Full file"}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                {showDiff ? (
                  <div className="p-2">
                    <DiffView diff={current.diff} />
                  </div>
                ) : (
                  <CodeView content={current.content} truncated={current.truncated} />
                )}
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
