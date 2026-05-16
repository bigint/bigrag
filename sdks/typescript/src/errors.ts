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

export function errorForStatus(status: number, message: string, code?: string): APIError {
  return new APIError(status, message, code);
}
