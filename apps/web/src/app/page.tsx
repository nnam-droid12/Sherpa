import { NewRunForm } from "@/components/new-run-form";

const steps = [
  { name: "Audit", text: "An AI shopper buys from your live store on desktop and mobile, recording every step." },
  { name: "Fix", text: "A coding agent upgrades your PayPal integration and opens a pull request." },
  { name: "Verify", text: "Sherpa deploys a preview, re-runs the shopper and completes a real sandbox payment." },
  { name: "Agent-ready", text: "It adds a catalog feed and Cart API so AI buyer agents can purchase through PayPal." },
];

export default function Home() {
  return (
    <div className="grid gap-12 pt-12 lg:grid-cols-[1.2fr_1fr] lg:items-start">
      <section className="grid gap-6">
        <p className="w-fit rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted">
          PayPal sandbox · Gemini computer use
        </p>
        <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
          Your AI integration engineer for PayPal checkout.
        </h1>
        <p className="max-w-xl text-lg text-muted">
          Paste a store URL and repo. Sherpa audits the checkout like a real shopper, fixes what it finds in a pull
          request, and proves the fix with a real sandbox payment.
        </p>
        <ol className="grid gap-3 sm:grid-cols-2">
          {steps.map((s, i) => (
            <li key={s.name} className="rounded-xl border border-border bg-surface p-4">
              <p className="font-mono text-xs text-muted">0{i + 1}</p>
              <p className="font-medium">{s.name}</p>
              <p className="mt-1 text-sm text-muted">{s.text}</p>
            </li>
          ))}
        </ol>
      </section>
      <NewRunForm />
    </div>
  );
}
