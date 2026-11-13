import { useEffect, useRef } from 'react';
import type { Message } from '../types';
import { MessageBubble } from './MessageBubble';
import { Logo } from './Logo';
import { AlertIcon } from './Icons';

interface Props {
  messages: Message[];
  isSending: boolean;
  isOpening: boolean;
  openError: string | null;
  expandSources: boolean;
  onRetry: (assistantId: string) => void;
}

function Thinking() {
  return (
    <div className="msg msg--assistant" role="status" aria-label="FireOrbit is searching documents">
      <div className="msg__avatar"><Logo size={24} withWordmark={false} /></div>
      <div className="msg__body">
        <div className="typing">
          <span /><span /><span />
          <em>Searching documents…</em>
        </div>
      </div>
    </div>
  );
}

export function ChatWindow({ messages, isSending, isOpening, openError, expandSources, onRetry }: Props) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: 'end' });
  }, [messages, isSending, isOpening]);

  if (openError) {
    return (
      <div className="thread">
        <div className="error-card" role="alert">
          <AlertIcon size={18} />
          <div className="error-card__text">
            <strong>Couldn&apos;t open this conversation</strong>
            <p>{openError}</p>
          </div>
        </div>
      </div>
    );
  }

  if (isOpening) {
    return (
      <div className="thread">
        <p className="thread__loading" role="status">Loading conversation…</p>
      </div>
    );
  }

  const lastIdx = messages.length - 1;
  return (
    <div className="thread" role="log" aria-live="polite" aria-label="Conversation">
      {messages.map((m, i) => (
        <MessageBubble
          key={m.id}
          message={m}
          isLast={i === lastIdx}
          busy={isSending}
          expandSources={expandSources}
          onRetry={onRetry}
        />
      ))}
      {isSending && <Thinking />}
      <div ref={endRef} />
    </div>
  );
}
