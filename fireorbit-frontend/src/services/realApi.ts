import type {
  ChatApi,
  ChatRequest,
  ChatResponse,
  ConversationDetail,
  ConversationSummary,
  HealthStatus,
  Source,
} from '../types';
import { request } from './httpClient';

/**
 * Real FastAPI implementation. Endpoint paths and response shapes are PROPOSED, not confirmed.
 * If the backend differs, adapt here only; UI code depends on the ChatApi interface.
 */
const ENDPOINTS = {
  chat: '/api/chat',
  conversations: '/api/conversations',
  conversation: (id: string) => `/api/conversations/${encodeURIComponent(id)}`,
  health: '/health',
} as const;

function normalizeSources(raw: unknown): Source[] {
  if (!Array.isArray(raw)) return [];
  return raw.map((s, i) => {
    const r = (s ?? {}) as Partial<Source>;
    return {
      document: r.document ?? 'Unknown document',
      page: typeof r.page === 'number' ? r.page : null,
      chunk_id: r.chunk_id ?? `chunk_${i + 1}`,
      content: r.content ?? '',
    };
  });
}

export const realApi: ChatApi = {
  async sendChat(req: ChatRequest, opts): Promise<ChatResponse> {
    const res = await request<Partial<ChatResponse>>(ENDPOINTS.chat, {
      method: 'POST',
      body: JSON.stringify(req),
      signal: opts?.signal,
    });
    return {
      answer: res.answer ?? '',
      conversation_id: res.conversation_id ?? req.conversation_id ?? '',
      sources: normalizeSources(res.sources),
    };
  },

  async listConversations(): Promise<ConversationSummary[]> {
    const res = await request<ConversationSummary[] | { conversations: ConversationSummary[] }>(
      ENDPOINTS.conversations,
    );
    return Array.isArray(res) ? res : (res.conversations ?? []);
  },

  async getConversation(id: string): Promise<ConversationDetail> {
    const res = await request<Partial<ConversationDetail>>(ENDPOINTS.conversation(id));
    return {
      id: res.id ?? id,
      title: res.title ?? 'Conversation',
      messages: (res.messages ?? []).map((m) => ({ ...m, sources: normalizeSources(m.sources) })),
    };
  },

  health(): Promise<HealthStatus> {
    return request<HealthStatus>(ENDPOINTS.health);
  },
};
