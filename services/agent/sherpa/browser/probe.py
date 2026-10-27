"""Deterministic in-page measurements taken alongside the visual shopper."""

from __future__ import annotations

from typing import Any

from playwright.async_api import Page

# Finds the first PayPal payment surface (v5 iframe, v6 web component or a container) and
# reports whether a person could actually see it, and where it sits relative to the fold.
_PROBE_JS = r"""
() => {
  const sel = [
    'iframe[src*="paypal.com"]', 'iframe[name^="__zoid__paypal"]', 'paypal-button', 'venmo-button',
    'paypal-pay-later-button', '[data-funding-source="paypal"]', '#paypal-button-container',
    '[id*="paypal-button"]', '[class*="paypal-button"]'
  ];
  const nodes = [];
  for (const s of sel) document.querySelectorAll(s).forEach(n => nodes.includes(n) || nodes.push(n));
  const clipped = (el) => {
    for (let n = el; n && n !== document.documentElement; n = n.parentElement) {
      const cs = getComputedStyle(n);
      if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) === 0) return true;
      const r = n.getBoundingClientRect();
      if ((cs.overflow !== 'visible' || cs.overflowY !== 'visible') && (r.height < 8 || r.width < 8)) return true;
    }
    return false;
  };
  const vh = window.innerHeight;
  const out = [];
  for (const n of nodes) {
    const r = n.getBoundingClientRect();
    if (r.width === 0 && r.height === 0 && n.tagName !== 'PAYPAL-BUTTON') continue;
    out.push({
      tag: n.tagName.toLowerCase(), id: n.id || null,
      doc_top: Math.round(r.top + window.scrollY), height: Math.round(r.height),
      visible: !clipped(n) && r.height >= 8,
    });
  }
  const text = (document.body && document.body.innerText || '').slice(0, 4000);
  return {
    url: location.href, viewport_height: vh, scroll_y: Math.round(window.scrollY),
    doc_height: document.documentElement.scrollHeight, candidates: out,
    crashed: /Application error|client-side exception|Unhandled Runtime Error/i.test(text),
    blank: text.trim().length === 0,
    payment_gate: [...document.querySelectorAll('button, a, [role="button"]')].some(e =>
      /choose (a )?payment|select (a )?payment|show payment/i.test(e.innerText || '') && e.getBoundingClientRect().height > 0),
    pay_later_message: !!document.querySelector('[data-pp-message], paypal-message, paypal-messages, .paypal-message'),
  };
}
"""


async def probe_page(page: Page) -> dict[str, Any]:
    try:
        data = await page.evaluate(_PROBE_JS)
    except Exception as exc:  # page navigating or closed
        return {"error": str(exc)}
    visible = [c for c in data["candidates"] if c["visible"]]
    data["paypal_present"] = bool(data["candidates"])
    data["paypal_visible"] = bool(visible)
    data["above_fold"] = bool(visible) and min(c["doc_top"] for c in visible) < data["viewport_height"]
    return data
