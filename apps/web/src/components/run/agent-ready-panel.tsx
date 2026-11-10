"use client";

import { useEffect, useRef } from "react";
import type { Run, RunEvent } from "@/lib/types";
import { FixWorkspace } from "../fix-workspace";
import { LiveView } from "../live-view";
import { AgentShelf } from "./agent-shelf";
import { McpConnect } from "./mcp-connect";
import type { StageState } from "./mission-bar";

type FeedItem = {
  id?: string;
  title?: string;
  price?: { value?: string; currency_code?: string };
  availability?: string;
  image_url?: string;
};

const METHOD: Record<string, string> = {
  GET: "bg-good/15 text-good",
  POST: "bg-accent/15 text-accent",
  PUT: "bg-warn/15 text-warn",
};

const TONE: Record<string, string> = { good: "bg-good", warn: "bg-warn", bad: "bg-bad" };

function Step({ n, title, sub, children }: { n: number; title: string; sub: string; children: React.ReactNode }) {
  return (
    <section className="grid gap-3">
      <div className="flex items-baseline gap-3">
        <span className="grid size-7 shrink-0 place-items-center rounded-full bg-accent/15 text-xs font-semibold text-accent">{n}</span>
        <div>
          <h3 className="font-semibold">{title}</h3>
          <p className="text-xs text-muted">{sub}</p>
        </div>
      </div>
      <div className="sm:pl-10">{children}</div>
    </section>
  );
}

function Catalog({ event }: { event?: RunEvent }) {
  const items = (event?.items as FeedItem[] | undefined) ?? [];
  if (!event) return <p className="text-sm text-muted">Waiting for the new feed to go live…</p>;
  return (
    <div className="grid gap-2">
      <a href={String(event.url)} target="_blank" rel="noreferrer" className="w-fit font-mono text-xs text-accent hover:underline">
        GET {String(event.url).replace(/^https?:\/\/[^/]+/, "")} · {String(event.count)} products ↗
      </a>
      <div className="flex gap-3 overflow-x-auto pb-1">
        {items.map((it, i) => (
          <div key={it.id ?? i} className="fade-up w-40 shrink-0 overflow-hidden rounded-xl border border-border bg-surface" style={{ animationDelay: `${i * 80}ms` }}>
            {it.image_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={it.image_url} alt="" className="aspect-[4/3] w-full object-cover" />
            )}
            <div className="p-2 text-xs">
              <p className="line-clamp-2 font-medium">{it.title}</p>
              <p className="mt-1 flex justify-between text-muted">
                <span className="font-semibold text-fg">${it.price?.value}</span>
                <span>{it.availability}</span>
              </p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ContractTests({ results, running }: { results: RunEvent[]; running: boolean }) {
  const passed = results.filter((r) => r.ok).length;
  if (!results.length) return <p className="text-sm text-muted">{running ? "Waiting for the preview to redeploy…" : "Not run yet."}</p>;
  return (
    <div className="grid gap-2">
      <p className="text-sm">
        <span className={passed === results.length ? "font-semibold text-good" : "font-semibold text-warn"}>
          {passed}/{results.length} passing
        </span>{" "}
        <span className="text-muted">against the live preview</span>
      </p>
      <ul className="grid gap-1.5">
        {results.map((r) => {
          const method = String(r.method);
          return (
            <li key={r.seq} className="fade-up flex items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2">
              <span className={`w-12 shrink-0 rounded px-1.5 py-0.5 text-center font-mono text-[11px] font-semibold ${METHOD[method] ?? "bg-surface-2"}`}>{method}</span>
              <span className="min-w-0 flex-1 truncate font-mono text-xs">{String(r.path)}</span>
              <span className="hidden truncate text-xs text-muted sm:block">{String(r.detail ?? "")}</span>
              <span className={`grid size-6 shrink-0 place-items-center rounded-full text-xs font-bold ${r.ok ? "bg-good/15 text-good" : "bg-bad/15 text-bad"}`}>
                {r.ok ? "✓" : "✕"}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function Chat({ messages, order, running, hasBrowser, events }: { messages: RunEvent[]; order?: RunEvent; running: boolean; hasBrowser: boolean; events: RunEvent[] }) {
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages.length]);
  if (!messages.length) return <p className="text-sm text-muted">{running ? "The buyer agent starts after the contract tests…" : "Not run yet."}</p>;
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
      <div className="grid max-h-[560px] content-start gap-2 overflow-y-auto rounded-2xl border border-border bg-surface-2/40 p-3" aria-live="polite">
        {messages.map((m) =>
          m.role === "tool" ? (
            <div key={m.seq} className="fade-up flex items-start gap-2 rounded-lg border border-border bg-surface px-3 py-2 text-xs">
              <span className={`mt-1 size-2 shrink-0 rounded-full ${TONE[String(m.tone)] ?? "bg-muted"}`} />
              <span className="min-w-0">
                <span className="block font-mono font-semibold">{String(m.endpoint ?? m.tool)}</span>
                <span className="block text-muted">{m.text}</span>
              </span>
            </div>
          ) : (
            <p
              key={m.seq}
              className={`fade-up max-w-[85%] rounded-2xl px-4 py-2 text-sm ${
                m.role === "user" ? "justify-self-end rounded-br-sm bg-accent text-accent-fg" : "rounded-bl-sm bg-surface"
              }`}
            >
              {m.text}
            </p>
          ),
        )}
        {running && !order && (
          <span className="flex w-fit gap-1 rounded-2xl bg-surface px-4 py-3" aria-label="Agent is working">
            {[0, 1, 2].map((i) => (
              <span key={i} className="size-1.5 animate-bounce rounded-full bg-muted" style={{ animationDelay: `${i * 150}ms` }} />
            ))}
          </span>
        )}
        <div ref={end} />
      </div>
      <div className="grid content-start gap-3">
        {hasBrowser ? (
          <>
            <p className="text-xs text-muted">The shopper approves the PayPal payment in a cloud browser:</p>
            <LiveView events={events} running={running} phase="agent_ready" />
          </>
        ) : (
          <div className="grid place-items-center rounded-2xl border border-dashed border-border p-6 text-center text-sm text-muted">
            When the cart is valid, the PayPal approval opens here in a live cloud browser.
          </div>
        )}
        {order && (
          <div className="fade-up grid gap-2 rounded-2xl bg-gradient-to-br from-[#003087] to-[#0070e0] p-5 text-white shadow-lg">
            <div className="flex items-center justify-between">
              <span className="text-lg font-bold italic">PayPal</span>
              <span className="rounded-full bg-[#3ecf8e] px-3 py-0.5 text-sm font-semibold text-[#06301d]">✓ {String(order.status)}</span>
            </div>
            <p className="font-mono">{String(order.id)}</p>
            <p className="text-sm text-white/80">{String(order.amount ?? "")} · bought by an AI agent through the store&apos;s Cart API</p>
          </div>
        )}
      </div>
    </div>
  );
}

const PREVIEW = [
  ["Catalog feed", "A machine-readable /catalog.json built from the store's real products."],
  ["PayPal Cart API", "POST, GET and PUT /merchant-cart plus /checkout, wired to PayPal Orders, as a second commit on the PR."],
  ["Contract tests", "Every endpoint is tested live against the redeployed preview."],
  ["Agent Shelf", "Live Channel3 market data: what a shopper's agent finds elsewhere, and how this store's prices compare."],
  ["AI buyer agent", "An agent is asked to buy something for a shopper, and checks out through PayPal on its own."],
];

export function AgentReadyPanel({ run, events, state }: { run: Run | null; events: RunEvent[]; state: StageState }) {
  const mine = events.filter((e) => e.phase === "agent_ready");
  const running = state === "running";
  const catalog = [...mine].reverse().find((e) => e.kind === "catalog");
  const contracts = mine.filter((e) => e.kind === "contract");
  const chat = mine.filter((e) => e.kind === "chat");
  const orderEvent = [...mine].reverse().find((e) => e.kind === "order");
  const order = orderEvent ?? (run?.agent_ready?.order ? ({ ...run.agent_ready.order, seq: -1 } as unknown as RunEvent) : undefined);
  const hasBrowser = mine.some((e) => e.kind === "session");
  const hasCode = mine.some((e) => e.kind === "file" || e.kind === "tool");

  return (
    <div className="grid gap-8">
      <p className="rounded-xl bg-surface-2 px-4 py-3 text-sm text-muted">
        In production, PayPal&apos;s Commerce Platform calls these merchant endpoints after Store Sync onboarding. In this sandbox
        build, Sherpa&apos;s AI buyer agent plays that caller so you can watch the full loop.
      </p>

      {state === "todo" && !run?.agent_ready ? (
        <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {PREVIEW.map(([t, d], i) => (
            <li key={t} className="rounded-xl border border-dashed border-border p-4">
              <p className="font-mono text-xs text-accent">0{i + 1}</p>
              <p className="mt-1 font-medium">{t}</p>
              <p className="mt-1 text-xs text-muted">{d}</p>
            </li>
          ))}
        </ol>
      ) : (
        <>
          <Step n={1} title="Agent-ready code" sub="The coding agent writes the catalog feed, Cart API and contract tests, as a second commit on the PR.">
            {hasCode ? <FixWorkspace events={events} phase="agent_ready" /> : <p className="text-sm text-muted">Starting the coding agent…</p>}
          </Step>
          <Step n={2} title="Catalog feed" sub="What AI shopping agents now see when they discover the store.">
            <Catalog event={catalog} />
            {!!run?.agent_ready?.invented_products?.length && (
              <p role="alert" className="mt-3 rounded-xl border border-bad/40 bg-bad/10 px-4 py-3 text-sm text-bad">
                Not in the store&apos;s original code, so possibly invented: {run.agent_ready.invented_products.join(", ")}. Review before merging.
              </p>
            )}
          </Step>
          <Step n={3} title="Agent Shelf" sub="What a shopper's AI agent finds on the open web for the same products, and how this store's prices compare.">
            <AgentShelf run={run} events={events} running={running} />
          </Step>
          <Step n={4} title="Cart API contract tests" sub="Each PayPal Cart API v1 endpoint is called on the live preview.">
            <ContractTests results={contracts} running={running} />
          </Step>
          <Step n={5} title="AI buyer agent" sub="Gemini function calling drives the Cart API; the PayPal Agent Toolkit checks the order.">
            <Chat messages={chat} order={order} running={running} hasBrowser={hasBrowser} events={events} />
          </Step>
          {run?.agent_ready && (
            <Step n={6} title="Connect any AI assistant (MCP)" sub="The store as an MCP server: any MCP-capable assistant can search, fill a cart and pay through PayPal.">
              <McpConnect run={run} />
            </Step>
          )}
        </>
      )}
    </div>
  );
}
