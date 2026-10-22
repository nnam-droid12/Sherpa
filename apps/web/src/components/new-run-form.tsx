"use client";

import { useState } from "react";

const field = "rounded-lg border border-border bg-bg px-3 py-2 outline-none transition focus:border-accent";

export function NewRunForm() {
  const [storeUrl, setStoreUrl] = useState("");
  const [repo, setRepo] = useState("");
  const [storeType, setStoreType] = useState("auto");

  return (
    <form
      onSubmit={(e) => e.preventDefault()}
      className="grid gap-4 rounded-2xl border border-border bg-surface p-5 shadow-sm sm:p-6"
    >
      <h2 className="text-lg font-semibold">New run</h2>
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
      <label className="grid gap-1.5 text-sm">
        <span className="text-muted">GitHub repository</span>
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
      <button type="submit" disabled className="rounded-lg bg-accent px-4 py-2.5 font-medium text-accent-fg opacity-60">
        Start audit (coming soon)
      </button>
    </form>
  );
}
