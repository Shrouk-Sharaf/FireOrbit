import { useCallback, useEffect, useState } from 'react';
import { api, config } from '../services/api';

export type HealthState = 'mock' | 'checking' | 'online' | 'offline';

export function useHealth() {
  const [state, setState] = useState<HealthState>(config.useMock ? 'mock' : 'checking');

  const check = useCallback(async () => {
    if (config.useMock) {
      setState('mock');
      return 'mock' as const;
    }
    setState('checking');
    try {
      await api.health();
      setState('online');
      return 'online' as const;
    } catch {
      setState('offline');
      return 'offline' as const;
    }
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  return { state, check };
}
