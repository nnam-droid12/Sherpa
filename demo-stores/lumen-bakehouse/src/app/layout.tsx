import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { CartLink } from "@/components/cart-link";

export const metadata: Metadata = {
  title: "Lumen Bakehouse — Preorder cakes",
  description: "Small-batch celebration cakes, baked to order and delivered.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav className="nav">
          <Link href="/" className="logo">
            Lumen Bakehouse
          </Link>
          <CartLink />
        </nav>
        {children}
        <footer>Lumen Bakehouse is a fictional demo store. Payments run in the PayPal sandbox.</footer>
      </body>
    </html>
  );
}
