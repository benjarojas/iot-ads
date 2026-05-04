import { api } from './api';
import { AnomalyEvent } from '../types/domain';

export interface AnomalyListParams {
  device_id?: string;
  model_version?: string;
  status?: 'open' | 'closed' | 'all';
  since?: string;
  until?: string;
  limit?: number;
  offset?: number;
}

export const anomalyService = {
  list: (params: AnomalyListParams = {}) => {
    const qs = new URLSearchParams();
    if (params.device_id)     qs.set('device_id', params.device_id);
    if (params.model_version) qs.set('model_version', params.model_version);
    if (params.status)        qs.set('status', params.status);
    if (params.since)         qs.set('since', params.since);
    if (params.until)         qs.set('until', params.until);
    if (params.limit  != null) qs.set('limit',  String(params.limit));
    if (params.offset != null) qs.set('offset', String(params.offset));
    const query = qs.toString();
    return api.get<AnomalyEvent[]>(`/anomalies${query ? '?' + query : ''}`);
  },
  get: (id: string) => api.get<AnomalyEvent>(`/anomalies/${id}`),
};
