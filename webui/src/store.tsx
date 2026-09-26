import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState, type ReactNode } from 'react'
import { api, onBridgeEvent, type DoneEvent, type DownloadRequest, type ProgressEvent, type RecentItem } from './bridge'
import { NEUTRAL, type Palette } from './ortam/color'

export type JobPhase = 'queued' | 'downloading' | 'merging' | 'done' | 'error' | 'cancelled'

export type Job = {
  id: number
  url: string
  title: string
  image: string | null
  thumbnail: string
  /** 'home': ana sayfa kendi gösteriyor ve bitince kapağı yığına kendisi uçuruyor. */
  owner: 'home' | 'background'
  phase: JobPhase
  /** 0..1, yalnızca 'downloading' sırasında anlamlı */
  fraction: number
  done: number
  total: number
  speed: number
  eta: number
  statusText: string
  file: string | null
  size: number | null
  error: string | null
}

export function newJob(id: number, url: string, title: string, thumbnail: string, owner: Job['owner']): Job {
  return { id, url, title, image: null, thumbnail, owner, phase: 'queued', fraction: 0, done: 0, total: 0, speed: 0, eta: 0,
    statusText: 'Sırada', file: null, size: null, error: null }
}

export type JobAction =
  | { type: 'add'; job: Job }
  | { type: 'event'; e: ProgressEvent | DoneEvent }
  | { type: 'remove'; id: number }

export function applyEvent(job: Job, e: ProgressEvent | DoneEvent): Job {
  if (e.type === 'done') {
    if (e.ok) return { ...job, phase: 'done', fraction: 1, file: e.file, size: e.size, statusText: '' }
    return { ...job, phase: e.cancelled ? 'cancelled' : 'error', error: e.cancelled ? null : e.error, statusText: '' }
  }
  switch (e.status) {
    case 'downloading': {
      const total = e.total_bytes ?? 0
      const done = e.downloaded_bytes ?? 0
      const fraction = total ? done / total : (e.progress ?? 0) / 100
      return { ...job, phase: 'downloading', done, total: total || job.total, fraction: Math.max(job.fraction, Math.min(1, fraction)),
        speed: e.speed ?? 0, eta: e.eta ?? 0, statusText: '' }
    }
    case 'recording':
      return { ...job, phase: 'merging', done: e.downloaded_bytes ?? job.done, statusText: 'Kaydediliyor' }
    case 'converting':
      return { ...job, phase: 'merging', statusText: `H.264'e dönüştürülüyor, %${Math.round(e.progress ?? 0)}` }
    default:
      return { ...job, phase: 'merging', fraction: 1, statusText: 'Görüntü ve ses birleştiriliyor' }
  }
}

export function jobsReducer(jobs: Job[], a: JobAction): Job[] {
  switch (a.type) {
    case 'add':
      return jobs.some((j) => j.id === a.job.id) ? jobs : [a.job, ...jobs]
    case 'remove':
      return jobs.filter((j) => j.id !== a.id)
    case 'event':
      return jobs.map((j) => (j.id === a.e.job ? applyEvent(j, a.e) : j))
  }
}

type Store = {
  jobs: Job[]
  recent: RecentItem[]
  downloadDir: string
  palette: Palette
  cover: string | null
  setAmbient: (palette: Palette, cover: string | null) => void
  startDownload: (req: DownloadRequest, image: string | null, owner: Job['owner']) => Promise<number>
  cancel: (id: number) => void
  dismiss: (id: number) => void
  pushRecent: (item: RecentItem) => void
  activeCount: number
  toasts: Toast[]
  notify: (text: string, tone?: Toast['tone']) => void
}

export type Toast = { id: number; text: string; tone: 'info' | 'error' }
/** Kısa bildirimin ekranda kalma süresi. */
const TOAST_MS = 4200

const Ctx = createContext<Store | null>(null)

export function StoreProvider({ children, downloadDir, recent: initialRecent }: { children: ReactNode; downloadDir: string; recent: RecentItem[] }) {
  const [jobs, dispatch] = useReducer(jobsReducer, [])
  const [recent, setRecent] = useState<RecentItem[]>(initialRecent)
  const [palette, setPalette] = useState<Palette>(NEUTRAL)
  const [cover, setCover] = useState<string | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const toastId = useRef(0)
  const notify = useCallback((text: string, tone: Toast['tone'] = 'info') => {
    const id = ++toastId.current
    setToasts((t) => [...t, { id, text, tone }])
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), TOAST_MS)
  }, [])
  const jobsRef = useRef(jobs)
  jobsRef.current = jobs

  useEffect(() => onBridgeEvent((e) => {
    if (e.type === 'progress' || e.type === 'done') dispatch({ type: 'event', e })
    // Zamanlayıcı, abonelik ya da yarım kalan kuyruktan Python'un başlattığı işler.
    if (e.type === 'added' && e.origin !== 'ui') {
      dispatch({ type: 'add', job: newJob(e.job, e.url, e.title, e.thumbnail, 'background') })
    }
  }), [])

  // Biten indirme son indirilenler yığınına girer (ana sayfa uçuşu kendi ekler; burada yalnız diğerleri).
  useEffect(() => onBridgeEvent((e) => {
    if (e.type !== 'done' || !e.ok) return
    const job = jobsRef.current.find((j) => j.id === e.job)
    if (!job || job.owner === 'home') return
    setRecent((r) => [{ key: `job-${job.id}`, url: job.url, title: job.title, note: e.note, failed: false, file: e.file,
      thumbnail: job.thumbnail, image: job.image ?? undefined }, ...r.filter((x) => x.url !== job.url)])
  }), [])

  useEffect(() => onBridgeEvent((e) => { if (e.type === 'notice') notify(e.text, e.tone) }), [notify])

  const startDownload = useCallback(async (req: DownloadRequest, image: string | null, owner: Job['owner']) => {
    const id = await api().start_download(req)
    dispatch({ type: 'add', job: { ...newJob(id, req.url, req.title || req.url, req.thumbnail, owner), image } })
    return id
  }, [])

  const cancel = useCallback((id: number) => {
    api().cancel(id).catch((err) => console.error(`İndirme ${id} iptal edilemedi`, err))
  }, [])

  const setAmbient = useCallback((p: Palette, c: string | null) => {
    setPalette(p)
    setCover(c)
    api().set_title_bar(p.deepHex).catch((err) => console.error('Başlık çubuğu boyanamadı', err))
  }, [])

  const value = useMemo<Store>(() => ({
    jobs, recent, downloadDir, palette, cover, setAmbient, startDownload, cancel,
    dismiss: (id) => dispatch({ type: 'remove', id }),
    pushRecent: (item) => setRecent((r) => [item, ...r.filter((x) => x.url !== item.url)]),
    activeCount: jobs.filter((j) => j.phase === 'queued' || j.phase === 'downloading' || j.phase === 'merging').length,
    toasts, notify,
  }), [jobs, recent, downloadDir, palette, cover, setAmbient, startDownload, cancel, toasts, notify])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useStore(): Store {
  const s = useContext(Ctx)
  if (!s) throw new Error('useStore: StoreProvider dışında kullanıldı')
  return s
}
