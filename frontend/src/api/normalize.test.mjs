import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeProfile, normalizeProject } from './normalize.ts'

test('normalizes profile bullets and blank dates without mutating or dropping ids', () => {
  const source = {
    full_name: 'Ada', headline: '', email: '', phone: '', location: '', links: [], summary: '',
    experience: [{ id: 'exp-1', company: 'A', title: 'Dev', location: null, start_date: ' ', end_date: '', bullets: [' shipped ', '  ', 'fixed'], skills: ['TS'] }],
    education: [{ id: 'edu-1', school: 'U', degree: null, field: null, start_date: '  ', end_date: '2020-01', gpa: null }],
    skills: { languages: [], frameworks: [], tools: [] }, languages: [], certifications: [{ name: 'Cert', issuer: null, date: '  ' }], updated_at: null,
  }
  const result = normalizeProfile(source)
  assert.deepEqual(result.experience[0], { ...source.experience[0], start_date: null, end_date: null, bullets: ['shipped', 'fixed'] })
  assert.deepEqual(result.education[0], { ...source.education[0], start_date: null })
  assert.equal(result.certifications[0].date, null)
  assert.equal(source.experience[0].bullets[0], ' shipped ')
  assert.equal(source.experience[0].start_date, ' ')
  assert.equal(result.experience[0].id, 'exp-1')
  assert.equal(result.education[0].id, 'edu-1')
})

test('normalizes project bullets and blank dates immutably', () => {
  const source = { name: 'P', role: null, summary: '', bullets: ['', ' win ', '  '], tech: ['TS'], links: [], start_date: '', end_date: ' ', featured: false }
  const result = normalizeProject(source)
  assert.deepEqual(result, { ...source, bullets: ['win'], start_date: null, end_date: null })
  assert.deepEqual(source.bullets, ['', ' win ', '  '])
})
