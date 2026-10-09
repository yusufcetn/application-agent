import test, { afterEach } from 'node:test'
import assert from 'node:assert/strict'
import { api, getCvUrl, ApiError, NetworkError } from './client.ts'

const originalFetch = globalThis.fetch
afterEach(() => { globalThis.fetch = originalFetch })

test('real client uses contract paths, methods and encoded ids', async () => {
  const seen = []
  globalThis.fetch = async (url, init) => {
    seen.push({ url, init })
    return new Response(JSON.stringify({ status: 'applied' }), { status: 200, headers: { 'Content-Type': 'application/json' } })
  }
  await api.updateJob('job/one', { status: 'applied' })
  assert.equal(seen[0].url, '/api/jobs/job%2Fone')
  assert.equal(seen[0].init.method, 'PATCH')
  assert.equal(JSON.parse(seen[0].init.body).status, 'applied')
  assert.equal(getCvUrl('job/one'), '/api/jobs/job%2Fone/cv.pdf')
  assert.equal(getCvUrl('job/one', '2026-09-27T16:30:00Z'), '/api/jobs/job%2Fone/cv.pdf?v=2026-09-27T16%3A30%3A00Z')
})

test('settings assistant sends the expected paths and payloads', async () => {
  const seen = []
  globalThis.fetch = async (url, init) => {
    seen.push({ url, init })
    return new Response(JSON.stringify(url.endsWith('suggest-roles') ? { target_roles: ['Platform Engineer'] } : { companies: [], warnings: [] }), { status: 200 })
  }
  assert.deepEqual(await api.suggestRoles('Python platform services'), { target_roles: ['Platform Engineer'] })
  await api.discoverCompanies({ description: 'climate tech', target_roles: ['Platform Engineer'], locations: ['Berlin'], remote_only: true })
  assert.equal(seen[0].url, '/api/settings/suggest-roles')
  assert.equal(seen[0].init.method, 'POST')
  assert.deepEqual(JSON.parse(seen[0].init.body), { description: 'Python platform services' })
  assert.equal(seen[1].url, '/api/settings/discover-companies')
  assert.deepEqual(JSON.parse(seen[1].init.body), { description: 'climate tech', target_roles: ['Platform Engineer'], locations: ['Berlin'], remote_only: true })
})

test('real client returns backend detail text on errors', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Paket hazırlamak için önce profilini doldur.' }), { status: 409, headers: { 'Content-Type': 'application/json' } })
  await assert.rejects(api.createPackage('job_1'), /profilini doldur/)
})

test('manual job uses response status to distinguish duplicate from new', async () => {
  const jobs = [{ id: 'j' }, { id: 'j' }]
  globalThis.fetch = async () => new Response(JSON.stringify(jobs.shift()), { status: jobs.length ? 201 : 200 })
  assert.equal((await api.addManualJob({ url: 'https://example.com' })).created, true)
  assert.equal((await api.addManualJob({ url: 'https://example.com' })).created, false)
})

test('API errors preserve status and parse string and validation detail', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: [{ msg: 'url is required' }, { loc: ['body'], msg: 'invalid URL' }, { msg: 3 }] }), { status: 422 })
  await assert.rejects(api.getAuthStatus(), error => error instanceof ApiError && error.status === 422 && error.message === 'url is required; invalid URL')
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Gone' }), { status: 404 })
  await assert.rejects(api.getAuthStatus(), error => error instanceof ApiError && error.status === 404 && error.message === 'Gone')
  for (const status of [409, 502, 503]) {
    globalThis.fetch = async () => new Response('oops', { status })
    await assert.rejects(api.getAuthStatus(), error => error instanceof ApiError && error.status === status)
  }
  for (const status of [413, 415, 502, 503]) {
    const detail = `CV yüklenemedi: ${status}`
    globalThis.fetch = async () => new Response(JSON.stringify({ detail }), { status })
    await assert.rejects(api.importProfile(new File(['demo'], 'cv.txt')), error => error instanceof ApiError && error.status === status && error.message === detail)
  }
})

test('network failures have a distinct class', async () => {
  globalThis.fetch = async () => { throw new TypeError('offline') }
  await assert.rejects(api.getAuthStatus(), error => error instanceof NetworkError)
  globalThis.fetch = async () => new Response(null, { status: 503, headers: { 'X-Apply-Agent-Offline': '1' } })
  await assert.rejects(api.getAuthStatus(), error => error instanceof NetworkError)
})

test('auth endpoints, search-run query, cookies and multipart headers follow contract', async () => {
  const seen = []
  globalThis.fetch = async (url, init) => {
    seen.push({ url, init })
    return new Response(null, { status: 204 })
  }
  await api.login('secret token')
  await api.logout()
  await api.deleteProject('a/b')
  await api.deleteJob('job/two')
  assert.deepEqual(seen.slice(0, 4).map(item => item.url), ['/api/auth/login', '/api/auth/logout', '/api/projects/a%2Fb', '/api/jobs/job%2Ftwo'])
  assert.equal(seen[3].init.method, 'DELETE')
  assert.equal(JSON.parse(seen[0].init.body).token, 'secret token')
  assert.equal(seen[0].init.headers.has('Authorization'), false)
  assert.equal(seen[0].init.credentials, 'same-origin')
  globalThis.fetch = async (url, init) => { seen.push({ url, init }); return new Response(JSON.stringify([]), { status: 200 }) }
  await api.listSearchRuns(12)
  assert.equal(seen.at(-1).url, '/api/search/runs?limit=12')
  globalThis.fetch = async (_url, init) => { seen.push({ url: '', init }); return new Response('{}', { status: 200 }) }
  await api.importProfile(new File(['x'], 'profile.pdf'))
  assert.equal(seen.at(-1).init.headers.has('Content-Type'), false)
  globalThis.fetch = async (url, init) => { seen.push({ url, init }); return new Response(JSON.stringify({ sent_to: 'me@x.com' }), { status: 200 }) }
  assert.equal((await api.sendRunReport('run/1')).sent_to, 'me@x.com')
  assert.equal(seen.at(-1).url, '/api/search/runs/run%2F1/report')
  assert.equal(seen.at(-1).init.method, 'POST')
})

test('project import sends every file as multipart "files"', async () => {
  let seen
  globalThis.fetch = async (url, init) => { seen = { url, init }; return new Response(JSON.stringify({ created: [], updated: [], errors: [] }), { status: 200 }) }
  await api.importProjects([new File(['{}'], 'a.json'), new File(['[]'], 'b.json')])
  assert.equal(seen.url, '/api/projects/import')
  assert.equal(seen.init.method, 'POST')
  assert.deepEqual(seen.init.body.getAll('files').map(file => file.name), ['a.json', 'b.json'])
  assert.equal(seen.init.headers.has('Content-Type'), false)
})
