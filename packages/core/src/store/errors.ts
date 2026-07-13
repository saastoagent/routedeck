import {
  RouteDeckError,
  RouteDeckHttpError,
  RouteDeckStreamError,
} from "../client/errors";
import type { RouteDeckClientErrorState } from "./state";

export function safeError(error: unknown): RouteDeckClientErrorState {
  if (
    error instanceof RouteDeckError ||
    error instanceof RouteDeckStreamError
  ) {
    return { code: error.code, message: error.message };
  }
  return {
    code: "unexpected_client_failure",
    message: "The RouteDeck client encountered an unexpected failure.",
  };
}

export function isExpiredBootstrapError(error: unknown): boolean {
  return (
    (error instanceof RouteDeckHttpError ||
      error instanceof RouteDeckStreamError) &&
    error.status === 410
  );
}

export function isMissingBootstrapError(error: unknown): boolean {
  return (
    (error instanceof RouteDeckHttpError &&
      error.status === 404 &&
      error.failure?.code === "session_not_found") ||
    (error instanceof RouteDeckStreamError &&
      error.status === 404 &&
      error.code === "stream_session_not_found")
  );
}

export function isUpgradeBootstrapError(error: unknown): boolean {
  return (
    error instanceof RouteDeckHttpError &&
    error.status === 409 &&
    error.failure?.code === "session_upgrade_required"
  );
}
