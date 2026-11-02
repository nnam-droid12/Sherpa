"use client";

import Link from "next/link";
import { cartTotal, useCart, writeCart } from "@/lib/cart";
import { findProduct } from "@/lib/products";

export default function CartPage() {
  const items = useCart();
  return (
    <main className="container" style={{ maxWidth: 820 }}>
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link href="/">Home</Link> / Cart
      </nav>
      <h1>Your cart</h1>
      {items.length === 0 ? (
        <div className="box">
          <p>
            Your cart is empty. <Link href="/#cakes">Browse this week&apos;s cakes</Link>
          </p>
        </div>
      ) : (
        <>
          <div className="box">
            {items.map((i) => (
              <div key={i.id} className="cart-line">
                <div className="who">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={findProduct(i.id)?.image} alt="" />
                  <div>
                    <strong>{i.title}</strong>
                    <div className="muted">Qty {i.qty}</div>
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div className="price">${(Number(i.price) * i.qty).toFixed(2)}</div>
                  <button
                    className="button ghost"
                    style={{ padding: "4px 12px", fontSize: "0.8rem" }}
                    onClick={() => writeCart(items.filter((x) => x.id !== i.id))}
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
            <p style={{ textAlign: "right", fontSize: "1.15rem" }}>
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
