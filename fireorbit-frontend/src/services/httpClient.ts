import { config } from './config';

export class ApiError extends Error {
  readonly status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export function isAbortError(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'AbortError';
}

const REQUEST_TIMEOUT_MS = 60_000;

/** Pull a readable message out of FastAPI-style error bodies ({ detail: string | [...] }). */
async function readErrorDetail(res: Response): Promise<string | undefined> {
  try {
    const body: unknown = await res.json();
    if (body && typeof body === 'object' && 'detail' in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === 'string') return detail;
      if (Array.isArray(detail)) {
        return detail
          .map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : ''))
          .filter(Boolean)
          .join('; ');
      }
    }
  } catch {
    /* body was not JSON */
  }
  return undefined;
}

export async function request<T>(
  path: string,
  init: RequestInit & { signal?: AbortSignal } = {},
): Promise<T> {
  const timeout = new AbortController();
  const timer = setTimeout(() => timeout.abort(), REQUEST_TIMEOUT_MS);
  const external = init.signal ?? undefined;
  const onExternalAbort = () => timeout.abort();
  external?.addEventListener('abort', onExternalAbort);

  try {
    const res = await fetch(`${config.apiBaseUrl}${path}`, {
      ...init,
      signal: timeout.signal,
      headers: { 'Content-Type': 'application/json', Accept: 'application/json', ...init.headers },
    });
    if (!res.ok) {
      const detail = await readErrorDetail(res);
      throw new ApiError(detail ?? `Request failed (${res.status} ${res.statusText}).`, res.status);
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (isAbortError(err)) {
      if (external?.aborted) throw err; // user cancelled
      throw new ApiError('The request timed out. The backend took too long to respond.');
    }
    throw new ApiError(
      `Could not reach the backend at ${config.apiBaseUrl}. Check that it is running and that CORS allows this origin.`,
    );
  } finally {
    clearTimeout(timer);
    external?.removeEventListener('abort', onExternalAbort);
  }
}
