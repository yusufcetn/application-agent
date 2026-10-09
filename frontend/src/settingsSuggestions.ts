import type { CompanySuggestion, SearchSettings, SearchSources } from './api/types'

export function mergeUnique(existing: string[], additions: string[]): string[] {
  const merged = [...existing]
  for (const item of additions) {
    const value = item.trim()
    if (value && !merged.some(current => comparisonKey(current) === comparisonKey(value))) merged.push(value)
  }
  return merged
}

function comparisonKey(value: string): string {
  return value.replace(/[İIı]/g, 'i').normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase()
    .replace(/ß/g, 'ss').replace(/ς/g, 'σ').trim().replace(/\s+/gu, ' ')
}

export function mergeSuggestedRoles(current: SearchSettings, suggestions: string[]): SearchSettings {
  return { ...current, target_roles: mergeUnique(current.target_roles, suggestions) }
}

export function mergeCompanySuggestions(current: SearchSettings, suggestions: CompanySuggestion[]): SearchSettings {
  const sources: SearchSources = { ...current.sources }
  for (const source of ['greenhouse', 'lever', 'ashby'] as const) {
    const additions = suggestions.filter(company => company.source === source).map(company => company.slug)
    sources[source] = mergeUnique(sources[source], additions)
  }
  return { ...current, sources }
}
