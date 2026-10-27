"use client";

import { useEffect, useState } from "react";
import { scoreTone } from "@/lib/score";

export function ScoreDial({
  score,
  size = 148,
  label = "Checkout score",
  pending = false,
}: {
  score: number | null;
  size?: number;
  label?: string;
  pending?: boolean;
}) {
  const [shown, setShown] = useState(0);
  useEffect(() => {
    if (score == null) return;
    const id = requestAnimationFrame(() => setShown(score));
    return () => cancelAnimationFrame(id);
  }, [score]);

  const stroke = 12;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const value = score == null ? 0 : shown;
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${label}: ${score ?? "pending"} out of 100`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-2)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={score == null ? "var(--border)" : scoreTone(score)}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c - (c * value) / 100}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{ transition: "stroke-dashoffset 1.2s cubic-bezier(.2,.8,.2,1), stroke .4s" }}
          className={pending ? "animate-pulse" : ""}
        />
      </svg>
      <div className="absolute text-center">
        <div className="text-4xl font-semibold tabular-nums">{score ?? "–"}</div>
        <div className="text-xs text-muted">{label}</div>
      </div>
    </div>
  );
}
