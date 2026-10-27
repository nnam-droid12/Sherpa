"use client";

import Link from "next/link";
import { useCart } from "@/lib/cart";

export function CartLink() {
  const items = useCart();
  return <Link href="/cart">Cart ({items.reduce((n, i) => n + i.qty, 0)})</Link>;
}
