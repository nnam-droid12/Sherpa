import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import Link from "next/link";
import { Logo, SiteHeader } from "@/components/site-header";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono-face" });

export const metadata: Metadata = {
  title: "Sherpa — AI integration engineer for PayPal checkout",
  description:
    "Sherpa audits a live store's PayPal checkout, opens a pull request that fixes it, verifies it with a real sandbox payment, and makes the store agent-ready.",
};

const themeScript = `(() => { try {
  const t = localStorage.getItem("sherpa-theme");
  const d = t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = d ? "dark" : "light";
} catch (e) { document.documentElement.dataset.theme = "light"; } })();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${inter.variable} ${mono.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-dvh font-sans antialiased">
        <SiteHeader />
        <main className="mx-auto w-full max-w-6xl px-4 pb-24 sm:px-6">{children}</main>
        <footer className="border-t border-border">
          <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-8 text-sm text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <Logo />
            <p>PayPal sandbox only. Built on Gemini Enterprise Agent Platform, KERNEL and Google Cloud Run.</p>
            <nav className="flex gap-4" aria-label="Footer">
              <Link href="/dashboard" className="hover:text-fg">
                Dashboard
              </Link>
              <a href="https://github.com/nnam-droid12/Sherpa" className="hover:text-fg">
                GitHub
              </a>
              <a href="https://github.com/nnam-droid12/Sherpa/blob/main/LICENSE" className="hover:text-fg">
                MIT license
              </a>
            </nav>
          </div>
        </footer>
      </body>
    </html>
  );
}
