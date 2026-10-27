"use client";

import { useEffect, useState } from "react";
import type { Product } from "./products";

export type CartItem = { id: string; title: string; price: string; qty: number };

const KEY = "lumen-cart";

export function readCart(): CartItem[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "[]");
  } catch {
    return [];
  }
}

export function writeCart(items: CartItem[]) {
  localStorage.setItem(KEY, JSON.stringify(items));
  window.dispatchEvent(new Event("cart-change"));
}

export function addToCart(p: Product) {
  const items = readCart();
  const line = items.find((i) => i.id === p.id);
  if (line) line.qty += 1;
  else items.push({ id: p.id, title: p.title, price: p.price, qty: 1 });
  writeCart(items);
}

export function cartTotal(items: CartItem[]) {
  return items.reduce((s, i) => s + Number(i.price) * i.qty, 0).toFixed(2);
}

export function useCart() {
  const [items, setItems] = useState<CartItem[]>([]);
  useEffect(() => {
    const sync = () => setItems(readCart());
    sync();
    window.addEventListener("cart-change", sync);
    return () => window.removeEventListener("cart-change", sync);
  }, []);
  return items;
}
