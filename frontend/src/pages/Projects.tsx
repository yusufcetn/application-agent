import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUpRight, FileUp, FolderKanban, Plus, Star, Trash2, X } from 'lucide-react'
import { api } from '../api'
import { normalizeProject } from '../api/normalize'
import type { Project, ProjectImportIssue, ProjectInput } from '../api'
import { useToast } from '../App'
import { EmptyState, ErrorState, Field, LoadingRows, PageHeading, TagInput, TagList } from '../components/ui'

const blankProject = (): ProjectInput => ({ name: '', role: '', summary: '', bullets: [], tech: [], links: [], start_date: '', end_date: null, featured: false })

function ProjectDrawer({ project, onClose }: { project: Project | null; onClose: () => void }) {
  const [draft, setDraft] = useState<ProjectInput>(project || blankProject())
  const toast = useToast()
  const queryClient = useQueryClient()
  const save = useMutation({ mutationFn: () => project ? api.updateProject(project.id, normalizeProject(draft)) : api.createProject(normalizeProject(draft)), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['projects'] }); toast(project ? 'Proje güncellendi.' : 'Proje eklendi.', 'success'); onClose() }, onError: error => toast(error.message, 'error') })
  const remove = useMutation({ mutationFn: () => api.deleteProject(project!.id), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['projects'] }); toast('Proje silindi.', 'success'); onClose() }, onError: error => toast(error.message, 'error') })
  const update = (patch: Partial<ProjectInput>) => setDraft(current => ({ ...current, ...patch }))
  useEffect(() => { const close = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }; document.addEventListener('keydown', close); return () => document.removeEventListener('keydown', close) }, [onClose])
  return <div className="drawer-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}><aside className="drawer" role="dialog" aria-modal="true" aria-label={project ? 'Projeyi düzenle' : 'Proje ekle'}><div className="drawer-header"><div><p className="page-eyebrow">Portföy</p><h2>{project ? 'Projeyi düzenle' : 'Yeni proje'}</h2></div><button className="icon-button" aria-label="Kapat" onClick={onClose}><X size={20} /></button></div><div className="drawer-body"><Field label="Proje adı"><input aria-label="Proje adı" value={draft.name} onChange={event => update({ name: event.target.value })} placeholder="Projenin adı" /></Field><Field label="Rolün"><input aria-label="Rolün" value={draft.role || ''} onChange={event => update({ role: event.target.value })} placeholder="Frontend geliştirici" /></Field><Field label="Kısa açıklama"><textarea aria-label="Kısa açıklama" rows={4} value={draft.summary} onChange={event => update({ summary: event.target.value })} /></Field><Field label="Öne çıkan çalışmalar" hint="Her satıra bir madde yaz."><textarea aria-label="Öne çıkan çalışmalar" rows={5} value={draft.bullets.join('\n')} onChange={event => update({ bullets: event.target.value.split('\n') })} /></Field><Field label="Teknolojiler"><TagInput items={draft.tech} onChange={tech => update({ tech })} /></Field><div className="form-grid"><Field label="Başlangıç"><input aria-label="Başlangıç ayı" type="month" value={draft.start_date || ''} onChange={event => update({ start_date: event.target.value })} /></Field><Field label="Bitiş"><input aria-label="Bitiş ayı" type="month" value={draft.end_date || ''} onChange={event => update({ end_date: event.target.value || null })} /></Field></div><div className="repeat-list">{draft.links.map((link, index) => <div className="inline-fields" key={index}><input aria-label={`Bağlantı ${index + 1} adı`} placeholder="GitHub" value={link.label} onChange={event => update({ links: draft.links.map((item, i) => i === index ? { ...item, label: event.target.value } : item) })} /><input aria-label={`Bağlantı ${index + 1} adresi`} type="url" placeholder="https://" value={link.url} onChange={event => update({ links: draft.links.map((item, i) => i === index ? { ...item, url: event.target.value } : item) })} /><button className="icon-button" aria-label="Bağlantıyı sil" onClick={() => update({ links: draft.links.filter((_, i) => i !== index) })}><Trash2 size={17} /></button></div>)}</div><button className="text-button" onClick={() => update({ links: [...draft.links, { label: '', url: '' }] })}><Plus size={16} /> Bağlantı ekle</button><label className="toggle-row"><span><strong>Öne çıkan proje</strong><small>Başvuru paketlerinde öncelik verilir.</small></span><input type="checkbox" checked={draft.featured} onChange={event => update({ featured: event.target.checked })} /><span className="switch" /></label></div><div className="drawer-footer">{project && <button className="button danger" disabled={remove.isPending} onClick={() => { if (window.confirm('Bu projeyi silmek istediğine emin misin?')) remove.mutate() }}><Trash2 size={16} /> Sil</button>}<button className="button primary" disabled={!draft.name.trim() || save.isPending} onClick={() => save.mutate()}>{save.isPending ? 'Kaydediliyor…' : 'Projeyi kaydet'}</button></div></aside></div>
}

export function ProjectsPage() {
  const projects = useQuery({ queryKey: ['projects'], queryFn: api.listProjects })
  const [drawer, setDrawer] = useState<{ open: boolean; project: Project | null }>({ open: false, project: null })
  const [importIssues, setImportIssues] = useState<ProjectImportIssue[]>([])
  const fileInput = useRef<HTMLInputElement>(null)
  const toast = useToast()
  const queryClient = useQueryClient()
  const importFiles = useMutation({
    mutationFn: api.importProjects,
    onSuccess: result => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setImportIssues(result.errors)
      const parts = [result.created.length && `${result.created.length} proje eklendi`, result.updated.length && `${result.updated.length} proje güncellendi`].filter(Boolean)
      if (parts.length) toast(`${parts.join(', ')}.`, 'success')
      if (result.errors.length) toast(`${result.errors.length} kayıt içe aktarılamadı.`, 'error')
    },
    onError: error => toast(error.message, 'error'),
  })
  const pickFiles = (list: FileList | null) => {
    const files = Array.from(list || [])
    if (fileInput.current) fileInput.current.value = ''
    if (files.length) importFiles.mutate(files)
  }
  const importButton = <button className="button secondary" disabled={importFiles.isPending} onClick={() => fileInput.current?.click()}><FileUp size={17} /> {importFiles.isPending ? 'İçe aktarılıyor…' : 'JSON içe aktar'}</button>
  return <><PageHeading eyebrow="Portföy" title="Projeler" description="İlana özel CV’lerde kullanılabilecek çalışmalarını burada topla." actions={<>{importButton}<button className="button primary" onClick={() => setDrawer({ open: true, project: null })}><Plus size={17} /> Proje ekle</button></>} />
    <input ref={fileInput} type="file" accept=".json,application/json" multiple hidden onChange={event => pickFiles(event.target.files)} />
    {importIssues.length > 0 && <section className="content-panel form-section" role="alert"><div className="panel-top"><div><h2>İçe aktarılamayanlar</h2><p>Dosyayı düzeltip tekrar içe aktarabilirsin; eklenmiş projeler kopyalanmaz, güncellenir.</p></div><button className="icon-button" aria-label="Kapat" onClick={() => setImportIssues([])}><X size={18} /></button></div><ul className="tips-list">{importIssues.map((issue, index) => <li key={`${issue.file}-${index}`}><strong>{issue.file}</strong>: {issue.message}</li>)}</ul></section>}
    <div className="projects-intro"><span className="projects-intro-icon"><FolderKanban size={22} /></span><p>Projelerini somut sonuçlarıyla anlat. Sistem, ilana en yakın olanları CV’ne taşır.</p></div>
    {projects.isLoading ? <LoadingRows count={3} /> : projects.isError ? <ErrorState error={projects.error} onRetry={() => projects.refetch()} /> : projects.data?.length ? <div className="project-grid">{projects.data.map(project => <button className="project-card" key={project.id} onClick={() => setDrawer({ open: true, project })}><div className="project-card-top"><span className="project-monogram">{project.name.slice(0, 1).toLocaleUpperCase('tr')}</span>{project.featured && <span className="featured"><Star size={14} fill="currentColor" /> Öne çıkan</span>}</div><h2>{project.name}</h2><p className="project-role">{project.role || 'Rol belirtilmemiş'}</p><p className="project-summary">{project.summary || 'Henüz açıklama eklenmedi.'}</p><TagList items={project.tech.slice(0, 4)} /><span className="project-open">Projeyi düzenle <ArrowUpRight size={16} /></span></button>)}</div> : <EmptyState icon={<FolderKanban size={23} />} title="Henüz proje eklenmedi" description="İlk projeni ekle ya da JSON dosyalarından toplu içe aktar; başvuru paketlerinde ilgili çalışmaların öne çıksın." action={<div className="page-actions">{importButton}<button className="button primary" onClick={() => setDrawer({ open: true, project: null })}><Plus size={17} /> İlk projeni ekle</button></div>} />}
    {drawer.open && <ProjectDrawer project={drawer.project} onClose={() => setDrawer({ open: false, project: null })} />}
  </>
}
