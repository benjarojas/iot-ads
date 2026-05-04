import { api } from './api';
import { ModelInfo } from '../types/domain';

export const modelService = {
  list: () => api.get<ModelInfo[]>('/models'),
};
