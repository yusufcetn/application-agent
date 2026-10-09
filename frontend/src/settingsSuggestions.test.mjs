import test from 'node:test'
import assert from 'node:assert/strict'
import { mergeCompanySuggestions, mergeSuggestedRoles, mergeUnique } from './settingsSuggestions.ts'

const settings = () => ({
  target_roles: ['Backend Developer'], locations: ['İstanbul'], remote_only: false, seniority: ['mid'],
  keywords_exclude: [], min_score: 70, auto_package: true, cv_language: 'auto',
  sources: { greenhouse: ['acme'], lever: [], ashby: ['ramp'], remoteok: true, remotive: true, arbeitnow: true, adzuna: false, email_alerts: false, web_search: false },
  schedule_cron: '0 8 * * *', daily_report: false,
})

test('role suggestions preserve current draft edits and dedupe case-insensitively', () => {
  const current = settings()
  current.target_roles.push('Staff Engineer')
  const merged = mergeSuggestedRoles(current, ['backend developer', 'Platform Engineer', '  '])
  assert.deepEqual(merged.target_roles, ['Backend Developer', 'Staff Engineer', 'Platform Engineer'])
  assert.deepEqual(current.target_roles, ['Backend Developer', 'Staff Engineer'])
})

test('dedupe folds whitespace, accents, Turkish I, and common case-fold differences', () => {
  assert.deepEqual(mergeUnique(['AI Engineer', 'İstanbul'], [' ai   engineer ', 'Istanbul', 'ıSTANBUL']), ['AI Engineer', 'İstanbul'])
})

test('company suggestions group by provider, preserve current edits, and do not mutate inputs', () => {
  const current = settings()
  current.sources.lever.push('manual-company')
  const suggestions = [
    { name: 'Acme', source: 'greenhouse', slug: 'ACME', url: '', reason: '' },
    { name: 'New GH', source: 'greenhouse', slug: 'new-gh', url: '', reason: '' },
    { name: 'Lever Co', source: 'lever', slug: 'lever-co', url: '', reason: '' },
    { name: 'Ashby Co', source: 'ashby', slug: 'ashby-co', url: '', reason: '' },
  ]
  const merged = mergeCompanySuggestions(current, suggestions)
  assert.deepEqual(merged.sources.greenhouse, ['acme', 'new-gh'])
  assert.deepEqual(merged.sources.lever, ['manual-company', 'lever-co'])
  assert.deepEqual(merged.sources.ashby, ['ramp', 'ashby-co'])
  assert.equal(merged.sources.remoteok, true)
  assert.deepEqual(current.sources.greenhouse, ['acme'])
  assert.deepEqual(current.sources.lever, ['manual-company'])
  assert.equal(suggestions[0].slug, 'ACME')
})
