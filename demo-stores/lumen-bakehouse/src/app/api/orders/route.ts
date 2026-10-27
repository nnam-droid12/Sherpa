import { NextResponse } from "next/server";
import { type CartLine, createOrder } from "@/lib/paypal";

export async function POST(req: Request) {
  const { items } = (await req.json()) as { items: CartLine[] };
  if (!Array.isArray(items) || items.length === 0) {
    return NextResponse.json({ error: "cart is empty" }, { status: 400 });
  }
  const { status, body } = await createOrder(items);
  return NextResponse.json(body, { status });
}
