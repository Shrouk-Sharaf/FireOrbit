import type { ChatApi } from '../types';
import { mockApi } from '../mocks/mockApi';
import { config } from './config';
import { realApi } from './realApi';

/** The only place that decides mock vs real. UI imports `api` and never knows which it is. */
export const api: ChatApi = config.useMock ? mockApi : realApi;
export { config };
