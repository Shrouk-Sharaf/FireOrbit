/**
 * Runtime configuration from Vite env vars.
 * Mock mode is ON unless VITE_USE_MOCK_API is explicitly "false", because the RAG backend isn't ready yet.
 */
export const config = {
  useMock: import.meta.env.VITE_USE_MOCK_API !== 'false',
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/+$/, ''),
} as const;
