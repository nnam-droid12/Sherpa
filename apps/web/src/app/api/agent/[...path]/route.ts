// Server-side proxy to the agent service. The shared API key stays on the server.
import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

const AGENT_URL = process.env.SHERPA_AGENT_URL || "http://localhost:8080";
const API_KEY = process.env.SHERPA_API_KEY || "";

async function forward(req: NextRequest, path: string[]) {
  const target = new URL(`/api/${path.map(encodeURIComponent).join("/")}`, AGENT_URL);
  target.search = req.nextUrl.search;
  const headers: Record<string, string> = { "X-Sherpa-Key": API_KEY };
  const contentType = req.headers.get("content-type");
  if (contentType) headers["Content-Type"] = contentType;
  // The MCP endpoint must validate Origin to stop browser pages from driving it (DNS rebinding).
  const origin = req.headers.get("origin");
  if (origin) headers["Origin"] = origin;
  const forwardedFor = req.headers.get("x-forwarded-for");
  if (forwardedFor) headers["X-Client-Ip"] = forwardedFor.split(",")[0].trim();

  const res = await fetch(target, {
    method: req.method,
    headers,
    body: req.method === "GET" || req.method === "HEAD" ? undefined : await req.text(),
    cache: "no-store",
  });
  const out = new Headers();
  for (const key of ["content-type", "cache-control", "content-disposition"]) {
    const value = res.headers.get(key);
    if (value) out.set(key, value);
  }
  if (out.get("content-type")?.includes("text/event-stream")) {
    out.set("Cache-Control", "no-cache, no-transform");
    out.set("X-Accel-Buffering", "no");
  }
  return new Response(res.body, { status: res.status, headers: out });
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}

export async function POST(req: NextRequest, ctx: Ctx) {
  return forward(req, (await ctx.params).path);
}
