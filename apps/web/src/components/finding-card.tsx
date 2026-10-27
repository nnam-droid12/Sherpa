import { artifactUrl, CATEGORY_LABELS, type Finding } from "@/lib/types";

const SEVERITY_STYLE: Record<string, string> = {
  critical: "bg-bad/15 text-bad",
  high: "bg-warn/15 text-warn",
  medium: "bg-accent/15 text-accent",
  low: "bg-surface-2 text-muted",
};

export function FindingCard({ finding }: { finding: Finding }) {
  const shot = artifactUrl(finding.evidence.screenshot as string | undefined);
  const code = (finding.evidence.code || finding.evidence.script) as string | undefined;
  return (
    <article className="grid gap-3 rounded-xl border border-border bg-surface p-4 sm:grid-cols-[1fr_auto]">
      <div className="grid gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${SEVERITY_STYLE[finding.severity]}`}>
            {finding.severity}
          </span>
          <span className="text-xs text-muted">{CATEGORY_LABELS[finding.category] ?? finding.category}</span>
        </div>
        <h4 className="font-medium">{finding.title}</h4>
        {finding.impact && (
          <p className="text-sm">
            <span className="text-muted">Impact: </span>
            {finding.impact}
          </p>
        )}
        {finding.fix && (
          <p className="text-sm">
            <span className="text-muted">Fix: </span>
            {finding.fix}
          </p>
        )}
        {code && <code className="w-fit max-w-full truncate rounded bg-surface-2 px-2 py-1 font-mono text-xs">{code}</code>}
      </div>
      {shot && (
        <a href={shot} target="_blank" rel="noreferrer" className="block sm:w-40">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={shot} alt={`Evidence for: ${finding.title}`} className="w-full rounded-lg border border-border" loading="lazy" />
        </a>
      )}
    </article>
  );
}
