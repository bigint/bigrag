/**
 * Base error class for all bigRAG errors.
 */
export class BigRAGError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "BigRAGError";
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/**
 * Error returned by the bigRAG API.
 */
export class APIError extends BigRAGError {
  public readonly status: number;
  public readonly code?: string;

  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = "APIError";
    this.status = status;
    this.code = code;
  }
}

/**
 * 400 Bad Request — the request was malformed or invalid.
 */
export class BadRequestError extends APIError {
  constructor(message: string, code?: string) {
    super(400, message, code);
    this.name = "BadRequestError";
  }
}

/**
 * 401 Unauthorized — missing or invalid API key.
 */
export class AuthenticationError extends APIError {
  constructor(message: string, code?: string) {
    super(401, message, code);
    this.name = "AuthenticationError";
  }
}

/**
 * 404 Not Found — the requested resource does not exist.
 */
export class NotFoundError extends APIError {
  constructor(message: string, code?: string) {
    super(404, message, code);
    this.name = "NotFoundError";
  }
}

/**
 * 429 Too Many Requests — rate limit exceeded.
 */
export class RateLimitError extends APIError {
  constructor(message: string, code?: string) {
    super(429, message, code);
    this.name = "RateLimitError";
  }
}

/**
 * 500 Internal Server Error — something went wrong on the server.
 */
export class InternalServerError extends APIError {
  constructor(message: string, code?: string) {
    super(500, message, code);
    this.name = "InternalServerError";
  }
}

/**
 * Failed to establish a connection to the server.
 */
export class ConnectionError extends BigRAGError {
  constructor(message: string) {
    super(message);
    this.name = "ConnectionError";
  }
}

/**
 * The request timed out.
 */
export class TimeoutError extends BigRAGError {
  constructor(message: string) {
    super(message);
    this.name = "TimeoutError";
  }
}

/**
 * Map an HTTP status code to the appropriate error class.
 */
export function errorForStatus(status: number, message: string, code?: string): APIError {
  switch (status) {
    case 400:
      return new BadRequestError(message, code);
    case 401:
      return new AuthenticationError(message, code);
    case 404:
      return new NotFoundError(message, code);
    case 429:
      return new RateLimitError(message, code);
    case 500:
      return new InternalServerError(message, code);
    default:
      return new APIError(status, message, code);
  }
}
