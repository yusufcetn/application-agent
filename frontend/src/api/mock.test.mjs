import test, { beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { mockApi } from './mock.ts'

const storage = new Map()
globalThis.localStorage = {
  getItem: key => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, String(value)),
  removeItem: key => storage.delete(key),
}
beforeEach(() => storage.clear())

test('demo jobs cover the primary package and status states', async () => {
  const jobs = await mockApi.listJobs()
  assert.ok(jobs.some(job => job.status === 'new' && job.package_status === 'ready'))
  assert.ok(jobs.some(job => job.package_status === 'failed'))
  assert.ok(jobs.some(job => job.score === null))
  const ready = jobs.find(job => job.package_status === 'ready')
  assert.equal((await mockApi.getPackage(ready.id)).job_id, ready.id)
})

test('manual job creation rejects unsafe URLs and supports status updates', async () => {
  await assert.rejects(mockApi.addManualJob({ url: 'javascript:alert(1)' }), /http veya https/)
  const first = await mockApi.addManualJob({ url: 'https://example.com/jobs/123', text: 'Deneme ilanı' })
  const added = first.job
  assert.equal(first.created, true)
  assert.equal((await mockApi.addManualJob({ url: 'https://example.com/jobs/123' })).created, false)
  assert.equal(added.status, 'new')
  assert.equal(added.package_status, 'none')
  assert.equal(added.posting_status, 'unknown')
  assert.equal((await mockApi.getJob('job_demo_6')).posting_status, 'closed')
  assert.equal((await mockApi.listJobs())[0].id, added.id)
  assert.equal((await mockApi.updateJob(added.id, { status: 'applied', notes: 'Başvuru yapıldı' })).status, 'applied')
  assert.equal((await mockApi.getJob(added.id)).notes, 'Başvuru yapıldı')
  await assert.rejects(mockApi.addManualJob({}), /bağlantısı veya ilan metni/)
  const textOnly = await mockApi.addManualJob({ text: 'Sadece metinle ilan' })
  assert.equal(textOnly.created, true)
  assert.ok(textOnly.job.url.startsWith('manual:job_demo_'))
  await mockApi.deleteJob(textOnly.job.id)
})

test('package generation moves a demo job from generating to ready', async () => {
  const id = 'job_demo_5'
  assert.equal((await mockApi.createPackage(id)).package_status, 'generating')
  assert.equal((await mockApi.getJob(id)).package_status, 'generating')
  await new Promise(resolve => setTimeout(resolve, 600))
  assert.equal((await mockApi.getJob(id)).package_status, 'ready')
  assert.equal((await mockApi.getPackage(id)).job_id, id)
})

test('profile import previews without saving and project/settings edits persist', async () => {
  const profile = await mockApi.getProfile()
  const preview = await mockApi.importProfile(new File(['demo'], 'cv.pdf'))
  preview.full_name = 'Changed preview'
  assert.equal((await mockApi.getProfile()).full_name, profile.full_name)
  const project = await mockApi.createProject({ name: 'Test proje', role: null, summary: '', bullets: [], tech: [], links: [], start_date: null, end_date: null, featured: false })
  await mockApi.updateProject(project.id, { ...project, name: 'Yeni ad' })
  assert.equal((await mockApi.listProjects()).find(item => item.id === project.id).name, 'Yeni ad')
  await mockApi.deleteProject(project.id)
  assert.equal((await mockApi.listProjects()).some(item => item.id === project.id), false)
  const settings = await mockApi.getSettings()
  await mockApi.saveSettings({ ...settings, min_score: 85 })
  assert.equal((await mockApi.getSettings()).min_score, 85)
})

test('mock project import creates, then updates by name, and reports bad files', async () => {
  const project = { name: 'İçe Aktarılan', summary: 'x', tech: ['Go'] }
  const first = await mockApi.importProjects([new File([JSON.stringify(project)], 'p.json'), new File(['{bad'], 'bad.json')])
  assert.equal(first.created.length, 1)
  assert.deepEqual(first.errors.map(item => item.file), ['bad.json'])
  const again = await mockApi.importProjects([new File([JSON.stringify({ ...project, name: 'içe aktarılan', summary: 'y' })], 'p.json')])
  assert.equal(again.updated.length, 1)
  assert.equal((await mockApi.listProjects()).filter(item => item.name.toLocaleLowerCase('tr') === 'içe aktarılan').length, 1)
})

test('demo search reports its actual zero-result behavior', async () => {
  const run = await mockApi.runSearch()
  assert.equal(run.status, 'done')
  assert.equal(run.jobs_new, 0)
  assert.equal((await mockApi.getSearchRun(run.id)).id, run.id)
})

test('mock auth, email source, package errors, description updates and run limits match API', async () => {
  assert.deepEqual(await mockApi.getAuthStatus(), { token_required: false, authenticated: true })
  await mockApi.login('demo')
  await mockApi.logout()
  const jobs = await mockApi.listJobs()
  assert.ok(jobs.some(job => job.source === 'email'))
  assert.ok(jobs.every(job => typeof job.package_error === 'string' || job.package_error === null))
  assert.match(jobs.find(job => job.package_status === 'failed').package_error, /paket oluşturulamadı/)
  assert.ok(jobs.every(job => job.description === ''))
  assert.equal((await mockApi.updateJob('job_demo_2', { description: 'Updated description' })).description, 'Updated description')
  assert.equal((await mockApi.getSettings()).sources.email_alerts, true)
  const runs = await Promise.all([mockApi.runSearch(), mockApi.runSearch()])
  assert.equal((await mockApi.listSearchRuns(1)).length, 1)
  assert.equal((await mockApi.listSearchRuns(1))[0].id, runs.at(-1).id)
})

test('old persisted jobs and settings are normalized without changing mock storage namespace', async () => {
  storage.set('apply-agent-demo:jobs', JSON.stringify([{ id: 'old', package_status: 'failed', url: 'https://old.test' }]))
  storage.set('apply-agent-demo:settings', JSON.stringify({ sources: { greenhouse: [], lever: [], ashby: [] } }))
  assert.equal((await mockApi.getJob('old')).package_error, null)
  assert.equal((await mockApi.getSettings()).sources.email_alerts, false)
  assert.ok(storage.has('apply-agent-demo:jobs'))
})

test('demo settings assistant reports unavailable research without touching storage', async () => {
  await assert.rejects(mockApi.suggestRoles('Backend developer'), /Demo modunda.*dil modeli/)
  assert.deepEqual(await mockApi.discoverCompanies({ description: 'climate tech', target_roles: [], locations: [], remote_only: false }), {
    companies: [], warnings: ['Demo modunda internet araştırması yapılmaz. Gerçek araştırma için canlı bağlantıya geç.'],
  })
  assert.equal(storage.size, 0)
})
