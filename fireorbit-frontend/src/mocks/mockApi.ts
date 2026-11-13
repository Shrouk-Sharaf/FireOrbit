import type {
  ChatApi,
  ChatRequest,
  ChatResponse,
  ConversationDetail,
  ConversationSummary,
  StoredMessage,
} from '../types';
import { ApiError } from '../services/httpClient';
import { MOCK_ERROR_TRIGGER, fallbackAnswer, mockTopics } from './mockData';

/**
 * Mock implementation of ChatApi. Persists conversations in localStorage so history survives reloads.
 * Keep this file free of UI imports.
 */
const STORAGE_KEY = 'fireorbit.mock.conversations.v1';

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
    /* storage full or unavailable; mock history just won't persist */
  }
}

export function clearMockConversations(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

function delay(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException('Aborted', 'AbortError'));
    const timer = setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(timer);
      reject(new DOMException('Aborted', 'AbortError'));
    };
    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

function pickTopic(question: string) {
  const q = question.toLowerCase();
  let best: { topic: (typeof mockTopics)[number]; score: number } | null = null;
  for (const topic of mockTopics) {
    const score = topic.keywords.reduce((n, k) => (q.includes(k) ? n + 1 : n), 0);
    if (score > 0 && (!best || score > best.score)) best = { topic, score };
  }
  return best?.topic ?? null;
}

function newId(): string {
  return `mock_conv_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

function makeTitle(question: string): string {
  const t = question.trim().replace(/\s+/g, ' ');
  return t.length > 48 ? `${t.slice(0, 47)}…` : t;
}

export const mockApi: ChatApi = {
  async sendChat(req: ChatRequest, opts): Promise<ChatResponse> {
    await delay(700 + Math.random() * 800, opts?.signal);

    if (req.question.toLowerCase().includes(MOCK_ERROR_TRIGGER)) {
      throw new ApiError('Mock error: simulated backend failure (500).', 500);
    }

    const topic = pickTopic(req.question);
    const answer = topic ? topic.answer : fallbackAnswer(req.question);
    const sources = topic ? topic.sources.map((s) => ({ ...s, is_mock: true })) : [];

    const all = readAll();
    const now = new Date().toISOString();
    let conv = req.conversation_id ? all.find((c) => c.id === req.conversation_id) : undefined;
    if (!conv) {
      conv = {
        id: req.conversation_id ?? newId(),
        title: makeTitle(req.question),
        messages: [],
        updated_at: now,
      };
      all.push(conv);
    }

    // Regenerate support: if the same question was just answered, replace that answer instead of duplicating it.
    const msgs = conv.messages;
    const last = msgs[msgs.length - 1];
    const prev = msgs[msgs.length - 2];
    if (last?.role === 'assistant' && prev?.role === 'user' && prev.content === req.question) {
      msgs.pop();
    } else {
      msgs.push({ role: 'user', content: req.question, created_at: now });
    }
    msgs.push({ role: 'assistant', content: answer, sources, created_at: now });
    conv.updated_at = now;
    writeAll(all);

    return { answer, conversation_id: conv.id, sources };
  },

  async listConversations(): Promise<ConversationSummary[]> {
    await delay(150);
    return readAll()
      .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
      .map(({ id, title, updated_at }) => ({ id, title, updated_at }));
  },

  async getConversation(id: string): Promise<ConversationDetail> {
    await delay(150);
    const conv = readAll().find((c) => c.id === id);
    if (!conv) throw new ApiError('Conversation not found.', 404);
    const messages: StoredMessage[] = conv.messages;
    return { id: conv.id, title: conv.title, messages };
  },

  async health() {
    return { status: 'mock' };
  },
};
