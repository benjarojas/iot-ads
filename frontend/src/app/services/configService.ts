import { api } from './api';
import { SystemConfig } from '../types/domain';

export interface SystemConfigPatch {
  p_high?: number;
  p_low?: number;
  active_inference_model?: string | null;
}

export const configService = {
  getSystemConfig: () => api.get<SystemConfig>('/config'),
  updateSystemConfig: (patch: SystemConfigPatch) => api.put<SystemConfig>('/config', patch),
};
