"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import type { DemoStore, Run } from "@/lib/types";

const FLAWS: Record<string, number> = { "ember-oak": 9, "lumen-bakehouse": 7 };

export function DemoLauncher({ demos }: { demos: DemoStore[] }) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");

  async function start(d: DemoStore, autopilot = false) {
    setBusy(autopilot ? `${d.id}:auto` : d.id);
    setError("");
    try {
      const res = await fetch("/api/agent/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          store_url: d.store_url,
          repo: d.repo,
          store_type: d.id === "lumen-bakehouse" ? "nextjs" : "static-express",
          demo_store: d.id,
          autopilot,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Could not start (${res.status})`);
      router.push(`/runs/${(data as Run).id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(null);
    }
  }

  if (!demos.length) {
    return <p className="rounded-xl border border-border bg-surface p-4 text-sm text-muted">Demo stores are starting up. Refresh in a moment.</p>;
  }

  return (
    <div className="grid gap-4">
      <div className="grid gap-4 md:grid-cols-2">
        {demos.map((d) => (
          <article key={d.id} className="group overflow-hidden rounded-2xl border border-border bg-surface shadow-sm">
            <div className="relative aspect-[16/9] overflow-hidden bg-surface-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`${d.store_url}/img/hero.jpg`}
                alt={`${d.name} storefront`}
                className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"
              />
              <span className="absolute left-3 top-3 rounded-full bg-black/60 px-2.5 py-1 text-xs font-medium text-white backdrop-blur">
                {FLAWS[d.id] ?? "Several"} planted checkout flaws
              </span>
            </div>
            <div className="grid gap-3 p-4 sm:p-5">
              <div>
                <h3 className="text-lg font-semibold">{d.name}</h3>
                <p className="text-sm text-muted">{d.tagline}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => start(d)}
                  disabled={busy !== null}
                  className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition hover:opacity-90 disabled:opacity-60"
                >
                  {busy === d.id ? "Starting…" : "Run live audit"}
                </button>
                <button
                  onClick={() => start(d, true)}
                  disabled={busy !== null}
                  title="Audit, fix, verify and make agent-ready, back to back with no clicks"
                  className="rounded-lg border border-accent/50 px-4 py-2 text-sm font-medium text-accent transition hover:bg-accent/10 disabled:opacity-60"
                >
                  {busy === `${d.id}:auto` ? "Starting…" : "⚡ Full autopilot"}
                </button>
                {d.recent_run_id && (
                  <Link
                    href={`/runs/${d.recent_run_id}`}
                    className="rounded-lg border border-border px-4 py-2 text-sm transition hover:bg-surface-2"
                  >
                    View latest run
                  </Link>
                )}
                <a
                  href={d.store_url}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-lg px-3 py-2 text-sm text-muted transition hover:text-fg"
                >
                  Visit store ↗
                </a>
              </div>
            </div>
          </article>
        ))}
      </div>
      {error && (
        <p role="alert" className="rounded-xl border border-bad/40 bg-bad/10 px-4 py-3 text-sm text-bad">
          {error}
        </p>
      )}
    </div>
  );
}
