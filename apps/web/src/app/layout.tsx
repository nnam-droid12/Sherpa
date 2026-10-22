import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { SiteHeader } from "@/components/site-header";

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
      </body>
    </html>
  );
}
