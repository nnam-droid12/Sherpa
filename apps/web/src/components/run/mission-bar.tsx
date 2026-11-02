"use client";

import type { Run } from "@/lib/types";

export type StageKey = "audit" | "fix" | "verify" | "agent_ready";
export type StageState = "todo" | "running" | "done" | "failed";

export const STAGES: { key: StageKey; label: string; blurb: string }[] = [
  { key: "audit", label: "Audit", blurb: "AI shoppers test checkout" },
  { key: "fix", label: "Fix", blurb: "Coding agent opens a PR" },
  { key: "verify", label: "Verify", blurb: "Preview + real payment" },
  { key: "agent_ready", label: "Agent-ready", blurb: "Cart API + AI buyer" },
];

export function stageState(run: Run | null, key: StageKey): StageState {
  if (!run) return key === "audit" ? "running" : "todo";
  const [stage, state] = (run.status ?? "queued").split(":");
  if (run.status === "queued" && key === "audit") return "running";
  if (stage === key) return state === "done" ? "done" : state === "failed" ? "failed" : "running";
  const done = { audit: !!run.audit, fix: !!run.fix, verify: !!run.verify, agent_ready: !!run.agent_ready }[key];
  return done ? "done" : "todo";
}

type Action = { label: string; stage?: string; hint: string };

function nextAction(run: Run | null, states: Record<StageKey, StageState>): Action | null {
  if (!run || states.audit === "running") return null;
  if (Object.values(states).includes("running")) return null;
  if (!run.audit) return null;
  if (!run.repo) return { label: "Add a repo to fix", hint: "Start a new run with a GitHub repo to unlock Fix, Verify and Agent-ready." };
  if (!run.fix) {
    return states.fix === "failed"
      ? { label: "Retry fix", stage: "fix", hint: "The coding agent stopped early. Try again." }
      : { label: "Fix it", stage: "fix", hint: "A Gemini coding agent fixes every finding and opens a pull request." };
  }
  if (!run.verify) {
    return states.verify === "failed"
      ? { label: "Retry verify", stage: "verify", hint: "Deploy the PR to a preview again and re-test with a real payment." }
      : { label: "Deploy preview & verify", stage: "verify", hint: "Deploy the PR, re-run the shoppers and complete a real sandbox payment." };
  }
  if (!run.agent_ready) {
    return states.agent_ready === "failed"
      ? { label: "Retry agent-ready", stage: "agent-ready", hint: "Add the catalog feed and Cart API again, then let the AI buyer shop." }
      : { label: "Make agent-ready", stage: "agent-ready", hint: "Add a catalog feed and PayPal Cart API, then watch an AI agent buy." };
  }
  return null;
}

const DOT: Record<StageState, string> = {
  todo: "border-border bg-surface text-muted",
  running: "border-accent bg-accent text-accent-fg",
  done: "border-good bg-good text-white",
  failed: "border-bad bg-bad text-white",
};

/** Sticky progress bar with the single next action, so nobody has to hunt for buttons. */
export function MissionBar({
  run,
  busy,
  onAction,
}: {
  run: Run | null;
  busy: boolean;
  onAction: (stage: string) => void;
}) {
  const states = Object.fromEntries(STAGES.map((s) => [s.key, stageState(run, s.key)])) as Record<StageKey, StageState>;
  const action = nextAction(run, states);
  const running = STAGES.find((s) => states[s.key] === "running");
  const complete = run?.agent_ready && !running;

  return (
    <div className="sticky top-14 z-20 -mx-4 border-b border-border bg-bg/85 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <ol className="flex items-center gap-1 sm:gap-2" aria-label="Progress">
          {STAGES.map((s, i) => {
            const st = states[s.key];
            return (
              <li key={s.key} className="flex items-center gap-1 sm:gap-2">
                <a href={`#${s.key}`} className="group flex items-center gap-2 rounded-lg px-1.5 py-1 transition hover:bg-surface-2">
                  <span className={`grid size-7 shrink-0 place-items-center rounded-full border text-xs font-semibold ${DOT[st]}`}>
                    {st === "done" ? "✓" : st === "failed" ? "!" : st === "running" ? <span className="size-2 animate-ping rounded-full bg-white" /> : i + 1}
                  </span>
                  <span className="hidden leading-tight sm:block">
                    <span className="block text-sm font-medium">{s.label}</span>
                    <span className="block text-[11px] text-muted">{s.blurb}</span>
                  </span>
                </a>
                {i < STAGES.length - 1 && (
                  <span className={`h-px w-4 sm:w-8 ${states[STAGES[i + 1].key] !== "todo" || st === "done" ? "bg-good" : "bg-border"}`} aria-hidden />
                )}
              </li>
            );
          })}
        </ol>

        <div className="flex flex-wrap items-center gap-2">
          {run?.fix?.pr_url && (
            <a
              href={run.fix.pr_url}
              target="_blank"
              rel="noreferrer"
              className="rounded-lg border border-border bg-surface px-3 py-2 text-sm font-medium transition hover:bg-surface-2"
            >
              Open pull request #{run.fix.pr_number} ↗
            </a>
          )}
          {running && (
            <span className="flex items-center gap-2 rounded-lg bg-accent/10 px-3 py-2 text-sm text-accent">
              <span className="size-2 animate-pulse rounded-full bg-accent" />
              {running.label} in progress…
            </span>
          )}
          {complete && (
            <span className="rounded-lg bg-good/15 px-3 py-2 text-sm font-medium text-good">All four stages complete</span>
          )}
          {action && (
            <button
              onClick={() => action.stage && onAction(action.stage)}
              disabled={busy || !action.stage}
              title={action.hint}
              className={`rounded-lg px-4 py-2 text-sm font-semibold transition disabled:opacity-60 ${
                action.stage ? "glow bg-accent text-accent-fg hover:opacity-90" : "border border-border text-muted"
              }`}
            >
              {busy ? "Starting…" : `${action.label} →`}
            </button>
          )}
        </div>
      </div>
      {action?.stage && <p className="mt-1.5 text-xs text-muted lg:text-right">{action.hint}</p>}
    </div>
  );
}
