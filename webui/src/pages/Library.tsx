import { memo, useCallback, useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronDown, Music, MoreHorizontal, RefreshCw, Search, Video } from 'lucide-react'
import { api, onBridgeEvent, type LibraryFile, type Tags } from '../bridge'
import * as fmt from '../ortam/format'
import { useStore } from '../store'
import { Popover, SPRING_SEGMENT } from '../components/Controls'
import { ConfirmSheet, Sheet } from '../components/Sheets'

const CONVERT_FORMATS = ['mp3', 'mp4', 'mkv', 'webm', 'wav', 'aac'] as const
const TAGGABLE = new Set(['mp3', 'mp4', 'm4a'])
const WHISPER_MODELS = ['tiny', 'base', 'small', 'medium', 'large'] as const
const SORTS = [
  { id: 'new', label: 'En yeni' },
  { id: 'old', label: 'En eski' },
  { id: 'az', label: 'Ad (A–Z)' },
  { id: 'za', label: 'Ad (Z–A)' },
  { id: 'big', label: 'En büyük' },
] as const
type SortId = (typeof SORTS)[number]['id']
type Kind = 'all' | 'video' | 'audio'

/** Oturumda sonucu belli olan kapaklar: sayfaya dönünce iskelet yeniden oynamasın. */
const thumbResults = new Map<string, 'ready' | 'none'>()
/** Kütüphane taranırken gösterilen iskelet kart sayısı (tipik pencerede iki sıra). */
const SKELETON_CARDS = 8

/**
 * Kapak <img> ile yerel sunucudan gelir (src/web/thumb_server.py): tarayıcı yüklemeyi ve çözmeyi
 * ana iş parçacığı dışında yapar, görünür olana kadar istemez (loading="lazy").
 * Yüklenene kadar iskelet parıltısı; kapak yoksa (404) tür simgesi.
 */
const Thumb = memo(function Thumb({ src, kind }: { src: string; kind: LibraryFile['kind'] }) {
  const [state, setState] = useState<'loading' | 'ready' | 'none'>(() => thumbResults.get(src) ?? 'loading')
  const settle = (result: 'ready' | 'none') => { thumbResults.set(src, result); setState(result) }
  const Icon = kind === 'audio' ? Music : Video
  return (
    <div className="am-lib-thumb" data-state={state}>
      {state === 'none'
        ? <Icon size={26} strokeWidth={1.4} />
        : <img src={src} alt="" loading="lazy" decoding="async" onLoad={() => settle('ready')} onError={() => settle('none')} />}
    </div>
  )
})

type CardActions = {
  toggleMenu: (path: string) => void
  closeMenu: () => void
  convert: (path: string) => void
  editTags: (path: string) => void
  transcribe: (path: string) => void
  remove: (file: LibraryFile) => void
}

/** Kart yalnız kendi dosyası ya da menü durumu değişince yeniden çizilir (318 kartta arama yazarken fark ediyor). */
const LibraryCard = memo(function LibraryCard({ file, menuOpen, actions }: { file: LibraryFile; menuOpen: boolean; actions: CardActions }) {
  return (
    <li className="am-lib-card">
      <div className="am-lib-cv">
        <button className="am-lib-open" onClick={() => api().open_file(file.path)} title={`${file.name} dosyasını aç`}>
          <Thumb src={file.thumb} kind={file.kind} />
          <strong>{file.name.replace(/\.[^.]+$/, '')}</strong>
          <span>{file.ext.toUpperCase()}, {fmt.size(file.size)}{file.folder && `, ${file.folder.replaceAll('\\', ' / ')}`}</span>
        </button>
      </div>
      <button className="am-icon-btn am-lib-more" aria-label="Eylemler" aria-haspopup="menu" aria-expanded={menuOpen} onClick={() => actions.toggleMenu(file.path)}>
        <MoreHorizontal size={16} strokeWidth={1.8} />
      </button>
      <Popover open={menuOpen} onClose={actions.closeMenu} style={{ right: 6, top: 40 }}>
        <button onClick={() => { api().reveal(file.path); actions.closeMenu() }}>Klasörde göster</button>
        <button onClick={() => { actions.convert(file.path); actions.closeMenu() }}>Dönüştür</button>
        {TAGGABLE.has(file.ext) && <button onClick={() => { actions.editTags(file.path); actions.closeMenu() }}>Etiketleri düzenle</button>}
        <button onClick={() => { actions.transcribe(file.path); actions.closeMenu() }}>Metne çevir (Whisper)</button>
        <button onClick={() => { actions.remove(file); actions.closeMenu() }}>Sil</button>
      </Popover>
    </li>
  )
})

function SkeletonCard() {
  return (
    <li className="am-lib-card" aria-hidden="true">
      <div className="am-lib-cv">
        <div className="am-lib-open am-lib-skeleton">
          <div className="am-lib-thumb" data-state="loading" />
          <i /><i /><i />
        </div>
      </div>
    </li>
  )
}

export function Library() {
  const store = useStore()
  const [files, setFiles] = useState<LibraryFile[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [kind, setKind] = useState<Kind>('all')
  const [sort, setSort] = useState<SortId>('new')
  const [sortOpen, setSortOpen] = useState(false)
  const [menuFor, setMenuFor] = useState<string | null>(null)
  const [convertFor, setConvertFor] = useState<string | null>(null)
  const [tagsFor, setTagsFor] = useState<string | null>(null)
  const [transcribeFor, setTranscribeFor] = useState<string | null>(null)
  const [deleteFor, setDeleteFor] = useState<LibraryFile | null>(null)

  const load = useCallback(() => {
    api().library().then((r) => { setFiles(r.files); setLoadError(null) }).catch((err) => setLoadError(String(err?.message ?? err)))
  }, [])
  useEffect(load, [load])

  const shown = useMemo(() => {
    const q = query.trim().toLocaleLowerCase('tr-TR')
    const list = (files ?? []).filter((f) => (kind === 'all' || f.kind === kind) && (!q || `${f.name} ${f.folder}`.toLocaleLowerCase('tr-TR').includes(q)))
    const by: Record<SortId, (a: LibraryFile, b: LibraryFile) => number> = {
      new: (a, b) => b.mtime - a.mtime,
      old: (a, b) => a.mtime - b.mtime,
      az: (a, b) => a.name.localeCompare(b.name, 'tr'),
      za: (a, b) => b.name.localeCompare(a.name, 'tr'),
      big: (a, b) => b.size - a.size,
    }
    return list.sort(by[sort])
  }, [files, query, kind, sort])

  const actions = useMemo<CardActions>(() => ({
    toggleMenu: (path) => setMenuFor((m) => (m === path ? null : path)),
    closeMenu: () => setMenuFor(null),
    convert: setConvertFor,
    editTags: setTagsFor,
    transcribe: setTranscribeFor,
    remove: setDeleteFor,
  }), [])

  const pickAndConvert = () => api().pick_media_file().then((p) => p && setConvertFor(p))

  return (
    <div className="am-page-pad">
      <div className="am-page-head">
        <h1 className="am-page-title">Kütüphane</h1>
        <div className="am-page-actions">
          <button className="am-text-btn" onClick={pickAndConvert}>Başka bir dosyayı dönüştür</button>
          <button className="am-text-btn" onClick={load}><RefreshCw size={14} strokeWidth={1.8} /> Yenile</button>
        </div>
      </div>

      <div className="am-lib-filters">
        <div className="am-url am-search" style={{ marginBottom: 0 }}>
          <Search size={16} strokeWidth={1.8} style={{ color: 'var(--text-2)', flex: 'none' }} />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Dosya ya da klasör ara" aria-label="Kütüphanede ara" />
        </div>
        <div className="am-seg" role="radiogroup" aria-label="Tür" style={{ marginBottom: 0 }}>
          {(['all', 'video', 'audio'] as const).map((k) => (
            <button key={k} role="radio" aria-checked={kind === k} onClick={() => setKind(k)}>
              {kind === k && <motion.span layoutId="am-lib-kind" className="am-seg-ind" transition={SPRING_SEGMENT} />}
              <span className="am-seg-text">{k === 'all' ? 'Tümü' : k === 'video' ? 'Video' : 'Ses'}</span>
            </button>
          ))}
        </div>
        <div style={{ position: 'relative' }}>
          <button className="am-text-btn" style={{ color: 'var(--text-2)' }} onClick={() => setSortOpen((v) => !v)} aria-haspopup="menu">
            {SORTS.find((s) => s.id === sort)?.label} <ChevronDown size={13} strokeWidth={2.2} />
          </button>
          <Popover open={sortOpen} onClose={() => setSortOpen(false)} style={{ right: 0, top: 30 }}>
            {SORTS.map((s) => (
              <button key={s.id} role="menuitemradio" aria-checked={sort === s.id} onClick={() => { setSort(s.id); setSortOpen(false) }}>{s.label}</button>
            ))}
          </Popover>
        </div>
      </div>

      {loadError && <p className="am-error-text">Kütüphane okunamadı: {loadError}</p>}
      {files && shown.length === 0 && (
        <p className="am-empty-note">{files.length ? 'Bu filtreyle eşleşen dosya yok.' : 'Kütüphane klasörlerinde henüz medya dosyası yok.'}</p>
      )}

      <ul className="am-lib-grid" aria-busy={files === null && !loadError}>
        {files === null && !loadError && Array.from({ length: SKELETON_CARDS }, (_, i) => <SkeletonCard key={i} />)}
        {shown.map((f) => <LibraryCard key={f.path} file={f} menuOpen={menuFor === f.path} actions={actions} />)}
      </ul>

      <AnimatePresence>
        {convertFor && <ConvertSheet path={convertFor} onClose={() => setConvertFor(null)} onDone={(out) => { store.notify(`Dönüştürüldü: ${out}`); load() }} />}
        {tagsFor && <TagsSheet path={tagsFor} onClose={() => setTagsFor(null)} onSaved={() => store.notify('Etiketler kaydedildi.')} />}
        {transcribeFor && <TranscribeSheet path={transcribeFor} onClose={() => setTranscribeFor(null)} />}
        {deleteFor && (
          <ConfirmSheet title="Dosya silinsin mi?" body={`${deleteFor.name} diskten kalıcı olarak silinir. Geri dönüşüm kutusuna gitmez.`}
            confirmLabel="Kalıcı olarak sil" onClose={() => setDeleteFor(null)}
            onConfirm={() => api().delete_file(deleteFor.path).then(() => {
              setFiles((fs) => fs && fs.filter((x) => x.path !== deleteFor.path))
              store.notify(`${deleteFor.name} silindi.`)
              setDeleteFor(null)
            }).catch((err) => store.notify(`Silinemedi: ${err?.message ?? err}`, 'error'))} />
        )}
      </AnimatePresence>
    </div>
  )
}

function baseName(path: string) {
  return path.split(/[\\/]/).pop() ?? path
}

function ConvertSheet({ path, onClose, onDone }: { path: string; onClose: () => void; onDone: (out: string) => void }) {
  const current = path.split('.').pop()?.toLowerCase()
  const [target, setTarget] = useState<string>(CONVERT_FORMATS.find((f) => f !== current) ?? 'mp3')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const run = () => {
    setBusy(true)
    setError(null)
    api().convert(path, target).then((out) => { onDone(out); onClose() })
      .catch((err) => { setError(String(err?.message ?? err)); setBusy(false) })
  }
  return (
    <Sheet onClose={busy ? () => undefined : onClose}>
      <div>
        <h2>Dönüştür</h2>
        <p>{baseName(path)}. Yeni dosya aynı klasöre "_converted" ekiyle yazılır; asıl dosyaya dokunulmaz.</p>
      </div>
      <div>
        <div className="am-seg" role="radiogroup" aria-label="Hedef format">
          {CONVERT_FORMATS.map((f) => (
            <button key={f} role="radio" aria-checked={target === f} disabled={busy || f === current} onClick={() => setTarget(f)}>
              {target === f && <motion.span layoutId="am-convert-ind" className="am-seg-ind" transition={SPRING_SEGMENT} />}
              <span className="am-seg-text">{f.toUpperCase()}</span>
            </button>
          ))}
        </div>
        {error && <p className="am-error-text" style={{ fontSize: 12.5, userSelect: 'text' }}>{error}</p>}
      </div>
      <div className="am-sheet-foot">
        <span className="am-grow">{busy ? 'Dönüştürülüyor. Büyük dosyalarda birkaç dakika sürebilir.' : ''}</span>
        <button className="am-ghost" onClick={onClose} disabled={busy}>Vazgeç</button>
        <button className="am-primary" onClick={run} disabled={busy}>{busy ? 'Dönüştürülüyor' : `${target.toUpperCase()} yap`}</button>
      </div>
    </Sheet>
  )
}

const TAG_LABELS: [keyof Tags, string][] = [['title', 'Başlık'], ['artist', 'Sanatçı'], ['album', 'Albüm'], ['year', 'Yıl'], ['comment', 'Yorum']]

function TagsSheet({ path, onClose, onSaved }: { path: string; onClose: () => void; onSaved: () => void }) {
  const [tags, setTags] = useState<Tags | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { api().read_tags(path).then(setTags).catch((err) => setError(String(err?.message ?? err))) }, [path])
  const save = () => tags && api().write_tags(path, tags).then(() => { onSaved(); onClose() }).catch((err) => setError(String(err?.message ?? err)))
  return (
    <Sheet onClose={onClose}>
      <div>
        <h2>Etiketler</h2>
        <p>{baseName(path)}</p>
      </div>
      <div className="am-form">
        {TAG_LABELS.map(([key, label]) => (
          <label key={key}>
            <span>{label}</span>
            <input value={tags?.[key] ?? ''} disabled={!tags} onChange={(e) => setTags((t) => t && { ...t, [key]: e.target.value })} />
          </label>
        ))}
        {error && <p className="am-error-text" style={{ fontSize: 12.5 }}>{error}</p>}
      </div>
      <div className="am-sheet-foot">
        <span className="am-grow" />
        <button className="am-ghost" onClick={onClose}>Vazgeç</button>
        <button className="am-primary" onClick={save} disabled={!tags}>Kaydet</button>
      </div>
    </Sheet>
  )
}

function TranscribeSheet({ path, onClose }: { path: string; onClose: () => void }) {
  const [model, setModel] = useState<(typeof WHISPER_MODELS)[number]>('base')
  const [lang, setLang] = useState<'tr' | 'en' | 'auto'>('tr')
  const [lines, setLines] = useState<string[]>([])
  const [result, setResult] = useState<{ text: string; file: string } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => onBridgeEvent((e) => { if (e.type === 'transcribe' && e.path === path) setLines((l) => [...l, e.line]) }), [path])
  const run = () => {
    setBusy(true)
    setError(null)
    setLines([])
    setResult(null)
    api().transcribe(path, model, lang === 'auto' ? null : lang).then(setResult)
      .catch((err) => setError(String(err?.message ?? err))).finally(() => setBusy(false))
  }
  return (
    <Sheet onClose={busy ? () => undefined : onClose}>
      <div>
        <h2>Metne çevir</h2>
        <p>{baseName(path)}. Metin dosyanın yanına .txt olarak kaydedilir. Büyük modeller daha doğru ama daha yavaş.</p>
      </div>
      <div style={{ display: 'grid', gap: 12, minHeight: 0 }}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <div className="am-seg" role="radiogroup" aria-label="Model" style={{ marginBottom: 0 }}>
            {WHISPER_MODELS.map((m) => (
              <button key={m} role="radio" aria-checked={model === m} disabled={busy} onClick={() => setModel(m)}>
                {model === m && <motion.span layoutId="am-whisper-model" className="am-seg-ind" transition={SPRING_SEGMENT} />}
                <span className="am-seg-text">{m}</span>
              </button>
            ))}
          </div>
          <div className="am-seg" role="radiogroup" aria-label="Dil" style={{ marginBottom: 0 }}>
            {(['tr', 'en', 'auto'] as const).map((l) => (
              <button key={l} role="radio" aria-checked={lang === l} disabled={busy} onClick={() => setLang(l)}>
                {lang === l && <motion.span layoutId="am-whisper-lang" className="am-seg-ind" transition={SPRING_SEGMENT} />}
                <span className="am-seg-text">{l === 'tr' ? 'Türkçe' : l === 'en' ? 'İngilizce' : 'Otomatik'}</span>
              </button>
            ))}
          </div>
        </div>
        {(lines.length > 0 || error) && (
          <div className="am-log" aria-live="polite">
            {lines.map((l, i) => <div key={i}>{l}</div>)}
            {error && <div className="am-error-text">{error}</div>}
          </div>
        )}
        {result && <textarea readOnly value={result.text} style={{ minHeight: 140 }} />}
      </div>
      <div className="am-sheet-foot">
        {result && <button className="am-text-btn" onClick={() => api().open_file(result.file)}>Metin dosyasını aç</button>}
        <span className="am-grow" />
        <button className="am-ghost" onClick={onClose} disabled={busy}>Kapat</button>
        <button className="am-primary" onClick={run} disabled={busy}>{busy ? 'Çevriliyor' : result ? 'Yeniden çevir' : 'Başlat'}</button>
      </div>
    </Sheet>
  )
}
