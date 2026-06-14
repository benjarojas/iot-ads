import { api } from './api';
import { DatasetInfo } from '../types/domain';

export const datasetService = {
  list: () => api.get<DatasetInfo[]>('/datasets'),
};
