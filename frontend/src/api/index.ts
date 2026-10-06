import { api as realApi, getCvUrl as realGetCvUrl } from './client';
import { getMockCvUrl, mockApi } from './mock';

export const isMockMode = import.meta.env.VITE_USE_MOCK === 'true';
export const api = isMockMode ? mockApi : realApi;
export const getCvUrl = (jobId: string): string => isMockMode ? getMockCvUrl() : realGetCvUrl(jobId);
export * from './types';
export { ApiError, NetworkError } from './client';
