import { findProduct } from "./products";

const PAYPAL_BASE = "https://api-m.sandbox.paypal.com";

export type CartLine = { id: string; qty: number };

async function accessToken() {
  const auth = Buffer.from(`${process.env.PAYPAL_CLIENT_ID}:${process.env.PAYPAL_CLIENT_SECRET}`).toString("base64");
  const res = await fetch(`${PAYPAL_BASE}/v1/oauth2/token`, {
    method: "POST",
    headers: { Authorization: `Basic ${auth}`, "Content-Type": "application/x-www-form-urlencoded" },
    body: "grant_type=client_credentials",
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`PayPal auth failed: ${res.status}`);
  return (await res.json()).access_token as string;
}

export function priceCart(lines: CartLine[]) {
  let total = 0;
  for (const line of lines) {
    const product = findProduct(line.id);
    if (!product) throw new Error(`unknown product ${line.id}`);
    total += Number(product.price) * Math.max(1, Math.floor(line.qty));
  }
  return total.toFixed(2);
}

export async function createOrder(lines: CartLine[]) {
  const token = await accessToken();
  const res = await fetch(`${PAYPAL_BASE}/v2/checkout/orders`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      intent: "CAPTURE",
      purchase_units: [{ amount: { currency_code: "USD", value: priceCart(lines) } }],
    }),
    cache: "no-store",
  });
  return { status: res.status, body: await res.json() };
}

export async function captureOrder(orderId: string) {
  const token = await accessToken();
  const res = await fetch(`${PAYPAL_BASE}/v2/checkout/orders/${encodeURIComponent(orderId)}/capture`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    cache: "no-store",
  });
  return { status: res.status, body: await res.json() };
}
