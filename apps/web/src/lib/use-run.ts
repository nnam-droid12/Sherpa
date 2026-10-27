"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Run, RunEvent } from "./types";

/** Subscribes to a run's server-sent events; reconnects automatically. */
export function useRun(runId: string, initial?: Run | null) {
  const [run, setRun] = useState<Run | null>(initial ?? null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const seen = useRef(new Set<number>());

  useEffect(() => {
    seen.current = new Set();
    setEvents([]);
    const es = new EventSource(`/api/agent/runs/${runId}/events`);
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.addEventListener("event", (e) => {
      const ev = JSON.parse((e as MessageEvent).data) as RunEvent;
      if (seen.current.has(ev.seq)) return;
      seen.current.add(ev.seq);
      setEvents((prev) => [...prev, ev]);
    });
    es.addEventListener("run", (e) => setRun(JSON.parse((e as MessageEvent).data) as Run));
    return () => es.close();
  }, [runId]);

  const action = useCallback(
    async (stage: string, body: Record<string, unknown> = {}) => {
      const res = await fetch(`/api/agent/runs/${runId}/${stage}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail || `Request failed (${res.status})`);
      }
      setRun((await res.json()) as Run);
    },
    [runId],
  );

  return { run, events, connected, action };
}
