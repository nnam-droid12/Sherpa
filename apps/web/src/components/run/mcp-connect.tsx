"use client";

import { useEffect, useState } from "react";
import type { Run } from "@/lib/types";

type Tool = { name: string; title?: string; description: string };
type Product = { id: string; title: string; price?: { value?: string } };

async function rpc(url: string, method: string, params: Record<string, unknown> = {}) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json, text/event-stream" },
    body: JSON.stringify({ jsonrpc: "2.0", id: Date.now(), method, params }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok || data.error) throw new Error(data.error?.message || data.detail || `HTTP ${res.status}`);
  return data.result;
}

/** The store's MCP endpoint: any MCP-capable assistant can search, fill a cart and pay through PayPal. */
export function McpConnect({ run }: { run: Run }) {
  const [origin, setOrigin] = useState("");
  const [tools, setTools] = useState<Tool[] | null>(null);
  const [products, setProducts] = useState<Product[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  useEffect(() => setOrigin(window.location.origin), []);
  const path = `/api/agent/mcp/${run.id}`;
  const url = `${origin}${path}`;
  const config = JSON.stringify({ mcpServers: { [`sherpa-${run.demo_store ?? "store"}`]: { type: "http", url } } }, null, 2);

  async function tryIt() {
    setBusy(true);
    setError("");
    try {
      await rpc(path, "initialize", { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "sherpa-console", version: "1" } });
      setTools((await rpc(path, "tools/list")).tools);
      const found = await rpc(path, "tools/call", { name: "search_products", arguments: {} });
      setProducts(found.structuredContent?.products ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded-lg border border-border bg-surface-2 px-3 py-2 font-mono text-xs">{url || path}</code>
        <button
          onClick={() => {
            navigator.clipboard?.writeText(url).then(() => setCopied(true), () => setCopied(false));
          }}
          className="rounded-lg border border-border px-3 py-2 text-sm hover:bg-surface-2"
        >
          {copied ? "Copied" : "Copy URL"}
        </button>
        <button
          onClick={tryIt}
          disabled={busy}
          className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-accent-fg transition hover:opacity-90 disabled:opacity-60"
        >
          {busy ? "Connecting…" : "Try it live"}
        </button>
      </div>
      <details className="text-sm">
        <summary className="cursor-pointer text-muted">Add it to an MCP client</summary>
        <pre className="mt-2 overflow-x-auto rounded-lg border border-border bg-surface-2 p-3 font-mono text-xs">{config}</pre>
      </details>
      {error && (
        <p role="alert" className="text-sm text-bad">
          {error}
        </p>
      )}
      {tools && (
        <div className="grid gap-2 sm:grid-cols-2">
          <div className="rounded-xl border border-border p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted">{tools.length} tools over MCP</p>
            <ul className="mt-2 grid gap-1 font-mono text-xs">
              {tools.map((t) => (
                <li key={t.name}>
                  <span className="text-accent">{t.name}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-xl border border-border p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-muted">search_products → {products?.length ?? 0} products</p>
            <ul className="mt-2 grid gap-1 text-xs">
              {products?.slice(0, 5).map((p) => (
                <li key={p.id} className="flex justify-between gap-2">
                  <span className="truncate">{p.title}</span>
                  <span className="tabular-nums text-muted">${p.price?.value}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
      <p className="text-xs text-muted">
        MCP Streamable HTTP. Every tool calls the store&apos;s own catalog feed and PayPal Cart API; payments are approved by the shopper on PayPal&apos;s
        page. This bridge is Sherpa&apos;s, not a PayPal product.
      </p>
    </div>
  );
}
