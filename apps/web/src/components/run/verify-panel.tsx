"use client";

import { scoreTone } from "@/lib/score";
import { artifactUrl, type Run, type RunEvent } from "@/lib/types";
import { CategoryBars } from "../category-bars";
import { LiveView } from "../live-view";
import { AttackReplay } from "./attack-replay";
import type { StageState } from "./mission-bar";

const PLAN = [
  ["Package the pull request", "Sherpa takes the PR branch exactly as the merchant would merge it."],
  ["Deploy a private preview", "Cloud Build builds it and Cloud Run serves it on its own URL, with no live traffic."],
  ["Re-run the AI shoppers", "The same desktop and mobile shoppers try to buy again, now on the fixed checkout."],
  ["Prove a real payment", "A PayPal sandbox payment completes and Sherpa confirms it with the Orders API."],
  ["Post the scorecard", "The before/after scorecard is posted on the pull request."],
];

function Receipt({ order }: { order: { id: string; status: string } }) {
  const ok = order.status === "COMPLETED";
  return (
    <div className="fade-up grid gap-3 rounded-2xl border border-border bg-gradient-to-br from-[#003087] to-[#0070e0] p-5 text-white shadow-lg">
      <div className="flex items-center justify-between">
        <span className="text-lg font-bold italic tracking-tight">PayPal</span>
        <span className="rounded-full bg-white/15 px-2.5 py-0.5 text-xs">sandbox</span>
      </div>
      <div>
        <p className="text-xs text-white/70">Order</p>
        <p className="font-mono text-lg">{order.id}</p>
      </div>
      <div className="flex items-center justify-between">
        <span className={`rounded-full px-3 py-1 text-sm font-semibold ${ok ? "bg-[#3ecf8e] text-[#06301d]" : "bg-white/20"}`}>
          {ok ? "✓ " : ""}
          {order.status}
        </span>
        <span className="text-xs text-white/70">Confirmed via the Orders API</span>
      </div>
    </div>
  );
}

function Shot({ events, phase, device }: { events: RunEvent[]; phase: string; device: string }) {
  const shot = [...events].reverse().find((e) => e.phase === phase && e.device === device && e.shot_id)?.shot_id;
  return shot ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={artifactUrl(shot)} alt="" className="aspect-[4/3] w-full rounded-lg border border-border object-cover object-top" />
  ) : (
    <div className="grid aspect-[4/3] place-items-center rounded-lg border border-dashed border-border text-xs text-muted">No screenshot</div>
  );
}

export function VerifyPanel({ run, events, state }: { run: Run | null; events: RunEvent[]; state: StageState }) {
  const before = run?.audit;
  const verify = run?.verify;
  const logs = events.filter((e) => e.phase === "verify" && (e.kind === "log" || e.kind === "error" || e.kind === "warning"));

  if (state === "todo" && !verify) {
    return (
      <div className="grid gap-4">
        <p className="text-sm text-muted">After the pull request is open, Verify proves the fix actually works:</p>
        <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
          {PLAN.map(([t, d], i) => (
            <li key={t} className="rounded-xl border border-dashed border-border p-3">
              <p className="font-mono text-xs text-accent">0{i + 1}</p>
              <p className="mt-1 text-sm font-medium">{t}</p>
              <p className="mt-1 text-xs text-muted">{d}</p>
            </li>
          ))}
        </ol>
      </div>
    );
  }

  return (
    <div className="grid gap-6">
      {(state === "running" || state === "failed") && (
        <ol className="grid gap-1.5" aria-live="polite">
          {logs.map((e, i) => {
            const last = i === logs.length - 1 && state === "running";
            return (
              <li key={e.seq} className={`fade-up flex items-start gap-2 text-sm ${e.kind === "error" ? "text-bad" : ""}`}>
                <span className={`mt-1 grid size-4 shrink-0 place-items-center rounded-full text-[10px] ${last ? "bg-accent/20" : e.kind === "error" ? "bg-bad/20" : "bg-good/20 text-good"}`}>
                  {last ? <span className="size-1.5 animate-ping rounded-full bg-accent" /> : e.kind === "error" ? "!" : "✓"}
                </span>
                <span>{e.message}</span>
              </li>
            );
          })}
          {logs.length === 0 && <li className="text-sm text-muted">Starting the preview build…</li>}
        </ol>
      )}

      {state === "running" && events.some((e) => e.phase === "audit:after") && (
        <LiveView events={events} running phase="audit:after" />
      )}

      {verify && before && (
        <>
          <div className="grid items-center gap-6 lg:grid-cols-[auto_1fr_auto]">
            <div className="flex items-center gap-4">
              <div className="text-center">
                <p className="text-5xl font-semibold tabular-nums" style={{ color: scoreTone(before.total) }}>
                  {before.total}
                </p>
                <p className="text-xs text-muted">before</p>
              </div>
              <span className="text-3xl text-muted">→</span>
              <div className="text-center">
                <p className="text-5xl font-semibold tabular-nums" style={{ color: scoreTone(verify.audit.total) }}>
                  {verify.audit.total}
                </p>
                <p className="text-xs text-muted">after</p>
              </div>
              <span className="rounded-full bg-good/15 px-3 py-1 text-sm font-semibold text-good">
                +{verify.audit.total - before.total}
              </span>
            </div>
            <div className="flex flex-wrap gap-2 lg:justify-center">
              <a href={verify.preview_url} target="_blank" rel="noreferrer" className="rounded-lg border border-border px-3 py-2 text-sm hover:bg-surface-2">
                Open the preview ↗
              </a>
              {verify.comment_url && (
                <a href={verify.comment_url} target="_blank" rel="noreferrer" className="rounded-lg border border-border px-3 py-2 text-sm hover:bg-surface-2">
                  Scorecard on the PR ↗
                </a>
              )}
            </div>
            {verify.order ? (
              <Receipt order={verify.order} />
            ) : (
              <p className="rounded-xl border border-warn/40 bg-warn/10 p-3 text-sm text-warn">No completed sandbox payment was confirmed.</p>
            )}
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {(["desktop", "mobile"] as const).map((d) => (
              <div key={d} className="grid gap-2">
                <p className="text-sm font-medium capitalize">{d}</p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <figure className="grid gap-1">
                    <Shot events={events} phase="audit:before" device={d} />
                    <figcaption className="flex justify-between text-muted">
                      Before <span className={before.shoppers[d]?.payment_completed ? "text-good" : "text-bad"}>{before.shoppers[d]?.payment_completed ? "paid" : "couldn't pay"}</span>
                    </figcaption>
                  </figure>
                  <figure className="grid gap-1">
                    <Shot events={events} phase="audit:after" device={d} />
                    <figcaption className="flex justify-between text-muted">
                      After <span className={verify.audit.shoppers[d]?.payment_completed ? "text-good" : "text-bad"}>{verify.audit.shoppers[d]?.payment_completed ? "paid" : "couldn't pay"}</span>
                    </figcaption>
                  </figure>
                </div>
              </div>
            ))}
          </div>
          {run && <AttackReplay run={run} events={events} />}
          <CategoryBars categories={verify.audit.categories} compare={before.categories} />
        </>
      )}
    </div>
  );
}
