"use client";

import Link from "next/link";
import { cartTotal, useCart, writeCart } from "@/lib/cart";

export default function CartPage() {
  const items = useCart();
  return (
    <main className="container">
      <h1>Your cart</h1>
      {items.length === 0 ? (
        <p>
          Your cart is empty. <Link href="/">Browse cakes</Link>
        </p>
      ) : (
        <>
          <div className="box">
            {items.map((i) => (
              <p key={i.id}>
                {i.title} × {i.qty} — <span className="price">${(Number(i.price) * i.qty).toFixed(2)}</span>{" "}
                <button className="button ghost" onClick={() => writeCart(items.filter((x) => x.id !== i.id))}>
                  Remove
                </button>
              </p>
            ))}
            <p>
              <strong>Total: ${cartTotal(items)}</strong>
            </p>
          </div>
          <Link href="/checkout" className="button">
            Checkout
          </Link>
        </>
      )}
    </main>
  );
}
