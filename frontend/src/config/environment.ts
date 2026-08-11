export interface FrontendEnvironmentInput {
  readonly VITE_API_BASE_URL?: string;
}

export interface FrontendEnvironment {
  readonly apiBaseUrl: string;
}

const ABSOLUTE_HTTP_PROTOCOLS = new Set(['http:', 'https:']);

function withoutTrailingSlashes(value: string): string {
  return value.replace(/\/+$/, '');
}

function invalidApiBaseUrl(): Error {
  return new Error(
    'VITE_API_BASE_URL must be an HTTP(S) URL or an origin-relative path.',
  );
}

export function normalizeApiBaseUrl(value: string | undefined): string {
  const candidate = value?.trim() ?? '';
  if (candidate === '') {
    return '';
  }

  if (candidate.startsWith('/')) {
    if (
      candidate.startsWith('//') ||
      candidate.includes('\\') ||
      candidate.includes('?') ||
      candidate.includes('#')
    ) {
      throw invalidApiBaseUrl();
    }
    return withoutTrailingSlashes(candidate);
  }

  let parsed: URL;
  try {
    parsed = new URL(candidate);
  } catch {
    throw invalidApiBaseUrl();
  }

  if (
    !ABSOLUTE_HTTP_PROTOCOLS.has(parsed.protocol) ||
    parsed.username !== '' ||
    parsed.password !== '' ||
    parsed.search !== '' ||
    parsed.hash !== ''
  ) {
    throw invalidApiBaseUrl();
  }

  return withoutTrailingSlashes(parsed.href);
}

export function readFrontendEnvironment(
  input: FrontendEnvironmentInput,
): FrontendEnvironment {
  return Object.freeze({
    apiBaseUrl: normalizeApiBaseUrl(input.VITE_API_BASE_URL),
  });
}

export const frontendEnvironment = readFrontendEnvironment(import.meta.env);
