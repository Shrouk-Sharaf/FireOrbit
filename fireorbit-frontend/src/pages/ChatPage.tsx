import { useCallback, useState } from 'react';
import { ChatWindow } from '../components/ChatWindow';
import { MenuIcon } from '../components/Icons';
import { MessageInput } from '../components/MessageInput';
import { SettingsModal } from '../components/SettingsModal';
import { Sidebar } from '../components/Sidebar';
import { WelcomeScreen } from '../components/WelcomeScreen';
import { useChat } from '../hooks/useChat';
import { useHealth } from '../hooks/useHealth';
import { useSettings } from '../hooks/useSettings';
import { clearMockConversations } from '../mocks/mockApi';
import { clearLiveConversations } from '../services/realApi';
import { config } from '../services/config';

export function ChatPage() {
  const chat = useChat();
  const { settings, update } = useSettings();
  const { state: health, check } = useHealth();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const closeSidebar = useCallback(() => setSidebarOpen(false), []);
  const closeSettings = useCallback(() => setSettingsOpen(false), []);

  const showWelcome = chat.messages.length === 0 && !chat.isSending && !chat.isOpeningConversation && !chat.openError;
  const title = chat.conversations.find((c) => c.id === chat.activeId)?.title ?? 'New chat';

  const handleClearMock = () => {
    clearMockConversations();
    clearLiveConversations();
    chat.newChat();
    void chat.refreshConversations();
  };

  return (
    <div className="app">
      <Sidebar
        conversations={chat.conversations}
        loadState={chat.conversationsState}
        activeId={chat.activeId}
        health={health}
        open={sidebarOpen}
        onClose={closeSidebar}
        onNewChat={() => {
          chat.newChat();
          closeSidebar();
        }}
        onSelect={(id) => {
          void chat.selectConversation(id);
          closeSidebar();
        }}
        onRetryLoad={() => void chat.refreshConversations()}
        onOpenSettings={() => {
          setSettingsOpen(true);
          closeSidebar();
        }}
      />

      <main className="main">
        <header className="topbar">
          <button type="button" className="icon-btn topbar__menu" onClick={() => setSidebarOpen(true)} aria-label="Open sidebar">
            <MenuIcon size={20} />
          </button>
          <h2 className="topbar__title">{title}</h2>
          {config.useMock && <span className="chip chip--mock">Mock mode</span>}
        </header>

        <div className="main__scroll">
          {showWelcome ? (
            <WelcomeScreen onPick={chat.send} />
          ) : (
            <ChatWindow
              messages={chat.messages}
              isSending={chat.isSending}
              isOpening={chat.isOpeningConversation}
              openError={chat.openError}
              expandSources={settings.expandSources}
              onRetry={chat.retryFrom}
            />
          )}
        </div>

        <MessageInput
          isSending={chat.isSending}
          onSend={chat.send}
          onStop={chat.stop}
          focusKey={chat.activeId}
        />
      </main>

      {settingsOpen && (
        <SettingsModal
          settings={settings}
          health={health}
          onChange={update}
          onCheckHealth={check}
          onClearMockData={handleClearMock}
          onClose={closeSettings}
        />
      )}
    </div>
  );
}
