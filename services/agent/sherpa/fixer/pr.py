"""Pull request text written for the merchant first and the reviewer second."""

from __future__ import annotations

from typing import Any

from sherpa.audit.rubric import CATEGORY_LABELS
from sherpa.store.artifacts import public_url

SEVERITY_ICON = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}


def pr_body(audit: dict[str, Any], outcome: Any, store_url: str) -> str:
    findings = audit.get("findings", [])
    lines = [
        "## What this changes for your shoppers",
        "",
        outcome.summary.strip() or "Upgrades the PayPal checkout integration.",
        "",
        f"Sherpa audited **{store_url}** with an AI shopper on desktop and mobile. "
        f"The checkout scored **{audit.get('total', '?')}/100** before this change.",
        "",
        "## Findings addressed",
        "",
        "| Severity | Finding | What changed |",
        "|---|---|---|",
    ]
    changes = {str(c.get("finding", "")).upper(): c for c in outcome.changes}
    for f in findings:
        change = changes.get(f["code"]) or next(
            (c for c in outcome.changes if f["code"].lower() in str(c.get("finding", "")).lower()), None
        )
        what = change.get("change", "") if change else f.get("fix", "")
        lines.append(f"| {SEVERITY_ICON.get(f['severity'], '')} {f['severity']} | {f['title']} | {what} |")
    lines += ["", "## Technical changelog", ""]
    for c in outcome.changes:
        files = ", ".join(f"`{p}`" for p in c.get("files", []) or [])
        lines.append(
            f"- **{c.get('finding', '')}**: {c.get('change', '')}" + (f" ({files})" if files else "")
        )
    if outcome.files_changed:
        lines += ["", "<details><summary>Files changed</summary>", ""]
        lines += [f"- `{p}`" for p in outcome.files_changed]
        lines += ["", "</details>"]

    shots = [(f["title"], f.get("evidence", {}).get("screenshot")) for f in findings]
    shots = [(t, s) for t, s in shots if s][:4]
    if shots:
        lines += ["", "## Evidence from the audit", ""]
        for title, shot in shots:
            lines.append(f'**{title}**<br><img src="{public_url(shot)}" width="360" alt="{title}">')
            lines.append("")

    cats = audit.get("categories", {})
    if cats:
        lines += ["", "<details><summary>Scorecard before this change</summary>", ""]
        lines += ["| Category | Score |", "|---|---|"]
        lines += [f"| {CATEGORY_LABELS.get(k, k)} | {v['score']}/{v['max']} |" for k, v in cats.items()]
        lines += ["", "</details>"]

    lines += [
        "",
        "## How this was checked",
        "",
        "- The build passes (`npm run build`).",
        "- Sherpa will deploy this branch to a preview, re-run the shopper on desktop and mobile, and complete a "
        "PayPal sandbox payment. The before/after scorecard is posted as a comment.",
        "",
        "All PayPal calls use the sandbox. Opened by Sherpa.",
    ]
    return "\n".join(lines)


def scorecard_comment(
    before: dict[str, Any],
    after: dict[str, Any],
    preview_url: str,
    order: dict | None,
    attacks: list[dict] | None = None,
) -> str:
    lines = [
        "## Sherpa verification",
        "",
        f"Preview: {preview_url}",
        "",
        f"**Score: {before.get('total')} → {after.get('total')}**",
        "",
        "| Category | Before | After |",
        "|---|---|---|",
    ]
    for k, v in after.get("categories", {}).items():
        b = before.get("categories", {}).get(k, {})
        lines.append(
            f"| {CATEGORY_LABELS.get(k, k)} | {b.get('score', '–')}/{v['max']} | {v['score']}/{v['max']} |"
        )
    for device in ("desktop", "mobile"):
        s = after.get("shoppers", {}).get(device)
        if s:
            status = (
                "completed a sandbox payment" if s.get("payment_completed") else "did not complete payment"
            )
            replay = f" ([replay]({s['replay_url']}))" if s.get("replay_url") else ""
            lines.append(f"- {device.title()} shopper {status}{replay}.")
    if order:
        lines.append(f"- Sandbox order `{order['id']}`: **{order['status']}** (checked with the Orders API).")
    if attacks:
        lines += ["", "### Attack replay", "", "| Attack | Before | After |", "|---|---|---|"]
        for a in attacks:
            lines.append(f"| {a['title']} | {a['before']['detail']} | {a['after']['detail']} |")
    remaining = after.get("findings", [])
    if remaining:
        lines += ["", "Still open:"] + [f"- {f['severity']}: {f['title']}" for f in remaining]
    lines += ["", "Opened by Sherpa."]
    return "\n".join(lines)
