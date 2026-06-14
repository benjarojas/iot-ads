import { api } from './api';
import { ReplayStatus } from '../types/domain';

export interface ReplayStartPayload {
  file: string;
  device_id?: string;
  speed?: number;
  max_frames?: number | null;
}

export const replayService = {
  start:  (payload: ReplayStartPayload) => api.post<ReplayStatus>('/replay/start', payload),
  status: ()                             => api.get<ReplayStatus | null>('/replay/status'),
  cancel: ()                             => api.post<{ status: string }>('/replay/cancel'),
  clear:  ()                             => api.delete<{ status: string }>('/replay/session'),
};
