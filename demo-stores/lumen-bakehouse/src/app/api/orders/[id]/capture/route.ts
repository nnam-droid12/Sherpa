import { NextResponse } from "next/server";
import { captureOrder } from "@/lib/paypal";

export async function POST(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const { status, body } = await captureOrder(id);
  return NextResponse.json(body, { status });
}
