import { useEffect, useRef, useState } from 'react';
import type { Message } from '../types';
import { copyText } from '../utils/helpers';
import { AlertIcon, CheckIcon, CopyIcon, RefreshIcon } from './Icons';
import { Logo } from './Logo';
import { MarkdownContent } from './MarkdownContent';
import { SourceCitations } from './SourceCitations';

interface Props {
  message: Message;
  isLast: boolean;
  busy: boolean;
  expandSources: boolean;
  onRetry: (assistantId: string) => void;
}

export function MessageBubble({ message, isLast, busy, expandSources, onRetry }: Props) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  if (message.role === 'user') {
    return (
      <div className="msg msg--user">
        <div className="msg__bubble msg__bubble--user">{message.content}</div>
      </div>
    );
  }

  if (message.status === 'error') {
    return (
      <div className="msg msg--assistant">
        <div className="msg__avatar"><Logo size={24} withWordmark={false} /></div>
        <div className="msg__body">
          <div className="error-card" role="alert">
            <AlertIcon size={18} />
            <div className="error-card__text">
              <strong>Couldn&apos;t get an answer</strong>
              <p>{message.content}</p>
            </div>
            {/* Only the newest message can be retried; retrying rewinds the thread to this point. */}
            {isLast && (
              <button type="button" className="btn btn--ghost" onClick={() => onRetry(message.id)} disabled={busy}>
                <RefreshIcon size={15} /> Retry
              </button>
            )}
          </div>
        </div>
      </div>
    );
  }

  const handleCopy = async () => {
    if (await copyText(message.content)) {
      setCopied(true);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(false), 1800);
    }
  };

  return (
    <div className="msg msg--assistant">
      <div className="msg__avatar"><Logo size={24} withWordmark={false} /></div>
      <div className="msg__body">
        <div className="msg__meta">
          <span className="msg__author">FireOrbit</span>
          {message.mock && <span className="chip chip--mock">Mock response</span>}
        </div>
        <MarkdownContent>{message.content}</MarkdownContent>
        <SourceCitations
          // Remount when the setting flips so the new default applies to already-rendered answers.
          key={String(expandSources)}
          sources={message.sources}
          defaultOpen={expandSources}
        />
        <div className="msg__actions">
          <button type="button" className="icon-btn" onClick={handleCopy} aria-label="Copy answer" title="Copy answer">
            {copied ? <CheckIcon size={16} /> : <CopyIcon size={16} />}
            <span className="icon-btn__label" aria-live="polite">{copied ? 'Copied' : 'Copy'}</span>
          </button>
          {isLast && (
            <button
              type="button"
              className="icon-btn"
              onClick={() => onRetry(message.id)}
              disabled={busy}
              aria-label="Regenerate answer"
              title="Regenerate answer"
            >
              <RefreshIcon size={16} />
              <span className="icon-btn__label">Regenerate</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
