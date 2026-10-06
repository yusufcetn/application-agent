import type { Profile, ProjectInput } from './types'

const nullableDate = (value: string | null): string | null => value?.trim() ? value : null
const cleanBullets = (bullets: string[]): string[] => bullets.map(item => item.trim()).filter(Boolean)

export function normalizeProfile(profile: Profile): Profile {
  return {
    ...profile,
    experience: profile.experience.map(item => ({ ...item, bullets: cleanBullets(item.bullets), start_date: nullableDate(item.start_date), end_date: nullableDate(item.end_date) })),
    education: profile.education.map(item => ({ ...item, start_date: nullableDate(item.start_date), end_date: nullableDate(item.end_date) })),
    certifications: profile.certifications.map(item => ({ ...item, date: nullableDate(item.date) })),
  }
}

export function normalizeProject(project: ProjectInput): ProjectInput {
  return { ...project, bullets: cleanBullets(project.bullets), start_date: nullableDate(project.start_date), end_date: nullableDate(project.end_date) }
}
