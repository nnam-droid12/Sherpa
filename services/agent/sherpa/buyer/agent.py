"""AI buyer agent: discovers a store's catalog and buys through its PayPal Cart API.

In production PayPal's Commerce Platform is the caller of these merchant endpoints after Store Sync onboarding.
Here the buyer agent plays that caller role against the sandbox.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from google.genai import types

from sherpa.agentready.spec import SAMPLE_ADDRESS
from sherpa.audit.shopper import run_shopper
from sherpa.config import get_settings
from sherpa.llm import generate

log = logging.getLogger(__name__)

Emit = Callable[..., Awaitable[Any]]

SYSTEM = """You are a shopping agent buying on behalf of a person. Use the store's catalog feed and its PayPal Cart \
API through the tools. Pick the product that best fits the request and budget, build a cart, and fix every \
validation issue the store reports (ask the shopper with ask_shopper when you need a fact you do not have, such as \
a delivery date). When the cart is VALID, call approve_payment so the shopper approves the PayPal payment, confirm \
with check_paypal_order that the order is APPROVED, then call checkout_cart. Finish with a short confirmation for \
the shopper including the order id and total. Never invent prices; use the store's."""

APPROVE_GOAL = (
    "You are a shopper approving a PayPal sandbox payment for an order you already chose. Signing in is handled for "
    "you. Review the amount, keep the default payment method and click the button that completes or continues the "
    "payment (for example 'Pay', 'Complete Purchase' or 'Continue'). Stop as soon as you are sent back to the store "
    "or see a confirmation, then give a one-line summary starting with SUMMARY:."
)
APPROVE_RULES = "Rules: Stay on PayPal and the store. Do not change the shipping address or funding source."


def next_weekday(weekday: int, min_days: int = 2, today: dt.date | None = None) -> dt.date:
    """Next given weekday (Mon=0) at least `min_days` away."""
    d = (today or dt.date.today()) + dt.timedelta(days=min_days)
    return d + dt.timedelta(days=(weekday - d.weekday()) % 7)


class Persona:
    """Answers the agent's questions the way the demo shopper would."""

    def __init__(self, request: str) -> None:
        self.request = request
        self.name = {"given_name": "Alex", "surname": "Rivera"}
        self.email = "alex.rivera@example.com"

    def answer(self, question: str) -> str:
        q = question.lower()
        if any(w in q for w in ("date", "day", "when", "deliver")):
            sat = next_weekday(5)
            return f"Please deliver on Saturday {sat.isoformat()}."
        if any(w in q for w in ("address", "ship", "where")):
            return f"Ship to {json.dumps(SAMPLE_ADDRESS)}."
        if "email" in q:
            return f"My email is {self.email}."
        if "name" in q:
            return "My name is Alex Rivera."
        if any(w in q for w in ("note", "message", "instruction")):
            return "Write 'Happy birthday, Sam!' on the cake if you can."
        return "Use your best judgement within my budget."


def _fn(name: str, desc: str, props: dict[str, Any], required: list[str]) -> types.FunctionDeclaration:
    return types.FunctionDeclaration(
        name=name,
        description=desc,
        parameters_json_schema={"type": "object", "properties": props, "required": required},
    )


_cart_props = {
    "items": {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {"item_id": {"type": "string"}, "quantity": {"type": "integer"}},
            "required": ["item_id", "quantity"],
        },
    },
    "shipping_address": {
        "type": "object",
        "description": "address_line_1, admin_area_2, admin_area_1, postal_code, country_code",
    },
    "checkout_fields": {
        "type": "array",
        "items": {"type": "object", "properties": {"type": {"type": "string"}, "value": {"type": "string"}}},
    },
    "customer": {"type": "object", "description": "email_address and name {given_name, surname}"},
}

DECLARATIONS = [
    _fn(
        "search_catalog",
        "Search the store's catalog feed.",
        {"query": {"type": "string"}, "max_price": {"type": "number"}},
        [],
    ),
    _fn(
        "ask_shopper",
        "Ask the person you are shopping for a question.",
        {"question": {"type": "string"}},
        ["question"],
    ),
    _fn("create_cart", "POST /merchant-cart: create a cart.", _cart_props, ["items"]),
    _fn("get_cart", "GET /merchant-cart/{id}.", {"cart_id": {"type": "string"}}, ["cart_id"]),
    _fn(
        "update_cart",
        "PUT /merchant-cart/{id}: replace the whole cart (send every field again).",
        {"cart_id": {"type": "string"}, **_cart_props},
        ["cart_id", "items"],
    ),
    _fn(
        "approve_payment",
        "Have the shopper approve the cart's PayPal payment.",
        {"cart_id": {"type": "string"}},
        ["cart_id"],
    ),
    _fn("check_paypal_order", "Get a PayPal order's status.", {"order_id": {"type": "string"}}, ["order_id"]),
    _fn(
        "checkout_cart",
        "POST /merchant-cart/{id}/checkout to complete the purchase.",
        {"cart_id": {"type": "string"}},
        ["cart_id"],
    ),
]


def toolkit_order_status(order_id: str) -> dict[str, Any]:
    """Look up an order with the PayPal Agent Toolkit (Orders actions, sandbox)."""
    from paypal_agent_toolkit.shared.api import PayPalAPI
    from paypal_agent_toolkit.shared.configuration import Context

    s = get_settings()
    api = PayPalAPI(
        client_id=s.paypal_client_id, secret=s.paypal_client_secret, context=Context(sandbox=True)
    )
    data = json.loads(api.run("get_order_details", {"order_id": order_id}))
    raw = data.get("raw") or {}
    return {"id": raw.get("id", order_id), "status": data.get("status"), "amount": data.get("amount")}


async def run_buyer(store_url: str, request: str, emit: Emit, *, max_turns: int = 30) -> dict[str, Any]:
    settings = get_settings()
    base = store_url.rstrip("/")
    persona = Persona(request)
    transcript: list[dict[str, str]] = [{"role": "user", "text": request}]
    carts: dict[str, dict[str, Any]] = {}
    final_order: dict[str, Any] | None = None
    await emit("log", message=f"Buyer agent: {request}")

    async def say(role: str, text: str, tool: str | None = None) -> None:
        entry = {"role": role, "text": text[:800]}
        if tool:
            entry["tool"] = tool
        transcript.append(entry)
        await emit("chat", **entry)

    async with httpx.AsyncClient(timeout=40) as http:

        async def cart_call(method: str, path: str, body: dict | None = None) -> dict[str, Any]:
            r = await http.request(method, f"{base}{path}", json=body)
            try:
                data = r.json()
            except ValueError:
                data = {"error": r.text[:300]}
            data = data if isinstance(data, dict) else {"data": data}
            data["http_status"] = r.status_code
            if data.get("id"):
                carts[data["id"]] = data
            return data

        async def execute(name: str, args: dict[str, Any]) -> Any:
            nonlocal final_order
            if name == "search_catalog":
                feed = (await http.get(f"{base}/catalog.json")).json().get("items", [])
                q = str(args.get("query", "")).lower().split()
                cap = args.get("max_price")
                hits = [
                    i
                    for i in feed
                    if (not q or any(w in json.dumps(i).lower() for w in q))
                    and (cap is None or float(i.get("price", {}).get("value", 0)) <= float(cap))
                ]
                return (hits or feed)[:8]
            if name == "ask_shopper":
                answer = persona.answer(args["question"])
                await say("assistant", args["question"])
                await say("user", answer)
                return answer
            body = {k: v for k, v in args.items() if k != "cart_id" and v is not None}
            body.setdefault("payment_method", {"type": "paypal"})
            if name == "create_cart":
                return await cart_call("POST", "/merchant-cart", body)
            if name == "get_cart":
                return await cart_call("GET", f"/merchant-cart/{args['cart_id']}")
            if name == "update_cart":
                return await cart_call("PUT", f"/merchant-cart/{args['cart_id']}", body)
            if name == "check_paypal_order":
                return await asyncio.to_thread(toolkit_order_status, args["order_id"])
            if name == "approve_payment":
                cart = carts.get(args["cart_id"]) or await cart_call(
                    "GET", f"/merchant-cart/{args['cart_id']}"
                )
                token = (cart.get("payment_method") or {}).get("token")
                if not token:
                    return {"error": "the cart has no PayPal order token yet; fix validation issues first"}
                result = await run_shopper(
                    base,
                    "desktop",
                    emit,
                    goal=APPROVE_GOAL,
                    rules=APPROVE_RULES,
                    start_url=f"https://www.sandbox.paypal.com/checkoutnow?token={token}",
                    max_steps=25,
                    timeout_s=360,
                )
                status = await asyncio.to_thread(toolkit_order_status, token)
                return {"order_id": token, "status": status.get("status"), "replay_url": result.replay_url}
            if name == "checkout_cart":
                cart = carts.get(args["cart_id"]) or {}
                full = {
                    k: cart[k]
                    for k in ("items", "shipping_address", "checkout_fields", "customer", "payment_method")
                    if k in cart
                }
                full["items"] = [
                    {"item_id": i["item_id"], "quantity": i["quantity"]} for i in full.get("items", [])
                ]
                data = await cart_call("POST", f"/merchant-cart/{args['cart_id']}/checkout", full)
                token = (data.get("payment_method") or (cart.get("payment_method") or {})).get("token")
                if data.get("status") == "COMPLETED" and token:
                    final_order = await asyncio.to_thread(toolkit_order_status, token)
                return data
            return {"error": f"unknown tool {name}"}

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM,
            tools=[types.Tool(function_declarations=DECLARATIONS)],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        history = [
            types.Content(
                role="user",
                parts=[
                    types.Part(
                        text=f"Store: {base}\nToday is {dt.date.today().isoformat()}.\nRequest: {request}"
                    )
                ],
            )
        ]
        for _ in range(max_turns):
            resp = await generate(settings.gemini_model, history, config)
            cand = resp.candidates[0] if resp.candidates else None
            if not cand or not cand.content:
                break
            history.append(cand.content)
            text = " ".join(p.text for p in cand.content.parts or [] if p.text and not p.thought).strip()
            calls = [p.function_call for p in cand.content.parts or [] if p.function_call]
            if text:
                await say("assistant", text)
            if not calls:
                break
            replies = []
            for call in calls:
                args = dict(call.args or {})
                try:
                    out = await execute(call.name, args)
                except Exception as exc:  # surfaced to the model so it can recover
                    out = {"error": f"{type(exc).__name__}: {exc}"}
                if call.name != "ask_shopper":
                    summary = json.dumps(out)[:400] if not isinstance(out, str) else out
                    await say("tool", summary, tool=call.name)
                replies.append(
                    types.Part(
                        function_response=types.FunctionResponse(name=call.name, response={"result": out})
                    )
                )
            history.append(types.Content(role="user", parts=replies))

    return {"transcript": transcript, "order": final_order}
