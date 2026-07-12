import type { RouteDeckFailure } from "../contracts/generated";

export class RouteDeckError extends Error {
  readonly code: string;

  constructor(code: string, message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = new.target.name;
    this.code = code;
  }
}

export class RouteDeckContractError extends RouteDeckError {
  readonly path: string;

  constructor(path: string, expectation: string, options?: ErrorOptions) {
    super(
      "contract_invalid",
      `RouteDeck contract violation at ${path}: ${expectation}`,
      options,
    );
    this.path = path;
  }
}

export class RouteDeckResponseContractError extends RouteDeckContractError {}

export class RouteDeckHttpError extends RouteDeckError {
  readonly status: number;
  readonly failure: RouteDeckFailure | null;

  constructor(
    status: number,
    failure: RouteDeckFailure | null,
    message: string,
    options?: ErrorOptions,
  ) {
    super(failure?.code ?? "http_error", message, options);
    this.status = status;
    this.failure = failure;
  }
}

export interface RouteDeckStreamErrorOptions extends ErrorOptions {
  retryable?: boolean;
  status?: number | null;
}

export class RouteDeckStreamError extends RouteDeckError {
  readonly retryable: boolean;
  readonly status: number | null;

  constructor(
    code: string,
    message: string,
    options?: RouteDeckStreamErrorOptions,
  ) {
    super(code, message, options);
    this.retryable = options?.retryable ?? true;
    this.status = options?.status ?? null;
  }
}

export class RouteDeckTransportError extends RouteDeckError {
  readonly phase: "request" | "response";

  constructor(
    phase: "request" | "response",
    message: string,
    options?: ErrorOptions,
  ) {
    super("transport_failed", message, options);
    this.phase = phase;
  }
}

export class RouteDeckOutcomeUnknownError extends RouteDeckError {
  readonly requestId: string;

  constructor(requestId: string, message: string, options?: ErrorOptions) {
    super("operation_outcome_unknown", message, options);
    this.requestId = requestId;
  }
}

export class RouteDeckRouteError extends RouteDeckError {}

export class RouteDeckStateError extends RouteDeckError {}
