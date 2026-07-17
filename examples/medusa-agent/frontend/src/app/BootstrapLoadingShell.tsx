import { MedusaMark } from "../ui/MedusaMark";

export function BootstrapLoadingShell() {
  return (
    <section className="bootstrap-loading" role="status" aria-live="polite">
      <MedusaMark />
      <span>
        <strong>Medusa Agent</strong>
        <small>Preparing your shopping experience</small>
      </span>
    </section>
  );
}
