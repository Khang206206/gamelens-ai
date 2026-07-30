export type ApiErrorKind =
  | "aborted"
  | "network"
  | "invalid_response"
  | "validation"
  | "not_found"
  | "unavailable"
  | "unexpected";

interface ApiClientErrorOptions {
  kind: ApiErrorKind;
  message: string;
  status?: number;
  code?: string;
  cause?: unknown;
}

export class ApiClientError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  readonly code?: string;

  constructor({ kind, message, status, code, cause }: ApiClientErrorOptions) {
    super(message, { cause });
    this.name = "ApiClientError";
    this.kind = kind;
    this.status = status;
    this.code = code;
  }
}

interface ErrorEnvelope {
  error: {
    code: string;
    message: string;
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

  if (status === 404) {
    return new ApiClientError({
      kind: "not_found",
      status,
      code,
      message: "We could not find that game.",
    });
  }
  if (status === 422) {
    return new ApiClientError({
      kind: "validation",
      status,
      code,
      message: "The catalog request contains an invalid value.",
    });
  }
  if (status === 503 || status >= 500) {
    return new ApiClientError({
      kind: "unavailable",
      status,
      code,
      message: "The game catalog is temporarily unavailable.",
    });
  }
  return new ApiClientError({
    kind: "unexpected",
    status,
    code,
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
