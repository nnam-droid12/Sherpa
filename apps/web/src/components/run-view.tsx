"use client";

import { useState } from "react";
import { downloadReport } from "@/lib/report";
import type { Run, RunEvent } from "@/lib/types";
import { useRun } from "@/lib/use-run";
import { CategoryBars } from "./category-bars";
import { DiffView } from "./diff-view";
import { FindingCard } from "./finding-card";
import { FixWorkspace } from "./fix-workspace";
import { LiveView } from "./live-view";
import { AgentReadyPanel } from "./run/agent-ready-panel";
import { MissionBar, stageState, type StageState } from "./run/mission-bar";
import { VerifyPanel } from "./run/verify-panel";
import { ScoreDial } from "./score-dial";

const BADGE: Record<StageState, string> = {
  todo: "bg-surface-2 text-muted",
  running: "bg-accent/15 text-accent",
  done: "bg-good/15 text-good",
  failed: "bg-bad/15 text-bad",
};
const BADGE_TEXT: Record<StageState, string> = { todo: "Up next", running: "Running", done: "Done", failed: "Failed" };

function Panel({
  id,
  n,
  title,
  subtitle,
  state,
  actions,
  children,
}: {
  id: string;
  n?: number;
  title: string;
  subtitle?: string;
  state?: StageState;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section
      id={id}
      className={`grid scroll-mt-40 gap-5 rounded-2xl border bg-surface p-4 sm:p-6 ${state === "running" ? "border-accent/60 shadow-lg shadow-accent/5" : "border-border"}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          {n != null && (
            <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-accent/10 font-mono text-sm font-semibold text-accent">{n}</span>
          )}
          <div>
            <h2 className="text-lg font-semibold">{title}</h2>
            {subtitle && <p className="text-sm text-muted">{subtitle}</p>}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {state && <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${BADGE[state]}`}>{BADGE_TEXT[state]}</span>}
          {actions}
        </div>
      </div>
      {children}
    </section>
  );
}

function AgentLog({ events, phase }: { events: RunEvent[]; phase: string }) {
  const items = events.filter((e) => e.phase === phase && !["step", "file", "chat", "contract", "catalog"].includes(e.kind));
  if (!items.length) return null;
  return (
    <ol className="max-h-80 overflow-y-auto rounded-xl border border-border bg-bg p-3 font-mono text-xs leading-6">
      {items.map((e) => (
        <li key={e.seq} className={e.kind === "error" ? "text-bad" : e.kind === "tool" ? "" : "text-muted"}>
          <span className="text-muted">{new Date(e.ts * 1000).toLocaleTimeString()} </span>
          {e.kind === "tool" ? `${e.tool}(${e.target ?? ""})` : (e.message ?? e.text ?? e.kind)}
        </li>
      ))}
    </ol>
  );
}

const FIX_PREVIEW = [
  ["JS SDK v6", "Replace the legacy script with createInstance, eligibility checks and web-component buttons."],
  ["Above the fold", "PayPal and Venmo next to the order total, visible on phones too."],
  ["Pay Later", "Messaging on product and cart pages for eligible amounts."],
  ["Safer payments", "Server-side amounts, verified webhook signatures, graceful errors."],
];

export function RunView({ runId, initial }: { runId: string; initial: Run | null }) {
  const { run, events, connected, action } = useRun(runId, initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function go(stage: string) {
    setBusy(true);
    setError("");
    try {
      await action(stage);
      const anchor = stage === "agent-ready" ? "agent_ready" : stage;
      setTimeout(() => document.getElementById(anchor)?.scrollIntoView({ behavior: "smooth" }), 150);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const audit = stageState(run, "audit");
  const fix = stageState(run, "fix");
  const verify = stageState(run, "verify");
  const agentReady = stageState(run, "agent_ready");
  const liveScore = [...events].reverse().find((e) => e.kind === "score" && e.phase === "audit:before")?.total;
  const before = run?.audit;
  const after = run?.verify?.audit;

  return (
    <div className="grid gap-6">
      <MissionBar run={run} busy={busy} onAction={go} />

      <header className="grid gap-4 sm:grid-cols-[1fr_auto] sm:items-center">
        <div className="min-w-0">
          <p className="text-xs text-muted">
            Run {runId} · {connected ? "live" : "reconnecting…"}
          </p>
          <h1 className="truncate text-2xl font-semibold">{run?.store_url ?? "Loading…"}</h1>
          {run?.repo && (
            <a href={`https://github.com/${run.repo}`} target="_blank" rel="noreferrer" className="text-sm text-muted hover:text-fg">
              {run.repo} ↗
            </a>
          )}
        </div>
        <div className="flex items-center gap-4 justify-self-start sm:justify-self-end">
          <ScoreDial score={before?.total ?? liveScore ?? null} pending={audit === "running"} label="Before" />
          {after && <ScoreDial score={after.total} label="After" />}
        </div>
      </header>

      {(error || run?.error) && (
        <p role="alert" className="rounded-xl border border-bad/40 bg-bad/10 px-4 py-3 text-sm text-bad">
          {error || run?.error}
        </p>
      )}

      <Panel id="audit" n={1} title="Live audit" subtitle="Two AI shoppers try to buy with PayPal in real cloud browsers, on desktop and on a phone." state={audit}>
        <LiveView events={events} running={audit === "running"} phase="audit:before" />
      </Panel>

      {before && (
        <Panel
          id="scorecard"
          title={`Scorecard · ${before.total}/100`}
          subtitle="Deterministic score across seven checks. Each finding explains the business impact and the fix."
          actions={
            <button onClick={() => run && downloadReport(run)} className="rounded-lg border border-border px-3 py-1.5 text-sm transition hover:bg-surface-2">
              Download report
            </button>
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

      {before && (
        <Panel id="fix" n={2} title="Fix" subtitle="A Gemini coding agent edits the store's repository and opens a pull request." state={fix}>
          {fix === "todo" && !run?.fix ? (
            <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {FIX_PREVIEW.map(([t, d], i) => (
                <li key={t} className="rounded-xl border border-dashed border-border p-4">
                  <p className="font-mono text-xs text-accent">0{i + 1}</p>
                  <p className="mt-1 font-medium">{t}</p>
                  <p className="mt-1 text-xs text-muted">{d}</p>
                </li>
              ))}
            </ol>
          ) : (
            <>
              {run?.fix && (
                <div className="flex flex-wrap items-center gap-3 rounded-xl border border-good/30 bg-good/5 p-4">
                  <span className="grid size-10 place-items-center rounded-full bg-good/15 text-lg text-good">✓</span>
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">Pull request #{run.fix.pr_number} is open</p>
                    <p className="text-sm text-muted">
                      {run.fix.files_changed.length} files changed · {run.fix.build_ok ? "build passing" : "build failing"} · {run.fix.tool_calls} agent tool calls
                    </p>
                  </div>
                  <a href={run.fix.pr_url} target="_blank" rel="noreferrer" className="rounded-lg bg-fg px-4 py-2 text-sm font-medium text-bg transition hover:opacity-90">
                    View on GitHub ↗
                  </a>
                </div>
              )}
              <FixWorkspace events={events} phase="fix" />
              {run?.fix && (
                <details className="rounded-xl border border-border p-3">
                  <summary className="cursor-pointer text-sm font-medium">Full diff of the pull request</summary>
                  <div className="mt-3 grid gap-3">
                    <p className="whitespace-pre-line text-sm text-muted">{run.fix.summary}</p>
                    <DiffView diff={run.fix.diff} />
                  </div>
                </details>
              )}
              <details className="text-sm">
                <summary className="cursor-pointer text-muted">Agent log</summary>
                <div className="mt-2">
                  <AgentLog events={events} phase="fix" />
                </div>
              </details>
            </>
          )}
        </Panel>
      )}

      {before && (
        <Panel id="verify" n={3} title="Verify" subtitle="Deploy the pull request to a preview, re-run the shoppers and complete a real sandbox payment." state={verify}>
          <VerifyPanel run={run} events={events} state={verify} />
        </Panel>
      )}

      {before && (
        <Panel id="agent_ready" n={4} title="Agent-ready" subtitle="Make the store buyable by AI shopping agents through PayPal." state={agentReady}>
          <AgentReadyPanel run={run} events={events} state={agentReady} />
          <details className="text-sm">
            <summary className="cursor-pointer text-muted">Agent log</summary>
            <div className="mt-2">
              <AgentLog events={events} phase="agent_ready" />
            </div>
          </details>
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
