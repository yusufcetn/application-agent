import type { AuthStatus, Job, Package, PackageStatus, Profile, Project, ProjectImportResult, ProjectInput, SearchRun, SearchSettings } from './types';

const BASE = '/api';

export class ApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) { super(message); this.name = 'ApiError'; this.status = status; }
}
export class NetworkError extends Error {
  constructor() { super('Sunucuya bağlanılamadı. Lütfen bağlantınızı kontrol edip tekrar deneyin.'); this.name = 'NetworkError'; }
}

async function request<T>(path: string, init: RequestInit = {}, statusOut?: { status?: number }): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, { ...init, headers, credentials: 'same-origin' });
  } catch {
    throw new NetworkError();
  }
  if (!response.ok) {
    // Development proxy connectivity failures are distinct from backend LLM 503s.
    if (response.headers.get('X-Apply-Agent-Offline') === '1') throw new NetworkError();
    let detail: unknown;
    try { detail = (await response.json() as { detail?: unknown }).detail; } catch { /* non-JSON error */ }
    const message = typeof detail === 'string' ? detail : Array.isArray(detail)
      ? detail.flatMap(item => item && typeof item === 'object' && typeof (item as { msg?: unknown }).msg === 'string' ? [(item as { msg: string }).msg] : []).join('; ')
      : '';
    throw new ApiError(message || `İstek başarısız oldu (HTTP ${response.status}).`, response.status);
  }
  if (statusOut) statusOut.status = response.status;
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  ...(body === undefined ? {} : { body: JSON.stringify(body) }),
});

export const api = {
  listJobs: () => request<Job[]>('/jobs'),
  getJob: (id: string) => request<Job>(`/jobs/${encodeURIComponent(id)}`),
  addManualJob: async (input: { url: string; text?: string }) => {
    const response = { status: 0 };
    const result = await request<Job>('/jobs/manual', json('POST', input), response);
    return { job: result, created: response.status === 201 };
  },
  updateJob: (id: string, input: { status?: Job['status']; notes?: string; description?: string }) => request<Job>(`/jobs/${encodeURIComponent(id)}`, json('PATCH', input)),
  createPackage: (id: string) => request<{ job_id: string; package_status: PackageStatus }>(`/jobs/${encodeURIComponent(id)}/package`, json('POST')),
  getPackage: (id: string) => request<Package>(`/jobs/${encodeURIComponent(id)}/package`),
  getProfile: () => request<Profile>('/profile'),
  saveProfile: (profile: Profile) => request<Profile>('/profile', json('PUT', profile)),
  importProfile: (file: File) => {
    const body = new FormData(); body.append('file', file);
    return request<Profile>('/profile/import', { method: 'POST', body });
  },
  listProjects: () => request<Project[]>('/projects'),
  createProject: (input: ProjectInput) => request<Project>('/projects', json('POST', input)),
  updateProject: (id: string, input: ProjectInput) => request<Project>(`/projects/${encodeURIComponent(id)}`, json('PUT', input)),
  deleteProject: (id: string) => request<void>(`/projects/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  importProjects: (files: File[]) => {
    const body = new FormData(); files.forEach(file => body.append('files', file));
    return request<ProjectImportResult>('/projects/import', { method: 'POST', body });
  },
  getSettings: () => request<SearchSettings>('/settings'),
  saveSettings: (settings: SearchSettings) => request<SearchSettings>('/settings', json('PUT', settings)),
  runSearch: () => request<SearchRun>('/search/run', json('POST')),
  getSearchRun: (id: string) => request<SearchRun>(`/search/runs/${encodeURIComponent(id)}`),
  getAuthStatus: () => request<AuthStatus>('/auth/status'),
  login: (token: string) => request<void>('/auth/login', json('POST', { token })),
  logout: () => request<void>('/auth/logout', json('POST')),
  listSearchRuns: (limit: number) => request<SearchRun[]>(`/search/runs?limit=${encodeURIComponent(String(limit))}`),
};

export const getCvUrl = (jobId: string): string => `${BASE}/jobs/${encodeURIComponent(jobId)}/cv.pdf`;
