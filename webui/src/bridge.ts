/**
 * Python köprüsü (src/web/api.py). pywebview yöntemleri window.pywebview.api altında açar;
 * Python'dan gelen olaylar window.__ortamEvent ile düşer.
 */

export type QualityOption = {
  label: string
  data: string
  short: string
  size: number | null
  preset: boolean
}

export type HeatSegment = { start: number; end: number; value: number }

export type VideoInfo = {
  kind: 'video'
  url: string
  spotify: boolean
  title: string
  channel: string
  duration: number
  thumbnail: string
  isLive: boolean
  heatmap: HeatSegment[] | null
  options: QualityOption[]
  autoFamily: string
}

export type ListInfo = { kind: 'list'; title: string; entries: { title: string; url: string }[] }

export type InfoResult =
  | VideoInfo
  | ListInfo
  | { kind: 'drm' }
  | { kind: 'error'; message: string }

export type RecentItem = {
  key: string
  url: string
  title: string
  note: string
  failed: boolean
  file: string | null
  thumbnail: string | null
  /** Oturumda eklenen kayıtlarda hazır kapak (data URL). */
  image?: string
}

export type DownloadRequest = {
  url: string
  outputDir: string
  type: 'video' | 'audio'
  format: string
  subs: boolean
  sponsorblock: boolean
  normalize: boolean
  saveMeta: boolean
  trim: [number, number] | null
  isLive: boolean
  title: string
  channel: string
  thumbnail: string
  duration: number
}

export type ProgressEvent = {
  type: 'progress'
  job: number
  status: 'downloading' | 'processing' | 'converting' | 'recording' | string
  downloaded_bytes: number | null
  total_bytes: number | null
  speed: number | null
  eta: number | null
  progress: number | null
}

export type DoneEvent =
  | { type: 'done'; job: number; ok: true; file: string; size: number | null; note: string }
  | { type: 'done'; job: number; ok: false; cancelled: boolean; error: string }

export type TranscribeEvent = { type: 'transcribe'; path: string; line: string }
export type AddedEvent = { type: 'added'; job: number; origin: 'ui' | 'schedule' | 'subscription' | 'restore'; url: string; title: string; thumbnail: string }
export type NoticeEvent = { type: 'notice'; tone: 'info' | 'error'; text: string }

/** Tepsi menüsü ana pencereyi belirli bir sayfada açtırır. */
export type NavigateEvent = { type: 'navigate'; page: string }
export type UpdateEvent = { type: 'update'; percent: number }

export type BridgeEvent = ProgressEvent | DoneEvent | TranscribeEvent | AddedEvent | NoticeEvent | NavigateEvent | UpdateEvent
  | { type: 'subscriptions-changed' }

/** Süren iş: eklendiği andaki bilgi ve son ilerleme olayı (mini pencere açılışta buradan başlar). */
export type ActiveJob = { added: AddedEvent; last: ProgressEvent | null }
export type UpdateOffer = { current: string; version: string; notes: string }

export type HistoryRow = {
  id: number
  url: string
  title: string
  channel: string
  date: string
  size: number | null
  duration: number | null
  type: string
  status: 'completed' | 'error' | string
  error: string
  file: string
  exists: boolean
  thumbnail: string
}

export type HistoryData = {
  rows: HistoryRow[]
  stats: { total_downloads: number; today: number; this_month: number; total_size_bytes: number; failed: number }
  platforms: { platform: string; count: number }[]
}

export type RetryRequest =
  | { mode: 'home'; url: string }
  | { mode: 'direct'; url: string; type: 'video' | 'audio'; format: string; outputDir: string; title: string; channel: string; thumbnail: string; duration: number }

export type LibraryFile = { path: string; name: string; ext: string; kind: 'video' | 'audio'; size: number; mtime: number }
export type Tags = { title: string; artist: string; album: string; year: string; comment: string }

export type Settings = {
  download_dir: string
  speed_limit: number
  max_concurrent: number
  fragment_downloads: number
  audio_quality: '0' | '320' | '256' | '192' | '128'
  auto_organize: boolean
  auto_shutdown: boolean
  filename_template: string
  proxy: string
  proxy_pool: string
  custom_ffmpeg_args: string
  webhook_url: string
  sub_check_hours: number
  library_folders: string
}
export type Subscription = { id: number; url: string; name: string; type: 'video' | 'audio'; lastChecked: string; active: boolean }
export type Schedule = { id: number; name: string; url: string; when: string; daily: boolean; type: 'video' | 'audio'; lastRun: string }
export type Rule = { name: string; match_field: 'title' | 'url' | 'channel'; pattern: string; output_subdir: string; type_override: '' | 'audio' | 'video' }

type Api = {
  bootstrap(): Promise<{ downloadDir: string; recent: RecentItem[] }>
  clipboard(): Promise<string>
  fetch_info(url: string): Promise<InfoResult>
  thumbnail(url: string): Promise<string | null>
  estimate_size(url: string, outputDir: string): Promise<{ size: number | null; free: number | null }>
  was_downloaded(url: string): Promise<boolean>
  start_download(req: DownloadRequest): Promise<number>
  cancel(job: number): Promise<boolean>
  recent(): Promise<RecentItem[]>
  reveal(path: string): Promise<boolean>
  open_file(path: string): Promise<boolean>
  pick_folder(current: string): Promise<string | null>
  set_title_bar(hex: string): Promise<boolean>
  history(): Promise<HistoryData>
  delete_history(id: number): Promise<boolean>
  clear_history(): Promise<boolean>
  missing_files(): Promise<string[]>
  export_history(kind: 'csv' | 'json'): Promise<string | null>
  retry_request(id: number): Promise<RetryRequest>
  library(): Promise<{ files: LibraryFile[]; dirs: string[] }>
  library_thumbnail(path: string): Promise<string | null>
  delete_file(path: string): Promise<boolean>
  read_tags(path: string): Promise<Tags>
  write_tags(path: string, values: Tags): Promise<boolean>
  convert(path: string, fmt: string): Promise<string>
  transcribe(path: string, model: string, language: string | null): Promise<{ text: string; file: string }>
  pick_media_file(): Promise<string | null>
  settings(): Promise<{ values: Settings; appVersion: string; ytdlpVersion: string; frozen: boolean }>
  set_setting<K extends keyof Settings>(key: K, value: Settings[K]): Promise<boolean>
  ytdlp_latest(): Promise<string | null>
  update_ytdlp(): Promise<string>
  test_proxy(proxy: string): Promise<string>
  subscriptions(): Promise<Subscription[]>
  add_subscription(url: string, type: 'video' | 'audio'): Promise<boolean>
  delete_subscription(id: number): Promise<boolean>
  schedules(): Promise<Schedule[]>
  add_schedule(req: { url: string; name: string; when: string; daily: boolean; type: 'video' | 'audio'; format?: string; outputDir?: string }): Promise<boolean>
  delete_schedule(id: number): Promise<boolean>
  rules(): Promise<Rule[]>
  add_rule(rule: Rule): Promise<boolean>
  delete_rule(name: string): Promise<boolean>
  reset_rules(): Promise<boolean>
  open_plugins_folder(): Promise<boolean>
  reload_plugins(): Promise<number>
  open_url(url: string): Promise<boolean>
  cancel_shutdown(): Promise<boolean>
  active_jobs(): Promise<ActiveJob[]>
  show_main(page: string | null): Promise<boolean>
  toggle_mini(): Promise<boolean>
  hide_mini(): Promise<boolean>
  fit_mini(height: number): Promise<boolean>
  quit_app(): Promise<boolean>
  check_update(): Promise<UpdateOffer | null>
  install_update(): Promise<boolean>
}

declare global {
  interface Window {
    pywebview?: { api: Api }
    __ortamEvent?: (e: BridgeEvent) => void
  }
}

const listeners = new Set<(e: BridgeEvent) => void>()
window.__ortamEvent = (e) => listeners.forEach((l) => l(e))

export function onBridgeEvent(listener: (e: BridgeEvent) => void): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** Köprü hazır olunca çözülür. Uygulama dışında (düz tarayıcı) açılırsa hata verir. */
export function waitForBridge(timeoutMs = 8000): Promise<Api> {
  return new Promise((resolve, reject) => {
    // pywebview önce boş `api: {}` kurar, yöntemleri sonra ekler; yalnız varlığına bakmak yetmez.
    if (typeof window.pywebview?.api?.bootstrap === 'function') return resolve(window.pywebview.api)
    const timer = window.setTimeout(
      () => reject(new Error('Python köprüsü bulunamadı. Bu arayüz uygulamanın içinden açılır: python -m src.web.app')),
      timeoutMs,
    )
    window.addEventListener('pywebviewready', () => {
      window.clearTimeout(timer)
      if (window.pywebview?.api) resolve(window.pywebview.api)
      else reject(new Error('pywebview hazır dedi ama api nesnesi yok.'))
    }, { once: true })
  })
}

export function api(): Api {
  const a = window.pywebview?.api
  if (!a) throw new Error('Python köprüsü henüz hazır değil.')
  return a
}
