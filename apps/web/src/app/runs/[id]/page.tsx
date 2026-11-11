import { RunView } from "@/components/run-view";
import { agentGet } from "@/lib/agent";
import type { AgentConfig, Run } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [run, config] = await Promise.all([agentGet<Run>(`runs/${encodeURIComponent(id)}`), agentGet<AgentConfig>("config")]);
  return <RunView runId={id} initial={run} limits={config?.limits} />;
}
