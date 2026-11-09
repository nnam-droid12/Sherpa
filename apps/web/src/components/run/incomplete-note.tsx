import type { Audit } from "@/lib/types";

/** Says plainly when a shopper could not run, so a cloud-browser failure is never read as the store's fault. */
export function IncompleteNote({ audit }: { audit?: Audit | null }) {
  const devices = audit?.incomplete ?? [];
  if (!devices.length) return null;
  return (
    <p role="status" className="rounded-xl border border-warn/40 bg-warn/10 px-4 py-3 text-sm text-warn">
      Incomplete: the {devices.join(" and ")} shopper could not run because the cloud browser failed, even after a retry. Those checks were
      skipped, not failed, so this score is lower than the store deserves. Run this stage again to complete it.
    </p>
  );
}
