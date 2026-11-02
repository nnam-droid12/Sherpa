import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { CartLink } from "@/components/cart-link";

export const metadata: Metadata = {
  title: "Lumen Bakehouse · Celebration cakes, baked to order",
  description: "Small-batch celebration cakes, tarts and morning buns, baked to order and delivered across San Francisco.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700&family=DM+Sans:wght@400;500;600;700&display=swap"
        />
      </head>
      <body>
        <div className="announce">Order by 2pm for delivery the day after tomorrow · Free delivery over $60</div>
        <header className="nav">
          <div className="nav-inner">
            <Link href="/" className="logo">
              Lumen <em>Bakehouse</em>
            </Link>
            <nav className="nav-links" aria-label="Shop">
              <Link href="/#cakes">Cakes</Link>
              <Link href="/#cakes">Tarts</Link>
              <Link href="/#cakes">Morning bakes</Link>
              <Link href="/#how">How ordering works</Link>
            </nav>
            <CartLink />
          </div>
        </header>
        {children}
        <footer className="footer">
          <div className="footer-inner">
            <div>
              <p className="logo">
                Lumen <em>Bakehouse</em>
              </p>
              <p>Baked to order in small batches on Valencia Street, San Francisco.</p>
            </div>
            <div>
              <h4>Shop</h4>
              <Link href="/#cakes">Celebration cakes</Link>
              <Link href="/#cakes">Tarts &amp; bundts</Link>
              <Link href="/#cakes">Morning bun boxes</Link>
            </div>
            <div>
              <h4>Help</h4>
              <Link href="/#how">Delivery &amp; lead times</Link>
              <Link href="/#how">Allergens</Link>
            </div>
            <div>
              <h4>About</h4>
              <a href="https://github.com/nnam-droid12/sherpa-demo-lumen-bakehouse/blob/main/CREDITS.md">Photo credits</a>
              <a href="https://github.com/nnam-droid12/sherpa-demo-lumen-bakehouse">Source code</a>
            </div>
          </div>
          <p className="footer-note">
            Lumen Bakehouse is a fictional store built to demo Sherpa. Payments run in the PayPal sandbox; no real orders
            are placed.
          </p>
        </footer>
      </body>
    </html>
  );
}
