import { createContext, useContext, useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, NavLink, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { BriefcaseBusiness, ChartNoAxesCombined, CircleHelp, FolderKanban, Menu, Moon, Radar, Settings2, Sun, UserRound, X } from 'lucide-react'
import { api, ApiError, type SearchRun } from './api'
import { AuthGate } from './auth'
import { BandContext } from './band'
import { Dashboard, JobDetail, Jobs } from './pages/Jobs'
import { ProfilePage } from './pages/Profile'
import { ProjectsPage } from './pages/Projects'
import { SettingsPage } from './pages/Settings'
import { ComponentsPage } from './pages/Components'
import { isFresh } from './freshness'

type ToastKind = 'success' | 'error' | 'info'
type Toast = { id: number; text: string; kind: ToastKind }
const ToastContext = createContext<(text: string, kind?: ToastKind) => void>(() => {})
export const useToast = () => useContext(ToastContext)

const navigation = [
  { to: '/', label: 'Özet', icon: ChartNoAxesCombined, end: true },
  { to: '/jobs', label: 'İlanlar', icon: BriefcaseBusiness },
  { to: '/profile', label: 'Profil', icon: UserRound },
  { to: '/projects', label: 'Projeler', icon: FolderKanban },
  { to: '/settings', label: 'Ayarlar', icon: Settings2 },
]

function Shell() {
  const [slot, setSlot] = useState<HTMLElement | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)
  const [runId, setRunId] = useState<string | null>(null)
  const [theme, setTheme] = useState(() => localStorage.getItem('apply-agent-theme') || 'light')
  const location = useLocation()
  const toast = useToast()
  const queryClient = useQueryClient()
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: api.listJobs, refetchInterval: query => query.state.data?.some(job => job.package_status === 'generating') ? 3000 : false })
  const lastRuns = useQuery({ queryKey: ['search-runs'], queryFn: () => api.listSearchRuns(1) })
  const lastRun = lastRuns.data?.[0]
  const finishSearch = (result: SearchRun) => {
    if (result.status === 'done') {
      toast(result.jobs_new ? `Tarama tamamlandı: ${result.jobs_new} yeni ilan.` : 'Tarama tamamlandı, yeni ilan bulunmadı.', 'success')
      if (result.error) toast(result.error, 'info')
    } else toast(result.error || 'Tarama tamamlanamadı.', 'error')
    void queryClient.invalidateQueries({ queryKey: ['jobs'] })
    void queryClient.invalidateQueries({ queryKey: ['search-runs'] })
  }
  const runSearch = useMutation({ mutationFn: api.runSearch, onSuccess: result => {
    if (result.status === 'running') { setRunId(result.id); toast('Tarama başladı.', 'info') }
    else finishSearch(result)
  }, onError: error => toast(error.message, 'error') })
  const run = useQuery({ queryKey: ['search-run', runId], queryFn: () => api.getSearchRun(runId!), enabled: Boolean(runId), refetchInterval: query => ['done', 'failed'].includes(query.state.data?.status || '') ? false : 2500 })
  // Only what the latest run brought in; the rest are still listed under "İncelenecek".
  const newCount = jobs.data?.filter(job => isFresh(job, lastRun)).length ?? 0
  const searching = runSearch.isPending || Boolean(runId)
  const scanState = searching ? 'running' : lastRun?.status === 'failed' || lastRuns.isError ? 'failed' : 'idle'

  useEffect(() => { setMenuOpen(false); window.scrollTo(0, 0) }, [location.pathname])
  useEffect(() => { if (lastRun?.status === 'running') setRunId(lastRun.id) }, [lastRun?.id, lastRun?.status])
  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem('apply-agent-theme', theme) }, [theme])
  // Jobs are saved batch by batch while a search runs; show them as they come.
  useEffect(() => {
    if (!runId || run.data?.status !== 'running') return
    void queryClient.invalidateQueries({ queryKey: ['jobs'] })
    void queryClient.invalidateQueries({ queryKey: ['search-runs'] })
  }, [runId, run.data?.jobs_scored, run.data?.jobs_new])
  useEffect(() => {
    if (!runId) return
    if (run.isError) { toast(run.error.message, 'error'); setRunId(null) }
    else if (run.data && run.data.status !== 'running') { finishSearch(run.data); setRunId(null) }
  }, [runId, run.data, run.isError, run.error])

  const scanButton = (label: boolean) => <button className="button scan-button" onClick={() => runSearch.mutate()} disabled={searching} aria-label={searching ? 'Taranıyor' : 'Şimdi tara'}><Radar size={17} className={searching ? 'spin' : ''} />{label && <span>{searching ? 'Taranıyor…' : 'Şimdi tara'}</span>}</button>

  return <BandContext.Provider value={slot}><div className={`app-shell ${location.pathname === '/' ? 'overlap' : ''}`}>
    <div className="backdrop" aria-hidden="true"><span className="orb one" /><span className="orb two" /><span className="orb three" /></div>
    {menuOpen && <button className="mobile-scrim" aria-label="Menüyü kapat" onClick={() => setMenuOpen(false)} />}
    <aside className={`sidebar ${menuOpen ? 'open' : ''}`}>
      <div className="brand"><span className="brand-mark"><BriefcaseBusiness size={18} strokeWidth={2.1} /></span><span><strong>Apply Agent</strong><small>Başvuru çalışma alanın</small></span><button className="icon-button mobile-close" aria-label="Menüyü kapat" onClick={() => setMenuOpen(false)}><X size={20} /></button></div>
      <div className="sidebar-content">
        <p className="nav-caption">Çalışma alanı</p>
        <nav className="nav-list" aria-label="Ana menü">{navigation.map(item => <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}><item.icon size={19} strokeWidth={1.9} /><span>{item.label}</span>{item.to === '/jobs' && newCount > 0 && <span className="nav-count">{newCount}</span>}</NavLink>)}</nav>
      </div>
      <div className="sidebar-footer">
        <div className={`scan-status ${scanState}`}><span className="scan-pulse" /><span><strong>{searching ? 'Taranıyor…' : lastRun ? `Son tarama: ${formatRunTime(lastRun.started_at)}` : lastRuns.isPending ? 'Tarama bilgisi yükleniyor…' : lastRuns.isError ? 'Tarama bilgisi alınamadı' : 'Henüz tarama yapılmadı'}</strong>{searching && run.data && <small>{run.data.jobs_scored} ilan puanlandı, {run.data.jobs_new} yeni</small>}{lastRun && !searching && <small>{lastRun.status === 'failed' ? 'Tarama tamamlanamadı' : `${lastRun.jobs_new} yeni ilan`}</small>}</span></div>
        {lastRun?.error && !searching && <p className="scan-warning">{lastRun.error}</p>}
        {lastRuns.isError && <button className="text-button" onClick={() => void lastRuns.refetch()}>Tekrar dene</button>}
        {scanButton(true)}
        <div className="footer-links"><button className="icon-button" title={theme === 'light' ? 'Koyu tema' : 'Açık tema'} aria-label={theme === 'light' ? 'Koyu temaya geç' : 'Açık temaya geç'} onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>{theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}</button><NavLink title="Bileşenler" aria-label="Bileşenler" to="/components" className="icon-button"><CircleHelp size={18} /></NavLink></div>
      </div>
    </aside>
    <div className="shell-main">
      <div className="band">
        <div className="mobile-bar"><button className="icon-button band-icon" aria-label="Menüyü aç" onClick={() => setMenuOpen(true)}><Menu size={21} /></button><strong>Apply Agent</strong>{scanButton(false)}</div>
        <div className="band-inner" ref={setSlot} />
      </div>
      <main className="main-panel">
        <div className="main-inner">{runSearch.error instanceof ApiError && runSearch.error.status === 409 && <div className="inline-error" role="alert">{runSearch.error.message} <Link to="/profile">Profilini doldur</Link></div>}<Outlet context={{ runSearch: () => runSearch.mutate(), searching }} /></div>
      </main>
    </div>
  </div></BandContext.Provider>
}

export default function App() {
  const [toasts, setToasts] = useState<Toast[]>([])
  const addToast = (text: string, kind: ToastKind = 'info') => {
    const id = Date.now() + Math.random()
    setToasts(current => [...current, { id, text, kind }])
    window.setTimeout(() => setToasts(current => current.filter(item => item.id !== id)), 4500)
  }
  return <ToastContext.Provider value={addToast}>
    <AuthGate><Routes><Route element={<Shell />}>
      <Route index element={<Dashboard />} />
      <Route path="jobs" element={<Jobs />} />
      <Route path="jobs/:id" element={<JobDetail />} />
      <Route path="profile" element={<ProfilePage />} />
      <Route path="projects" element={<ProjectsPage />} />
      <Route path="settings" element={<SettingsPage />} />
      <Route path="components" element={<ComponentsPage />} />
      <Route path="*" element={<div className="not-found"><h1>Bu sayfa bulunamadı.</h1><NavLink to="/">Özete dön</NavLink></div>} />
    </Route></Routes></AuthGate>
    <div className="toast-stack" role="status" aria-live="polite">{toasts.map(item => <div className={`toast ${item.kind}`} key={item.id}>{item.text}<button aria-label="Bildirimi kapat" onClick={() => setToasts(current => current.filter(toast => toast.id !== item.id))}><X size={15} /></button></div>)}</div>
  </ToastContext.Provider>
}

function formatRunTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Tarih bilinmiyor'
  const day = date.toLocaleDateString('tr-TR') === new Date().toLocaleDateString('tr-TR') ? 'bugün' : date.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long' })
  return `${day} ${date.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}`
}
