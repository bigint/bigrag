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

export class PermissionDeniedError extends APIError {
  constructor(message: string, code?: string) {
    super(403, message, code);
    this.name = "PermissionDeniedError";
  }
}

export class NotFoundError extends APIError {
  constructor(message: string, code?: string) {
    super(404, message, code);
    this.name = "NotFoundError";
  }
}

export class ConflictError extends APIError {
  constructor(message: string, code?: string) {
    super(409, message, code);
    this.name = "ConflictError";
  }
}

export class PayloadTooLargeError extends APIError {
  constructor(message: string, code?: string) {
    super(413, message, code);
    this.name = "PayloadTooLargeError";
  }
}

export class UnprocessableEntityError extends APIError {
  constructor(message: string, code?: string) {
    super(422, message, code);
    this.name = "UnprocessableEntityError";
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

export class BadGatewayError extends APIError {
  constructor(message: string, code?: string) {
    super(502, message, code);
    this.name = "BadGatewayError";
  }
}

export class ServiceUnavailableError extends APIError {
  constructor(message: string, code?: string) {
    super(503, message, code);
    this.name = "ServiceUnavailableError";
  }
}

export function errorForStatus(status: number, message: string, code?: string): APIError {
  switch (status) {
    case 400:
      return new BadRequestError(message, code);
    case 401:
      return new AuthenticationError(message, code);
    case 403:
      return new PermissionDeniedError(message, code);
    case 404:
      return new NotFoundError(message, code);
    case 409:
      return new ConflictError(message, code);
    case 413:
      return new PayloadTooLargeError(message, code);
    case 422:
      return new UnprocessableEntityError(message, code);
    case 429:
      return new RateLimitError(message, code);
    case 500:
      return new InternalServerError(message, code);
    case 502:
      return new BadGatewayError(message, code);
    case 503:
      return new ServiceUnavailableError(message, code);
    default:
      return new APIError(status, message, code);
  }
}
