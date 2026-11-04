"use client";

import { AllCommunityModule, ModuleRegistry, themeQuartz, type ColDef, type ICellRendererParams } from "ag-grid-community";
import { AgGridReact } from "ag-grid-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { scoreTone } from "@/lib/score";
import type { DemoStore, Run } from "@/lib/types";

ModuleRegistry.registerModules([AllCommunityModule]);

export type StoreHealth = {
  url: string;
  reachable: boolean;
  status: number | null;
  ms: number | null;
  sdk: "v6" | "v5" | "none";
  paypal: boolean;
  venmo: boolean;
  pay_later: boolean;
  catalog_feed: string | null;
  catalog_items: number;
  cart_api: boolean;
  score: number;
  issues: string[];
  error: string | null;
};

// The grid reads the console's own colour tokens, so it follows the light and dark themes.
const theme = themeQuartz.withParams({
  backgroundColor: "var(--surface)",
  foregroundColor: "var(--fg)",
  headerBackgroundColor: "var(--surface-2)",
  borderColor: "var(--border)",
  accentColor: "var(--accent)",
  oddRowBackgroundColor: "var(--surface)",
  rowHoverColor: "var(--surface-2)",
  fontFamily: "inherit",
  fontSize: 13,
  headerFontSize: 12,
  wrapperBorderRadius: 16,
});

const MAX = 25;

function Check({ value }: { value: boolean }) {
  return value ? <span className="text-good">✓</span> : <span className="text-bad">✗</span>;
}

export function FleetGrid({ demos }: { demos: DemoStore[] }) {
  const router = useRouter();
  const [text, setText] = useState("");
  const [rows, setRows] = useState<StoreHealth[]>([]);
  const [busy, setBusy] = useState(false);
  const [starting, setStarting] = useState<string | null>(null);
  const [error, setError] = useState("");

  const urls = text
    .split(/[\s,]+/)
    .map((u) => u.trim())
    .filter(Boolean)
    .map((u) => (/^https?:\/\//i.test(u) ? u : `https://${u}`));

  async function scan() {
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/agent/fleet/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urls: urls.slice(0, MAX) }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Scan failed (${res.status})`);
      setRows(data.stores);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function deepAudit(url: string) {
    const demo = demos.find((d) => d.store_url.replace(/\/$/, "") === url);
    setStarting(url);
    setError("");
    try {
      const res = await fetch("/api/agent/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          demo
            ? { store_url: url, repo: demo.repo, store_type: demo.id === "lumen-bakehouse" ? "nextjs" : "static-express", demo_store: demo.id }
            : { store_url: url },
        ),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Could not start (${res.status})`);
      router.push(`/runs/${(data as Run).id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStarting(null);
    }
  }

  const columns = useMemo<ColDef<StoreHealth>[]>(
    () => [
      {
        field: "score",
        headerName: "Health",
        width: 96,
        sort: "asc",
        cellRenderer: (p: ICellRendererParams<StoreHealth, number>) => (
          <span className="font-semibold tabular-nums" style={{ color: scoreTone(p.value ?? 0) }}>
            {p.value}
          </span>
        ),
      },
      { field: "url", headerName: "Store", flex: 1, minWidth: 180 },
      {
        field: "sdk",
        headerName: "PayPal SDK",
        width: 118,
        valueFormatter: (p) => (p.value === "none" ? "not seen" : p.value === "v5" ? "v5 (legacy)" : "v6"),
        cellClass: (p) => (p.value === "v6" ? "text-good" : p.value === "v5" ? "text-warn" : "text-bad"),
      },
      { field: "venmo", headerName: "Venmo", width: 86, cellRenderer: (p: ICellRendererParams<StoreHealth, boolean>) => <Check value={!!p.value} /> },
      { field: "pay_later", headerName: "Pay Later", width: 96, cellRenderer: (p: ICellRendererParams<StoreHealth, boolean>) => <Check value={!!p.value} /> },
      {
        field: "catalog_feed",
        headerName: "Catalog feed",
        width: 118,
        cellRenderer: (p: ICellRendererParams<StoreHealth, string | null>) =>
          p.value ? <span className="text-good">{p.data?.catalog_items} items</span> : <span className="text-bad">✗</span>,
      },
      { field: "cart_api", headerName: "Cart API", width: 90, cellRenderer: (p: ICellRendererParams<StoreHealth, boolean>) => <Check value={!!p.value} /> },
      {
        field: "issues",
        headerName: "Top issues",
        flex: 2,
        minWidth: 240,
        sortable: false,
        valueFormatter: (p) => (p.value?.length ? p.value.join(" · ") : "None found"),
        tooltipValueGetter: (p) => p.value?.join("\n"),
      },
      {
        colId: "action",
        headerName: "",
        width: 144,
        sortable: false,
        pinned: "right",
        cellRenderer: (p: ICellRendererParams<StoreHealth>) =>
          p.data?.reachable ? (
            <button
              onClick={() => p.data && deepAudit(p.data.url)}
              disabled={starting !== null}
              className="rounded-md border border-accent/50 px-2.5 py-1 text-xs font-medium text-accent transition hover:bg-accent/10 disabled:opacity-60"
            >
              {starting === p.data.url ? "Starting…" : "Deep audit →"}
            </button>
          ) : null,
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [starting, demos],
  );

  const scanned = rows.length;
  const avg = scanned ? Math.round(rows.reduce((s, r) => s + r.score, 0) / scanned) : null;
  const count = (f: (r: StoreHealth) => boolean) => rows.filter(f).length;

  return (
    <div className="grid gap-5">
      <div className="grid gap-3 rounded-2xl border border-border bg-surface p-4 sm:p-5">
        <label htmlFor="fleet-urls" className="text-sm text-muted">
          Store URLs, one per line or separated by commas (up to {MAX})
        </label>
        <textarea
          id="fleet-urls"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={4}
          placeholder={"https://store-one.example\nhttps://store-two.example"}
          className="w-full rounded-lg border border-border bg-bg px-3 py-2 font-mono text-sm outline-none transition focus:border-accent"
        />
        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={scan}
            disabled={busy || urls.length === 0}
            className="rounded-lg bg-accent px-5 py-2 text-sm font-medium text-accent-fg transition hover:opacity-90 disabled:opacity-60"
          >
            {busy ? `Scanning ${Math.min(urls.length, MAX)} stores…` : `Scan${urls.length ? ` ${Math.min(urls.length, MAX)}` : ""} stores`}
          </button>
          {demos.length > 0 && (
            <button
              onClick={() => setText(demos.map((d) => d.store_url).join("\n"))}
              className="rounded-lg border border-border px-4 py-2 text-sm transition hover:bg-surface-2"
            >
              Use the demo stores
            </button>
          )}
          <span className="text-xs text-muted">No browsers or AI calls: Sherpa reads public pages and probes the agent endpoints.</span>
        </div>
        {urls.length > MAX && <p className="text-xs text-warn">Only the first {MAX} URLs will be scanned.</p>}
      </div>

      {error && (
        <p role="alert" className="rounded-xl border border-bad/40 bg-bad/10 px-4 py-3 text-sm text-bad">
          {error}
        </p>
      )}

      {scanned > 0 && (
        <section className="grid grid-cols-2 gap-3 md:grid-cols-4" aria-label="Fleet summary">
          {[
            ["Stores scanned", String(scanned)],
            ["Average health", `${avg}/100`],
            ["Without PayPal seen", String(count((r) => !r.paypal))],
            ["Not ready for AI agents", String(count((r) => !r.catalog_feed || !r.cart_api))],
          ].map(([label, value]) => (
            <div key={label} className="rounded-2xl border border-border bg-surface p-4">
              <p className="text-xs text-muted">{label}</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
            </div>
          ))}
        </section>
      )}

      <div className="w-full [&_.ag-center-cols-viewport]:min-h-24">
        <AgGridReact<StoreHealth>
          theme={theme}
          rowData={rows}
          columnDefs={columns}
          defaultColDef={{ sortable: true, resizable: true }}
          getRowId={(p) => p.data.url}
          domLayout="autoHeight"
          tooltipShowDelay={300}
          overlayNoRowsTemplate={busy ? "Scanning…" : "Add store URLs above and press Scan."}
        />
      </div>
      <p className="text-xs text-muted">
        Health is a quick triage score from public signals (PayPal SDK 30, v6 SDK 20, Venmo 10, Pay Later 10, catalog feed 15,
        Cart API 15). Some stores load PayPal only after sign-in or in checkout scripts, so open a deep audit to confirm with
        real AI shoppers.
      </p>
    </div>
  );
}
