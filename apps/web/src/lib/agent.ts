import "server-only";

const AGENT_URL = process.env.SHERPA_AGENT_URL || "http://localhost:8080";
const API_KEY = process.env.SHERPA_API_KEY || "";

/** Server-side fetch to the agent API. Returns null when the agent is unreachable. */
export async function agentGet<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(new URL(`/api/${path}`, AGENT_URL), {
      headers: { "X-Sherpa-Key": API_KEY },
      cache: "no-store",
    });
    return res.ok ? ((await res.json()) as T) : null;
  } catch {
    return null;
  }
}
