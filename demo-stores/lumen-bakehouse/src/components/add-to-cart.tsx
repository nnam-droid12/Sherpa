"use client";

import { useRouter } from "next/navigation";
import { addToCart } from "@/lib/cart";
import type { Product } from "@/lib/products";

export function AddToCart({ product }: { product: Product }) {
  const router = useRouter();
  return (
    <button
      className="button"
      onClick={() => {
        addToCart(product);
        router.push("/cart");
      }}
    >
      Preorder this cake
    </button>
  );
}
