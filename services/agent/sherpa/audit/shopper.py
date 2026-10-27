"""Gemini computer-use shopper that buys from a live store in a KERNEL cloud browser."""

from __future__ import annotations

import asyncio
import io
import logging
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse

from google.genai import types
from PIL import Image
from playwright.async_api import Page

from sherpa.browser.probe import probe_page
from sherpa.browser.session import BrowserSession, Device, host_allowed, open_session
from sherpa.config import get_settings
from sherpa.llm import generate
from sherpa.paypal.client import PayPalClient, order_completed

log = logging.getLogger(__name__)

Emit = Callable[..., Awaitable[Any]]

GOAL = (
    "You are a careful first-time shopper. Find a product priced above $200, add it to the cart, proceed to "
    "checkout and pay with PayPal using the sandbox buyer account. Narrate what you see at each step, especially "
    "where payment options appear, whether PayPal, Venmo or Pay Later are offered, and anything confusing or broken."
)
RULES = (
    "Rules: Stay on this store and PayPal pages. Fill any required checkout form with realistic test details "
    "(name Alex Rivera, 500 Market St, San Francisco, 94105, a delivery date at least a week from today) and leave "
    "optional fields empty. If a PayPal login page appears, do not type credentials; wait one step, the test "
    "account is signed in for you. In the PayPal window, choose the default funding and click the button that "
    "completes the payment. If the page is blank, broken or you cannot find a way to pay after a few attempts, say "
    "so clearly and stop. When you are done, give a one-paragraph summary starting with SUMMARY:."
)

ORDER_ID_RE = re.compile(r"^[A-Z0-9]{17}$")
KEEP_SCREENSHOT_TURNS = 3


@dataclass
class Step:
    n: int
    action: str
    args: dict[str, Any]
    narration: str
    url: str
    probe: dict[str, Any]
    shot_id: str | None = None


@dataclass
class ShopperResult:
    device: Device
    reached_payment: bool = False
    payment_completed: bool = False
    order_ids: list[str] = field(default_factory=list)
    completed_order: dict[str, Any] | None = None
    steps: list[Step] = field(default_factory=list)
    probes: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    live_view_url: str | None = None
    replay_url: str | None = None
    blocked: list[str] = field(default_factory=list)
    crashed: bool = False
    blank_page: bool = False
    clicks_after_checkout: int | None = None
    error: str | None = None
    model_calls: int = 0
    seconds: float = 0.0


def _px(v: Any, size: int) -> int:
    return max(0, min(size - 1, int(float(v) / 1000 * size)))


def _jpeg(png: bytes, width: int = 480) -> bytes:
    img = Image.open(io.BytesIO(png)).convert("RGB")
    img.thumbnail((width, width * 3))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=60)
    return out.getvalue()


class _Browser:
    """Tracks the active page (PayPal opens a popup) and order ids seen on the wire."""

    def __init__(self, session: BrowserSession, store_host: str) -> None:
        self.session = session
        self.main = session.page
        self.page: Page = session.page
        self.store_host = store_host
        self.order_ids: list[str] = []
        session.context.on("page", self._on_page)
        session.context.on("response", self._on_response)

    def _on_page(self, page: Page) -> None:
        self.page = page
        page.on("close", lambda _p: setattr(self, "page", self.main))

    def _remember(self, value: Any) -> None:
        if isinstance(value, str) and ORDER_ID_RE.match(value) and value not in self.order_ids:
            self.order_ids.append(value)

    def _on_response(self, response) -> None:
        url = response.url
        for token in parse_qs(urlparse(url).query).get("token", []):
            self._remember(token)
        host = urlparse(url).hostname or ""
        if host == self.store_host and re.search(r"order|checkout|capture|cart", url, re.I):
            asyncio.ensure_future(self._read_json(response))

    async def _read_json(self, response) -> None:
        try:
            data = await response.json()
        except Exception:
            return
        if isinstance(data, dict):
            for key in ("id", "orderId", "orderID", "order_id"):
                self._remember(data.get(key))

    @property
    def size(self) -> tuple[int, int]:
        vp = self.page.viewport_size or {
            "width": self.session.device.width,
            "height": self.session.device.height,
        }
        return vp["width"], vp["height"]


async def _sandbox_login(page: Page, email: str, password: str) -> bool:
    """Sign the sandbox test buyer in on PayPal's login page. Values are never logged."""
    if not (urlparse(page.url).hostname or "").endswith("paypal.com") or not email:
        return False
    did = False
    try:
        email_box = page.locator("#email, input[name='login_email']").first
        if await email_box.is_visible(timeout=500) and not await email_box.input_value():
            await email_box.fill(email)
            nxt = page.locator("#btnNext")
            if await nxt.is_visible(timeout=500):
                await nxt.click()
                await page.wait_for_timeout(1500)
            did = True
        pwd = page.locator("#password, input[name='login_password']").first
        if await pwd.is_visible(timeout=1500) and not await pwd.input_value():
            await pwd.fill(password)
            await page.locator("#btnLogin, button[type='submit']").first.click()
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
            did = True
    except Exception:
        log.debug("sandbox login step skipped", exc_info=True)
    return did


async def _screenshot(page: Page) -> bytes:
    mask = [page.locator("#email, #password, input[type='password'], input[name='login_email']")]
    return await page.screenshot(type="png", mask=mask, animations="disabled")


async def _execute(
    b: _Browser, name: str, args: dict[str, Any], allowed_hosts: set[str], store_url: str
) -> str | None:
    """Run one computer-use action; returns an error string the model should see, if any."""
    page = b.page
    w, h = b.size
    key_map = {
        "control": "Control",
        "ctrl": "Control",
        "enter": "Enter",
        "shift": "Shift",
        "alt": "Alt",
        "meta": "Meta",
        "cmd": "Meta",
        "command": "Meta",
        "tab": "Tab",
        "escape": "Escape",
        "esc": "Escape",
        "backspace": "Backspace",
        "pagedown": "PageDown",
        "pageup": "PageUp",
        "space": " ",
    }

    def norm_keys(keys: Any) -> str:
        parts = keys if isinstance(keys, list) else str(keys).split("+")
        return "+".join(key_map.get(p.strip().lower(), p.strip()) for p in parts)

    if name in ("open_web_browser", "take_screenshot"):
        return None
    if name in ("wait_5_seconds", "wait"):
        await asyncio.sleep(float(args.get("seconds", 5)) if name == "wait" else 5)
    elif name == "go_back":
        await page.go_back(wait_until="domcontentloaded", timeout=20000)
    elif name == "go_forward":
        await page.go_forward(wait_until="domcontentloaded", timeout=20000)
    elif name == "search":
        await page.goto(store_url, wait_until="domcontentloaded", timeout=20000)
    elif name == "navigate":
        url = str(args.get("url", ""))
        if not host_allowed(url, allowed_hosts):
            b.session.blocked.append(url)
            return f"Navigation to {url} is blocked; stay on the store and PayPal."
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
    elif name in ("click_at", "click", "double_click", "triple_click", "right_click", "middle_click"):
        clicks = {"double_click": 2, "triple_click": 3}.get(name, 1)
        button = {"right_click": "right", "middle_click": "middle"}.get(name, "left")
        await page.mouse.click(_px(args["x"], w), _px(args["y"], h), click_count=clicks, button=button)
    elif name in ("hover_at", "move"):
        await page.mouse.move(_px(args["x"], w), _px(args["y"], h))
    elif name in ("type_text_at", "type"):
        if "x" in args and "y" in args:
            await page.mouse.click(_px(args["x"], w), _px(args["y"], h))
        if args.get("clear_before_typing", True) and name == "type_text_at":
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
        await page.keyboard.type(str(args.get("text", "")), delay=15)
        if args.get("press_enter", name == "type_text_at"):
            await page.keyboard.press("Enter")
    elif name in ("key_combination", "press_key", "hotkey"):
        await page.keyboard.press(norm_keys(args.get("keys") or args.get("key", "")))
    elif name in ("scroll_document", "scroll_at", "scroll"):
        direction = args.get("direction", "down")
        if "x" in args and "y" in args:
            await page.mouse.move(_px(args["x"], w), _px(args["y"], h))
        amount = int(args.get("magnitude_in_pixels") or float(args.get("magnitude", 800)) / 1000 * h)
        if name == "scroll_document":
            amount = int(h * 0.8)
        dx, dy = {"up": (0, -amount), "down": (0, amount), "left": (-amount, 0), "right": (amount, 0)}.get(
            direction, (0, amount)
        )
        await page.mouse.wheel(dx, dy)
    elif name == "drag_and_drop":
        sx, sy = args.get("x", args.get("start_x")), args.get("y", args.get("start_y"))
        ex, ey = args.get("destination_x", args.get("end_x")), args.get("destination_y", args.get("end_y"))
        await page.mouse.move(_px(sx, w), _px(sy, h))
        await page.mouse.down()
        await page.mouse.move(_px(ex, w), _px(ey, h), steps=8)
        await page.mouse.up()
    else:
        return f"Unsupported action {name}"
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=8000)
    except Exception:
        pass
    await asyncio.sleep(0.6)
    return None


def _prune_screenshots(history: list[types.Content]) -> None:
    """Keep only the most recent screenshots in the conversation to bound token use."""
    seen = 0
    for content in reversed(history):
        if content.role != "user" or not content.parts:
            continue
        has_shot = any(p.function_response and p.function_response.parts for p in content.parts)
        if not has_shot:
            continue
        seen += 1
        if seen > KEEP_SCREENSHOT_TURNS:
            for p in content.parts:
                if p.function_response and p.function_response.parts:
                    p.function_response.parts = None


async def run_shopper(
    store_url: str,
    device: Device,
    emit: Emit,
    *,
    extra_hosts: set[str] | None = None,
    save_shot: Callable[[bytes], Awaitable[str]] | None = None,
    max_steps: int = 60,
    timeout_s: int = 720,
    goal: str = GOAL,
    rules: str = RULES,
    start_url: str | None = None,
) -> ShopperResult:
    settings = get_settings()
    started = time.monotonic()
    store_host = urlparse(store_url).hostname or ""
    allowed = {store_host, *(extra_hosts or set())}
    result = ShopperResult(device=device)
    paypal = PayPalClient()

    config = types.GenerateContentConfig(
        tools=[types.Tool(computer_use=types.ComputerUse(environment=types.Environment.ENVIRONMENT_BROWSER))],
        temperature=0,
    )
    try:
        async with open_session(device, allowed, timeout_seconds=timeout_s + 120) as session:
            result.live_view_url = session.live_view_url
            await emit(
                "session", device=device, live_view_url=session.live_view_url, replay_url=session.replay_url
            )
            b = _Browser(session, store_host)
            await b.page.goto(start_url or store_url, wait_until="domcontentloaded")

            shot = await _screenshot(b.page)
            history: list[types.Content] = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            text=f"{goal}\n\n{rules}\n\nThe browser is open at {start_url or store_url}."
                        ),
                        types.Part.from_bytes(data=shot, mime_type="image/png"),
                    ],
                )
            ]
            checkout_seen_at: int | None = None
            clicks_since_checkout = 0

            for n in range(1, max_steps + 1):
                if time.monotonic() - started > timeout_s:
                    result.error = "timeout"
                    break
                response = await generate(settings.computer_use_model, history, config)
                result.model_calls += 1
                candidate = response.candidates[0] if response.candidates else None
                if not candidate or not candidate.content:
                    result.error = "empty model response"
                    break
                history.append(candidate.content)
                narration = " ".join(p.text for p in candidate.content.parts or [] if p.text).strip()
                calls = [p.function_call for p in candidate.content.parts or [] if p.function_call]
                if "SUMMARY:" in narration:
                    result.summary = narration.split("SUMMARY:", 1)[1].strip()
                if not calls:
                    if narration and not result.summary:
                        result.summary = narration
                    await emit("narration", device=device, step=n, text=narration)
                    break

                responses: list[types.Part] = []
                stop = False
                for call in calls:
                    args = dict(call.args or {})
                    extra: dict[str, Any] = {}
                    safety = args.pop("safety_decision", None)
                    if safety:
                        # Sherpa only ever shops its own sandbox stores with a sandbox test buyer, so payment
                        # confirmations are acknowledged; anything off-allowlist is refused.
                        ok = host_allowed(b.page.url, allowed)
                        await emit("safety", device=device, step=n, decision=safety, acknowledged=ok)
                        if not ok:
                            stop = True
                            break
                        extra["safety_acknowledgement"] = "true"
                    try:
                        error = await _execute(b, call.name, args, allowed, store_url)
                    except Exception as exc:  # report to the model and keep going
                        error = f"The action failed: {type(exc).__name__}: {str(exc)[:200]}"
                    if await _sandbox_login(
                        b.page, settings.paypal_buyer_email, settings.paypal_buyer_password
                    ):
                        await emit("sandbox_login", device=device, step=n)

                    probe = await probe_page(b.page if b.page is b.main else b.main)
                    result.probes.append(probe)
                    if probe.get("crashed"):
                        result.crashed = True
                    if probe.get("blank") and n > 1:
                        result.blank_page = True
                    if probe.get("paypal_visible"):
                        result.reached_payment = True
                    if checkout_seen_at is None and re.search(r"checkout|cart", probe.get("url", ""), re.I):
                        checkout_seen_at = n
                    if (
                        checkout_seen_at is not None
                        and not result.reached_payment
                        and call.name in ("click_at", "click")
                    ):
                        clicks_since_checkout += 1

                    shot = await _screenshot(b.page)
                    shot_id = await save_shot(_jpeg(shot)) if save_shot else None
                    safe_args = {
                        k: ("•••" if k == "text" and "paypal.com" in b.page.url else v)
                        for k, v in args.items()
                    }
                    # Gemini 3.x explains each action in an `intent` argument rather than in text.
                    said = narration or str(args.get("intent", ""))
                    step = Step(n, call.name, safe_args, said, b.page.url, probe, shot_id)
                    result.steps.append(step)
                    await emit(
                        "step",
                        device=device,
                        step=n,
                        action=call.name,
                        args=safe_args,
                        narration=said,
                        url=b.page.url,
                        shot_id=shot_id,
                        paypal_visible=probe.get("paypal_visible", False),
                        above_fold=probe.get("above_fold", False),
                        error=error,
                    )
                    payload: dict[str, Any] = {"url": b.page.url, **extra}
                    if error:
                        payload["error"] = error
                    responses.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                name=call.name,
                                response=payload,
                                parts=[
                                    types.FunctionResponsePart(
                                        inline_data=types.FunctionResponseBlob(
                                            mime_type="image/png", data=shot
                                        )
                                    )
                                ],
                            )
                        )
                    )
                if stop:
                    break
                history.append(types.Content(role="user", parts=responses))
                _prune_screenshots(history)

            result.clicks_after_checkout = clicks_since_checkout if checkout_seen_at is not None else None
            result.blocked = list(session.blocked)
            await asyncio.sleep(1.5)  # let in-flight capture responses land
            result.order_ids = list(b.order_ids)
        result.replay_url = session.replay_url
    except Exception as exc:
        log.exception("shopper failed")
        result.error = f"{type(exc).__name__}: {exc}"

    if paypal.configured:
        for order_id in reversed(result.order_ids):
            order = await paypal.get_order(order_id)
            if order_completed(order):
                result.payment_completed = True
                result.completed_order = {"id": order_id, "status": order["status"]}
                break
    result.seconds = round(time.monotonic() - started, 1)
    await emit(
        "shopper_done",
        device=device,
        reached_payment=result.reached_payment,
        payment_completed=result.payment_completed,
        order=result.completed_order,
        replay_url=result.replay_url,
        summary=result.summary,
        error=result.error,
    )
    return result
