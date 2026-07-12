import type { ReactNode } from "react";

export interface RouteDeckNeedsInputProps {
  title?: ReactNode;
  message: ReactNode;
  children?: ReactNode;
  className?: string;
}

export function RouteDeckNeedsInput({
  title = "More information is required",
  message,
  children,
  className,
}: RouteDeckNeedsInputProps) {
  return (
    <section className={className} aria-labelledby="routedeck-needs-input-title">
      <h2 id="routedeck-needs-input-title">{title}</h2>
      <p>{message}</p>
      {children}
    </section>
  );
}
