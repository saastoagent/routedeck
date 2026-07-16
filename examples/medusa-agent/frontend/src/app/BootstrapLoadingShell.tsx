import { MedusaMark } from "../ui/MedusaMark";

export type BootstrapLoadingPhase =
  | "storefront"
  | "session"
  | "checkout"
  | "setup";

export interface BootstrapLoadingShellProps {
  phase: BootstrapLoadingPhase;
}

const PHASE_LABELS: Readonly<Record<BootstrapLoadingPhase, string>> = {
  storefront: "Loading storefront",
  session: "Starting buyer session",
  checkout: "Restoring checkout",
  setup: "Finishing buyer setup",
};

export function BootstrapLoadingShell({ phase }: BootstrapLoadingShellProps) {
  return (
    <section className="bootstrap-loading" role="status" aria-live="polite">
      <MedusaMark />
      <span>
        <strong>Medusa Agent</strong>
        <small>{PHASE_LABELS[phase]}</small>
      </span>
    </section>
  );
}
