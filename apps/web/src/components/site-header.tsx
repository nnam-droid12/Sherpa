import Link from "next/link";
import { ThemeToggle } from "./theme-toggle";

export function Logo() {
  return (
    <span className="flex items-center gap-2 font-semibold tracking-tight">
      <span aria-hidden className="grid size-7 place-items-center rounded-lg bg-accent text-accent-fg">
        <svg viewBox="0 0 24 24" className="size-4" fill="currentColor">
          <path d="M12 3 3 20h18L12 3zm0 5.2L16.9 18H7.1L12 8.2z" />
        </svg>
      </span>
      Sherpa
    </span>
  );
}

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-bg/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <Link href="/" aria-label="Sherpa home">
          <Logo />
        </Link>
        <nav aria-label="Main" className="flex items-center gap-1 text-sm">
          <Link href="/#how" className="hidden rounded-lg px-3 py-1.5 text-muted transition hover:text-fg sm:block">
            How it works
          </Link>
          <Link href="/fleet" className="hidden rounded-lg px-3 py-1.5 text-muted transition hover:text-fg sm:block">
            Fleet scan
          </Link>
          <Link href="/runs" className="hidden rounded-lg px-3 py-1.5 text-muted transition hover:text-fg sm:block">
            Runs
          </Link>
          <a
            href="https://github.com/nnam-droid12/Sherpa"
            className="hidden rounded-lg px-3 py-1.5 text-muted transition hover:text-fg md:block"
          >
            GitHub
          </a>
          <ThemeToggle />
          <Link
            href="/dashboard"
            className="ml-1 rounded-lg bg-accent px-3.5 py-1.5 font-medium text-accent-fg transition hover:opacity-90"
          >
            Open dashboard
          </Link>
        </nav>
      </div>
    </header>
  );
}
