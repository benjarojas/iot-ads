import { api } from './api';
import { HealthStatus } from '../types/domain';

export const healthService = {
  get: () => api.get<HealthStatus>('/health'),
};
