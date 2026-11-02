import Link from "next/link";
import { agentGet } from "@/lib/agent";
import { scoreTone } from "@/lib/score";
import { CATEGORY_LABELS, type DemoStore, type Run } from "@/lib/types";

export const dynamic = "force-dynamic";

const STEPS = [
  {
    n: "01",
    name: "Audit",
    text: "An AI shopper buys from the live store in cloud browsers, on desktop and mobile, while deterministic checks measure the SDK, button placement, Venmo, Pay Later, webhooks and agent readiness.",
  },
  {
    n: "02",
    name: "Fix",
    text: "A Gemini coding agent upgrades the integration to JS SDK v6, moves PayPal above the fold, verifies amounts server-side, signs webhooks, then opens a real pull request.",
  },
  {
    n: "03",
    name: "Verify",
    text: "The PR is deployed to a preview, the same shopper runs again, and a real PayPal sandbox payment is confirmed through the Orders API. The before/after scorecard lands on the PR.",
  },
  {
    n: "04",
    name: "Agent-ready",
    text: "Sherpa adds a catalog feed and PayPal Cart API endpoints, then an AI buyer agent discovers the store and checks out through PayPal on its own.",
  },
];

const WEIGHTS: Record<string, number> = {
  presentment: 20,
  payment_options: 15,
  sdk_modernity: 10,
  mobile_completion: 15,
  steps_to_pay: 10,
  server_correctness: 20,
  agent_readiness: 10,
};

const CHECKS: Record<string, string> = {
  presentment: "Is the PayPal button above the fold on desktop and on a phone?",
  payment_options: "Are PayPal, Venmo and Pay Later messaging offered where they should be?",
  sdk_modernity: "Is the store on JS SDK v6, or the legacy script tag?",
  mobile_completion: "Can a shopper on a 390px screen actually finish paying?",
  steps_to_pay: "Any extra clicks or crashes between the cart and PayPal?",
  server_correctness: "Server-side amounts, verified webhook signatures, graceful errors.",
  agent_readiness: "Catalog feed and PayPal Cart API endpoints for AI shopping agents.",
};

const STACK = [
  "PayPal JS SDK v6",
  "Orders v2",
  "Webhooks",
  "Cart API v1",
  "Agent Toolkit",
  "Gemini 3.8 Flash",
  "Computer use",
  "KERNEL browsers",
  "Cloud Run",
  "Firestore",
];

const FAQ = [
  {
    q: "Is this using real money?",
    a: "No. Sherpa only talks to the PayPal sandbox and refuses to start if it is pointed at live PayPal. Payments are real sandbox transactions you can look up in the Orders API.",
  },
  {
    q: "Does Sherpa merge code on its own?",
    a: "Never. It opens a pull request with a plain-English summary, a technical changelog and audit screenshots. A human reviews and merges.",
  },
  {
    q: "Are scores decided by the AI?",
    a: "No. Scores come from deterministic code and documented weights. Gemini only writes the plain-English explanation of each finding.",
  },
  {
    q: "Is the buyer agent how PayPal's agentic commerce works in production?",
    a: "In production PayPal's Commerce Platform calls the merchant's Cart API after Store Sync onboarding. In this sandbox build, Sherpa's buyer agent plays that caller so you can see the full loop.",
  },
];

function Card({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-border bg-surface ${className}`}>{children}</div>;
}

export default async function Landing() {
  const [demos, runs] = await Promise.all([agentGet<DemoStore[]>("demo-stores"), agentGet<Run[]>("runs?limit=30")]);
  const latest = (runs ?? []).find((r) => r.audit && r.demo_store);
  const audit = latest?.audit;

  return (
    <div className="grid gap-24 pt-10 sm:pt-16">
      {/* Hero */}
      <section className="grid items-center gap-10 lg:grid-cols-[1.15fr_1fr]">
        <div className="grid gap-6">
          <p className="w-fit rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted">
            Built for the PayPal AI Hackathon · sandbox only
          </p>
          <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-6xl">
            The AI integration engineer for <span className="text-accent">PayPal checkout</span>.
          </h1>
          <p className="max-w-xl text-lg text-muted">
            Sherpa shops your store like a real customer, finds what&apos;s costing you PayPal sales, fixes it in a pull
            request, proves the fix with a real sandbox payment, and makes the store ready for AI shopping agents.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link
              href="/dashboard"
              className="rounded-xl bg-accent px-5 py-3 font-medium text-accent-fg shadow-sm transition hover:opacity-90"
            >
              Try it live, no sign-up
            </Link>
            <Link href="#how" className="rounded-xl border border-border px-5 py-3 font-medium transition hover:bg-surface-2">
              See how it works
            </Link>
          </div>
          <ul className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted">
            <li>✓ Real cloud browsers</li>
            <li>✓ Real pull requests</li>
            <li>✓ Real sandbox payments</li>
          </ul>
        </div>

        <Card className="grid gap-4 p-5 shadow-xl shadow-black/5 sm:p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-muted">{audit ? "Latest live audit" : "Live audit"}</p>
              <p className="font-medium">
                {latest
                  ? (demos ?? []).find((d) => d.id === latest.demo_store)?.name ?? latest.store_url
                  : "Ember & Oak"}
              </p>
            </div>
            <div className="text-right">
              <p className="text-4xl font-semibold tabular-nums" style={{ color: audit ? scoreTone(audit.total) : undefined }}>
                {audit ? audit.total : "–"}
                <span className="text-base text-muted">/100</span>
              </p>
              <p className="text-xs text-muted">checkout score</p>
            </div>
          </div>
          <ul className="grid gap-2">
            {(audit?.findings ?? []).slice(0, 5).map((f) => (
              <li key={f.code} className="flex items-start gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm">
                <span
                  className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${
                    f.severity === "critical" ? "bg-bad/15 text-bad" : f.severity === "high" ? "bg-warn/15 text-warn" : "bg-accent/15 text-accent"
                  }`}
                >
                  {f.severity}
                </span>
                <span>{f.title}</span>
              </li>
            ))}
            {!audit && <li className="text-sm text-muted">Run an audit from the dashboard to see findings here.</li>}
          </ul>
          {latest && (
            <Link href={`/runs/${latest.id}`} className="text-sm text-accent hover:underline">
              Open this run, with screenshots and session replays →
            </Link>
          )}
        </Card>
      </section>

      {/* Stack strip */}
      <section aria-label="Built with" className="-mt-10 flex flex-wrap justify-center gap-2">
        {STACK.map((s) => (
          <span key={s} className="rounded-full border border-border px-3 py-1 text-xs text-muted">
            {s}
          </span>
        ))}
      </section>

      {/* Problem */}
      <section className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1">
          <p className="text-xs font-medium uppercase tracking-widest text-accent">The problem</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight">Checkouts quietly leak PayPal sales.</h2>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:col-span-2">
          {[
            ["Buried buttons", "PayPal below the fold, behind an extra click, or hidden by a CSS bug on phones."],
            ["Missing options", "No Venmo for US buyers and no Pay Later messaging on high-value items."],
            ["Legacy integrations", "The old script tag, client-side amounts and unverified webhooks."],
            ["Not agent-ready", "No catalog feed or Cart API, so AI shopping agents can't buy at all."],
          ].map(([t, d]) => (
            <Card key={t} className="p-5">
              <h3 className="font-medium">{t}</h3>
              <p className="mt-1 text-sm text-muted">{d}</p>
            </Card>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="grid scroll-mt-20 gap-8">
        <div className="max-w-2xl">
          <p className="text-xs font-medium uppercase tracking-widest text-accent">How it works</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight">From URL to merged fix, with proof.</h2>
        </div>
        <ol className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s) => (
            <li key={s.n}>
              <Card className="h-full p-5">
                <p className="font-mono text-xs text-accent">{s.n}</p>
                <h3 className="mt-2 text-lg font-semibold">{s.name}</h3>
                <p className="mt-2 text-sm text-muted">{s.text}</p>
              </Card>
            </li>
          ))}
        </ol>
      </section>

      {/* Rubric */}
      <section className="grid gap-8 lg:grid-cols-[1fr_1.4fr]">
        <div>
          <p className="text-xs font-medium uppercase tracking-widest text-accent">The scorecard</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight">Seven checks. Deterministic scores.</h2>
          <p className="mt-3 text-muted">
            Every score comes from code you can read, with published weights. The AI explains the findings in plain
            English, and never decides the number.
          </p>
          <a
            href="https://github.com/nnam-droid12/Sherpa/blob/main/docs/SCORECARD.md"
            className="mt-4 inline-block text-sm text-accent hover:underline"
          >
            Read the rubric →
          </a>
        </div>
        <ul className="grid gap-2">
          {Object.entries(CHECKS).map(([k, v]) => (
            <li key={k} className="grid grid-cols-[1fr_auto] items-center gap-4 rounded-xl border border-border bg-surface px-4 py-3">
              <span>
                <span className="block font-medium">{CATEGORY_LABELS[k]}</span>
                <span className="text-sm text-muted">{v}</span>
              </span>
              <span className="rounded-lg bg-surface-2 px-2.5 py-1 font-mono text-sm tabular-nums">{WEIGHTS[k]} pts</span>
            </li>
          ))}
        </ul>
      </section>

      {/* Demo stores */}
      <section className="grid gap-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="max-w-2xl">
            <p className="text-xs font-medium uppercase tracking-widest text-accent">Try it on a real storefront</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight">Two stores with broken checkouts, on purpose.</h2>
          </div>
          <Link href="/dashboard" className="text-sm text-accent hover:underline">
            Run them from the dashboard →
          </Link>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {(demos ?? []).map((d) => (
            <a
              key={d.id}
              href={d.store_url}
              target="_blank"
              rel="noreferrer"
              className="group overflow-hidden rounded-2xl border border-border bg-surface"
            >
              <div className="aspect-[16/8] overflow-hidden bg-surface-2">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={`${d.store_url}/img/hero.jpg`}
                  alt={`${d.name} storefront`}
                  className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.03]"
                  loading="lazy"
                />
              </div>
              <div className="flex items-center justify-between gap-3 p-4">
                <span>
                  <span className="block font-medium">{d.name}</span>
                  <span className="text-sm text-muted">{d.tagline}</span>
                </span>
                <span className="text-sm text-muted">Visit ↗</span>
              </div>
            </a>
          ))}
        </div>
      </section>

      {/* Agent-ready */}
      <section className="grid items-center gap-8 lg:grid-cols-2">
        <div>
          <p className="text-xs font-medium uppercase tracking-widest text-accent">Agentic commerce</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight">Make any store buyable by AI agents.</h2>
          <p className="mt-3 text-muted">
            Sherpa generates a product catalog feed and the PayPal Cart API endpoints in the store&apos;s own stack, with
            contract tests. Then an AI buyer agent shops the store end to end through PayPal.
          </p>
        </div>
        <Card className="grid gap-3 p-5">
          <p className="w-fit justify-self-end rounded-2xl bg-accent px-4 py-2 text-sm text-accent-fg">
            I need a birthday cake for 12 people delivered Saturday, under $90.
          </p>
          <p className="w-fit rounded-2xl bg-surface-2 px-4 py-2 text-sm">
            Found the Vanilla Bean Celebration Cake, which serves 12 for $78. Which Saturday should it arrive?
          </p>
          <p className="w-fit rounded-xl bg-surface-2 px-3 py-1.5 font-mono text-xs text-muted">
            POST /merchant-cart → validation_status: INVALID (DELIVERY_DATE_PREFERENCE)
          </p>
          <p className="w-fit rounded-2xl bg-surface-2 px-4 py-2 text-sm">
            Delivery date added, PayPal payment approved, order placed.
          </p>
          <p className="text-xs text-muted">Illustrative transcript of the buyer agent flow.</p>
        </Card>
      </section>

      {/* FAQ */}
      <section className="grid gap-6 lg:grid-cols-[1fr_1.4fr]">
        <div>
          <p className="text-xs font-medium uppercase tracking-widest text-accent">Straight answers</p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight">What Sherpa does, and doesn&apos;t, do.</h2>
        </div>
        <div className="grid gap-3">
          {FAQ.map((f) => (
            <details key={f.q} className="group rounded-xl border border-border bg-surface px-4 py-3">
              <summary className="cursor-pointer list-none font-medium">
                {f.q}
                <span className="float-right text-muted transition group-open:rotate-45">+</span>
              </summary>
              <p className="mt-2 text-sm text-muted">{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="rounded-3xl border border-border bg-surface p-8 text-center sm:p-12">
        <h2 className="text-3xl font-semibold tracking-tight">See it fix a checkout in a few minutes.</h2>
        <p className="mx-auto mt-3 max-w-xl text-muted">No sign-up, no setup. Pick a demo store and watch the AI shopper work.</p>
        <Link
          href="/dashboard"
          className="mt-6 inline-block rounded-xl bg-accent px-6 py-3 font-medium text-accent-fg transition hover:opacity-90"
        >
          Open the dashboard
        </Link>
      </section>
    </div>
  );
}
