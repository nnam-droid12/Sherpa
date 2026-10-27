import Link from "next/link";
import { scoreTone } from "@/components/score-dial";
import { agentGet } from "@/lib/agent";
import type { Run } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function Runs() {
  const runs = (await agentGet<Run[]>("runs?limit=50")) ?? [];
  return (
    <div className="grid gap-6 pt-10">
      <h1 className="text-2xl font-semibold">Run history</h1>
      {runs.length === 0 ? (
        <p className="text-muted">
          No runs yet. <Link href="/" className="underline">Start one</Link>.
        </p>
      ) : (
        <ul className="grid gap-2">
          {runs.map((r) => {
            const before = r.audit?.total;
            const after = r.verify?.audit.total;
            return (
              <li key={r.id}>
                <Link
                  href={`/runs/${r.id}`}
                  className="grid gap-1 rounded-xl border border-border bg-surface px-4 py-3 transition hover:border-accent sm:grid-cols-[1fr_auto_auto] sm:items-center sm:gap-6"
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{r.store_url}</span>
                    <span className="text-xs text-muted">
                      {new Date(r.created_at * 1000).toLocaleString()} · {r.status.replace(":", " ")}
                    </span>
                  </span>
                  <span className="text-sm tabular-nums">
                    {before != null && <span style={{ color: scoreTone(before) }}>{before}</span>}
                    {after != null && (
                      <>
                        <span className="text-muted"> → </span>
                        <span style={{ color: scoreTone(after) }}>{after}</span>
                      </>
                    )}
                  </span>
                  <span className="text-xs text-muted">{r.fix ? "PR opened" : ""}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
