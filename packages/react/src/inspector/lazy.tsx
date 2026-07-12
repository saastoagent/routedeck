import { lazy, Suspense, type ReactNode } from "react";
import type { NavGraphInspectorProps } from "./NavGraphInspector";

const LazyInspector = lazy(async () => {
  const module = await import("./NavGraphInspector");
  return { default: module.NavGraphInspectorView };
});

export interface LazyNavGraphInspectorProps extends NavGraphInspectorProps {
  fallback?: ReactNode;
}

export function NavGraphInspector({
  fallback = <div role="status">Loading navigation graph…</div>,
  ...props
}: LazyNavGraphInspectorProps) {
  return (
    <Suspense fallback={fallback}>
      <LazyInspector {...props} />
    </Suspense>
  );
}
