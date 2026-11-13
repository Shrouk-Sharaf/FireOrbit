import type {
  ChatApi,
  ChatRequest,
  ChatResponse,
  ConversationDetail,
  ConversationSummary,
  HealthStatus,
  Source,
  StoredMessage,
} from '../types';
import { ApiError, request } from './httpClient';

/**
 * Real FastAPI implementation, matched to the FireOrbit backend (backend/routers/ai.py).
 *
 * - POST /api/chat   -> { answer | null, llm, retrieval, sources: [{ label, psi_id, file, page, chunk_id, content }], passages?, note? }
 * - GET  /health     -> { status: "ok", ... }
 * - The backend is stateless and has NO conversations endpoints, so chat history is kept in
 *   localStorage here. UI code still only depends on the ChatApi interface.
 */
const ENDPOINTS = {
  chat: '/api/chat',
  health: '/health',
} as const;

const STORAGE_KEY = 'fireorbit.live.conversations.v1';

/* ---------- backend response shapes (all fields optional on purpose) ---------- */

interface BackendSource {
  label?: string;
  psi_id?: string | null;
  file?: string | null;
  page?: number | string | null;
  chunk_id?: string;
  content?: string;
  text?: string;
}

interface BackendChatResponse {
  answer?: string | null;
  llm?: boolean;
  retrieval?: string;
  sources?: BackendSource[];
  passages?: string[];
  note?: string;
}

/* ---------- mapping ---------- */

function toPage(p: BackendSource['page']): number | null {
  if (typeof p === 'number') return p;
  if (typeof p === 'string' && p.trim() !== '' && !Number.isNaN(Number(p))) return Number(p);
  return null;
}

function normalizeSources(raw: unknown, passages: string[] = []): Source[] {
  if (!Array.isArray(raw)) return [];
  return (raw as BackendSource[]).map((s, i) => {
    const r = s ?? {};
    return {
      document: r.label ?? r.psi_id ?? r.file ?? 'Unknown document',
      page: toPage(r.page),
      chunk_id: r.chunk_id ?? `chunk_${i + 1}`,
      content: r.content ?? r.text ?? passages[i] ?? '',
    };
  });
}

/** When the backend has no LLM key it returns passages only; show them as a readable answer. */
function fallbackAnswer(res: BackendChatResponse, sources: Source[]): string {
  const intro =
    res.note ??
    'AI answer generation is not configured on the backend, so these are the most relevant passages found.';
  if (sources.length === 0) {
    return `${intro}\n\nNo relevant passages were found for this question. Try rephrasing it with specific terms (e.g. a PSI id, fuel, or material).`;
  }
  const list = sources
    .map((s, i) => `${i + 1}. **${s.document}${s.page ? ` (p.${s.page})` : ''}**: ${s.content.replace(/\s+/g, ' ').slice(0, 280)}…`)
    .join('\n');
  return `${intro}\n\n${list}`;
}

/* ---------- local conversation history ---------- */

interface StoredConversation extends ConversationDetail {
  updated_at: string;
}

function readAll(): StoredConversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredConversation[]) : [];
  } catch {
    return [];
  }
}

function writeAll(items: StoredConversation[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  } catch {
    /* storage full or unavailable; history just won't persist */
  }
}

export function clearLiveConversations(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

function newId(): string {
  return `conv_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

function makeTitle(question: string): string {
  const t = question.trim().replace(/\s+/g, ' ');
  return t.length > 48 ? `${t.slice(0, 47)}…` : t;
}

function saveTurn(conversationId: string | null, question: string, answer: string, sources: Source[]): string {
  const all = readAll();
  const now = new Date().toISOString();
  let conv = conversationId ? all.find((c) => c.id === conversationId) : undefined;
  if (!conv) {
    conv = { id: conversationId ?? newId(), title: makeTitle(question), messages: [], updated_at: now };
    all.push(conv);
  }
  const msgs: StoredMessage[] = conv.messages;
  const last = msgs[msgs.length - 1];
  const prev = msgs[msgs.length - 2];
  // Regenerate: same question asked again -> replace the previous answer instead of duplicating the turn.
  if (last?.role === 'assistant' && prev?.role === 'user' && prev.content === question) {
    msgs.pop();
  } else {
    msgs.push({ role: 'user', content: question, created_at: now });
  }
  msgs.push({ role: 'assistant', content: answer, sources, created_at: now });
  conv.updated_at = now;
  writeAll(all);
  return conv.id;
}

/* ---------- ChatApi ---------- */

export const realApi: ChatApi = {
  async sendChat(req: ChatRequest, opts): Promise<ChatResponse> {
    // Backend requires question length >= 3 and ignores conversation_id (it is stateless).
    const res = await request<BackendChatResponse>(ENDPOINTS.chat, {
      method: 'POST',
      body: JSON.stringify({ question: req.question }),
      signal: opts?.signal,
    });
    const sources = normalizeSources(res.sources, res.passages);
    const answer = res.answer?.trim() ? res.answer : fallbackAnswer(res, sources);
    const conversation_id = saveTurn(req.conversation_id, req.question, answer, sources);
    return { answer, conversation_id, sources };
  },

  async listConversations(): Promise<ConversationSummary[]> {
    return readAll()
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
      .map(({ id, title, updated_at }) => ({ id, title, updated_at }));
  },

  async getConversation(id: string): Promise<ConversationDetail> {
    const conv = readAll().find((c) => c.id === id);
    if (!conv) throw new ApiError('Conversation not found.', 404);
    return { id: conv.id, title: conv.title, messages: conv.messages };
  },

  health(): Promise<HealthStatus> {
    return request<HealthStatus>(ENDPOINTS.health);
  },
};
