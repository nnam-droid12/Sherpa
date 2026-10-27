export type Severity = "critical" | "high" | "medium" | "low";

export type Finding = {
  code: string;
  category: string;
  severity: Severity;
  title: string;
  evidence: Record<string, unknown> & { screenshot?: string; code?: string; script?: string };
  impact: string;
  fix: string;
};

export type CategoryScore = { score: number; max: number };

export type ShopperSummary = {
  reached_payment: boolean;
  payment_completed: boolean;
  order: { id: string; status: string } | null;
  replay_url: string | null;
  live_view_url: string | null;
  summary: string;
  steps: number;
  model_calls: number;
  seconds: number;
  error: string | null;
};

export type Audit = {
  label: string;
  store_url: string;
  total: number;
  categories: Record<string, CategoryScore>;
  findings: Finding[];
  shoppers: Partial<Record<"desktop" | "mobile", ShopperSummary>>;
  evidence: Record<string, unknown>;
};

export type FixResult = {
  pr_url: string;
  pr_number: number;
  branch: string;
  summary: string;
  files_changed: string[];
  diff: string;
  build_ok: boolean;
  tool_calls: number;
};

export type VerifyResult = {
  preview_url: string;
  audit: Audit;
  order: { id: string; status: string } | null;
  comment_url?: string;
};

export type AgentReady = {
  pr_url?: string;
  catalog_preview?: unknown[];
  endpoints: { method: string; path: string; ok: boolean; detail?: string }[];
  transcript: { role: string; text: string; tool?: string }[];
  order: { id: string; status: string } | null;
};

export type Run = {
  id: string;
  status: string;
  stage?: string;
  store_url: string;
  repo?: string | null;
  demo_store?: string | null;
  created_at: number;
  updated_at: number;
  error?: string | null;
  audit?: Audit;
  fix?: FixResult;
  verify?: VerifyResult;
  agent_ready?: AgentReady;
  usage?: { model_calls: number; browser_minutes: number; steps: number; seconds: number };
};

export type RunEvent = {
  run_id: string;
  seq: number;
  ts: number;
  kind: string;
  phase?: string;
  device?: "desktop" | "mobile";
  step?: number;
  action?: string;
  args?: Record<string, unknown>;
  narration?: string;
  text?: string;
  message?: string;
  url?: string;
  shot_id?: string | null;
  live_view_url?: string | null;
  replay_url?: string | null;
  paypal_visible?: boolean;
  above_fold?: boolean;
  total?: number;
  categories?: Record<string, CategoryScore>;
  [key: string]: unknown;
};

export type DemoStore = {
  id: string;
  name: string;
  tagline: string;
  store_url: string;
  repo: string;
  recent_run_id?: string | null;
};

export const CATEGORY_LABELS: Record<string, string> = {
  presentment: "Presentment",
  payment_options: "Payment options",
  sdk_modernity: "SDK modernity",
  mobile_completion: "Mobile checkout",
  steps_to_pay: "Steps to pay",
  server_correctness: "Server-side correctness",
  agent_readiness: "Agent readiness",
};

export function artifactUrl(id?: string | null) {
  return id ? `/api/agent/artifacts/${id}` : undefined;
}
