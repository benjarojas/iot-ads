import { api } from './api';
import { AppMode } from '../types/domain';

export const stateService = {
  get: ()              => api.get<{ mode: AppMode }>('/state'),
  set: (mode: AppMode) => api.put<{ mode: AppMode }>(`/state/${mode}`),
};
