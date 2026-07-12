import { useCallback, useMemo, type AnchorHTMLAttributes } from "react";
import { RouteDeckStateError } from "@routedeck/core";

import { useRouteDeckRuntime } from "../provider/RouteDeckProvider";

const EMPTY_PARAMS: Readonly<Record<string, string>> = Object.freeze({});

export interface RouteDeckLinkProps
  extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> {
  nodeId: string;
  params?: Readonly<Record<string, string>>;
  resumeHandle?: string;
  replace?: boolean;
}

export function RouteDeckLink({
  nodeId,
  params = EMPTY_PARAMS,
  resumeHandle,
  replace = false,
  onClick,
  ...anchorProps
}: RouteDeckLinkProps) {
  const { routeCodec, routeController, navigationActions } = useRouteDeckRuntime();
  if (routeCodec === null || routeController === null) {
    throw new RouteDeckStateError(
      "routing_adapter_required",
      "RouteDeckLink requires the compiled route codec and route controller.",
    );
  }
  const href = useMemo(
    () =>
      routeCodec.encode(nodeId, params, {
        ...(resumeHandle === undefined ? {} : { resumeHandle }),
      }),
    [routeCodec, nodeId, params, resumeHandle],
  );
  const handleClick = useCallback<
    NonNullable<AnchorHTMLAttributes<HTMLAnchorElement>["onClick"]>
  >(
    (event) => {
      onClick?.(event);
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }
      event.preventDefault();
      if (!navigationActions?.openPath) {
        throw new RouteDeckStateError(
          "history_open_action_required",
          "RouteDeckLink requires a confirmed navigation action.",
        );
      }
      void navigationActions.openPath(href, { replace });
    },
    [onClick, navigationActions, href, replace],
  );

  return <a {...anchorProps} href={href} onClick={handleClick} />;
}
