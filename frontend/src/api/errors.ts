export type ApiErrorKind =
  | 'network'
  | 'timeout'
  | 'aborted'
  | 'http'
  | 'invalid_response';

interface ApiErrorOptions {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  readonly code?: string;
  readonly publicMessage?: string;
}

const SAFE_MESSAGES: Record<ApiErrorKind, string> = {
  network: 'Network request failed.',
  timeout: 'Request timed out.',
  aborted: 'Request was cancelled.',
  http: 'Backend request failed.',
  invalid_response: 'Backend response was invalid.',
};

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | undefined;
  readonly code: string | undefined;
  readonly publicMessage: string | undefined;

  constructor(options: ApiErrorOptions) {
    super(SAFE_MESSAGES[options.kind]);
    this.name = 'ApiError';
    this.kind = options.kind;
    this.status = options.status;
    this.code = options.code;
    this.publicMessage = options.publicMessage;
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}
