export type ApiErrorKind =
  | "aborted"
  | "network"
  | "invalid_response"
  | "unauthorized"
  | "forbidden"
  | "conflict"
  | "validation"
  | "not_found"
  | "unavailable"
  | "unexpected";

interface ApiClientErrorOptions {
  kind: ApiErrorKind;
  message: string;
  status?: number;
  code?: string;
  details?: unknown;
  cause?: unknown;
}

export class ApiClientError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  readonly code?: string;
  readonly details?: unknown;

  constructor({ kind, message, status, code, details, cause }: ApiClientErrorOptions) {
    super(message, { cause });
    this.name = "ApiClientError";
    this.kind = kind;
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (!value || typeof value !== "object" || !("error" in value)) {
    return false;
  }
  const error = value.error;
  return (
    error !== null &&
    error !== undefined &&
    typeof error === "object" &&
    "code" in error &&
    typeof error.code === "string" &&
    "message" in error &&
    typeof error.message === "string"
  );
}

export function errorFromResponse(status: number, payload: unknown): ApiClientError {
  const code = isErrorEnvelope(payload) ? payload.error.code : undefined;
  const details = isErrorEnvelope(payload) ? payload.error.details : undefined;

  if (status === 401) {
    return new ApiClientError({
      kind: "unauthorized",
      status,
      code,
      details,
      message: "Your saved session is unavailable.",
    });
  }
  if (status === 403) {
    return new ApiClientError({
      kind: "forbidden",
      status,
      code,
      details,
      message: "The protected request was not permitted.",
    });
  }
  if (status === 404) {
    return new ApiClientError({
      kind: "not_found",
      status,
      code,
      details,
      message: "We could not find that game.",
    });
  }
  if (status === 409) {
    return new ApiClientError({
      kind: "conflict",
      status,
      code,
      details,
      message: "Saved personalization needs attention before continuing.",
    });
  }
  if (status === 422) {
    return new ApiClientError({
      kind: "validation",
      status,
      code,
      details,
      message: "The catalog request contains an invalid value.",
    });
  }
  if (status === 503 || status >= 500) {
    return new ApiClientError({
      kind: "unavailable",
      status,
      code,
      details,
      message: "The game catalog is temporarily unavailable.",
    });
  }
  return new ApiClientError({
    kind: "unexpected",
    status,
    code,
    details,
    message: "The catalog request could not be completed.",
  });
}

export function normalizeRequestError(error: unknown): ApiClientError {
  if (error instanceof ApiClientError) {
    return error;
  }
  if (error instanceof DOMException && error.name === "AbortError") {
    return new ApiClientError({
      kind: "aborted",
      message: "The request was cancelled.",
      cause: error,
    });
  }
  return new ApiClientError({
    kind: "network",
    message: "We could not connect to the game catalog.",
    cause: error,
  });
}
