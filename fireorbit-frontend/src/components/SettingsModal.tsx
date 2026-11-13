import { useEffect, useRef, useState } from 'react';
import type { HealthState } from '../hooks/useHealth';
import { config } from '../services/config';
import type { Settings } from '../types';
import { CloseIcon } from './Icons';

interface Props {
  settings: Settings;
  health: HealthState;
  onChange: (patch: Partial<Settings>) => void;
  onCheckHealth: () => Promise<HealthState>;
  onClearMockData: () => void;
  onClose: () => void;
}

export function SettingsModal({ settings, health, onChange, onCheckHealth, onClearMockData, onClose }: Props) {
  const [checking, setChecking] = useState(false);
  const [confirmClear, setConfirmClear] = useState(false);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const runCheck = async () => {
    setChecking(true);
    await onCheckHealth();
    setChecking(false);
  };

  const healthText =
    health === 'mock'
      ? 'Not applicable in mock mode'
      : health === 'checking'
        ? 'Checking…'
        : health === 'online'
          ? 'Backend reachable'
          : 'Backend unreachable';

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="settings-title">
        <div className="modal__header">
          <h2 id="settings-title">Settings</h2>
          <button ref={closeRef} type="button" className="icon-btn" onClick={onClose} aria-label="Close settings">
            <CloseIcon size={18} />
          </button>
        </div>

        <section className="modal__section">
          <h3>Connection</h3>
          <dl className="kv">
            <dt>Mode</dt>
            <dd>{config.useMock ? 'Mock API (no backend)' : 'Live backend'}</dd>
            <dt>API base URL</dt>
            <dd className="mono">{config.apiBaseUrl}</dd>
            <dt>Health</dt>
            <dd>{healthText}</dd>
          </dl>
          <button type="button" className="btn btn--ghost" onClick={runCheck} disabled={config.useMock || checking}>
            {checking ? 'Checking…' : 'Check connection'}
          </button>
          <p className="modal__note">
            Set <code>VITE_USE_MOCK_API</code> and <code>VITE_API_BASE_URL</code> in <code>.env</code>, then restart the dev server.
          </p>
        </section>

        <section className="modal__section">
          <h3>Display</h3>
          <label className="toggle">
            <input
              type="checkbox"
              checked={settings.expandSources}
              onChange={(e) => onChange({ expandSources: e.target.checked })}
            />
            <span>Expand source passages by default</span>
          </label>
        </section>

        <section className="modal__section">
          <h3>Data</h3>
          {config.useMock ? (
            confirmClear ? (
              <div className="row">
                <span>Delete all mock conversations?</span>
                <button
                  type="button"
                  className="btn btn--danger"
                  onClick={() => {
                    onClearMockData();
                    setConfirmClear(false);
                  }}
                >
                  Delete
                </button>
                <button type="button" className="btn btn--ghost" onClick={() => setConfirmClear(false)}>Cancel</button>
              </div>
            ) : (
              <button type="button" className="btn btn--ghost" onClick={() => setConfirmClear(true)}>
                Clear mock conversations
              </button>
            )
          ) : (
            <p className="modal__note">Conversation history is stored by the backend and can&apos;t be cleared from here.</p>
          )}
        </section>
      </div>
    </div>
  );
}
