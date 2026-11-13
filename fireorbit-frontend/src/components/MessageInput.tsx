import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { SendIcon, StopIcon } from './Icons';

interface Props {
  isSending: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
  /** Changing this value focuses the textarea (e.g. when switching conversation). */
  focusKey?: string | null;
}

const MAX_HEIGHT_PX = 200;

export function MessageInput({ isSending, onSend, onStop, focusKey }: Props) {
  const [value, setValue] = useState('');
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, MAX_HEIGHT_PX)}px`;
  }, [value]);

  useEffect(() => {
    ref.current?.focus();
  }, [focusKey]);

  const submit = () => {
    const text = value.trim();
    if (!text || isSending) return;
    onSend(text);
    setValue('');
  };

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="composer">
      <div className="composer__box">
        <textarea
          ref={ref}
          className="composer__input"
          rows={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask about combustion science research…"
          aria-label="Message FireOrbit"
        />
        {isSending ? (
          <button type="button" className="composer__btn composer__btn--stop" onClick={onStop} aria-label="Stop generating" title="Stop">
            <StopIcon size={16} />
          </button>
        ) : (
          <button
            type="button"
            className="composer__btn"
            onClick={submit}
            disabled={!value.trim()}
            aria-label="Send message"
            title="Send (Enter)"
          >
            <SendIcon size={18} />
          </button>
        )}
      </div>
      <p className="composer__hint">
        Enter to send, Shift+Enter for a new line. FireOrbit can make mistakes; verify against the cited sources.
      </p>
    </div>
  );
}
