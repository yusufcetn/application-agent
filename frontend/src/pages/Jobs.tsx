import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useOutletContext, useParams } from 'react-router-dom'
import { ArrowDownToLine, ArrowLeft, ArrowRight, ArrowUpRight, Check, CheckCheck, ChevronDown, Clipboard, ExternalLink, FileText, Filter, Link2, MapPin, Plus, Radar, Search, Sparkles, X, RefreshCw } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { api, getCvUrl, isMockMode } from '../api'
import { ApiError } from '../api'
import type { Job, JobStatus } from '../api'
import { useToast } from '../App'
import { EmptyState, ErrorState, formatDate, LoadingRows, PackageBadge, PageHeading, ScoreBadge, SectionTitle, sourceLabels, StatusPill, statusLabels } from '../components/ui'
import { copyText } from '../clipboard'

function JobRow({ job, compact = false }: { job: Job; compact?: boolean }) {
  return <Link className={`job-row ${compact ? 'compact' : ''}`} to={`/jobs/${job.id}`}>
    <ScoreBadge score={job.score} />
    <span className="job-main"><strong>{job.title}</strong><small>{job.company}</small></span>
    <span className="job-location"><MapPin size={15} />{job.location || 'Konum belirtilmemiş'}</span>
    {!compact && <span className="job-source">{sourceLabels[job.source] || job.source}</span>}
    <span className="job-package"><PackageBadge status={job.package_status} /></span>
    <span className="job-status"><StatusPill status={job.status} /></span>
    <ArrowUpRight className="job-arrow" size={19} />
  </Link>
}

function Metric({ value, label, accent }: { value: number; label: string; accent?: boolean }) {
  return <div className={`metric ${accent ? 'accent' : ''}`}><strong>{value.toString().padStart(2, '0')}</strong><span>{label}</span></div>
}

export function Dashboard() {
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: api.listJobs })
  const profile = useQuery({ queryKey: ['profile'], queryFn: api.getProfile })
  const list = jobs.data || []
  const fresh = list.filter(job => job.status === 'new').sort((a, b) => (b.score ?? -1) - (a.score ?? -1))
  const spotlight = fresh.find(job => job.package_status === 'ready') || fresh[0]
  const followups = list.filter(job => ['applied', 'interview', 'offer'].includes(job.status)).slice(0, 3)
  const now = new Date().getHours()
  const greeting = now < 11 ? 'Günaydın' : now < 18 ? 'İyi günler' : 'İyi akşamlar'

  return <>
    <PageHeading eyebrow={isMockMode ? 'Örnek çalışma alanı' : 'Çalışma alanın'} title={`${greeting}, bugün nereden başlayalım?`} description="En uygun ilanları gözden geçir, hazır paketini aç ve başvuruna devam et." actions={<Link className="button secondary" to="/jobs">Tüm ilanları gör <ArrowRight size={17} /></Link>} />
    {jobs.isLoading ? <LoadingRows count={5} /> : jobs.isError ? <ErrorState error={jobs.error} onRetry={() => jobs.refetch()} /> : !profile.isLoading && !profile.data?.full_name && !isMockMode ? <EmptyState title="Önce profilini oluşturalım" description="İlan eşleşmeleri ve başvuru paketleri için CV bilgilerini ekle." action={<Link to="/profile" className="button primary">Profilimi doldur <ArrowRight size={17} /></Link>} /> : <>
      <section className="metrics-strip" aria-label="Başvuru özeti"><Metric value={fresh.length} label="İncelenecek ilan" accent /><Metric value={fresh.filter(job => job.package_status === 'ready').length} label="Paketi hazır" /><Metric value={list.filter(job => job.status === 'applied').length} label="Başvuruldu" /><Metric value={list.filter(job => job.status === 'interview').length} label="Mülakat" /></section>
      {spotlight ? <section className="spotlight" aria-labelledby="spotlight-heading"><div className="spotlight-copy"><div className="spotlight-intro"><span className="sparkle-mark"><Sparkles size={17} /></span><span>Bugün öne çıkan ilan</span></div><h2 id="spotlight-heading">{spotlight.title}</h2><p className="spotlight-company">{spotlight.company}<span>·</span>{spotlight.location || 'Konum belirtilmemiş'}</p><p className="spotlight-reason">{spotlight.score_reason || 'İlan ayrıntılarını açarak eşleşmeyi incele.'}</p><Link to={`/jobs/${spotlight.id}`} className="button spotlight-button">Başvuru paketini aç <ArrowRight size={18} /></Link></div><div className="spotlight-side"><span className="spotlight-orbit orbit-one" /><span className="spotlight-orbit orbit-two" /><div className="spotlight-score"><span>Profil uyumu</span><strong>{spotlight.score ?? '—'}</strong><small>/ 100</small></div><PackageBadge status={spotlight.package_status} /></div></section> : <EmptyState title="Henüz ilan yok" description="Bir ilan linki ekleyerek veya tarama başlatarak başlayabilirsin." action={<Link className="button primary" to="/jobs">İlanlara git <ArrowRight size={17} /></Link>} />}
      <div className="dashboard-grid"><section className="surface-list"><SectionTitle title="Sıradaki fırsatlar" action={<Link className="text-link" to="/jobs">Tümünü gör <ArrowRight size={16} /></Link>} />{fresh.filter(job => job.id !== spotlight?.id).slice(0, 4).length ? fresh.filter(job => job.id !== spotlight?.id).slice(0, 4).map(job => <JobRow compact job={job} key={job.id} />) : <p className="quiet-line">Yeni fırsatların burada görünecek.</p>}</section><aside className="followup-panel"><SectionTitle title="Takiptekiler" /><p>Başvurduğun ilanları tek yerde izle.</p>{followups.length ? followups.map(job => <Link to={`/jobs/${job.id}`} className="followup-row" key={job.id}><span className="followup-initial">{job.company.slice(0, 1)}</span><span><strong>{job.title}</strong><small>{job.company}</small></span><StatusPill status={job.status} /></Link>) : <p className="quiet-line">Takip ettiğin bir başvuru henüz yok.</p>}</aside></div>
    </>}
  </>
}

function AddJobModal({ onClose }: { onClose: () => void }) {
  const [url, setUrl] = useState('')
  const [text, setText] = useState('')
  const [showText, setShowText] = useState(false)
  const toast = useToast()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const mutation = useMutation({ mutationFn: api.addManualJob, onSuccess: result => { queryClient.invalidateQueries({ queryKey: ['jobs'] }); toast(result.created ? 'İlan eklendi.' : 'Bu ilan zaten ekliydi.', 'success'); onClose(); navigate(`/jobs/${result.job.id}`) }, onError: error => { if (error instanceof ApiError && [422, 502, 503].includes(error.status)) setShowText(true) } })
  useEffect(() => { const close = (event: KeyboardEvent) => { if (event.key === 'Escape' && !mutation.isPending) onClose() }; document.addEventListener('keydown', close); return () => document.removeEventListener('keydown', close) }, [onClose, mutation.isPending])
  const submit = (event: React.FormEvent) => { event.preventDefault(); if (mutation.isPending) return; mutation.mutate({ url: url.trim(), ...(text.trim() ? { text: text.trim() } : {}) }) }
  return <div className="modal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget && !mutation.isPending) onClose() }}><div className="modal" role="dialog" aria-modal="true" aria-labelledby="add-job-title"><button className="icon-button modal-close" aria-label="Kapat" disabled={mutation.isPending} onClick={onClose}><X size={20} /></button><div className="modal-icon"><Link2 size={22} /></div><h2 id="add-job-title">İlan linki ekle</h2><p>Bir ilanı kaydet; profilinle eşleşmesini ve başvuru paketini incele.</p><form onSubmit={submit}><label className="field-label" htmlFor="job-url">İlan bağlantısı</label><input id="job-url" autoFocus type="url" value={url} onChange={event => setUrl(event.target.value)} placeholder="https://..." required /><button className="subtle-toggle" type="button" disabled={mutation.isPending} onClick={() => setShowText(!showText)}>{showText ? 'İlan metnini gizle' : 'Link açılamıyorsa ilan metnini yapıştır'} <ChevronDown size={15} /></button>{showText && <textarea rows={5} aria-label="İlan metni" placeholder="İlan metnini yapıştır" value={text} onChange={event => setText(event.target.value)} disabled={mutation.isPending} />}{mutation.isError && <p role="alert" className="form-error">{mutation.error.message}</p>}<div className="modal-actions"><button className="button secondary" type="button" disabled={mutation.isPending} onClick={onClose}>Vazgeç</button><button className="button primary" type="submit" disabled={mutation.isPending}>{mutation.isPending ? 'İlan okunuyor… (15–30 sn)' : 'İlanı ekle'} <ArrowRight size={17} /></button></div></form></div></div>
}

export function Jobs() {
  const { runSearch, searching } = useOutletContext<{ runSearch: () => void; searching: boolean }>()
  const [modalOpen, setModalOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<JobStatus | 'all'>('all')
  const [minimum, setMinimum] = useState(0)
  const [source, setSource] = useState('all')
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: api.listJobs, refetchInterval: query => query.state.data?.some(job => job.package_status === 'generating') ? 3000 : false })
  const list = jobs.data || []
  const filtered = useMemo(() => list.filter(job => {
    const matchText = `${job.title} ${job.company}`.toLocaleLowerCase('tr').includes(query.toLocaleLowerCase('tr'))
    return matchText && (status === 'all' || job.status === status) && (job.score ?? 0) >= minimum && (source === 'all' || job.source === source)
  }).sort((a, b) => (b.score ?? -1) - (a.score ?? -1) || Date.parse(b.found_at) - Date.parse(a.found_at)), [list, query, status, minimum, source])
  const counts = { all: list.length, new: list.filter(job => job.status === 'new').length, applied: list.filter(job => job.status === 'applied').length, interview: list.filter(job => job.status === 'interview').length, skipped: list.filter(job => job.status === 'skipped').length }
  const tabs = ['all', 'new', 'applied', 'interview', 'skipped'] as const

  return <><PageHeading eyebrow="Fırsat panosu" title="İlanlar" description="Bulunan fırsatları karşılaştır, hazır olanlardan başla." actions={<><button className="button secondary" onClick={() => setModalOpen(true)}><Plus size={17} /> Link ile ekle</button><button className="button primary" disabled={searching} onClick={runSearch}><Radar size={17} /> {searching ? 'Taranıyor…' : 'Şimdi tara'}</button></>} />
    <div className="tabs job-tabs" role="tablist" aria-label="İlan durumları">{tabs.map(tab => <button key={tab} role="tab" aria-selected={status === tab} className={status === tab ? 'active' : ''} onClick={() => setStatus(tab)}>{tab === 'all' ? 'Tümü' : statusLabels[tab]} <span>{counts[tab]}</span></button>)}</div>
    <div className="filter-bar"><label className="search-field"><Search size={18} /><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Pozisyon veya şirket ara" aria-label="Pozisyon veya şirket ara" /></label><label className="select-field"><Filter size={16} /><span>Kaynak</span><select value={source} onChange={event => setSource(event.target.value)} aria-label="Kaynak"><option value="all">Tümü</option>{Object.entries(sourceLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="range-field"><span>En az {minimum} puan</span><input type="range" min="0" max="100" step="10" value={minimum} onChange={event => setMinimum(Number(event.target.value))} /></label></div>
    <div className="list-summary"><strong>{filtered.length} ilan</strong><span>Uyum puanına göre sıralı</span></div>
    {jobs.isLoading ? <LoadingRows count={5} /> : jobs.isError ? <ErrorState error={jobs.error} onRetry={() => jobs.refetch()} /> : filtered.length ? <div className="job-list">{filtered.map(job => <JobRow job={job} key={job.id} />)}</div> : <EmptyState title="Bu filtreyle ilan bulunamadı" description="Aramayı veya filtreleri değiştirebilirsin." action={<button className="button secondary" onClick={() => { setStatus('all'); setQuery(''); setMinimum(0); setSource('all') }}>Filtreleri temizle</button>} />}
    {modalOpen && <AddJobModal onClose={() => setModalOpen(false)} />}
  </>
}

const detailTabs = [{ id: 'overview', label: 'Genel bakış' }, { id: 'cv', label: 'CV' }, { id: 'letter', label: 'Ön yazı' }, { id: 'answers', label: 'Hazır cevaplar' }, { id: 'description', label: 'İlan metni' }] as const
type DetailTab = typeof detailTabs[number]['id']

export function JobDetail() {
  const { id = '' } = useParams()
  return <JobDetailContent key={id} id={id} />
}

function JobDetailContent({ id }: { id: string }) {
  const [tab, setTab] = useState<DetailTab>('overview')
  const [copied, setCopied] = useState('')
  const [notes, setNotes] = useState<string | null>(null)
  const [description, setDescription] = useState('')
  const toast = useToast()
  const queryClient = useQueryClient()
  const job = useQuery({ queryKey: ['job', id], queryFn: () => api.getJob(id), refetchInterval: query => query.state.data?.package_status === 'generating' ? 2500 : false })
  const pkg = useQuery({ queryKey: ['package', id], queryFn: () => api.getPackage(id), enabled: job.data?.package_status === 'ready', retry: 1 })
  const projects = useQuery({ queryKey: ['projects'], queryFn: api.listProjects, enabled: job.data?.package_status === 'ready' })
  const profile = useQuery({ queryKey: ['profile'], queryFn: api.getProfile, enabled: job.data?.package_status === 'ready' })
  const update = useMutation({ mutationFn: (patch: { status?: JobStatus; notes?: string; description?: string }) => api.updateJob(id, patch), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['job', id] }); queryClient.invalidateQueries({ queryKey: ['jobs'] }); toast('İlan güncellendi.', 'success') }, onError: error => toast(error.message, 'error') })
  const generate = useMutation({ mutationFn: async (text?: string) => { if (text !== undefined) await api.updateJob(id, { description: text }); return api.createPackage(id) }, onSuccess: () => { queryClient.setQueryData<Job>(['job', id], old => old ? { ...old, package_status: 'generating', package_error: null } : old); queryClient.removeQueries({ queryKey: ['package', id] }); queryClient.invalidateQueries({ queryKey: ['job', id] }); queryClient.invalidateQueries({ queryKey: ['jobs'] }); toast('Başvuru paketi hazırlanıyor.', 'info') }, onError: error => { queryClient.invalidateQueries({ queryKey: ['job', id] }); if (!(error instanceof ApiError && error.status === 409)) toast(error.message, 'error') } })
  const copy = async (key: string, text: string) => { try { await copyText(text); setCopied(key); toast('Metin kopyalandı.', 'success'); window.setTimeout(() => setCopied(''), 2000) } catch { toast('Metin kopyalanamadı. Tarayıcı izinlerini kontrol et.', 'error') } }
  if (job.isLoading) return <LoadingRows count={5} />
  if (job.isError || !job.data) return <ErrorState error={job.error || new Error('İlan bulunamadı.')} onRetry={() => job.refetch()} />
  const current = job.data
  const externalUrl = safeExternalUrl(current.url)
  const demoFixture = isMockMode && current.source !== 'manual' && current.id.startsWith('job_demo_')
  const analysis = pkg.data?.analysis
  const detailsUnavailable = current.package_status !== 'ready'

  return <><Link className="back-link" to="/jobs"><ArrowLeft size={16} /> İlanlara dön</Link><div className="detail-hero"><div className="detail-hero-main"><ScoreBadge score={current.score} large /><div><p className="detail-company">{current.company}</p><h1>{current.title}</h1><p className="detail-meta"><span><MapPin size={15} />{current.location || 'Konum belirtilmemiş'}</span><span>{sourceLabels[current.source] || current.source}</span><span>{formatDate(current.posted_at || current.found_at)}</span></p></div></div><div className="detail-actions">{externalUrl && !demoFixture ? <a className="button primary" href={externalUrl} target="_blank" rel="noopener noreferrer">İlana git <ExternalLink size={17} /></a> : <button className="button primary" onClick={() => toast(demoFixture ? "Bu örnek ilanın gerçek bağlantısı yok." : "Geçerli bir ilan bağlantısı bulunamadı.", "info")}>İlana git <ExternalLink size={17} /></button>}<label className="status-select"><span className="sr-only">Başvuru durumu</span><select value={current.status} disabled={update.isPending} onChange={event => update.mutate({ status: event.target.value as JobStatus })}>{Object.entries(statusLabels).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select><ChevronDown size={15} /></label>{current.package_status === 'ready' && <button className="icon-button" aria-label="Paketi yeniden oluştur" title="Paketi yeniden oluştur" disabled={generate.isPending} onClick={() => generate.mutate()}><RefreshCw size={17} /></button>}</div></div>
    <div className="detail-under"><PackageBadge status={current.package_status} /><span>{current.score_reason || 'Bu ilan için uyum analizi henüz hazır değil.'}</span></div>
    {generate.isError && generate.error instanceof ApiError && generate.error.status === 409 && <p role="alert" className="form-error">{generate.error.message} <Link to="/profile">Profilini tamamla</Link></p>}
    <div className="tabs detail-tabs" role="tablist" aria-label="İlan ayrıntıları">{detailTabs.map(item => <button key={item.id} role="tab" aria-selected={tab === item.id} onClick={() => setTab(item.id)} className={tab === item.id ? 'active' : ''}>{item.label}</button>)}</div>
    {detailsUnavailable && tab !== 'description' ? <div className="package-state">{current.package_status === 'generating' ? <><div className="package-state-icon spin"><Radar size={31} /></div><h2>Başvuru paketi hazırlanıyor</h2><p>İlana özel CV, ön yazı ve cevaplar hazırlanıyor. Bu işlem yaklaşık 1 dakika sürebilir.</p><div className="skeleton state-skeleton" /><div className="skeleton state-skeleton short" /></> : <><div className="package-state-icon"><FileText size={30} /></div><h2>{current.package_status === 'failed' ? 'Paket hazırlanamadı' : 'Başvuru paketini hazırla'}</h2><p>{current.package_status === 'failed' ? (current.package_error || 'İlan metnini kontrol edip yeniden deneyebilirsin.') : 'CV ve ön yazını bu ilana göre düzenleyelim.'}</p>{current.package_status === 'failed' && <><label className="field-label" htmlFor="retry-description">İlan metnini yapıştır</label><textarea id="retry-description" rows={6} value={description} onChange={event => setDescription(event.target.value)} placeholder="İlan metnini yapıştır" disabled={generate.isPending} /></>}<button className="button primary" disabled={generate.isPending || (current.package_status === 'failed' && !description.trim())} onClick={() => generate.mutate(current.package_status === 'failed' ? description.trim() : undefined)}>{generate.isPending ? 'Başlatılıyor…' : current.package_status === 'failed' ? 'Kaydet ve yeniden oluştur' : 'Paket oluştur'} <ArrowRight size={17} /></button>{current.package_status === 'failed' && <button className="button secondary" disabled={generate.isPending} onClick={() => generate.mutate(undefined)}>Tekrar dene</button>}</>}</div> : pkg.isError && tab !== 'description' ? <ErrorState error={pkg.error} onRetry={() => pkg.refetch()} /> : tab === 'overview' ? <div className="detail-layout"><div className="detail-primary"><section className="content-panel"><SectionTitle title="Bu ilan neden sana uygun?" /><p className="reason-copy">{current.score_reason || 'Eşleşme analizi hazır olduğunda burada görünecek.'}</p><div className="skill-columns"><div><h3>Eşleşen yetenekler</h3><div className="skill-list">{analysis?.matched_skills.length ? analysis.matched_skills.map(skill => <span className="skill matched" key={skill}><Check size={14} />{skill}</span>) : <span className="muted">Henüz bilgi yok</span>}</div></div><div><h3>Geliştirilebilecek alanlar</h3><div className="skill-list">{analysis?.missing_skills.length ? analysis.missing_skills.map(skill => <span className="skill missing" key={skill}>{skill}</span>) : <span className="muted">Eksik yetenek belirtilmedi</span>}</div></div></div></section><section className="content-panel"><SectionTitle title="Öne çıkan deneyimler" /><p className="muted">CV'de bu ilana uygun deneyim ve projelerin öne çıkarıldı.</p><div className="highlight-list">{analysis?.highlighted_projects.map(project => { const match = projects.data?.find(item => item.id === project); return match ? <span key={project}><FolderIcon /> Proje · {match.name}</span> : null })}{analysis?.highlighted_experience.map(exp => { const match = profile.data?.experience.find(item => item.id === exp); return match ? <span key={exp}><BriefcaseIcon /> Deneyim · {match.title}</span> : null })}{!analysis?.highlighted_projects.length && !analysis?.highlighted_experience.length && <span className="muted">Öne çıkan içerik yok.</span>}</div></section>{analysis?.tips.length ? <section className="content-panel"><SectionTitle title="Kısa notlar" /><ul className="tips-list">{analysis.tips.map(tip => <li key={tip}>{tip}</li>)}</ul></section> : null}</div><aside className="application-panel"><span className="application-panel-symbol">✳</span><h2>Başvuruya hazırsın</h2><p>Her şeyi sırayla tamamla; son adımda başvuruyu kendin gönder.</p><button onClick={() => setTab('cv')}><span>1</span> CV'ni incele <ArrowRight size={16} /></button><button onClick={() => setTab('letter')}><span>2</span> Ön yazıyı kopyala <ArrowRight size={16} /></button>{externalUrl && !demoFixture ? <a href={externalUrl} target="_blank" rel="noopener noreferrer"><span>3</span> İlan sayfasına git <ArrowUpRight size={16} /></a> : <button onClick={() => toast(demoFixture ? "Bu örnek ilanın gerçek bağlantısı yok." : "Geçerli bir ilan bağlantısı bulunamadı.", "info")}><span>3</span> İlan sayfasına git <ArrowUpRight size={16} /></button>}<button className="button application-complete" onClick={() => update.mutate({ status: 'applied' })} disabled={current.status === 'applied' || update.isPending}><CheckCheck size={17} />{current.status === 'applied' ? 'Başvuruldu' : 'Başvurdum olarak işaretle'}</button></aside></div> : tab === 'cv' ? <section className="content-panel cv-panel"><div className="panel-top"><div><h2>İlana özel CV</h2><p>{pkg.data?.cv_language === 'en' ? 'İngilizce' : 'Türkçe'} · PDF</p></div><a className="button primary" href={getCvUrl(id)} download><ArrowDownToLine size={17} /> PDF indir</a></div><div className="pdf-frame desktop-pdf">{isMockMode ? <MockCvPreview /> : <iframe title="CV PDF önizleme" src={getCvUrl(id)} />}</div><a className="button secondary mobile-pdf" href={getCvUrl(id)} target="_blank" rel="noopener noreferrer">PDF'i aç <ExternalLink size={17} /></a></section> : tab === 'letter' ? <section className="content-panel reading-panel"><div className="panel-top"><div><h2>Ön yazı</h2><p>İlana özel hazırlanan metin</p></div><button className="button secondary" onClick={() => copy('letter', pkg.data?.cover_letter || '')}>{copied === 'letter' ? <Check size={17} /> : <Clipboard size={17} />}{copied === 'letter' ? 'Kopyalandı' : 'Kopyala'}</button></div>{pkg.isLoading ? <LoadingRows /> : pkg.isError ? <ErrorState error={pkg.error} onRetry={() => pkg.refetch()} /> : <div className="reading-copy">{pkg.data?.cover_letter || 'Ön yazı bulunamadı.'}</div>}</section> : tab === 'answers' ? <section className="answers-panel"><SectionTitle title="Hazır cevaplar" />{pkg.data?.answers.length ? pkg.data.answers.map((item, index) => <article className="content-panel answer-card" key={`${item.question}-${index}`}><div><h3>{item.question}</h3><button className="button secondary" onClick={() => copy(`answer-${index}`, item.answer)}>{copied === `answer-${index}` ? <Check size={16} /> : <Clipboard size={16} />}{copied === `answer-${index}` ? 'Kopyalandı' : 'Kopyala'}</button></div><p>{item.answer}</p></article>) : <EmptyState title="Hazır cevap yok" description="Bu paket için soru ve cevap üretilmemiş." />}</section> : <section className="content-panel reading-panel"><SectionTitle title="İlan metni" /><div className="reading-copy markdown-content"><JobDescriptionMarkdown content={current.description || 'İlan metni bulunamadı.'} /></div><div className="notes-area"><label htmlFor="job-notes">Kendi notların</label><textarea id="job-notes" rows={4} placeholder="Mülakat, araştırma veya takip notlarını buraya yaz…" value={notes ?? current.notes} onChange={event => setNotes(event.target.value)} /><button className="button secondary" disabled={update.isPending || notes === null || notes === current.notes} onClick={() => update.mutate({ notes: notes || '' })}>Notları kaydet</button></div></section>}
  </>
}

function FolderIcon() { return <span aria-hidden="true">▧</span> }
function BriefcaseIcon() { return <span aria-hidden="true">◈</span> }

function safeExternalUrl(value: string) {
  try { const parsed = new URL(value); return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.href : null }
  catch { return null }
}

function JobDescriptionMarkdown({ content }: { content: string }) {
  return <ReactMarkdown skipHtml components={{ a: ({ href, children }) => {
    const url = href ? safeExternalUrl(href) : null
    return url ? <a href={url} target="_blank" rel="noopener noreferrer">{children}</a> : <span>{children}</span>
  } }}>{content}</ReactMarkdown>
}

function MockCvPreview() {
  return <div className="mock-cv" aria-label="Örnek CV önizlemesi"><div className="mock-cv-head"><strong>Demo Kullanıcı</strong><span>Backend Developer</span><small>demo@example.com · İstanbul, Türkiye</small></div><div className="mock-cv-section"><h3>Profil</h3><p>Python ve FastAPI ile servisler geliştiren demo backend geliştiricisi.</p></div><div className="mock-cv-section"><h3>Deneyim</h3><strong>Backend Developer · Demo Teknoloji</strong><p>FastAPI servisleri ve PostgreSQL veritabanı üzerinde çalıştı.</p></div><div className="mock-cv-section"><h3>Yetenekler</h3><p>Python · FastAPI · PostgreSQL · Docker</p></div><div className="mock-cv-watermark">Örnek CV</div></div>
}
