import type { HealthState } from '../hooks/useHealth';
import type { ConversationSummary } from '../types';
import { relativeTime } from '../utils/helpers';
import { CloseIcon, MessageIcon, PlusIcon, SlidersIcon } from './Icons';
import { Logo } from './Logo';

interface Props {
  conversations: ConversationSummary[];
  loadState: 'loading' | 'ready' | 'error';
  activeId: string | null;
  health: HealthState;
  open: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onSelect: (id: string) => void;
  onRetryLoad: () => void;
  onOpenSettings: () => void;
}

const STATUS_LABEL: Record<HealthState, string> = {
  mock: 'Mock mode',
  checking: 'Checking backend…',
  online: 'Backend online',
  offline: 'Backend offline',
};

export function Sidebar({
  conversations,
  loadState,
  activeId,
  health,
  open,
  onClose,
  onNewChat,
  onSelect,
  onRetryLoad,
  onOpenSettings,
}: Props) {
  return (
    <>
      <div className={`scrim ${open ? 'scrim--show' : ''}`} onClick={onClose} aria-hidden="true" />
      <aside className={`sidebar ${open ? 'sidebar--open' : ''}`} aria-label="Sidebar">
        <div className="sidebar__top">
          <Logo />
          <button type="button" className="icon-btn sidebar__close" onClick={onClose} aria-label="Close sidebar">
            <CloseIcon size={18} />
          </button>
        </div>

        <button type="button" className="btn btn--primary sidebar__new" onClick={onNewChat}>
          <PlusIcon size={16} /> New chat
        </button>

        <nav className="sidebar__history" aria-label="Conversation history">
          <h2 className="sidebar__heading">History</h2>
          {loadState === 'loading' && <p className="sidebar__empty">Loading conversations…</p>}
          {loadState === 'error' && (
            <div className="sidebar__empty">
              <p>Couldn&apos;t load conversations.</p>
              <button type="button" className="btn btn--ghost" onClick={onRetryLoad}>Retry</button>
            </div>
          )}
          {loadState === 'ready' && conversations.length === 0 && (
            <p className="sidebar__empty">No conversations yet. Ask your first question.</p>
          )}
          {loadState === 'ready' && conversations.length > 0 && (
            <ul className="history">
              {conversations.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    className={`history__item ${c.id === activeId ? 'history__item--active' : ''}`}
                    aria-current={c.id === activeId ? 'true' : undefined}
                    onClick={() => onSelect(c.id)}
                  >
                    <MessageIcon size={15} />
                    <span className="history__title">{c.title}</span>
                    <span className="history__time">{relativeTime(c.updated_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </nav>

        <div className="sidebar__footer">
          <span className={`status status--${health}`} role="status">
            <span className="status__dot" aria-hidden="true" />
            {STATUS_LABEL[health]}
          </span>
          <button type="button" className="btn btn--ghost" onClick={onOpenSettings}>
            <SlidersIcon size={16} /> Settings
          </button>
        </div>
      </aside>
    </>
  );
}
