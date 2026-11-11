import type { Metadata } from "next";
import Link from "next/link";
import { DemoLauncher } from "@/components/demo-launcher";
import { codingPaused, DemoLimitsNotice } from "@/components/demo-limits";
import { NewRunForm } from "@/components/new-run-form";
import { agentGet } from "@/lib/agent";
import { scoreTone } from "@/lib/score";
import type { AgentConfig, DemoStore, Run } from "@/lib/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Dashboard · Sherpa" };

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-2xl border border-border bg-surface p-4">
      <p className="text-xs text-muted">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-muted">{hint}</p>}
    </div>
  );
}

const STAGE_LABEL: Record<string, string> = {
  audit: "Audit",
  fix: "Fix",
  verify: "Verify",
  agent_ready: "Agent-ready",
};

function status(run: Run) {
  const [stage, state] = run.status.split(":");
  return `${STAGE_LABEL[stage] ?? stage} ${state ?? ""}`.trim();
}

export default async function Dashboard() {
  const [demos, runs, config] = await Promise.all([
    agentGet<DemoStore[]>("demo-stores"),
    agentGet<Run[]>("runs?limit=30"),
    agentGet<AgentConfig>("config"),
  ]);
  const all = runs ?? [];
  const audited = all.filter((r) => r.audit);
  const avgBefore = audited.length
    ? Math.round(audited.reduce((s, r) => s + (r.audit?.total ?? 0), 0) / audited.length)
    : null;
  const prs = all.filter((r) => r.fix?.pr_url).length;
  const paid = all.filter((r) =>
    Object.values(r.verify?.audit.shoppers ?? r.audit?.shoppers ?? {}).some((s) => s?.payment_completed),
  ).length;

  return (
    <div className="grid gap-10 pt-8">
      <header className="grid gap-2">
        <p className="text-xs font-medium uppercase tracking-widest text-accent">Dashboard · no sign-up needed</p>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Watch Sherpa fix a real checkout.</h1>
        <p className="max-w-2xl text-muted">
          Pick a demo store and press <strong className="text-fg">Run live audit</strong>. Two AI shoppers open cloud
          browsers and try to buy with PayPal while you watch. Then press <strong className="text-fg">Fix it</strong>,{" "}
          <strong className="text-fg">Verify</strong> and <strong className="text-fg">Make agent-ready</strong> on the run
          page.
        </p>
      </header>
      <DemoLimitsNotice limits={config?.limits} />

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4" aria-label="Activity">
        <Stat label="Runs" value={String(all.length)} hint="most recent 30" />
        <Stat label="Average score before" value={avgBefore == null ? "–" : `${avgBefore}/100`} />
        <Stat label="Pull requests opened" value={String(prs)} />
        <Stat label="Sandbox payments confirmed" value={String(paid)} hint="checked via Orders API" />
      </section>

      <section className="grid gap-4" aria-labelledby="demo-heading">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h2 id="demo-heading" className="text-xl font-semibold">
              1. Try a demo store
            </h2>
            <p className="text-sm text-muted">
              Two fictional stores with deliberately broken PayPal checkouts. Every flaw is documented in the{" "}
              <a className="underline" href="https://github.com/nnam-droid12/Sherpa/blob/main/docs/SCORECARD.md">
                scorecard
              </a>
              .
            </p>
          </div>
        </div>
        <DemoLauncher demos={demos ?? []} autopilot={!codingPaused(config?.limits)} />
      </section>

      <section className="grid gap-4 lg:grid-cols-[1.1fr_1fr]">
        <div className="grid content-start gap-3">
          <h2 className="text-xl font-semibold">2. Or audit your own</h2>
          <NewRunForm />
        </div>
        <div className="grid content-start gap-3">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-semibold">Recent runs</h2>
            <Link href="/runs" className="text-sm text-accent hover:underline">
              All runs →
            </Link>
          </div>
          {all.length === 0 ? (
            <p className="rounded-2xl border border-border bg-surface p-5 text-sm text-muted">No runs yet. Start one on the left.</p>
          ) : (
            <ul className="grid gap-2">
              {all.slice(0, 8).map((r) => {
                const before = r.audit?.total;
                const after = r.verify?.audit.total;
                return (
                  <li key={r.id}>
                    <Link
                      href={`/runs/${r.id}`}
                      className="flex items-center justify-between gap-3 rounded-xl border border-border bg-surface px-4 py-3 transition hover:border-accent"
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium">
                          {r.demo_store
                            ? (demos ?? []).find((d) => d.id === r.demo_store)?.name ?? r.store_url
                            : r.store_url}
                        </span>
                        <span className="text-xs text-muted">
                          {new Date(r.created_at * 1000).toLocaleString()} · {status(r)}
                        </span>
                      </span>
                      <span className="shrink-0 text-sm font-semibold tabular-nums">
                        {before != null && <span style={{ color: scoreTone(before) }}>{before}</span>}
                        {after != null && (
                          <>
                            <span className="text-muted"> → </span>
                            <span style={{ color: scoreTone(after) }}>{after}</span>
                          </>
                        )}
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}
