import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Clock3, Compass, Mail, Radar, SlidersHorizontal, Sparkles, Search } from 'lucide-react'
import { api } from '../api'
import type { SearchSettings, Seniority } from '../api'
import { useToast } from '../App'
import { useAuth } from '../auth'
import { ErrorState, Field, LoadingRows, PageHeading, SectionTitle, TagInput } from '../components/ui'
import { mergeCompanySuggestions, mergeSuggestedRoles } from '../settingsSuggestions'

const levels: { value: Seniority; label: string }[] = [{ value: 'intern', label: 'Stajyer' }, { value: 'junior', label: 'Junior' }, { value: 'mid', label: 'Mid' }, { value: 'senior', label: 'Senior' }, { value: 'lead', label: 'Lead' }]
const sourceToggles = [{ key: 'remoteok', label: 'RemoteOK' }, { key: 'remotive', label: 'Remotive' }, { key: 'arbeitnow', label: 'Arbeitnow' }, { key: 'adzuna', label: 'Adzuna' }] as const

export function SettingsPage() {
  const settings = useQuery({ queryKey: ['settings'], queryFn: api.getSettings })
  const [draft, setDraft] = useState<SearchSettings | null>(null)
  const [dirty, setDirty] = useState(false)
  const [roleDescription, setRoleDescription] = useState('')
  const [rolePreview, setRolePreview] = useState<string[] | null>(null)
  const [companyTheme, setCompanyTheme] = useState('')
  const [selectedCompanies, setSelectedCompanies] = useState<string[]>([])
  const toast = useToast()
  const auth = useAuth()
  const queryClient = useQueryClient()
  useEffect(() => { if (settings.data && !dirty) setDraft(settings.data) }, [settings.data, dirty])
  const save = useMutation({ mutationFn: api.saveSettings, onSuccess: result => { setDraft(result); setDirty(false); queryClient.setQueryData(['settings'], result); toast('Arama ayarları kaydedildi.', 'success') } })
  const sendReport = useMutation({
    mutationFn: async () => {
      const [run] = await api.listSearchRuns(1)
      if (!run) throw new Error('Henüz tarama yapılmadı; rapor için önce bir tarama gerekli.')
      return api.sendRunReport(run.id)
    },
    onSuccess: result => toast(`Rapor gönderildi: ${result.sent_to}`, 'success'),
    onError: error => toast(error.message, 'error'),
  })
  const suggestRoles = useMutation({
    mutationFn: api.suggestRoles,
    onSuccess: result => setRolePreview(result.target_roles),
  })
  const discoverCompanies = useMutation({
    mutationFn: api.discoverCompanies,
    onSuccess: () => setSelectedCompanies([]),
  })
  const update = (change: Partial<SearchSettings>) => { setDraft(current => current ? { ...current, ...change } : current); setDirty(true) }
  const mergeRoles = (items: string[]) => {
    setDraft(current => current ? mergeSuggestedRoles(current, items) : current)
    setDirty(true)
  }
  const mergeCompanies = () => {
    const companies = discoverCompanies.data?.companies.filter(company => selectedCompanies.includes(companyKey(company)) && canonicalBoardUrl(company)) ?? []
    if (!companies.length) return
    setDraft(current => {
      if (!current) return current
      return mergeCompanySuggestions(current, companies)
    })
    setDirty(true)
  }
  if (settings.isLoading) return <LoadingRows count={5} />
  if (settings.isError || !draft) return <ErrorState error={settings.error || new Error('Ayarlar yüklenemedi.')} onRetry={() => settings.refetch()} />
  const [cronMinute, cronHour] = draft.schedule_cron.split(' ')
  const hour = Number(cronHour)
  const minute = Number(cronMinute)
  const scheduleTime = `${String(Number.isInteger(hour) && hour >= 0 && hour < 24 ? hour : 8).padStart(2, '0')}:${String(Number.isInteger(minute) && minute >= 0 && minute < 60 ? minute : 0).padStart(2, '0')}`
  const setScheduleTime = (value: string) => { const [selectedHour, selectedMinute] = value.split(':').map(Number); if (Number.isInteger(selectedHour) && Number.isInteger(selectedMinute)) update({ schedule_cron: `${selectedMinute} ${selectedHour} * * *` }) }
  return <><PageHeading eyebrow="Arama tercihlerin" title="Ayarlar" description="Sana uygun fırsatları bulmak için sınırlarını ve önceliklerini belirle." actions={<button className="button primary" disabled={!dirty || save.isPending} onClick={() => save.mutate(draft)}><Check size={17} /> {save.isPending ? 'Kaydediliyor…' : 'Ayarları kaydet'}</button>} />
    <div className="settings-layout"><div className="settings-lead"><div className="settings-lead-icon"><Compass size={28} /></div><h2>Aradığın işe biraz daha yaklaş.</h2><p>Buradaki tercihler ilan taramasını ve hangi başvuru paketlerinin otomatik hazırlanacağını belirler.</p></div><div className="settings-sections">
      <section className="content-panel form-section"><SectionTitle title="Ne arıyorsun?" /><Field label="Hedef pozisyonlar"><TagInput items={draft.target_roles} onChange={target_roles => update({ target_roles })} placeholder="Pozisyon ekle" /></Field>
        <div className="suggestion-tool"><label className="field-label" htmlFor="role-description">İş hedefini anlat</label><textarea id="role-description" rows={3} maxLength={2000} value={roleDescription} onChange={event => setRoleDescription(event.target.value)} placeholder="Örn. Python ve bulut servisleriyle API geliştirdiğim, uzaktan çalışabileceğim ürün ekipleri arıyorum." /><p className="field-hint">Yapay zekâ bu açıklamadan uygun pozisyon anahtar kelimeleri önerir. En az 3 karakter.</p><button className="button secondary" type="button" disabled={roleDescription.trim().length < 3 || suggestRoles.isPending} onClick={() => { setRolePreview(null); suggestRoles.mutate(roleDescription.trim()) }}><Sparkles size={16} />{suggestRoles.isPending ? 'Öneriler hazırlanıyor…' : 'Pozisyon öner'}</button>
          {suggestRoles.isPending && <p className="suggestion-status" role="status">Pozisyon önerileri hazırlanıyor…</p>}
          {suggestRoles.isError && <p className="error-message" role="alert">{suggestRoles.error.message}</p>}
          {rolePreview && <div className="suggestion-preview">{rolePreview.length === 0 ? <p className="suggestion-status" role="status">Bu açıklama için pozisyon önerisi bulunamadı. Açıklamayı değiştirip yeniden deneyebilirsin.</p> : <><label className="field-label">Önerileri düzenle</label><TagInput items={rolePreview} onChange={setRolePreview} placeholder="Öneri ekle" /><p className="field-hint">Ekleme yalnızca ayar taslağını değiştirir; kalıcı olması için ayarları kaydet.</p><button className="button primary" type="button" disabled={suggestRoles.isPending || !rolePreview.some(role => role.trim())} onClick={() => mergeRoles(rolePreview)}>Pozisyonları ekle</button></>}</div>}
        </div>
        <Field label="Deneyim seviyesi"><div className="choice-list">{levels.map(level => <label className={`choice-chip ${draft.seniority.includes(level.value) ? 'selected' : ''}`} key={level.value}><input type="checkbox" checked={draft.seniority.includes(level.value)} onChange={event => update({ seniority: event.target.checked ? [...draft.seniority, level.value] : draft.seniority.filter(item => item !== level.value) })} />{level.label}</label>)}</div></Field><Field label="Hariç tutulacak kelimeler"><TagInput items={draft.keywords_exclude} onChange={keywords_exclude => update({ keywords_exclude })} placeholder="Kelime ekle" /></Field></section>
      <section className="content-panel form-section"><SectionTitle title="Nerede?" /><Field label="Konumlar"><TagInput items={draft.locations} onChange={locations => update({ locations })} placeholder="Konum ekle" /></Field><label className="toggle-row"><span><strong>Sadece uzaktan</strong><small>Yalnızca remote ilanları göster.</small></span><input type="checkbox" checked={draft.remote_only} onChange={event => update({ remote_only: event.target.checked })} /><span className="switch" /></label></section>
      <section className="content-panel form-section"><SectionTitle title="Eşleşme ve paket" /><Field label={`Minimum uyum puanı: ${draft.min_score}`} hint="Bu puanın üzerindeki ilanlar için paket otomatik hazırlanabilir."><input type="range" min="0" max="100" step="5" value={draft.min_score} onChange={event => update({ min_score: Number(event.target.value) })} /></Field><label className="toggle-row"><span><strong>Paketleri otomatik hazırla</strong><small>Uygun ilanlarda CV ve ön yazı üret.</small></span><input type="checkbox" checked={draft.auto_package} onChange={event => update({ auto_package: event.target.checked })} /><span className="switch" /></label><Field label="CV dili"><select aria-label="CV dili" value={draft.cv_language} onChange={event => update({ cv_language: event.target.value as SearchSettings['cv_language'] })}><option value="auto">İlan diline göre</option><option value="tr">Türkçe</option><option value="en">İngilizce</option></select></Field></section>
      <section className="content-panel form-section"><SectionTitle title="İlan kaynakları" /><p className="section-help">Takip edilecek siteleri ve şirketleri seç.</p>{sourceToggles.map(source => <label className="toggle-row source-toggle" key={source.key}><span><strong>{source.label}</strong></span><input type="checkbox" checked={draft.sources[source.key]} onChange={event => update({ sources: { ...draft.sources, [source.key]: event.target.checked } })} /><span className="switch" /></label>)}<div className="source-company-grid"><Field label="Greenhouse şirketleri" hint="Örnek: job-boards.greenhouse.io/anthropic → anthropic"><TagInput items={draft.sources.greenhouse} onChange={greenhouse => update({ sources: { ...draft.sources, greenhouse } })} placeholder="Şirket adı ekle" /></Field><Field label="Lever şirketleri" hint="Örnek: jobs.lever.co/palantir → palantir"><TagInput items={draft.sources.lever} onChange={lever => update({ sources: { ...draft.sources, lever } })} placeholder="Şirket adı ekle" /></Field><Field label="Ashby şirketleri" hint="Örnek: jobs.ashbyhq.com/ramp → ramp"><TagInput items={draft.sources.ashby} onChange={ashby => update({ sources: { ...draft.sources, ashby } })} placeholder="Şirket adı ekle" /></Field>
        <div className="suggestion-tool company-discovery"><label className="field-label" htmlFor="company-theme">Çalışmak istediğin şirketleri anlat</label><textarea id="company-theme" rows={3} maxLength={2000} value={companyTheme} onChange={event => setCompanyTheme(event.target.value)} placeholder="Örn. iklim teknolojisi alanında çalışan, Avrupa'da ürün ekibi olan şirketler." /><p className="field-hint">Şirketlerin kariyer panoları Greenhouse, Lever ve Ashby üzerinde aranıp doğrulanır. Mevcut pozisyon ve konum tercihlerin araştırma kapsamına eklenir.</p><button className="button secondary" type="button" disabled={companyTheme.trim().length < 3 || discoverCompanies.isPending} onClick={() => { setSelectedCompanies([]); discoverCompanies.mutate({ description: companyTheme.trim(), target_roles: draft.target_roles.slice(0, 30).map(item => item.slice(0, 120)), locations: draft.locations.slice(0, 30).map(item => item.slice(0, 120)), remote_only: draft.remote_only }) }}><Search size={16} />{discoverCompanies.isPending ? 'Şirketler araştırılıyor…' : 'Şirket önerilerini araştır'}</button>
          {discoverCompanies.isPending && <p className="suggestion-status" role="status">Şirket panoları aranıp doğrulanıyor…</p>}
          {discoverCompanies.isError && <p className="error-message" role="alert">{discoverCompanies.error.message}</p>}
          {discoverCompanies.data && !discoverCompanies.isPending && <div className="suggestion-preview" aria-live="polite">
            {discoverCompanies.data.warnings.map((warning, index) => <p className="field-hint" role="status" key={`${warning}-${index}`}>{warning}</p>)}
            {discoverCompanies.data.companies.length === 0 ? <p className="suggestion-status" role="status">Doğrulanmış şirket önerisi bulunamadı. Açıklamayı değiştirip yeniden araştırabilirsin.</p> : <>
              <p className="field-label">Doğrulanmış şirket panoları</p><div className="company-suggestions">{discoverCompanies.data.companies.map(company => { const key = companyKey(company); const href = canonicalBoardUrl(company); return <label className="company-suggestion" key={key}><input type="checkbox" disabled={!href} checked={selectedCompanies.includes(key)} onChange={event => setSelectedCompanies(current => event.target.checked ? [...current, key] : current.filter(item => item !== key))} /><span className="company-suggestion-copy"><strong>{company.name}</strong><small>{company.source} · {company.slug}</small><span>{company.reason}</span>{href && <a href={href} target="_blank" rel="noreferrer" onClick={event => event.stopPropagation()}>Kariyer panosunu aç</a>}</span></label> })}</div><p className="field-hint">Ekleme yalnızca ayar taslağını değiştirir; kalıcı olması için ayarları kaydet.</p><button className="button primary" type="button" disabled={discoverCompanies.isPending || !discoverCompanies.data.companies.some(company => selectedCompanies.includes(companyKey(company)) && canonicalBoardUrl(company))} onClick={mergeCompanies}>Seçilen şirketleri ekle</button>
            </>}
          </div>}
        </div>
      </div><label className="toggle-row"><span><strong>Web araması</strong><small>Yapay zekâ ajanı şirket kariyer sayfalarında, Youthall ve Kariyer.net'te, LinkedIn linkleri üzerinden açık ilan arar ve her ilanın sayfasını açıp başvuruya açık olduğunu kontrol eder. Tarama birkaç dakika uzar.</small></span><input type="checkbox" checked={draft.sources.web_search} onChange={event => update({ sources: { ...draft.sources, web_search: event.target.checked } })} /><span className="switch" /></label><label className="toggle-row"><span><strong>E-posta alarmları</strong><small>LinkedIn, Kariyer.net, Indeed alarm e-postalarını okur. E-posta bilgileri bilgisayardaki .env dosyasında ayarlanır.</small></span><input type="checkbox" checked={draft.sources.email_alerts} onChange={event => update({ sources: { ...draft.sources, email_alerts: event.target.checked } })} /><span className="switch" /></label></section>
      <section className="content-panel form-section"><SectionTitle title="Zamanlama" /><div className="schedule-row"><div className="schedule-icon"><Clock3 size={20} /></div><div><strong>Günlük tarama saati</strong><p>Yeni fırsatlar her gün bu saatte aranır.</p></div><input type="time" aria-label="Günlük tarama saati" value={scheduleTime} onInput={event => setScheduleTime(event.currentTarget.value)} onChange={event => setScheduleTime(event.target.value)} /></div><label className="toggle-row"><span><strong>Sabah raporu</strong><small>Günlük taramadan sonra yeni, kapanan ve son başvurusu yaklaşan ilanları e-postayla gönderir. E-posta hesabı bilgisayardaki .env dosyasında ayarlanır.</small></span><input type="checkbox" checked={draft.daily_report} onChange={event => update({ daily_report: event.target.checked })} /><span className="switch" /></label><button className="button secondary" type="button" disabled={sendReport.isPending} onClick={() => sendReport.mutate()}><Mail size={16} /> {sendReport.isPending ? 'Gönderiliyor…' : 'Son taramanın raporunu şimdi gönder'}</button></section>
      {save.error && <p role="alert" className="error-message">{save.error.message}</p>}<div className="form-bottom"><span><SlidersHorizontal size={16} /> {dirty ? 'Kaydedilmemiş değişiklikler var' : 'Tercihlerin güncel'}</span><button className="button primary" disabled={!dirty || save.isPending} onClick={() => save.mutate(draft)}><Check size={17} /> Kaydet</button></div>{auth.tokenRequired && <button className="text-button" disabled={auth.loggingOut} onClick={auth.logout}>{auth.loggingOut ? 'Çıkış yapılıyor…' : 'Bu cihazdan çıkış yap'}</button>}
    </div></div><div className="settings-footnote"><Radar size={17} /> Ayarları kaydettikten sonra yeni ilan aramak için “Şimdi tara”yı kullanabilirsin.</div>
  </>
}

function companyKey(company: { source: string; slug: string }): string { return `${company.source}:${company.slug.toLocaleLowerCase('en-US')}` }

function canonicalBoardUrl(company: { source: string; slug: string }): string | null {
  const hosts = { greenhouse: 'job-boards.greenhouse.io', lever: 'jobs.lever.co', ashby: 'jobs.ashbyhq.com' }
  if (!(company.source in hosts) || !company.slug.trim()) return null
  const host = hosts[company.source as keyof typeof hosts]
  return `https://${host}/${encodeURIComponent(company.slug.trim())}`
}
