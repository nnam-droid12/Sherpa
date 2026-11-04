"use client";

import { useEffect, useMemo, useState } from "react";
import type { Finding } from "@/lib/types";

/**
 * Estimated PayPal revenue at risk from the audit findings.
 * Every number is an editable assumption or a merchant input; nothing here is measured data.
 */

type Inputs = { sessions: number; conversion: number; aov: number; paypalShare: number; mobileShare: number };

const DEFAULT_INPUTS: Inputs = { sessions: 50_000, conversion: 2.5, aov: 120, paypalShare: 30, mobileShare: 60 };

// Share (%) of PayPal checkouts each finding is assumed to lose. `mobile`/`desktop` scale it by traffic mix.
const LOSS: Record<string, { pct: number; scope?: "mobile" | "desktop"; why: string }> = {
  BUTTON_HIDDEN_MOBILE: { pct: 100, scope: "mobile", why: "PayPal can't be used on phones at all" },
  MOBILE_PAYMENT_FAILED: { pct: 50, scope: "mobile", why: "Phone shoppers often can't finish paying" },
  CHECKOUT_CRASH: { pct: 50, why: "Shoppers who leave the optional field empty hit a crash" },
  BUTTON_BELOW_FOLD_DESKTOP: { pct: 10, scope: "desktop", why: "Some shoppers never scroll down to PayPal" },
  BUTTON_BELOW_FOLD_MOBILE: { pct: 10, scope: "mobile", why: "Some phone shoppers never scroll down to PayPal" },
  EXTRA_CLICK: { pct: 5, why: "An extra step before PayPal loses some buyers" },
  NO_VENMO: { pct: 3, why: "Venmo-first buyers leave without their preferred option" },
  NO_PAY_LATER: { pct: 3, why: "Higher-priced items convert better with Pay Later" },
  SDK_LEGACY: { pct: 2, why: "The legacy SDK misses newer eligibility and experiences" },
  BLANK_PAGE_ON_ERROR: { pct: 1, why: "Failed payments end in a blank page with no retry" },
  NO_ERROR_HANDLING: { pct: 1, why: "Payment errors aren't caught, so shoppers get stuck" },
  NO_PAYPAL: { pct: 100, why: "PayPal isn't offered" },
};

const RISK_ONLY: Record<string, string> = {
  AMOUNT_FROM_CLIENT: "Fraud exposure: buyers can change the price in the browser.",
  WEBHOOK_UNVERIFIED: "Forged webhooks could mark orders paid or refunded.",
  WEBHOOK_MISSING: "Captures that fail or reverse after checkout go unnoticed.",
  NO_CATALOG_FEED: "Invisible to AI shopping agents.",
  NO_CART_API: "AI agents can't buy from the store.",
};

const KEY = "sherpa-revenue-inputs";
const money = (n: number) => n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

function NumberField({ label, value, suffix, prefix, onChange }: { label: string; value: number; suffix?: string; prefix?: string; onChange: (v: number) => void }) {
  return (
    <label className="grid gap-1 text-xs">
      <span className="text-muted">{label}</span>
      <span className="flex items-center rounded-lg border border-border bg-bg px-2 focus-within:border-accent">
        {prefix && <span className="text-muted">{prefix}</span>}
        <input
          type="number"
          min={0}
          value={value}
          onChange={(e) => onChange(Math.max(0, Number(e.target.value) || 0))}
          className="w-full bg-transparent py-1.5 text-sm tabular-nums outline-none"
        />
        {suffix && <span className="text-muted">{suffix}</span>}
      </span>
    </label>
  );
}

export function RevenueAtRisk({ findings, after }: { findings: Finding[]; after?: Finding[] }) {
  const [inputs, setInputs] = useState<Inputs>(DEFAULT_INPUTS);
  const [loss, setLoss] = useState<Record<string, number>>(() => Object.fromEntries(Object.entries(LOSS).map(([k, v]) => [k, v.pct])));

  useEffect(() => {
    try {
      const saved = localStorage.getItem(KEY);
      if (saved) setInputs({ ...DEFAULT_INPUTS, ...JSON.parse(saved) });
    } catch {}
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(inputs));
    } catch {}
  }, [inputs]);

  const paypalRevenue = inputs.sessions * (inputs.conversion / 100) * inputs.aov * (inputs.paypalShare / 100);

  const shareLost = (code: string) => {
    const rule = LOSS[code];
    if (!rule) return 0;
    const scope = rule.scope === "mobile" ? inputs.mobileShare / 100 : rule.scope === "desktop" ? 1 - inputs.mobileShare / 100 : 1;
    return Math.min(1, ((loss[code] ?? rule.pct) / 100) * scope);
  };

  // Combine without double counting: the share kept is the product of what each issue leaves.
  const atRisk = (list: Finding[]) => paypalRevenue * (1 - list.reduce((kept, f) => kept * (1 - shareLost(f.code)), 1));

  const rows = useMemo(() => findings.filter((f) => LOSS[f.code]), [findings]);
  const risks = findings.filter((f) => RISK_ONLY[f.code]);
  const before = atRisk(findings);
  const remaining = after ? atRisk(after) : null;

  return (
    <section className="grid gap-4 rounded-2xl border border-border bg-surface-2/40 p-4 sm:p-5" aria-labelledby="rar-title">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h3 id="rar-title" className="font-semibold">
            Estimated PayPal revenue at risk
          </h3>
          <p className="text-xs text-muted">An estimate from your inputs and the assumptions below, not measured data. Edit them to match your store.</p>
        </div>
        <div className="text-right">
          <p className="text-3xl font-semibold tabular-nums text-bad">{money(before)}<span className="text-sm font-normal text-muted"> / month</span></p>
          {remaining != null && (
            <p className="text-sm text-good">
              {money(Math.max(0, before - remaining))} / month recovered after the fix
            </p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <NumberField label="Monthly sessions" value={inputs.sessions} onChange={(v) => setInputs({ ...inputs, sessions: v })} />
        <NumberField label="Conversion rate" value={inputs.conversion} suffix="%" onChange={(v) => setInputs({ ...inputs, conversion: v })} />
        <NumberField label="Average order" value={inputs.aov} prefix="$" onChange={(v) => setInputs({ ...inputs, aov: v })} />
        <NumberField label="PayPal share of orders" value={inputs.paypalShare} suffix="%" onChange={(v) => setInputs({ ...inputs, paypalShare: v })} />
        <NumberField label="Mobile share of traffic" value={inputs.mobileShare} suffix="%" onChange={(v) => setInputs({ ...inputs, mobileShare: v })} />
      </div>
      <p className="text-xs text-muted">PayPal revenue at these inputs: {money(paypalRevenue)} / month.</p>

      {rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th className="py-1.5 pr-3 font-normal">Finding</th>
                <th className="py-1.5 pr-3 font-normal">Assumed share of affected PayPal checkouts lost</th>
                <th className="py-1.5 text-right font-normal">Est. / month</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((f) => (
                <tr key={f.code} className="border-t border-border">
                  <td className="py-2 pr-3">
                    <span className="block">{f.title}</span>
                    <span className="text-xs text-muted">
                      {LOSS[f.code].why}
                      {LOSS[f.code].scope ? ` (${LOSS[f.code].scope} traffic only)` : ""}
                    </span>
                  </td>
                  <td className="py-2 pr-3">
                    <span className="inline-flex items-center rounded-md border border-border bg-bg px-2">
                      <input
                        type="number"
                        min={0}
                        max={100}
                        aria-label={`Assumed loss for ${f.title}`}
                        value={loss[f.code] ?? LOSS[f.code].pct}
                        onChange={(e) => setLoss({ ...loss, [f.code]: Math.min(100, Math.max(0, Number(e.target.value) || 0)) })}
                        className="w-14 bg-transparent py-1 text-sm tabular-nums outline-none"
                      />
                      <span className="text-muted">%</span>
                    </span>
                  </td>
                  <td className="py-2 text-right tabular-nums">{money(paypalRevenue * shareLost(f.code))}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-2 text-xs text-muted">Issues overlap, so the total combines them without double counting rather than adding the rows.</p>
        </div>
      )}

      {risks.length > 0 && (
        <ul className="grid gap-1 text-sm">
          {risks.map((f) => (
            <li key={f.code} className="flex gap-2">
              <span className="text-warn">⚠</span>
              <span>
                <span className="font-medium">{f.title}.</span> <span className="text-muted">{RISK_ONLY[f.code]} Not priced here.</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
