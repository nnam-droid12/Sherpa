import { CATEGORY_LABELS, type CategoryScore } from "@/lib/types";
import { scoreTone } from "@/lib/score";

export function CategoryBars({
  categories,
  compare,
}: {
  categories: Record<string, CategoryScore>;
  compare?: Record<string, CategoryScore>;
}) {
  return (
    <ul className="grid gap-3">
      {Object.entries(categories).map(([key, c]) => {
        const pct = Math.round((c.score / c.max) * 100);
        const before = compare?.[key];
        return (
          <li key={key} className="grid gap-1">
            <div className="flex items-baseline justify-between text-sm">
              <span>{CATEGORY_LABELS[key] ?? key}</span>
              <span className="tabular-nums text-muted">
                {before && <span className="mr-2 line-through opacity-70">{before.score}</span>}
                {c.score}/{c.max}
              </span>
            </div>
            <div className="relative h-2 overflow-hidden rounded-full bg-surface-2">
              {before && (
                <div
                  className="absolute inset-y-0 left-0 rounded-full bg-border"
                  style={{ width: `${Math.round((before.score / before.max) * 100)}%` }}
                />
              )}
              <div
                className="absolute inset-y-0 left-0 rounded-full transition-[width] duration-1000 ease-out"
                style={{ width: `${pct}%`, background: scoreTone(pct) }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
