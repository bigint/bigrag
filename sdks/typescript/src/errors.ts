export class BigRAGError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "BigRAGError";
  }
}

export class APIError extends BigRAGError {
  readonly status: number;
  readonly code: string | undefined;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.code = code;
  }
}

export class BadRequestError extends APIError {
  constructor(message: string, code?: string) {
    super(400, message, code);
    this.name = "BadRequestError";
  }
}

export class AuthenticationError extends APIError {
  constructor(message: string, code?: string) {
    super(401, message, code);
    this.name = "AuthenticationError";
  }
}

export class NotFoundError extends APIError {
  constructor(message: string, code?: string) {
    super(404, message, code);
    this.name = "NotFoundError";
  }
}

export class RateLimitError extends APIError {
  constructor(message: string, code?: string) {
    super(429, message, code);
    this.name = "RateLimitError";
  }
}

export class InternalServerError extends APIError {
  constructor(message: string, code?: string) {
    super(500, message, code);
    this.name = "InternalServerError";
  }
}

export class APIConnectionError extends BigRAGError {
  constructor(message: string = "Connection error") {
    super(message);
    this.name = "APIConnectionError";
  }
}

export class APITimeoutError extends BigRAGError {
  constructor(message: string = "Request timed out") {
    super(message);
    this.name = "APITimeoutError";
  }
}

const STATUS_MAP: Record<number, new (message: string, code?: string) => APIError> = {
  400: BadRequestError,
  401: AuthenticationError,
  404: NotFoundError,
  429: RateLimitError,
  500: InternalServerError,
};

export function errorForStatus(
  status: number,
  message: string,
  code?: string,
): APIError {
  const Cls = STATUS_MAP[status];
  if (Cls) return new Cls(message, code);
  return new APIError(status, message, code);
}
