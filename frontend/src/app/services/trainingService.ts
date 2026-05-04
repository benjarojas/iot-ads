import { api } from './api';
import { TrainingStatus } from '../types/domain';

export interface TrainingStartPayload {
  name: string;
  device_id: string;
  duration_minutes: number;
  notes?: string;
}

export const trainingService = {
  start:  (payload: TrainingStartPayload) => api.post<TrainingStatus>('/training/start', payload),
  status: ()                               => api.get<TrainingStatus | null>('/training/status'),
  cancel: ()                               => api.post<{ status: string }>('/training/cancel'),
  clear:  ()                               => api.delete<{ status: string }>('/training/session'),
};
