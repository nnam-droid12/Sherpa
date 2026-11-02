"use client";

import { useEffect, useRef } from "react";
import { artifactUrl, type RunEvent } from "@/lib/types";

const ACTION_LABEL: Record<string, string> = {
  click_at: "Click",
  click: "Click",
  double_click: "Double-click",
  type: "Type",
  scroll: "Scroll",
  press_key: "Key",
  hotkey: "Keys",
  wait: "Wait",
  type_text_at: "Type",
  scroll_document: "Scroll",
  scroll_at: "Scroll",
  navigate: "Go to",
  go_back: "Back",
  wait_5_seconds: "Wait",
  key_combination: "Keys",
  hover_at: "Hover",
};

function describe(ev: RunEvent) {
  switch (ev.kind) {
    case "step":
      return ev.narration || `${ACTION_LABEL[ev.action ?? ""] ?? ev.action}`;
    case "sandbox_login":
      return "Signed in to the PayPal sandbox test buyer (credentials masked).";
    case "safety":
      return `Safety check: ${ev.acknowledged ? "confirmed for the sandbox store" : "refused, stopping"}.`;
    case "shopper_done":
      return ev.payment_completed
        ? `Payment completed. Order ${(ev.order as { id: string } | null)?.id ?? ""}`
        : ev.summary
          ? String(ev.summary)
          : "Shopper finished without completing payment.";
    case "narration":
      return ev.text ?? "";
    default:
      return ev.message ?? ev.text ?? "";
  }
}

export function Timeline({ events, device }: { events: RunEvent[]; device?: "desktop" | "mobile" }) {
  const end = useRef<HTMLLIElement>(null);
  const items = events.filter(
    (e) =>
      ["step", "sandbox_login", "safety", "shopper_done", "narration", "warning", "error"].includes(e.kind) &&
      (!device || !e.device || e.device === device),
  );
  useEffect(() => {
    // Braces matter: scrollIntoView returns a Promise in recent browsers, and an effect must not return one.
    end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [items.length]);

  if (!items.length) {
    return <p className="p-4 text-sm text-muted">Waiting for the shopper to start…</p>;
  }
  return (
    <ol className="grid gap-2 p-2" aria-live="polite">
      {items.map((ev) => {
        const shot = artifactUrl(ev.shot_id);
        const tone =
          ev.kind === "error" || ev.kind === "warning"
            ? "border-bad/40"
            : ev.kind === "shopper_done" && ev.payment_completed
              ? "border-good/50"
              : "border-border";
        return (
          <li key={ev.seq} className={`flex gap-3 rounded-lg border bg-surface p-2.5 ${tone}`}>
            {shot ? (
              <a href={shot} target="_blank" rel="noreferrer" className="shrink-0">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={shot} alt="" className="h-14 w-20 rounded object-cover object-top" loading="lazy" />
              </a>
            ) : (
              <span className="grid h-14 w-20 shrink-0 place-items-center rounded bg-surface-2 text-xs text-muted">
                {ev.kind === "sandbox_login" ? "PayPal" : "•"}
              </span>
            )}
            <div className="min-w-0 text-sm">
              <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted">
                {ev.step != null && <span className="font-mono">#{ev.step}</span>}
                {ev.device && <span className="capitalize">{ev.device}</span>}
                {ev.action && <span className="font-mono">{ACTION_LABEL[ev.action] ?? ev.action}</span>}
                {ev.paypal_visible && <span className="text-good">PayPal visible</span>}
              </p>
              <p className="line-clamp-3">{describe(ev)}</p>
            </div>
          </li>
        );
      })}
      <li ref={end} aria-hidden />
    </ol>
  );
}
