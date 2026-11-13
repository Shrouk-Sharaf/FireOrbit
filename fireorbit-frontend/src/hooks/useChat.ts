import { useCallback, useEffect, useRef, useState } from 'react';
import { api, config } from '../services/api';
import { isAbortError } from '../services/httpClient';
import type { ChatResponse, ConversationSummary, Message } from '../types';
import { errorMessage, uid } from '../utils/helpers';

type LoadState = 'loading' | 'ready' | 'error';

function userMessage(content: string): Message {
  return { id: uid(), role: 'user', content, sources: [], status: 'done', created_at: new Date().toISOString() };
}

function assistantMessage(res: ChatResponse): Message {
  return {
    id: uid(),
    role: 'assistant',
    content: res.answer,
    sources: res.sources,
    status: 'done',
    mock: config.useMock,
    created_at: new Date().toISOString(),
  };
}

function failedMessage(text: string): Message {
  return { id: uid(), role: 'assistant', content: text, sources: [], status: 'error', created_at: new Date().toISOString() };
}

/** All chat state and actions. Components stay presentational; services stay UI-agnostic. */
export function useChat() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationsState, setConversationsState] = useState<LoadState>('loading');
  const [activeId, setActiveIdState] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [isOpeningConversation, setIsOpeningConversation] = useState(false);
  const [openError, setOpenError] = useState<string | null>(null);

  const activeIdRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  /** Bumped whenever the visible conversation changes, so late responses from old requests are dropped. */
  const epochRef = useRef(0);

  const setActiveId = useCallback((id: string | null) => {
    activeIdRef.current = id;
    setActiveIdState(id);
  }, []);

  const refreshConversations = useCallback(async () => {
    try {
      const list = await api.listConversations();
      setConversations(list);
      setConversationsState('ready');
    } catch {
      setConversationsState('error');
    }
  }, []);

  useEffect(() => {
    void refreshConversations();
  }, [refreshConversations]);

  const resetContext = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    epochRef.current += 1;
    setIsSending(false);
    setIsOpeningConversation(false);
    setOpenError(null);
  }, []);

  const newChat = useCallback(() => {
    resetContext();
    setActiveId(null);
    setMessages([]);
  }, [resetContext, setActiveId]);

  const selectConversation = useCallback(
    async (id: string) => {
      if (id === activeIdRef.current) return;
      resetContext();
      const epoch = epochRef.current;
      setActiveId(id);
      setMessages([]);
      setIsOpeningConversation(true);
      try {
        const detail = await api.getConversation(id);
        if (epoch !== epochRef.current) return;
        setMessages(
          detail.messages.map((m) => ({
            id: uid(),
            role: m.role,
            content: m.content,
            sources: m.sources ?? [],
            status: 'done' as const,
            mock: config.useMock,
            created_at: m.created_at ?? new Date().toISOString(),
          })),
        );
      } catch (err) {
        if (epoch !== epochRef.current) return;
        setOpenError(errorMessage(err));
      } finally {
        if (epoch === epochRef.current) setIsOpeningConversation(false);
      }
    },
    [resetContext, setActiveId],
  );

  /** Sends `question` and shows `base` (history ending with that question) while waiting. */
  const run = useCallback(
    async (question: string, base: Message[]) => {
      const epoch = epochRef.current;
      const controller = new AbortController();
      abortRef.current = controller;
      setMessages(base);
      setIsSending(true);
      try {
        const res = await api.sendChat(
          { question, conversation_id: activeIdRef.current },
          { signal: controller.signal },
        );
        if (epoch !== epochRef.current) return;
        if (res.conversation_id) setActiveId(res.conversation_id);
        setMessages([...base, assistantMessage(res)]);
        void refreshConversations();
      } catch (err) {
        if (epoch !== epochRef.current) return;
        setMessages([...base, failedMessage(isAbortError(err) ? 'Request cancelled.' : errorMessage(err))]);
      } finally {
        if (epoch === epochRef.current) {
          setIsSending(false);
          abortRef.current = null;
        }
      }
    },
    [refreshConversations, setActiveId],
  );

  const send = useCallback(
    (text: string) => {
      const question = text.trim();
      if (!question || isSending) return;
      void run(question, [...messages, userMessage(question)]);
    },
    [isSending, messages, run],
  );

  /** Re-asks the user question that precedes `assistantId` and replaces that answer. */
  const retryFrom = useCallback(
    (assistantId: string) => {
      if (isSending) return;
      const idx = messages.findIndex((m) => m.id === assistantId);
      if (idx < 1) return;
      const asked = messages[idx - 1];
      if (asked.role !== 'user') return;
      void run(asked.content, messages.slice(0, idx));
    },
    [isSending, messages, run],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  return {
    conversations,
    conversationsState,
    activeId,
    messages,
    isSending,
    isOpeningConversation,
    openError,
    newChat,
    selectConversation,
    send,
    retryFrom,
    stop,
    refreshConversations,
  };
}
