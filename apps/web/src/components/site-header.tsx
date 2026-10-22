import Link from "next/link";
import { ThemeToggle } from "./theme-toggle";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-bg/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span aria-hidden className="grid size-7 place-items-center rounded-lg bg-accent text-xs text-accent-fg">
            ▲
          </span>
          Sherpa
        </Link>
        <nav aria-label="Main" className="flex items-center gap-2 text-sm">
          <Link href="/runs" className="rounded-lg px-3 py-1.5 text-muted transition hover:text-fg">
            Runs
          </Link>
          <ThemeToggle />
        </nav>
      </div>
    </header>
  );
}
