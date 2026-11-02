"use client";

import { useState } from "react";
import { downloadReport } from "@/lib/report";
import { artifactUrl, type Run, type RunEvent } from "@/lib/types";
import { useRun } from "@/lib/use-run";
import { CategoryBars } from "./category-bars";
import { DiffView } from "./diff-view";
import { FindingCard } from "./finding-card";
import { FixWorkspace } from "./fix-workspace";
import { LiveView } from "./live-view";
import { ScoreDial } from "./score-dial";

const STAGES = [
  { key: "audit", label: "Audit" },
  { key: "fix", label: "Fix" },
  { key: "verify", label: "Verify" },
  { key: "agent_ready", label: "Agent-ready" },
] as const;

function stageState(run: Run | null, key: string) {
  if (!run) return "todo";
  const [stage, state] = run.status.split(":");
  if (stage === key) return state === "done" ? "done" : state === "failed" ? "failed" : "running";
  const done = { audit: !!run.audit, fix: !!run.fix, verify: !!run.verify, agent_ready: !!run.agent_ready }[key];
  return done ? "done" : "todo";
}

function Panel({ title, actions, children }: { title: string; actions?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="grid gap-4 rounded-2xl border border-border bg-surface p-4 sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-lg font-semibold">{title}</h2>
        {actions}
      </div>
      {children}
    </section>
  );
}

function ActionButton({ onClick, busy, children }: { onClick: () => void; busy: boolean; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      disabled={busy}
      className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition hover:opacity-90 disabled:opacity-50"
    >
      {children}
    </button>
  );
}

function AgentLog({ events, phase }: { events: RunEvent[]; phase: string }) {
  const items = events.filter((e) => e.phase === phase && e.kind !== "step" && e.kind !== "file");
  if (!items.length) return null;
  return (
    <ol className="max-h-80 overflow-y-auto rounded-xl border border-border bg-bg p-3 font-mono text-xs leading-6" aria-live="polite">
      {items.map((e) => (
        <li key={e.seq} className={e.kind === "error" ? "text-bad" : e.kind === "tool" ? "" : "text-muted"}>
          <span className="text-muted">{new Date(e.ts * 1000).toLocaleTimeString()} </span>
          {e.kind === "tool" ? `${e.tool}(${e.target ?? ""})` : (e.message ?? e.text ?? e.kind)}
        </li>
      ))}
    </ol>
  );
}

export function RunView({ runId, initial }: { runId: string; initial: Run | null }) {
  const { run, events, connected, action } = useRun(runId, initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function go(stage: string) {
    setBusy(true);
    setError("");
    try {
      await action(stage);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const status = run?.status ?? "queued";
  const running = status.endsWith(":running") || status === "queued";
  const auditRunning = stageState(run, "audit") === "running" || status === "queued";
  const liveScore = [...events].reverse().find((e) => e.kind === "score" && e.phase === "audit:before")?.total;
  const before = run?.audit;
  const after = run?.verify?.audit;

  return (
    <div className="grid gap-6 pt-8">
      <header className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-center">
        <div className="min-w-0">
          <p className="text-xs text-muted">
            Run {runId} · {connected ? "live" : "reconnecting…"}
          </p>
          <h1 className="truncate text-2xl font-semibold">{run?.store_url ?? "Loading…"}</h1>
          {run?.repo && <p className="text-sm text-muted">{run.repo}</p>}
          <ol className="mt-4 flex flex-wrap gap-2 text-sm" aria-label="Progress">
            {STAGES.map((s, i) => {
              const st = stageState(run, s.key);
              return (
                <li
                  key={s.key}
                  className={`flex items-center gap-2 rounded-full border px-3 py-1 ${
                    st === "done"
                      ? "border-good/40 text-good"
                      : st === "running"
                        ? "border-accent text-accent"
                        : st === "failed"
                          ? "border-bad/40 text-bad"
                          : "border-border text-muted"
                  }`}
                >
                  <span className="font-mono text-xs">{i + 1}</span> {s.label}
                  {st === "running" && <span className="size-1.5 animate-pulse rounded-full bg-accent" aria-label="running" />}
                </li>
              );
            })}
          </ol>
        </div>
        <div className="flex items-center gap-4 justify-self-start sm:justify-self-end">
          <ScoreDial score={before?.total ?? liveScore ?? null} pending={auditRunning} label="Before" />
          {after && <ScoreDial score={after.total} label="After" />}
        </div>
      </header>

      {(error || run?.error) && (
        <p role="alert" className="rounded-xl border border-bad/40 bg-bad/10 px-4 py-3 text-sm text-bad">
          {error || run?.error}
        </p>
      )}

      <Panel title="Live audit">
        <LiveView events={events} running={auditRunning} phase="audit:before" />
      </Panel>

      {before && (
        <Panel
          title={`Scorecard · ${before.total}/100`}
          actions={
            <div className="flex gap-2">
              <button
                onClick={() => run && downloadReport(run)}
                className="rounded-lg border border-border px-4 py-2 text-sm transition hover:bg-surface-2"
              >
                Download report
              </button>
              {!run?.fix && run?.repo && (
                <ActionButton onClick={() => go("fix")} busy={busy || running}>
                  Fix it
                </ActionButton>
              )}
            </div>
          }
        >
          <div className="grid gap-6 lg:grid-cols-[1fr_1.6fr]">
            <CategoryBars categories={before.categories} />
            <div className="grid content-start gap-3">
              {before.findings.length === 0 && <p className="text-sm text-muted">No issues found.</p>}
              {before.findings.map((f) => (
                <FindingCard key={f.code} finding={f} />
              ))}
            </div>
          </div>
          {Object.entries(before.shoppers).map(([d, s]) =>
            s?.summary ? (
              <blockquote key={d} className="border-l-2 border-border pl-4 text-sm text-muted">
                <span className="capitalize text-fg">{d} shopper:</span> {s.summary}
              </blockquote>
            ) : null,
          )}
        </Panel>
      )}

      {(run?.fix || stageState(run, "fix") !== "todo") && (
        <Panel
          title="Fix"
          actions={
            run?.fix && !run.verify ? (
              <ActionButton onClick={() => go("verify")} busy={busy || running}>
                Deploy preview &amp; verify
              </ActionButton>
            ) : undefined
          }
        >
          <FixWorkspace events={events} phase="fix" />
          <details className="text-sm">
            <summary className="cursor-pointer text-muted">Agent log</summary>
            <div className="mt-2">
              <AgentLog events={events} phase="fix" />
            </div>
          </details>
          {run?.fix && (
            <div className="grid gap-4">
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <a href={run.fix.pr_url} target="_blank" rel="noreferrer" className="rounded-lg bg-surface-2 px-3 py-1.5 font-medium underline-offset-4 hover:underline">
                  Pull request #{run.fix.pr_number}
                </a>
                <span className={run.fix.build_ok ? "text-good" : "text-bad"}>{run.fix.build_ok ? "Build passing" : "Build failing"}</span>
                <span className="text-muted">{run.fix.files_changed.length} files · {run.fix.tool_calls} tool calls</span>
              </div>
              <p className="whitespace-pre-line text-sm">{run.fix.summary}</p>
              <DiffView diff={run.fix.diff} />
            </div>
          )}
        </Panel>
      )}

      {(run?.verify || stageState(run, "verify") !== "todo") && (
        <Panel
          title="Verify"
          actions={
            run?.verify && !run.agent_ready ? (
              <ActionButton onClick={() => go("agent-ready")} busy={busy || running}>
                Make agent-ready
              </ActionButton>
            ) : undefined
          }
        >
          <AgentLog events={events} phase="verify" />
          {stageState(run, "verify") === "running" && <LiveView events={events} running phase="audit:after" />}
          {run?.verify && before && (
            <div className="grid gap-6">
              <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
                <a href={run.verify.preview_url} target="_blank" rel="noreferrer" className="underline">
                  Preview deployment
                </a>
                {run.verify.order && (
                  <span>
                    Sandbox order <span className="font-mono">{run.verify.order.id}</span>{" "}
                    <span className={run.verify.order.status === "COMPLETED" ? "font-medium text-good" : "text-warn"}>{run.verify.order.status}</span>
                  </span>
                )}
                {run.verify.comment_url && (
                  <a href={run.verify.comment_url} target="_blank" rel="noreferrer" className="underline">
                    Scorecard on the PR
                  </a>
                )}
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                {(["desktop", "mobile"] as const).map((d) => {
                  const b = before.shoppers[d];
                  const a = run.verify!.audit.shoppers[d];
                  return (
                    <div key={d} className="grid gap-2">
                      <h3 className="text-sm font-medium capitalize">{d}</h3>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <BeforeAfterShot label="Before" events={events} phase="audit:before" device={d} paid={b?.payment_completed} />
                        <BeforeAfterShot label="After" events={events} phase="audit:after" device={d} paid={a?.payment_completed} replay={a?.replay_url} />
                      </div>
                    </div>
                  );
                })}
              </div>
              <CategoryBars categories={run.verify.audit.categories} compare={before.categories} />
            </div>
          )}
        </Panel>
      )}

      {(run?.agent_ready || stageState(run, "agent_ready") !== "todo") && (
        <Panel title="Agent-ready">
          <p className="rounded-xl bg-surface-2 px-4 py-3 text-sm text-muted">
            In production, PayPal&apos;s Commerce Platform calls these merchant endpoints after Store Sync onboarding. In
            this sandbox build, Sherpa&apos;s buyer agent plays that caller role.
          </p>
          <FixWorkspace events={events} phase="agent_ready" />
          <details className="text-sm">
            <summary className="cursor-pointer text-muted">Agent log</summary>
            <div className="mt-2">
              <AgentLog events={events} phase="agent_ready" />
            </div>
          </details>
          {stageState(run, "agent_ready") === "running" && <LiveView events={events} running phase="agent_ready" />}
          {run?.agent_ready && (
            <div className="grid gap-6 lg:grid-cols-2">
              <div className="grid content-start gap-4">
                <h3 className="text-sm font-medium">Cart API contract tests</h3>
                <ul className="grid gap-1.5 text-sm">
                  {run.agent_ready.endpoints.map((ep) => (
                    <li key={ep.method + ep.path} className="flex items-center justify-between gap-2 rounded-lg border border-border px-3 py-2">
                      <span className="font-mono text-xs">
                        {ep.method} {ep.path}
                      </span>
                      <span className={ep.ok ? "text-good" : "text-bad"}>{ep.ok ? "pass" : "fail"}</span>
                    </li>
                  ))}
                </ul>
                {run.agent_ready.catalog_preview && (
                  <details className="rounded-xl border border-border">
                    <summary className="cursor-pointer px-3 py-2 text-sm">Catalog feed preview</summary>
                    <pre className="max-h-72 overflow-auto p-3 font-mono text-xs">{JSON.stringify(run.agent_ready.catalog_preview, null, 2)}</pre>
                  </details>
                )}
              </div>
              <div className="grid content-start gap-3">
                <h3 className="text-sm font-medium">Buyer agent</h3>
                <ol className="grid max-h-[520px] gap-2 overflow-y-auto">
                  {run.agent_ready.transcript.map((m, i) => (
                    <li
                      key={i}
                      className={`rounded-xl px-3 py-2 text-sm ${
                        m.role === "user" ? "justify-self-end bg-accent text-accent-fg" : m.role === "tool" ? "bg-surface-2 font-mono text-xs" : "bg-surface-2"
                      }`}
                    >
                      {m.tool && <span className="text-muted">{m.tool}: </span>}
                      {m.text}
                    </li>
                  ))}
                </ol>
                {run.agent_ready.order && (
                  <p className="text-sm">
                    Sandbox order <span className="font-mono">{run.agent_ready.order.id}</span>{" "}
                    <span className="font-medium text-good">{run.agent_ready.order.status}</span>
                  </p>
                )}
              </div>
            </div>
          )}
        </Panel>
      )}

      {run?.usage && (
        <p className="text-xs text-muted">
          {run.usage.steps} browser steps · {run.usage.browser_minutes.toFixed(1)} browser minutes · {run.usage.model_calls} model calls ·{" "}
          {Math.round(run.usage.seconds)}s
        </p>
      )}
    </div>
  );
}

function BeforeAfterShot({
  label,
  events,
  phase,
  device,
  paid,
  replay,
}: {
  label: string;
  events: RunEvent[];
  phase: string;
  device: string;
  paid?: boolean;
  replay?: string | null;
}) {
  const shot = [...events].reverse().find((e) => e.phase === phase && e.device === device && e.shot_id)?.shot_id;
  return (
    <figure className="grid gap-1">
      {shot ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={artifactUrl(shot)} alt={`${label} ${device}`} className="aspect-[4/5] w-full rounded-lg border border-border object-cover object-top" />
      ) : (
        <div className="grid aspect-[4/5] place-items-center rounded-lg border border-border bg-surface-2 text-muted">No screenshot</div>
      )}
      <figcaption className="flex justify-between">
        <span>{label}</span>
        <span className={paid ? "text-good" : "text-bad"}>{paid ? "paid" : "not paid"}</span>
      </figcaption>
      {replay && (
        <a href={replay} target="_blank" rel="noreferrer" className="underline">
          Replay
        </a>
      )}
    </figure>
  );
}
