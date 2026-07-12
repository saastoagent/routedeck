import type { ReactNode } from "react";

import {
  useRouteDeckPrivateForm,
  type RouteDeckPrivateFormBinding,
} from "./useRouteDeckPrivateForm";

export interface RouteDeckPrivateFormProps {
  formId: string;
  loadOnMount?: boolean;
  children(binding: RouteDeckPrivateFormBinding): ReactNode;
}

export function RouteDeckPrivateForm({
  formId,
  loadOnMount = true,
  children,
}: RouteDeckPrivateFormProps) {
  const binding = useRouteDeckPrivateForm(formId, { loadOnMount });
  return <>{children(binding)}</>;
}
