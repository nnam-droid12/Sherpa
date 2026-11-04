import type { Metadata } from "next";
import { FleetGrid } from "@/components/fleet-grid";
import { agentGet } from "@/lib/agent";
import type { DemoStore } from "@/lib/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Fleet scan · Sherpa" };

export default async function FleetPage() {
  const demos = await agentGet<DemoStore[]>("demo-stores");
  return (
    <div className="grid gap-8 pt-8">
      <header className="grid gap-2">
        <p className="text-xs font-medium uppercase tracking-widest text-accent">Fleet scan · for platforms and agencies</p>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Check PayPal checkout health across many stores.</h1>
        <p className="max-w-2xl text-muted">
          Paste up to 25 store URLs. In seconds Sherpa ranks them by checkout health, worst first, so you know which
          merchants to fix. Open a <strong className="text-fg">deep audit</strong> on any row to send in the AI shoppers.
        </p>
      </header>
      <FleetGrid demos={demos ?? []} />
    </div>
  );
}
