"use client";

import { useState } from "react";
import { cartTotal, useCart } from "@/lib/cart";
import { PayPalButton } from "./paypal-button";

type Shipping = {
  name: string;
  street: string;
  city: string;
  zip: string;
  deliveryDate: string;
  notes?: string;
};

function formatNotes(notes: string) {
  return notes.trim() || "None";
}

export function Checkout({ clientId }: { clientId: string }) {
  const items = useCart();
  const [step, setStep] = useState<"shipping" | "review">("shipping");
  const [shipping, setShipping] = useState<Shipping>({ name: "", street: "", city: "", zip: "", deliveryDate: "" });
  const [showPayment, setShowPayment] = useState(false);

  const set = (key: keyof Shipping) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setShipping({ ...shipping, [key]: e.target.value });

  if (items.length === 0) {
    return (
      <main className="container">
        <h1>Checkout</h1>
        <p>Your cart is empty.</p>
      </main>
    );
  }

  return (
    <main className="container">
      <h1>Checkout</h1>
      <div className="steps">
        <span className={step === "shipping" ? "on" : ""}>1. Delivery</span>
        <span className={step === "review" ? "on" : ""}>2. Review &amp; pay</span>
      </div>

      {step === "shipping" && (
        <form
          className="form box"
          onSubmit={(e) => {
            e.preventDefault();
            setStep("review");
          }}
        >
          <label>
            Full name
            <input required value={shipping.name} onChange={set("name")} autoComplete="name" />
          </label>
          <label>
            Street address
            <input required value={shipping.street} onChange={set("street")} autoComplete="street-address" />
          </label>
          <label>
            City
            <input required value={shipping.city} onChange={set("city")} autoComplete="address-level2" />
          </label>
          <label>
            ZIP code
            <input required value={shipping.zip} onChange={set("zip")} autoComplete="postal-code" />
          </label>
          <label>
            Delivery date
            <input required type="date" value={shipping.deliveryDate} onChange={set("deliveryDate")} />
          </label>
          <label>
            Delivery notes (optional)
            <textarea rows={2} value={shipping.notes} onChange={set("notes")} />
          </label>
          <button className="button" type="submit">
            Continue to review
          </button>
        </form>
      )}

      {step === "review" && (
        <section className="box">
          <h2>Review your order</h2>
          {items.map((i) => (
            <p key={i.id}>
              {i.title} × {i.qty}
            </p>
          ))}
          <p>
            Deliver to {shipping.name}, {shipping.street}, {shipping.city} {shipping.zip} on {shipping.deliveryDate}
          </p>
          <p>Notes: {formatNotes(shipping.notes as string)}</p>
          <p>
            <strong>Total: ${cartTotal(items)}</strong>
          </p>
          {!showPayment ? (
            <button className="button" onClick={() => setShowPayment(true)}>
              Choose payment method
            </button>
          ) : (
            <PayPalButton clientId={clientId} items={items} />
          )}
        </section>
      )}
    </main>
  );
}
