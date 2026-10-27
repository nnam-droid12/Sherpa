import { RunView } from "@/components/run-view";
import { agentGet } from "@/lib/agent";
import type { Run } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const run = await agentGet<Run>(`runs/${encodeURIComponent(id)}`);
  return <RunView runId={id} initial={run} />;
}
