export interface ProfileLink { label: string; url: string }
export interface Experience {
  id: string; company: string; title: string; location: string | null;
  start_date: string | null; end_date: string | null; bullets: string[]; skills: string[];
}
export interface Education {
  id: string; school: string; degree: string | null; field: string | null; start_date: string | null;
  end_date: string | null; gpa: string | null;
}
export interface Skills { languages: string[]; frameworks: string[]; tools: string[] }
export interface Language { name: string; level: string }
export interface Certification { name: string; issuer: string | null; date: string | null }
export interface Profile {
  full_name: string; headline: string; email: string; phone: string; location: string;
  links: ProfileLink[]; summary: string; experience: Experience[]; education: Education[];
  skills: Skills; languages: Language[]; certifications: Certification[]; updated_at: string | null;
}
export interface ProjectInput {
  name: string; role: string | null; summary: string; bullets: string[]; tech: string[];
  links: ProfileLink[]; start_date: string | null; end_date: string | null; featured: boolean;
}
export interface Project extends ProjectInput { id: string }
export interface ProjectImportIssue { file: string; message: string }
export interface ProjectImportResult { created: Project[]; updated: Project[]; errors: ProjectImportIssue[] }
export type JobStatus = 'new' | 'applied' | 'skipped' | 'interview' | 'rejected' | 'offer';
export type PackageStatus = 'none' | 'generating' | 'ready' | 'failed';
export type JobSource = 'greenhouse' | 'lever' | 'ashby' | 'remoteok' | 'remotive' | 'arbeitnow' | 'adzuna' | 'email' | 'web' | 'manual';
export type EmploymentType = 'full_time' | 'part_time' | 'working_student' | 'internship' | 'contract';
export type PostingStatus = 'open' | 'closed' | 'unknown';
export type Seniority = 'intern' | 'junior' | 'mid' | 'senior' | 'lead';
export interface Job {
  id: string; source: JobSource; url: string; company: string; title: string;
  location: string | null; remote: boolean | null; seniority: Seniority | null;
  employment_type: EmploymentType | null; posted_at: string | null; found_at: string; description: string;
  posting_status: PostingStatus; last_verified_at: string | null; application_deadline: string | null;
  verification_reason: string | null; score: number | null; score_reason: string | null; status: JobStatus;
  package_status: PackageStatus; package_error: string | null; notes: string; seen_at: string | null;
}
export interface PackageAnswer { question: string; answer: string }
export interface PackageAnalysis {
  score: number; matched_skills: string[]; missing_skills: string[];
  highlighted_projects: string[]; highlighted_experience: string[]; tips: string[];
}
export interface Package {
  job_id: string; generated_at: string; cv_pdf_url: string; cv_language: 'tr' | 'en';
  cover_letter: string; answers: PackageAnswer[]; analysis: PackageAnalysis;
}
export interface SearchSources {
  greenhouse: string[]; lever: string[]; ashby: string[];
  remoteok: boolean; remotive: boolean; arbeitnow: boolean; adzuna: boolean; email_alerts: boolean;
  web_search: boolean;
}
export interface SearchSettings {
  target_roles: string[]; locations: string[]; remote_only: boolean; seniority: Seniority[];
  keywords_exclude: string[]; min_score: number; auto_package: boolean;
  cv_language: 'auto' | 'tr' | 'en'; sources: SearchSources; schedule_cron: string; daily_report: boolean;
}
export interface RoleSuggestions { target_roles: string[] }
export type CompanyBoardSource = 'greenhouse' | 'lever' | 'ashby'
export interface CompanySuggestion {
  name: string; source: CompanyBoardSource; slug: string; url: string; reason: string
}
export interface CompanySuggestions { companies: CompanySuggestion[]; warnings: string[] }
export interface SearchRun {
  id: string; status: 'running' | 'done' | 'failed';
  started_at: string; finished_at: string | null; jobs_found: number; jobs_scored: number; jobs_new: number;
  jobs_above_threshold: number; jobs_closed: number; error: string | null;
}
export interface AuthStatus { token_required: boolean; authenticated: boolean }
