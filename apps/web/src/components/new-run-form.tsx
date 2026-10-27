"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import type { DemoStore, Run } from "@/lib/types";

const field = "rounded-lg border border-border bg-bg px-3 py-2 outline-none transition focus:border-accent";

function detectType(repo: string, url: string) {
  if (/bakehouse|next/i.test(repo + url)) return "nextjs";
  if (repo || url) return "static-express";
  return "auto";
}

export function NewRunForm() {
  const router = useRouter();
  const [storeUrl, setStoreUrl] = useState("");
  const [repo, setRepo] = useState("");
  const [storeType, setStoreType] = useState("auto");
  const [demoStore, setDemoStore] = useState<string | null>(null);
  const [demos, setDemos] = useState<DemoStore[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/agent/demo-stores")
      .then((r) => (r.ok ? r.json() : []))
      .then(setDemos)
      .catch(() => setDemos([]));
  }, []);

  function pickDemo(d: DemoStore) {
    setStoreUrl(d.store_url);
    setRepo(d.repo);
    setDemoStore(d.id);
    setStoreType(d.id === "lumen-bakehouse" ? "nextjs" : "static-express");
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await fetch("/api/agent/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          store_url: storeUrl,
          repo: repo || null,
          store_type: storeType === "auto" ? detectType(repo, storeUrl) : storeType,
          demo_store: demoStore,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : `Could not start the run (${res.status})`);
      router.push(`/runs/${(data as Run).id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="grid gap-4 rounded-2xl border border-border bg-surface p-5 shadow-sm sm:p-6">
      <h2 className="text-lg font-semibold">New run</h2>
      {demos.length > 0 && (
        <div className="grid gap-2">
          <p className="text-sm text-muted">Try it on a demo store</p>
          <div className="grid gap-2 sm:grid-cols-2">
            {demos.map((d) => (
              <button
                key={d.id}
                type="button"
                onClick={() => pickDemo(d)}
                aria-pressed={demoStore === d.id}
                className={`rounded-xl border px-3 py-2.5 text-left transition hover:border-accent ${
                  demoStore === d.id ? "border-accent bg-accent/10" : "border-border"
                }`}
              >
                <span className="block text-sm font-medium">Use {d.name}</span>
                <span className="block text-xs text-muted">{d.tagline}</span>
              </button>
            ))}
          </div>
        </div>
      )}
      <label className="grid gap-1.5 text-sm">
        <span className="text-muted">Store URL</span>
        <input
          required
          type="url"
          value={storeUrl}
          onChange={(e) => {
            setStoreUrl(e.target.value);
            setDemoStore(null);
          }}
          placeholder="https://your-store.example"
          className={field}
        />
      </label>
      <label className="grid gap-1.5 text-sm">
        <span className="text-muted">GitHub repository</span>
        <input
          value={repo}
          onChange={(e) => {
            setRepo(e.target.value);
            setDemoStore(null);
          }}
          placeholder="owner/repo"
          className={field}
        />
      </label>
      <label className="grid gap-1.5 text-sm">
        <span className="text-muted">Store type</span>
        <select value={storeType} onChange={(e) => setStoreType(e.target.value)} className={field}>
          <option value="auto">Auto-detect</option>
          <option value="static-express">HTML/JS + Express</option>
          <option value="nextjs">Next.js</option>
        </select>
      </label>
      {error && (
        <p role="alert" className="text-sm text-bad">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={busy}
        className="rounded-lg bg-accent px-4 py-2.5 font-medium text-accent-fg transition hover:opacity-90 disabled:opacity-60"
      >
        {busy ? "Starting…" : "Start audit"}
      </button>
      <p className="text-xs text-muted">PayPal sandbox only. Runs use cloud browsers and are rate limited.</p>
    </form>
  );
}
