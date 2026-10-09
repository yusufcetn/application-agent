import { ArrowUpRight, BadgeCheck, Check, CircleAlert, CircleX, Clock3, LoaderCircle } from 'lucide-react'
import type { HTMLAttributes, ReactNode } from 'react'
import type { EmploymentType, Job, JobStatus, PackageStatus } from '../api'
import { BandPortal } from '../band'

export const statusLabels: Record<JobStatus, string> = {
  new: 'İncelenecek', applied: 'Başvuruldu', skipped: 'Geçildi', interview: 'Mülakat', rejected: 'Olumsuz', offer: 'Teklif',
}

export const sourceLabels: Record<string, string> = {
  manual: 'Elle eklendi', greenhouse: 'Greenhouse', lever: 'Lever', ashby: 'Ashby',
  remoteok: 'RemoteOK', remotive: 'Remotive', arbeitnow: 'Arbeitnow', adzuna: 'Adzuna', email: 'E-posta alarmı',
  web: 'Web araması',
}

export const employmentLabels: Record<EmploymentType, string> = {
  full_time: 'Tam zamanlı', part_time: 'Yarı zamanlı', working_student: 'Working student', internship: 'Staj', contract: 'Sözleşmeli',
}

export function ScoreBadge({ score, large = false }: { score: number | null; large?: boolean }) {
  const tone = score == null ? 'muted' : score >= 80 ? 'high' : score >= 60 ? 'medium' : 'low'
  const stroke = large ? 2.6 : 3.4
  return <span className={`score-badge ${tone} ${large ? 'large' : ''}`} aria-label={score == null ? 'Uyum puanı yok' : `Uyum puanı ${score}`}>
    <svg viewBox="0 0 36 36" aria-hidden="true"><circle className="score-track" cx="18" cy="18" r="15.9155" strokeWidth={stroke} /><circle className="score-value" cx="18" cy="18" r="15.9155" strokeWidth={stroke} strokeDasharray={`${Math.max(0, Math.min(100, score ?? 0))} 100`} transform="rotate(-90 18 18)" /></svg>
    <strong>{score == null ? '—' : score}</strong>{large && <small>uyum</small>}
  </span>
}

export function StatusPill({ status }: { status: JobStatus }) {
  return <span className={`status-pill ${status}`}><span className="status-dot" />{statusLabels[status]}</span>
}

export function PackageBadge({ status }: { status: PackageStatus }) {
  const icon = status === 'ready' ? <Check size={14} /> : status === 'generating' ? <LoaderCircle size={14} className="spin" /> : status === 'failed' ? <CircleAlert size={14} /> : <Clock3 size={14} />
  const label = { ready: 'Paket hazır', generating: 'Hazırlanıyor', failed: 'Paket hatası', none: 'Paket yok' }[status]
  return <span className={`package-badge ${status}`}>{icon}{label}</span>
}

/** Whether the posting still takes applications; nothing while that is unknown. */
export function PostingBadge({ job }: { job: Pick<Job, 'posting_status' | 'verification_reason'> }) {
  if (job.posting_status === 'unknown') return null
  const open = job.posting_status === 'open'
  return <span className={`posting-badge ${job.posting_status}`} title={job.verification_reason || undefined}>{open ? <BadgeCheck size={14} /> : <CircleX size={14} />}{open ? 'Açık' : 'Kapandı'}</span>
}

export function SectionTitle({ title, action }: { title: string; action?: ReactNode }) {
  return <div className="section-heading"><h2>{title}</h2>{action}</div>
}

export function PageHeading({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: string; actions?: ReactNode }) {
  return <BandPortal><header className="page-heading"><div>{eyebrow && <p className="page-eyebrow">{eyebrow}</p>}<h1>{title}</h1>{description && <p className="page-description">{description}</p>}</div>{actions && <div className="page-actions">{actions}</div>}</header></BandPortal>
}

export function EmptyState({ icon, title, description, action }: { icon?: ReactNode; title: string; description: string; action?: ReactNode }) {
  return <div className="empty-state"><div className="empty-icon">{icon || <ArrowUpRight size={23} />}</div><h3>{title}</h3><p>{description}</p>{action}</div>
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return <div className="empty-state error-state"><div className="empty-icon"><CircleAlert size={22} /></div><h3>Bu bölüm yüklenemedi</h3><p>{error instanceof Error ? error.message : 'Beklenmeyen bir sorun oluştu.'}</p>{onRetry && <button className="button secondary" onClick={onRetry}>Tekrar dene</button>}</div>
}

export function LoadingRows({ count = 3 }: { count?: number }) {
  return <div className="loading-rows" aria-label="Yükleniyor">{Array.from({ length: count }, (_, index) => <div className="loading-row skeleton" key={index} />)}</div>
}

export function Field({ label, hint, children, ...props }: { label: string; hint?: string; children: ReactNode } & HTMLAttributes<HTMLDivElement>) {
  return <div className="field" {...props}><label className="field-label">{label}</label>{children}{hint && <p className="field-hint">{hint}</p>}</div>
}

export function TagList({ items, onRemove }: { items: string[]; onRemove?: (item: string) => void }) {
  return <div className="tag-list">{items.map(item => <span className="tag" key={item}>{item}{onRemove && <button type="button" aria-label={`${item} etiketini kaldır`} onClick={() => onRemove(item)}>×</button>}</span>)}</div>
}

export function TagInput({ items, onChange, placeholder = 'Yaz ve Enter’a bas' }: { items: string[]; onChange: (items: string[]) => void; placeholder?: string }) {
  const commit = (raw: string) => {
    const value = raw.trim().replace(/,$/, '')
    if (value && !items.some(item => item.toLocaleLowerCase('tr') === value.toLocaleLowerCase('tr'))) onChange([...items, value])
  }
  return <div className="tag-input"><TagList items={items} onRemove={item => onChange(items.filter(value => value !== item))} /><input aria-label={placeholder} placeholder={placeholder} onBlur={event => { commit(event.currentTarget.value); event.currentTarget.value = '' }} onKeyDown={event => {
    if (event.key !== 'Enter' && event.key !== ',') return
    event.preventDefault()
    commit(event.currentTarget.value)
    event.currentTarget.value = ''
  }} /></div>
}

export function formatDate(value: string | null | undefined) {
  if (!value) return 'Tarih yok'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Tarih yok' : new Intl.DateTimeFormat('tr-TR', { day: 'numeric', month: 'long' }).format(date)
}
