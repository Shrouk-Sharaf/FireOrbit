/** A retrieved passage backing an answer. Mirrors the proposed `sources[]` contract. */
export interface Source {
  document: string;
  page: number | null;
  chunk_id: string;
  content: string;
  /** Set only by the mock API so the UI can label placeholder sources. */
  is_mock?: boolean;
}

/** POST /api/chat request body (proposed contract). */
export interface ChatRequest {
  question: string;
  conversation_id: string | null;
}

/** POST /api/chat response body (proposed contract). */
export interface ChatResponse {
  answer: string;
  conversation_id: string;
  sources: Source[];
}

/** GET /api/conversations item (proposed shape, not confirmed by backend). */
export interface ConversationSummary {
  id: string;
  title: string;
  updated_at: string;
}

/** A message as persisted by the backend / mock store. */
export interface StoredMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  created_at?: string;
}

/** GET /api/conversations/{id} response (proposed shape, not confirmed by backend). */
export interface ConversationDetail {
  id: string;
  title: string;
  messages: StoredMessage[];
}

/** GET /health response. Any 2xx is treated as healthy; `status` is optional. */
export interface HealthStatus {
  status?: string;
}

/** A message as held in UI state. */
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources: Source[];
  /** 'error' messages render as an error card with a retry action. */
  status: 'done' | 'error';
  /** True when the answer came from the mock API. */
  mock?: boolean;
  created_at: string;
}

export interface Settings {
  /** Open source passages automatically when an answer has citations. */
  expandSources: boolean;
}

/** Single seam between UI and data. Real and mock implementations share it. */
export interface ChatApi {
  sendChat(req: ChatRequest, opts?: { signal?: AbortSignal }): Promise<ChatResponse>;
  listConversations(): Promise<ConversationSummary[]>;
  getConversation(id: string): Promise<ConversationDetail>;
  health(): Promise<HealthStatus>;
}
