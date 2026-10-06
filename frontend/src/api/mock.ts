import type { ProjectImportResult, AuthStatus, Job, Package, Profile, Project, ProjectInput, SearchRun, SearchSettings } from './types';

const now = () => new Date().toISOString();
const profileSeed: Profile = {
  full_name: 'Demo Kullanıcı', headline: 'Backend Developer', email: 'demo@example.com',
  phone: '+90 555 000 00 00', location: 'İstanbul, Türkiye',
  links: [{ label: 'GitHub', url: 'https://github.com/demo' }, { label: 'LinkedIn', url: 'https://linkedin.com/in/demo' }],
  summary: 'Python ve FastAPI ile ölçeklenebilir servisler geliştiren demo backend geliştiricisi.',
  experience: [{ id: 'exp_demo', company: 'Demo Teknoloji', title: 'Backend Developer', location: 'İstanbul', start_date: '2024-02', end_date: null, bullets: ['FastAPI ile servisler geliştirdim.', 'PostgreSQL sorgularını optimize ettim.'], skills: ['Python', 'FastAPI', 'PostgreSQL', 'Docker'] }],
  education: [{ id: 'edu_demo', school: 'Örnek Üniversitesi', degree: 'Lisans', field: 'Bilgisayar Mühendisliği', start_date: '2019-09', end_date: '2023-06', gpa: '3.21/4.00' }],
  skills: { languages: ['Python', 'TypeScript', 'SQL'], frameworks: ['FastAPI', 'React'], tools: ['Docker', 'Git', 'AWS'] },
  languages: [{ name: 'Türkçe', level: 'Ana dil' }, { name: 'İngilizce', level: 'C1' }],
  certifications: [{ name: 'AWS Cloud Practitioner', issuer: 'Amazon', date: '2024-05' }], updated_at: '2026-09-22T10:00:00Z',
};
const projectSeed: Project[] = [{ id: 'prj_demo', name: 'Demo Apply Agent', role: 'Backend & LLM', summary: 'İş ilanları için demo başvuru paketi hazırlama projesi.', bullets: ['İlanları sınıflandıran demo tarayıcı geliştirdim.', 'CV eşleşme analizi oluşturdum.'], tech: ['Python', 'FastAPI', 'React'], links: [{ label: 'GitHub', url: 'https://github.com/demo/apply-agent' }], start_date: '2026-01', end_date: null, featured: true }];
const jobSeed: Job[] = [
  { id: 'job_demo_1', source: 'lever', url: 'https://jobs.lever.co/demo/engineer', company: 'Demo Teknoloji', title: 'Backend Engineer', location: 'Remote (EMEA)', remote: true, seniority: 'mid', posted_at: '2026-09-20T00:00:00Z', found_at: '2026-09-22T06:00:00Z', description: 'Demo ilan: Python ve FastAPI ile servis geliştirme.', score: 84, score_reason: 'Demo eşleşme puanı.', status: 'new', package_status: 'ready', package_error: null, notes: '' },
  { id: 'job_demo_2', source: 'greenhouse', url: 'https://boards.greenhouse.io/demo/jobs/456', company: 'Örnek Yazılım', title: 'Python Developer', location: 'İstanbul, Türkiye', remote: false, seniority: 'junior', posted_at: '2026-09-18T00:00:00Z', found_at: '2026-09-22T06:10:00Z', description: 'Demo ilan: Python uygulamaları ve PostgreSQL.', score: 72, score_reason: 'Demo eşleşme puanı.', status: 'interview', package_status: 'none', package_error: null, notes: 'Demo takip notu' },
  { id: 'job_demo_3', source: 'ashby', url: 'https://jobs.ashbyhq.com/demo/pm', company: 'Örnek Ürün', title: 'Platform Engineer', location: null, remote: null, seniority: 'senior', posted_at: null, found_at: '2026-09-21T12:00:00Z', description: 'Demo ilan: platform araçları.', score: null, score_reason: null, status: 'applied', package_status: 'generating', package_error: null, notes: '' },
  { id: 'job_demo_4', source: 'remoteok', url: 'https://remoteok.com/remote-jobs/demo-789', company: 'Demo Global', title: 'API Developer', location: 'Worldwide', remote: true, seniority: 'mid', posted_at: '2026-09-19T00:00:00Z', found_at: '2026-09-22T06:20:00Z', description: 'Demo ilan: API geliştirme.', score: 61, score_reason: 'Demo eşleşme puanı.', status: 'rejected', package_status: 'failed', package_error: 'Demo paket oluşturulamadı. Profili kontrol edip tekrar deneyin.', notes: '' },
  { id: 'job_demo_5', source: 'remotive', url: 'https://remotive.com/remote-jobs/software-dev/demo-101', company: 'Demo Collective', title: 'Software Engineer', location: 'Remote', remote: true, seniority: 'mid', posted_at: '2026-09-20T08:00:00Z', found_at: '2026-09-22T06:25:00Z', description: 'Demo ilan: yazılım geliştirme ve servis entegrasyonları.', score: 78, score_reason: 'Demo eşleşme puanı.', status: 'new', package_status: 'none', package_error: null, notes: '' },
  { id: 'job_demo_6', source: 'arbeitnow', url: 'https://www.arbeitnow.com/view/demo-engineer', company: 'Demo Systems', title: 'API Engineer', location: 'Berlin / Remote', remote: true, seniority: 'senior', posted_at: '2026-09-19T10:00:00Z', found_at: '2026-09-22T06:30:00Z', description: 'Demo ilan: API tasarımı ve veri işleme.', score: 69, score_reason: 'Demo eşleşme puanı.', status: 'new', package_status: 'none', package_error: null, notes: '' },
  { id: 'job_demo_7', source: 'adzuna', url: 'https://www.adzuna.com/demo/backend-role', company: 'Demo Labs', title: 'Backend Developer', location: 'Remote (Europe)', remote: true, seniority: 'junior', posted_at: '2026-09-18T08:00:00Z', found_at: '2026-09-22T06:35:00Z', description: 'Demo ilan: backend uygulama geliştirme.', score: 74, score_reason: 'Demo eşleşme puanı.', status: 'new', package_status: 'none', package_error: null, notes: '' },
  { id: 'job_demo_8', source: 'email', url: 'https://jobs.example.com/email-role', company: 'Email Örnek', title: 'Email Alert Engineer', location: 'Remote', remote: true, seniority: 'mid', posted_at: '2026-09-21T10:00:00Z', found_at: '2026-09-22T06:40:00Z', description: 'Demo email uyarı ilanı.', score: 88, score_reason: 'Demo eşleşme puanı.', status: 'new', package_status: 'none', package_error: null, notes: '' },
];
const settingsSeed: SearchSettings = {
  target_roles: ['Backend Developer', 'Python Developer'], locations: ['İstanbul', 'Remote'], remote_only: false,
  seniority: ['junior', 'mid'], keywords_exclude: ['Senior Staff', 'Principal'], min_score: 70,
  auto_package: true, cv_language: 'auto',
  sources: { greenhouse: ['demo-company'], lever: ['demo-company'], ashby: [], remoteok: true, remotive: true, arbeitnow: true, adzuna: false, email_alerts: true },
  schedule_cron: '0 8 * * *',
};
const packageSeed: Package = {
  job_id: 'job_demo_1', generated_at: '2026-09-22T06:05:00Z', cv_pdf_url: '/sample-cv.pdf', cv_language: 'en',
  cover_letter: 'Dear Hiring Team,\n\nThis is a sample demo cover letter.',
  answers: [{ question: 'Why are you interested in this role?', answer: 'This is a demo answer.' }],
  analysis: { score: 84, matched_skills: ['Python', 'FastAPI'], missing_skills: ['Kubernetes'], highlighted_projects: ['prj_demo'], highlighted_experience: ['exp_demo'], tips: ['Demo önerisi: ilgili proje deneyiminizi anlatın.'] },
};

function read<T>(key: string, seed: T): T {
  try {
    const value = localStorage.getItem(`apply-agent-demo:${key}`);
    if (!value) return structuredClone(seed);
    const parsed = JSON.parse(value) as T;
    if (key === 'jobs' && Array.isArray(parsed)) return parsed.map((job: Job) => ({ ...job, package_error: job.package_error ?? null })) as T;
    if (key === 'settings' && parsed && typeof parsed === 'object') {
      const sources = (parsed as unknown as SearchSettings).sources;
      return { ...(parsed as object), sources: { ...sources, email_alerts: sources.email_alerts ?? false } } as T;
    }
    return parsed;
  }
  catch { return structuredClone(seed); }
}
function write<T>(key: string, value: T): void {
  try { localStorage.setItem(`apply-agent-demo:${key}`, JSON.stringify(value)); } catch { /* storage can be unavailable */ }
}
function state<T>(key: string, seed: T): T { return read(key, seed); }
const missing = (kind: string): Error => new Error(`${kind} bulunamadı.`);
const clone = <T>(value: T): T => structuredClone(value);

export const mockApi = {
  async listJobs(): Promise<Job[]> { return clone(state('jobs', jobSeed).map(job => ({ ...job, description: '' }))); },
  async getJob(id: string): Promise<Job> { const job = state('jobs', jobSeed).find(item => item.id === id); if (!job) throw missing('İş ilanı'); return clone(job); },
  async addManualJob(input: { url: string; text?: string }): Promise<{ job: Job; created: boolean }> {
    let parsed: URL;
    try { parsed = new URL(input.url); } catch { throw new Error('Geçerli bir ilan URL adresi girin.'); }
    if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') throw new Error('İlan adresi http veya https ile başlamalıdır.');
    const jobs = state('jobs', jobSeed); const existing = jobs.find(item => item.url === parsed.href);
    if (existing) return { job: clone(existing), created: false };
    const id = `job_demo_${Date.now()}`;
    const job: Job = { id, source: 'manual', url: parsed.href, company: 'Demo manuel ilan', title: 'İncelenecek demo ilan', location: null, remote: null, seniority: null, posted_at: null, found_at: now(), description: input.text ?? '', score: null, score_reason: null, status: 'new', package_status: 'none', package_error: null, notes: '' };
    jobs.unshift(job); write('jobs', jobs); return { job: clone(job), created: true };
  },
  async updateJob(id: string, input: { status?: Job['status']; notes?: string; description?: string }): Promise<Job> {
    const jobs = state('jobs', jobSeed); const index = jobs.findIndex(item => item.id === id); if (index < 0) throw missing('İş ilanı');
    jobs[index] = { ...jobs[index], ...input }; write('jobs', jobs); return clone(jobs[index]);
  },
  async createPackage(id: string): Promise<{ job_id: string; package_status: Job['package_status'] }> {
    const jobs = state('jobs', jobSeed); const job = jobs.find(item => item.id === id); if (!job) throw missing('İş ilanı');
    job.package_status = 'generating'; job.package_error = null; write('jobs', jobs);
    setTimeout(() => {
      const latest = state('jobs', jobSeed); const found = latest.find(item => item.id === id);
      if (found) { found.package_status = 'ready'; found.package_error = null; write('jobs', latest); }
      const packages = state<Record<string, Package>>('packages', { job_demo_1: packageSeed });
      packages[id] = { ...clone(packageSeed), job_id: id, generated_at: now(), cv_pdf_url: '/sample-cv.pdf' }; write('packages', packages);
    }, 500);
    return { job_id: id, package_status: 'generating' };
  },
  async getPackage(id: string): Promise<Package> {
    const packages = state<Record<string, Package>>('packages', { job_demo_1: packageSeed }); const pkg = packages[id]; if (!pkg) throw missing('Başvuru paketi'); return clone(pkg);
  },
  async getProfile(): Promise<Profile> { return clone(state('profile', profileSeed)); },
  async saveProfile(profile: Profile): Promise<Profile> { const saved = { ...clone(profile), updated_at: now() }; write('profile', saved); return clone(saved); },
  async importProfile(_file: File): Promise<Profile> { return clone(profileSeed); },
  async listProjects(): Promise<Project[]> { return clone(state('projects', projectSeed)); },
  async createProject(input: ProjectInput): Promise<Project> { const items = state('projects', projectSeed); const project = { ...clone(input), id: `prj_demo_${Date.now()}` }; items.push(project); write('projects', items); return clone(project); },
  async updateProject(id: string, input: ProjectInput): Promise<Project> {
    const items = state('projects', projectSeed); const index = items.findIndex(item => item.id === id); if (index < 0) throw missing('Proje');
    items[index] = { ...items[index], ...clone(input) }; write('projects', items); return clone(items[index]);
  },
  async deleteProject(id: string): Promise<void> { const items = state('projects', projectSeed); const filtered = items.filter(item => item.id !== id); if (items.length === filtered.length) throw missing('Proje'); write('projects', filtered); },
  async importProjects(files: File[]): Promise<ProjectImportResult> {
    const items = state('projects', projectSeed); const result: ProjectImportResult = { created: [], updated: [], errors: [] };
    for (const file of files) {
      let data: unknown;
      try { data = JSON.parse(await file.text()); } catch { result.errors.push({ file: file.name, message: 'Geçerli bir JSON değil.' }); continue; }
      const list = Array.isArray(data) ? data : [data];
      list.forEach((raw, index) => {
        const label = list.length === 1 ? file.name : `${file.name} #${index + 1}`;
        const input = raw as Partial<Project>;
        if (!input || typeof input !== 'object' || typeof input.name !== 'string' || !input.name.trim()) { result.errors.push({ file: label, message: "'name' alanı geçersiz." }); return; }
        const existing = items.find(item => (input.id && item.id === input.id) || item.name.toLocaleLowerCase('tr') === input.name!.toLocaleLowerCase('tr'));
        const project = { role: null, summary: '', bullets: [], tech: [], links: [], start_date: null, end_date: null, featured: false, ...clone(input), name: input.name, id: existing?.id || input.id || `prj_demo_${Date.now()}_${index}` } as Project;
        if (existing) { Object.assign(existing, project); result.updated.push(clone(project)) } else { items.push(project); result.created.push(clone(project)) }
      });
    }
    write('projects', items); return result;
  },
  async getSettings(): Promise<SearchSettings> { return clone(state('settings', settingsSeed)); },
  async saveSettings(settings: SearchSettings): Promise<SearchSettings> { write('settings', settings); return clone(settings); },
  async runSearch(): Promise<SearchRun> {
    const stamp = now(); const run: SearchRun = { id: `run_demo_${Date.now()}`, status: 'done', started_at: stamp, finished_at: stamp, jobs_found: 0, jobs_new: 0, jobs_above_threshold: 0, error: null };
    const runs = state<SearchRun[]>('search_runs', []); runs.unshift(run); write('search_runs', runs); return clone(run);
  },
  async getSearchRun(id: string): Promise<SearchRun> { const run = state<SearchRun[]>('search_runs', []).find(item => item.id === id); if (!run) throw missing('Arama çalışması'); return clone(run); },
  async getAuthStatus(): Promise<AuthStatus> { return { token_required: false, authenticated: true }; },
  async login(_token: string): Promise<void> {},
  async logout(): Promise<void> {},
  async listSearchRuns(limit: number): Promise<SearchRun[]> { return clone(state<SearchRun[]>('search_runs', []).sort((a, b) => b.started_at.localeCompare(a.started_at)).slice(0, Math.max(0, limit))); },
};

export const getMockCvUrl = (): string => '/sample-cv.pdf';
