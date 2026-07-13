import type { ReactNode } from "react";

import { sectionTitleStyle } from "./styles";

export function Legend({ color, label }: { color: string; label: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
      <span
        aria-hidden="true"
        style={{ width: 7, height: 7, borderRadius: "50%", background: color }}
      />
      {label}
    </span>
  );
}

export function InspectorSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section style={{ marginTop: "0.85rem" }}>
      <h4 style={sectionTitleStyle}>{title}</h4>
      {children}
    </section>
  );
}
