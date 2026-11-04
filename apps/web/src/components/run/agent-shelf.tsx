"use client";

import { useState } from "react";
import type { Run, RunEvent, Shelf, ShelfItem } from "@/lib/types";

const usd = (n: number) => n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: n < 100 ? 2 : 0 });

const BADGE: Record<ShelfItem["position"], string> = {
  below: "bg-good/15 text-good",
  in_line: "bg-accent/15 text-accent",
  above: "bg-warn/15 text-warn",
  no_match: "bg-surface-2 text-muted",
};

function verdict(item: ShelfItem) {
  const pct = item.delta == null ? 0 : Math.round(Math.abs(item.delta) * 100);
  if (item.position === "below") return `${pct}% below market`;
  if (item.position === "above") return `${pct}% above market`;
  if (item.position === "in_line") return "In line with market";
  return "No direct competitors found";
}

/** Merchant price against the live market: every dot is a real in-stock offer. */
function PriceRange({ item }: { item: ShelfItem }) {
  const prices = item.comparables.map((c) => c.price);
  const { min, max, median } = item.market;
  if (min == null || max == null || item.price == null) return null;
  const lo = Math.min(min, item.price);
  const hi = Math.max(max, item.price);
  const at = (v: number) => `${hi === lo ? 50 : ((v - lo) / (hi - lo)) * 100}%`;
  return (
    <div className="grid gap-1.5" aria-label={`Market ${usd(min)} to ${usd(max)}, median ${usd(median ?? 0)}, store ${usd(item.price)}`}>
      <div className="relative mx-2 h-8">
        <div className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-surface-2" />
        <div className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-accent/25" style={{ left: at(min), width: `calc(${at(max)} - ${at(min)})` }} />
        {prices.map((p, i) => (
          <span key={i} className="absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-surface bg-muted" style={{ left: at(p) }} />
        ))}
        {median != null && <span className="absolute top-1 h-6 w-px -translate-x-1/2 bg-fg/40" style={{ left: at(median) }} />}
        <span
          className="absolute top-1/2 grid size-5 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-full bg-accent text-[9px] font-bold text-accent-fg shadow ring-4 ring-accent/20"
          style={{ left: at(item.price) }}
          title={`This store: ${usd(item.price)}`}
        >
          ★
        </span>
      </div>
      <div className="flex justify-between text-[11px] tabular-nums text-muted">
        <span>{usd(lo)}</span>
        {median != null && <span>median {usd(median)}</span>}
        <span>{usd(hi)}</span>
      </div>
    </div>
  );
}

function ShelfRow({ item }: { item: ShelfItem }) {
  return (
    <article className="grid gap-4 rounded-2xl border border-border bg-surface p-4 lg:grid-cols-[260px_1fr]">
      <div className="grid content-start gap-3">
        <div className="flex gap-3">
          {item.image && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={item.image} alt="" className="size-16 shrink-0 rounded-lg object-cover" />
          )}
          <div className="min-w-0">
            <p className="text-xs text-muted">This store</p>
            <p className="font-medium leading-snug">{item.title}</p>
            {item.price != null && <p className="text-lg font-semibold tabular-nums">{usd(item.price)}</p>}
          </div>
        </div>
        <span className={`w-fit rounded-full px-2.5 py-1 text-xs font-medium ${BADGE[item.position]}`}>{verdict(item)}</span>
        <p className="text-xs text-muted">
          Agent searched: <span className="font-mono text-fg">&ldquo;{item.query}&rdquo;</span>
        </p>
      </div>

      {item.position === "no_match" ? (
        <div className="grid content-center rounded-xl border border-dashed border-border p-4 text-sm text-muted">
          <p>
            A shopper&apos;s agent searching the open web found no comparable product for sale, so it can&apos;t compare prices.
            For products like this, the store&apos;s own catalog feed and Cart API are how agents find and buy them.
          </p>
        </div>
      ) : (
        <div className="grid content-start gap-3">
          <PriceRange item={item} />
          <p className="text-xs text-muted">
            {item.market.count} comparable in-stock {item.market.count === 1 ? "offer" : "offers"} from {item.market.retailers.length}{" "}
            {item.market.retailers.length === 1 ? "retailer" : "retailers"}: {item.market.retailers.slice(0, 4).join(", ")}
            {item.market.retailers.length > 4 ? "…" : ""}
          </p>
          <ul className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {item.comparables.map((c) => (
              <li key={c.id}>
                <a
                  href={c.url ?? undefined}
                  target="_blank"
                  rel="noreferrer sponsored"
                  className="grid h-full gap-1.5 rounded-xl border border-border p-2 transition hover:border-accent"
                >
                  {c.image && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={c.image} alt="" loading="lazy" className="aspect-square w-full rounded-lg bg-white object-contain" />
                  )}
                  <span className="line-clamp-2 text-xs leading-snug">{c.title}</span>
                  <span className="mt-auto flex items-baseline justify-between gap-1">
                    <span className="text-sm font-semibold tabular-nums">{usd(c.price)}</span>
                    <span className="truncate text-[11px] text-muted">{c.domain}</span>
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}

export function AgentShelf({ run, events, running }: { run: Run | null; events: RunEvent[]; running: boolean }) {
  const [local, setLocal] = useState<Shelf | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const event = [...events].reverse().find((e) => e.phase === "agent_ready" && e.kind === "shelf") as unknown as Shelf | undefined;
  const shelf = local ?? run?.shelf ?? event ?? null;

  async function check() {
    if (!run) return;
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`/api/agent/runs/${run.id}/shelf`, { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Could not check the shelf (${res.status})`);
      setLocal((data as Run).shelf ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!shelf?.items?.length) {
    if (running) return <p className="text-sm text-muted">Waiting for the catalog feed…</p>;
    if (!run?.agent_ready) return null;
    return (
      <div className="grid justify-items-start gap-3 rounded-2xl border border-dashed border-border p-5">
        <p className="text-sm text-muted">
          See what a shopper&apos;s AI agent finds on the open web for this store&apos;s products, and how the store&apos;s prices compare.
        </p>
        <button
          onClick={check}
          disabled={busy}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition hover:opacity-90 disabled:opacity-60"
        >
          {busy ? "Searching the market…" : "Check the Agent Shelf"}
        </button>
        {error && (
          <p role="alert" className="text-sm text-bad">
            {error}
          </p>
        )}
      </div>
    );
  }

  const priced = shelf.items.filter((i) => i.position !== "no_match");
  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
        <span className="rounded-full bg-surface-2 px-2.5 py-1 font-medium text-fg">Live market data from Channel3</span>
        <span>
          {shelf.items.length} products checked · {priced.length} with direct competitors ·{" "}
          {priced.filter((i) => i.position === "above").length} priced above market
        </span>
      </div>
      {shelf.items.map((item) => (
        <ShelfRow key={item.id} item={item} />
      ))}
      <p className="text-xs text-muted">
        Prices are live, in-stock US offers returned by Channel3. Gemini keeps only products a shopper would accept as alternatives.
        &ldquo;In line&rdquo; means within 10% of the median.
      </p>
    </div>
  );
}
