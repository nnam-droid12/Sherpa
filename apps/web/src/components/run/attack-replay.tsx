"use client";

import { useState } from "react";
import type { Attack, AttackOutcome, Run, RunEvent } from "@/lib/types";

const VERDICT: Record<AttackOutcome["verdict"], { label: string; tone: string }> = {
  vulnerable: { label: "Attack worked", tone: "border-bad/40 bg-bad/10 text-bad" },
  blocked: { label: "Blocked", tone: "border-good/40 bg-good/10 text-good" },
  missing: { label: "No endpoint", tone: "border-border bg-surface-2 text-muted" },
  unknown: { label: "Inconclusive", tone: "border-warn/40 bg-warn/10 text-warn" },
  skipped: { label: "Not attacked", tone: "border-border bg-surface-2 text-muted" },
};

function Outcome({ label, o }: { label: string; o: AttackOutcome }) {
  const v = VERDICT[o.verdict];
  return (
    <div className={`grid content-start gap-1.5 rounded-xl border p-3 ${v.tone}`}>
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="font-medium uppercase tracking-wide opacity-80">{label}</span>
        <span className="rounded-full bg-current/10 px-2 py-0.5 font-semibold">
          {o.verdict === "vulnerable" ? "✗ " : o.verdict === "blocked" ? "✓ " : ""}
          {v.label}
        </span>
      </div>
      <p className="text-sm text-fg">{o.detail}</p>
      {o.request && <p className="font-mono text-[11px] text-muted">{o.request}</p>}
    </div>
  );
}

/** Real attacks against the store before and after the fix, so the security fixes are proven, not claimed. */
export function AttackReplay({ run, events }: { run: Run; events: RunEvent[] }) {
  const [local, setLocal] = useState<Attack[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const live = events.filter((e) => e.phase === "verify" && e.kind === "attack") as unknown as Attack[];
  const attacks = local ?? run.verify?.attacks ?? (live.length ? live : null);

  async function replay() {
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`/api/agent/runs/${run.id}/attacks`, { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Attack replay failed (${res.status})`);
      setLocal((data as Run).verify?.attacks ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="grid gap-3" aria-labelledby="attack-title">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 id="attack-title" className="font-semibold">
            Attack replay
          </h3>
          <p className="text-sm text-muted">Sherpa tries real attacks on the store before and after the fix, in the PayPal sandbox.</p>
        </div>
        {!attacks && (
          <button
            onClick={replay}
            disabled={busy}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition hover:opacity-90 disabled:opacity-60"
          >
            {busy ? "Attacking the store…" : "Run attack replay"}
          </button>
        )}
      </div>
      {error && (
        <p role="alert" className="text-sm text-bad">
          {error}
        </p>
      )}
      {attacks?.map((a) => (
        <article key={a.id} className="grid gap-3 rounded-2xl border border-border bg-surface p-4 lg:grid-cols-[220px_1fr_1fr]">
          <div>
            <p className="font-medium">{a.title}</p>
            <p className="text-xs text-muted">{a.threat}</p>
          </div>
          <Outcome label="Before the fix" o={a.before} />
          <Outcome label="After the fix" o={a.after} />
        </article>
      ))}
      {attacks && (
        <p className="text-xs text-muted">
          Orders created by the price attack are never captured, so nothing is charged. Only sandbox stores are attacked.
        </p>
      )}
    </section>
  );
}
