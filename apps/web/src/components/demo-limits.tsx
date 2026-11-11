import Link from "next/link";
import type { DemoLimits } from "@/lib/types";

// Finished runs that show every stage, recorded from real runs. Viewing them costs nothing.
const SHOWCASE = [
  { id: "823477e9b5a3", label: "Ember & Oak", result: "15 → 100" },
  { id: "c0f8218ae7c0", label: "Lumen Bakehouse", result: "14 → 100" },
  { id: "61387375ff4d", label: "PayPal's own sample", result: "71 → 82" },
];

export function codingPaused(limits?: DemoLimits | null) {
  return !!limits?.demo && (limits.coding_runs_per_day ?? 0) <= 0;
}

/** Tells judges up front how the public demo limits Gemini, and where to see every stage instead. */
export function DemoLimitsNotice({ limits, compact = false }: { limits?: DemoLimits | null; compact?: boolean }) {
  if (!limits?.demo) return null;
  const paused = codingPaused(limits);
  const coding = paused
    ? "Fix and Agent-ready use the most Gemini, so they are paused here"
    : `Fix and Agent-ready are limited to ${limits.coding_runs_per_day} runs a day in total`;
  const audits = limits.audit_runs_per_day ? `; live audits are limited to ${limits.audit_runs_per_day} a day in total` : "";
  return (
    <aside role="note" className="grid gap-3 rounded-2xl border border-warn/40 bg-warn/10 p-4 text-sm">
      <p className="font-semibold text-fg">Gemini is capped on this public demo to keep cloud costs down.</p>
      <p className="text-muted">
        {coding}
        {audits}. Every stage is recorded in these finished runs, so you can watch Sherpa work end to end
        {compact ? ":" : ": the live shoppers, the code it wrote, real PayPal sandbox payments, the attack replay and the AI buyer."}
      </p>
      <div className="flex flex-wrap gap-2">
        {SHOWCASE.map((r) => (
          <Link key={r.id} href={`/runs/${r.id}`} className="rounded-lg border border-border bg-surface px-3 py-1.5 font-medium transition hover:border-accent">
            {r.label} <span className="tabular-nums text-good">{r.result}</span>
          </Link>
        ))}
      </div>
      {!compact && (
        <p className="text-xs text-muted">
          Fleet scan and the MCP endpoint don&apos;t use Gemini and stay fully open. To run every stage on your own store, see{" "}
          <a href="https://github.com/nnam-droid12/Sherpa#run-it-yourself" className="underline" target="_blank" rel="noreferrer">
            Run it yourself
          </a>
          .
        </p>
      )}
    </aside>
  );
}
