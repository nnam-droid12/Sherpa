"use client";

import { useMemo, useState } from "react";
import { artifactUrl, type RunEvent } from "@/lib/types";
import { Timeline } from "./timeline";

type Device = "desktop" | "mobile";

export function LiveView({ events, running, phase }: { events: RunEvent[]; running: boolean; phase: string }) {
  const [device, setDevice] = useState<Device>("desktop");
  const phaseEvents = useMemo(() => events.filter((e) => e.phase === phase), [events, phase]);

  const info = useMemo(() => {
    const byDevice: Record<Device, { live?: string; replay?: string; shot?: string; done: boolean }> = {
      desktop: { done: false },
      mobile: { done: false },
    };
    for (const e of phaseEvents) {
      if (!e.device) continue;
      const d = byDevice[e.device];
      if (e.kind === "session") {
        d.live = e.live_view_url ?? undefined;
        d.replay = e.replay_url ?? d.replay;
      }
      if (e.shot_id) d.shot = e.shot_id;
      if (e.kind === "shopper_done") {
        d.done = true;
        d.replay = (e.replay_url as string) ?? d.replay;
      }
    }
    return byDevice;
  }, [phaseEvents]);

  const current = info[device];
  const showLive = running && current.live && !current.done;
  const frame = device === "mobile" ? "mx-auto aspect-[390/844] max-h-[640px]" : "aspect-[1440/900] w-full";

  return (
    <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
      <section className="grid content-start gap-3 rounded-2xl border border-border bg-surface p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div role="tablist" aria-label="Device" className="flex rounded-lg bg-surface-2 p-1 text-sm">
            {(["desktop", "mobile"] as Device[]).map((d) => (
              <button
                key={d}
                role="tab"
                aria-selected={device === d}
                onClick={() => setDevice(d)}
                className={`rounded-md px-3 py-1 capitalize transition ${device === d ? "bg-surface shadow-sm" : "text-muted hover:text-fg"}`}
              >
                {d}
                {info[d].done && <span className="ml-1 text-good">✓</span>}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-3 text-xs text-muted">
            {showLive && (
              <span className="flex items-center gap-1.5">
                <span className="size-2 animate-pulse rounded-full bg-bad" aria-hidden /> Live
              </span>
            )}
            {current.replay && (
              <a href={current.replay} target="_blank" rel="noreferrer" className="underline hover:text-fg">
                Session replay
              </a>
            )}
          </div>
        </div>
        <div className={`overflow-hidden rounded-xl border border-border bg-bg ${frame}`}>
          {showLive ? (
            <iframe
              src={current.live}
              title={`Live ${device} browser`}
              className="h-full w-full"
              allow="clipboard-read; clipboard-write"
            />
          ) : current.shot ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={artifactUrl(current.shot)} alt={`Latest ${device} screenshot`} className="h-full w-full object-contain object-top" />
          ) : (
            <div className="grid h-full min-h-48 place-items-center p-6 text-center text-sm text-muted">
              {running ? "Starting a cloud browser…" : "No session recorded for this device."}
            </div>
          )}
        </div>
      </section>
      <section className="max-h-[640px] overflow-y-auto rounded-2xl border border-border bg-surface-2/50">
        <h3 className="sticky top-0 z-10 border-b border-border bg-surface px-4 py-2.5 text-sm font-medium">Shopper timeline</h3>
        <Timeline events={phaseEvents} device={device} />
      </section>
    </div>
  );
}
