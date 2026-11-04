"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { Run } from "@/lib/types";

const field = "rounded-lg border border-border bg-bg px-3 py-2 outline-none transition focus:border-accent";

function detectType(repo: string, url: string) {
  if (/next/i.test(repo + url)) return "nextjs";
  return "static-express";
}

/** Audit any store: only the URL is required; a repo enables the fix and verify stages. */
export function NewRunForm() {
  const router = useRouter();
  const [storeUrl, setStoreUrl] = useState("");
  const [repo, setRepo] = useState("");
  const [storeType, setStoreType] = useState("auto");
  const [autopilot, setAutopilot] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

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
          autopilot: autopilot && !!repo,
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
    <form onSubmit={submit} className="grid gap-4 rounded-2xl border border-border bg-surface p-5 sm:p-6">
      <div>
        <h2 className="text-lg font-semibold">Audit your own store</h2>
        <p className="text-sm text-muted">
          The audit only needs a URL. Add a GitHub repo to unlock Fix and Verify (Sherpa needs push access to open a PR).
        </p>
      </div>
      <label className="grid gap-1.5 text-sm">
        <span className="text-muted">Store URL</span>
        <input
          required
          type="url"
          value={storeUrl}
          onChange={(e) => setStoreUrl(e.target.value)}
          placeholder="https://your-store.example"
          className={field}
        />
      </label>
      <div className="grid gap-4 sm:grid-cols-[1fr_200px]">
        <label className="grid gap-1.5 text-sm">
          <span className="text-muted">GitHub repository (optional)</span>
          <input value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="owner/repo" className={field} />
        </label>
        <label className="grid gap-1.5 text-sm">
          <span className="text-muted">Store type</span>
          <select value={storeType} onChange={(e) => setStoreType(e.target.value)} className={field}>
            <option value="auto">Auto-detect</option>
            <option value="static-express">HTML/JS + Express</option>
            <option value="nextjs">Next.js</option>
          </select>
        </label>
      </div>
      <label className="flex items-start gap-2 text-sm">
        <input
          type="checkbox"
          checked={autopilot}
          disabled={!repo}
          onChange={(e) => setAutopilot(e.target.checked)}
          className="mt-0.5 size-4 accent-[var(--accent)]"
        />
        <span>
          <span className="font-medium">⚡ Autopilot</span>{" "}
          <span className="text-muted">run Fix, Verify and Agent-ready automatically after the audit (needs a repo)</span>
        </span>
      </label>
      {error && (
        <p role="alert" className="text-sm text-bad">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={busy}
        className="w-fit rounded-lg bg-accent px-5 py-2.5 font-medium text-accent-fg transition hover:opacity-90 disabled:opacity-60"
      >
        {busy ? "Starting…" : "Start audit"}
      </button>
      <p className="text-xs text-muted">PayPal sandbox only. Runs use cloud browsers and are limited per visitor.</p>
    </form>
  );
}
