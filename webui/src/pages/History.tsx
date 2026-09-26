import { useCallback, useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronDown, FolderOpen, Play, RotateCcw, Search, Trash2 } from 'lucide-react'
import { api, type HistoryData, type HistoryRow } from '../bridge'
import * as fmt from '../ortam/format'
import { useStore } from '../store'
import { Popover } from '../components/Controls'
import { ConfirmSheet } from '../components/Sheets'

const TR_INT = new Intl.NumberFormat('tr-TR')
/** Platform dağılımında gösterilen en fazla satır. */
const PLATFORM_ROWS = 6

function when(date: string): string {
  const d = new Date(date.replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return date
  const today = new Date()
  const time = d.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })
  if (d.toDateString() === today.toDateString()) return `bugün ${time}`
  const yesterday = new Date(today.getTime() - 86_400_000)
  if (d.toDateString() === yesterday.toDateString()) return `dün ${time}`
  return `${d.toLocaleDateString('tr-TR')} ${time}`
}

function meta(r: HistoryRow): string {
  const parts = [r.channel, when(r.date)]
  if (r.size) parts.push(fmt.size(r.size))
  if (r.duration) parts.push(fmt.duration(r.duration))
  return parts.filter(Boolean).join(', ')
}

export function History({ onOpenInHome, onShowQueue }: { onOpenInHome: (url: string) => void; onShowQueue: () => void }) {
  const store = useStore()
  const [data, setData] = useState<HistoryData | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [exportOpen, setExportOpen] = useState(false)
  const [confirmClear, setConfirmClear] = useState(false)

  const load = useCallback(() => {
    api().history().then((d) => { setData(d); setLoadError(null) }).catch((err) => setLoadError(String(err?.message ?? err)))
  }, [])
  useEffect(load, [load])
  // Arka planda biten indirmeler listeye girsin.
  const doneCount = store.jobs.filter((j) => j.phase === 'done' || j.phase === 'error').length
  useEffect(() => { if (doneCount) load() }, [doneCount, load])

  const rows = useMemo(() => {
    if (!data) return []
    const q = query.trim().toLocaleLowerCase('tr-TR')
    if (!q) return data.rows
    return data.rows.filter((r) => [r.title, r.channel, r.url].some((f) => f.toLocaleLowerCase('tr-TR').includes(q)))
  }, [data, query])

  const remove = (r: HistoryRow) => api().delete_history(r.id).then(() => {
    setData((d) => d && { ...d, rows: d.rows.filter((x) => x.id !== r.id) })
    store.notify('Kayıt geçmişten silindi. Dosyaya dokunulmadı.')
  }).catch((err) => store.notify(`Silinemedi: ${err?.message ?? err}`, 'error'))

  const retry = async (r: HistoryRow) => {
    try {
      const req = await api().retry_request(r.id)
      if (req.mode === 'home') {
        onOpenInHome(req.url)
        return
      }
      await store.startDownload({ ...req, subs: false, sponsorblock: false, normalize: false, saveMeta: false, trim: null, isLive: false },
        null, 'background')
      onShowQueue()
    } catch (err) {
      store.notify(`Tekrar indirilemedi: ${(err as Error)?.message ?? err}`, 'error')
    }
  }

  const exportAs = (kind: 'csv' | 'json') => {
    setExportOpen(false)
    api().export_history(kind).then((path) => path && store.notify(`Dışa aktarıldı: ${path}`))
      .catch((err) => store.notify(`Dışa aktarılamadı: ${err?.message ?? err}`, 'error'))
  }

  const checkMissing = () => api().missing_files().then((names) => {
    if (!names.length) store.notify('Tamamlanan tüm dosyalar yerinde.')
    else store.notify(`${names.length} dosya taşınmış ya da silinmiş: ${names.slice(0, 3).join(', ')}${names.length > 3 ? ' …' : ''}`, 'error')
  })

  const maxPlatform = Math.max(1, ...(data?.platforms ?? []).map((p) => p.count))

  return (
    <div className="am-page-pad">
      <div className="am-page-head">
        <h1 className="am-page-title">Geçmiş</h1>
        <div className="am-page-actions">
          <div style={{ position: 'relative' }}>
            <button className="am-text-btn" onClick={() => setExportOpen((v) => !v)} aria-haspopup="menu">Dışa aktar <ChevronDown size={13} strokeWidth={2.2} /></button>
            <Popover open={exportOpen} onClose={() => setExportOpen(false)} style={{ right: 0, top: 30 }}>
              <button onClick={() => exportAs('csv')}>CSV (Excel)</button>
              <button onClick={() => exportAs('json')}>JSON</button>
            </Popover>
          </div>
          <button className="am-text-btn" onClick={checkMissing}>Eksik dosyaları bul</button>
          <button className="am-text-btn" onClick={() => setConfirmClear(true)} disabled={!data?.rows.length}>Geçmişi temizle</button>
        </div>
      </div>

      {loadError && <p className="am-error-text">Geçmiş okunamadı: {loadError}</p>}

      {data && (
        <section className="am-stats" aria-label="İstatistikler">
          <div><strong>{TR_INT.format(data.stats.total_downloads)}</strong><span>indirme</span></div>
          <div><strong>{TR_INT.format(data.stats.today)}</strong><span>bugün</span></div>
          <div><strong>{TR_INT.format(data.stats.this_month)}</strong><span>bu ay</span></div>
          <div><strong>{fmt.size(data.stats.total_size_bytes) || '0 B'}</strong><span>toplam boyut</span></div>
          {data.platforms.length > 0 && (
            <ul className="am-platforms">
              {data.platforms.slice(0, PLATFORM_ROWS).map((p) => (
                <li key={p.platform}>
                  <span>{p.platform}</span>
                  <i><motion.b initial={{ scaleX: 0 }} animate={{ scaleX: p.count / maxPlatform }} transition={{ type: 'spring', stiffness: 260, damping: 26 }} /></i>
                  <em>{TR_INT.format(p.count)}</em>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <div className="am-url am-search">
        <Search size={16} strokeWidth={1.8} style={{ color: 'var(--text-2)', flex: 'none' }} />
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Başlık, kanal ya da bağlantı ara" aria-label="Geçmişte ara" />
      </div>

      {data && rows.length === 0 && (
        <p className="am-empty-note">{data.rows.length ? 'Bu aramayla eşleşen kayıt yok.' : 'Henüz indirme geçmişi yok.'}</p>
      )}

      <ul className="am-jobs">
        {rows.map((r) => (
          <li key={r.id} className="am-job">
            {r.thumbnail ? <img src={r.thumbnail} alt="" loading="lazy" onError={(e) => e.currentTarget.removeAttribute('src')} /> : <div className="am-job-ph" />}
            <div style={{ minWidth: 0 }}>
              <strong title={r.title}>{r.title}</strong>
              <div className="am-job-status">{meta(r)}</div>
              {r.status === 'error' && <div className="am-job-status am-error-text" title={r.error}>{r.error || 'İndirme başarısız oldu.'}</div>}
              {r.status === 'completed' && r.file && !r.exists && <div className="am-job-status">Dosya yerinde değil; taşınmış ya da silinmiş.</div>}
            </div>
            <div style={{ display: 'flex', gap: 2 }}>
              {r.exists && (
                <>
                  <button className="am-icon-btn" aria-label="Aç" title="Aç" onClick={() => api().open_file(r.file)}><Play size={16} strokeWidth={1.8} /></button>
                  <button className="am-icon-btn" aria-label="Klasörde göster" title="Klasörde göster" onClick={() => api().reveal(r.file)}><FolderOpen size={16} strokeWidth={1.8} /></button>
                </>
              )}
              {r.url && <button className="am-icon-btn" aria-label="Tekrar indir" title="Tekrar indir" onClick={() => retry(r)}><RotateCcw size={16} strokeWidth={1.8} /></button>}
              <button className="am-icon-btn" aria-label="Geçmişten sil" title="Geçmişten sil" onClick={() => remove(r)}><Trash2 size={16} strokeWidth={1.8} /></button>
            </div>
          </li>
        ))}
      </ul>

      <AnimatePresence>
        {confirmClear && (
          <ConfirmSheet title="Tüm geçmiş silinsin mi?" body="İndirme kayıtlarının hepsi silinir. İndirilmiş dosyalara dokunulmaz. Bu işlem geri alınamaz."
            confirmLabel="Geçmişi temizle" onClose={() => setConfirmClear(false)}
            onConfirm={() => api().clear_history().then(() => { setConfirmClear(false); load(); store.notify('Geçmiş temizlendi.') })} />
        )}
      </AnimatePresence>
    </div>
  )
}
