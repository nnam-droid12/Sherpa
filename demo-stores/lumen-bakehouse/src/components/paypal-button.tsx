"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { type CartItem, writeCart } from "@/lib/cart";

type PayPalNamespace = {
  Buttons: (opts: {
    createOrder: () => Promise<string>;
    onApprove: (data: { orderID: string }) => Promise<void>;
    onError?: (err: unknown) => void;
  }) => { render: (el: HTMLElement) => Promise<void> };
};

declare global {
  interface Window {
    paypal?: PayPalNamespace;
  }
}

export function PayPalButton({ clientId, items }: { clientId: string; items: CartItem[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const [error, setError] = useState("");

  useEffect(() => {
    const script = document.createElement("script");
    script.src = `https://www.paypal.com/sdk/js?client-id=${clientId}&currency=USD`;
    script.onload = () => {
      if (!window.paypal || !ref.current) return;
      window.paypal
        .Buttons({
          createOrder: async () => {
            const res = await fetch("/api/orders", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ items: items.map((i) => ({ id: i.id, qty: i.qty })) }),
            });
            const order = await res.json();
            return order.id;
          },
          onApprove: async (data) => {
            const res = await fetch(`/api/orders/${data.orderID}/capture`, { method: "POST" });
            const capture = await res.json();
            if (capture.status === "COMPLETED") {
              writeCart([]);
              router.push(`/thank-you?order=${capture.id}`);
            } else {
              setError("Payment could not be completed.");
            }
          },
          onError: () => setError("Payment could not be completed."),
        })
        .render(ref.current);
    };
    document.body.appendChild(script);
    return () => {
      script.remove();
    };
  }, [clientId, items, router]);

  return (
    <div>
      <div ref={ref} id="paypal-button-container" />
      {error && <p role="alert">{error}</p>}
    </div>
  );
}
