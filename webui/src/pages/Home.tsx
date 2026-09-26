import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion, useMotionValue, useSpring, useTransform } from 'motion/react'
import { CalendarClock, ClipboardPaste, Folder, Layers, MoreHorizontal } from 'lucide-react'
import { api, type InfoResult, type ListInfo, type VideoInfo } from '../bridge'
import { NEUTRAL, prepareCover, type PreparedCover } from '../ortam/color'
import * as fmt from '../ortam/format'
import { useStore } from '../store'
import { MorphButton, type MorphMode } from '../components/MorphButton'
import { Timeline } from '../components/Timeline'
import { Popover, QualityBar, Switch } from '../components/Controls'
import { RecentStack } from '../components/Shell'
import { BatchSheet, ListSheet, ScheduleSheet } from '../components/Sheets'

const FETCH_DEBOUNCE_MS = 600
const DONE_HOLD_MS = 1600
const TILT_DEG = 7
const COVER_SQUARE = 300
const COVER_WIDE_W = 380
/** Bu en-boy oranının üstündeki kapaklar kare yerine geniş (16:9) çizilir. */
const WIDE_ASPECT = 1.2
/** Boş alan uyarısı: tahmini boyutun bu katından az yer varsa. */
const DISK_MARGIN = 1.2
const URL_RE = /^https?:\/\/\S+$/i
const EMPTY_BODY = 'Bir bağlantı kopyala, gerisini uygulama halleder. YouTube, Spotify, SoundCloud, TikTok ve 1000’den fazla site.'

const rise = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { type: 'spring' as const, stiffness: 260, damping: 26 } },
}

type Stage =
  | { kind: 'empty'; title: string; body: string; button: boolean }
  | { kind: 'fetching' }
  | { kind: 'content'; info: VideoInfo }

const EMPTY: Stage = { kind: 'empty', title: 'Ne indirmek istersin?', body: EMPTY_BODY, button: true }

function Tilt({ children, active }: { children: React.ReactNode; active: boolean }) {
  const mx = useMotionValue(0)
  const my = useMotionValue(0)
  const rx = useSpring(useTransform(my, [-0.5, 0.5], [TILT_DEG, -TILT_DEG]), { stiffness: 150, damping: 15 })
  const ry = useSpring(useTransform(mx, [-0.5, 0.5], [-TILT_DEG, TILT_DEG]), { stiffness: 150, damping: 15 })
  return (
    <motion.div className="am-tilt" style={{ rotateX: active ? rx : 0, rotateY: active ? ry : 0 }}
      onPointerMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect()
        mx.set((e.clientX - r.left) / r.width - 0.5)
        my.set((e.clientY - r.top) / r.height - 0.5)
      }}
      onPointerLeave={() => { mx.set(0); my.set(0) }}>
      {children}
    </motion.div>
  )
}

export function Home({ incoming, onShowQueue }: { incoming: { text: string; nonce: number } | null; onShowQueue: () => void }) {
  const store = useStore()
  const [url, setUrl] = useState('')
  const [stage, setStage] = useState<Stage>(EMPTY)
  const [cover, setCover] = useState<PreparedCover | null>(null)
  const [optionIndex, setOptionIndex] = useState(0)
  const [audio, setAudio] = useState(false)
  const [subs, setSubs] = useState(false)
  const [sponsorblock, setSponsorblock] = useState(false)
  const [normalize, setNormalize] = useState(false)
  const [saveMeta, setSaveMeta] = useState(false)
  const [deltaSync, setDeltaSync] = useState(false)
  const [moreOpen, setMoreOpen] = useState(false)
  const [outputDir, setOutputDir] = useState(store.downloadDir)
  const [trim, setTrim] = useState<[number, number]>([0, 1])
  const [estimate, setEstimate] = useState<{ size: number | null; free: number | null } | null>(null)
  const [jobId, setJobId] = useState<number | null>(null)
  const [note, setNote] = useState<{ text: string; error?: boolean } | null>(null)
  const [list, setList] = useState<ListInfo | null>(null)
  const [batch, setBatch] = useState<string | null>(null)
  const [scheduling, setScheduling] = useState(false)
  const serial = useRef(0)
  const lastClipboard = useRef('')

  const job = store.jobs.find((j) => j.id === jobId) ?? null
  const info = stage.kind === 'content' ? stage.info : null

  // ── bağlantı → bilgi ──
  const resetContent = useCallback(() => {
    setCover(null)
    setEstimate(null)
    setTrim([0, 1])
    setNote(null)
  }, [])

  const handleInfo = useCallback((res: InfoResult, s: number) => {
    if (s !== serial.current) return
    if (res.kind === 'drm') {
      setStage({ kind: 'empty', title: 'Bu platform şifreli.', body: 'Apple Music, Tidal ve Deezer DRM kullanıyor; bu içerikler indirilemez.', button: false })
      store.setAmbient(NEUTRAL, null)
      return
    }
    if (res.kind === 'error') {
      setStage({ kind: 'empty', title: 'Bu bağlantı açılamadı.', body: res.message, button: false })
      store.setAmbient(NEUTRAL, null)
      return
    }
    if (res.kind === 'list') {
      setStage(EMPTY)
      setList(res)
      return
    }
    setOptionIndex(0)
    setAudio(res.spotify)
    setStage({ kind: 'content', info: res })
    if (res.thumbnail) {
      api().thumbnail(res.thumbnail)
        .then((data) => (data ? prepareCover(data) : null))
        .then((prepared) => {
          if (s !== serial.current) return
          setCover(prepared)
          store.setAmbient(prepared?.palette ?? NEUTRAL, prepared?.src ?? null)
        })
        .catch((err) => console.error('Kapak hazırlanamadı', err))
    }
    if (!res.spotify && !res.isLive) {
      api().estimate_size(res.url, outputDir).then((e) => { if (s === serial.current) setEstimate(e) })
        .catch((err) => console.error('Boyut tahmini alınamadı', err))
    }
  }, [outputDir, store])

  useEffect(() => {
    const text = url.trim()
    serial.current += 1
    const s = serial.current
    if (!URL_RE.test(text)) {
      if (!text && jobId === null) {
        setStage((st) => (st.kind === 'empty' ? st : EMPTY))
        resetContent()
      }
      return
    }
    if (job && job.url === text) return
    setJobId(null)
    resetContent()
    setStage({ kind: 'fetching' })
    const t = window.setTimeout(() => {
      api().fetch_info(text).then((res) => handleInfo(res, s)).catch((err) => {
        if (s !== serial.current) return
        setStage({ kind: 'empty', title: 'Bilgi alınamadı.', body: String(err?.message ?? err), button: false })
      })
    }, FETCH_DEBOUNCE_MS)
    return () => window.clearTimeout(t)
    // job kasıtlı dışarıda: yalnızca bağlantı değişince yeniden sorgula.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url])

  // Başka yerden (sürükle-bırak, Ctrl+V, geçmişten tekrar) gelen bağlantı; birden çoksa toplu indirme.
  useEffect(() => {
    if (!incoming) return
    const lines = incoming.text.split('\n').map((l) => l.trim()).filter((l) => URL_RE.test(l))
    if (lines.length > 1) setBatch(lines.join('\n'))
    else if (lines.length === 1) { lastClipboard.current = lines[0]; setUrl(lines[0]) }
  }, [incoming])

  // Pano: pencere odaklanınca yeni bir bağlantı varsa ve boştaysak kendiliğinden gelir.
  useEffect(() => {
    const check = () => api().clipboard().then((text) => {
      const t = text.trim()
      if (!URL_RE.test(t) || t === lastClipboard.current) return
      lastClipboard.current = t
      setUrl((cur) => (cur.trim() ? cur : t))
    }).catch((err) => console.error('Pano okunamadı', err))
    check()
    window.addEventListener('focus', check)
    return () => window.removeEventListener('focus', check)
  }, [])

  const paste = () => api().clipboard().then((t) => {
    const lines = t.split('\n').map((l) => l.trim()).filter((l) => URL_RE.test(l))
    if (lines.length > 1) setBatch(lines.join('\n'))
    else if (lines.length === 1) { lastClipboard.current = lines[0]; setUrl(lines[0]) }
  })

  // ── seçimler ──
  const options = useMemo(() => {
    if (!info) return []
    if (info.spotify) return [{ label: 'MP3 (en iyi kalite)', data: 'spotify_audio', short: 'MP3', size: null, preset: true }]
    return info.options
  }, [info])
  const selected = options[optionIndex]
  const hasTimeline = Boolean(info && info.duration && !info.isLive && !info.spotify)
  const trimmed = trim[0] > 0 || trim[1] < 1
  const selectedSize = useMemo(() => {
    if (audio || !selected) return null
    const size = selected.data === 'best' ? estimate?.size ?? null : selected.size
    return size ? size * (hasTimeline ? trim[1] - trim[0] : 1) : null
  }, [audio, selected, estimate, hasTimeline, trim])

  // ── indirme ──
  const busy = job !== null && (job.phase === 'queued' || job.phase === 'downloading' || job.phase === 'merging')
  const mode: MorphMode = !info ? 'disabled'
    : job?.phase === 'done' ? 'done'
    : job?.phase === 'error' ? 'error'
    : job && (job.phase === 'merging' || (info.isLive && busy)) ? 'merging'
    : busy ? 'progress'
    : 'idle'

  const start = async () => {
    if (!info) return
    if (deltaSync && await api().was_downloaded(info.url)) {
      setNote({ text: 'Delta Sync: bu bağlantı daha önce indirilmiş, atlandı.' })
      return
    }
    const before = await api().was_downloaded(info.url)
    const kind = audio || info.spotify ? 'audio' : 'video'
    const id = await store.startDownload({
      url: info.url, outputDir, type: kind, format: selected?.data ?? 'best',
      subs, sponsorblock, normalize, saveMeta,
      trim: hasTimeline && kind === 'video' && trimmed ? [trim[0] * info.duration, trim[1] * info.duration] : null,
      isLive: info.isLive, title: info.title, channel: info.channel, thumbnail: info.thumbnail, duration: info.duration,
    }, cover?.src ?? null, 'home')
    setJobId(id)
    setNote(before ? { text: 'Daha önce indirilmişti; yeniden iniyor.' } : null)
  }

  const onMorph = () => {
    if (mode === 'idle' || mode === 'error') start().catch((err) => setNote({ text: `İndirme başlatılamadı: ${err?.message ?? err}`, error: true }))
    else if (mode === 'progress' && job) store.cancel(job.id)
    else if (mode === 'done' && job?.file) api().reveal(job.file)
  }

  // Bitince: kısa bekleme, kapak yığına uçar, sahne "İndirildi. Sıradaki?" olur.
  useEffect(() => {
    if (job?.phase !== 'done' || !info) return
    const t = window.setTimeout(() => {
      store.pushRecent({ key: `job-${job.id}`, url: info.url, title: info.title, note: `${fmt.size(job.size)}, az önce`,
        failed: false, file: job.file, thumbnail: info.thumbnail, image: cover?.src })
      serial.current += 1
      setJobId(null)
      setUrl('')
      resetContent()
      setStage({ kind: 'empty', title: 'İndirildi. Sıradaki?', body: EMPTY_BODY, button: true })
    }, DONE_HOLD_MS)
    return () => window.clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job?.phase])

  useEffect(() => {
    if (job?.phase === 'cancelled') {
      setJobId(null)
      setNote({ text: 'İptal edildi.' })
    }
  }, [job?.phase])

  // Ctrl+Enter / Ctrl+D: hazırsa indir
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey && (e.key === 'Enter' || e.key.toLowerCase() === 'd')) && (mode === 'idle' || mode === 'error')) {
        e.preventDefault()
        onMorph()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  // ── metinler ──
  const statusText = (() => {
    if (job) {
      if (job.phase === 'queued') return 'Sırada'
      if (job.phase === 'downloading') {
        const parts = [job.total ? `${fmt.size(job.done)} / ${fmt.size(job.total)}` : fmt.size(job.done), fmt.speed(job.speed)]
        if (job.eta) parts.push(`${fmt.duration(job.eta)} kaldı`)
        return parts.join(', ')
      }
      if (job.phase === 'merging') return job.statusText
      if (job.phase === 'done') return `${fmt.size(job.size)} ${fmt.folderName(job.file ?? outputDir)} klasörüne kaydedildi`
      if (job.phase === 'error') return job.error ?? 'İndirme başarısız oldu.'
    }
    if (note) return note.text
    if (estimate?.free != null && estimate.size && estimate.free < estimate.size * DISK_MARGIN) return `Diskte yer az: ${fmt.size(estimate.free)} boş`
    if (hasTimeline && trimmed && !audio && info) return `Yalnız ${fmt.duration((trim[1] - trim[0]) * info.duration)} indirilecek`
    return ''
  })()
  const statusIsError = job?.phase === 'error' || note?.error || Boolean(estimate?.free != null && estimate.size && estimate.free < estimate.size * DISK_MARGIN)
  const hint = info?.isLive ? 'Canlı yayın: bitene ya da sen durdurana kadar kaydedilir.'
    : !audio && selected?.data === 'best' && (info?.autoFamily === 'av01' || info?.autoFamily === 'vp9')
      ? `En iyi kalite ${info.autoFamily === 'av01' ? 'AV1' : 'VP9'} olarak geliyor; After Effects ve Premiere açamaz.` : ''

  const progressFraction = job?.phase === 'downloading' ? job.fraction : job && (job.phase === 'merging' || job.phase === 'done') ? 1 : 0
  const head = trim[0] + progressFraction * (trim[1] - trim[0])
  const wide = cover ? cover.width / cover.height >= WIDE_ASPECT : false
  const coverW = wide ? COVER_WIDE_W : COVER_SQUARE
  const coverH = wide ? Math.round((COVER_WIDE_W * 9) / 16) : COVER_SQUARE

  return (
    <div className="am-main">
      <header className="am-top">
        <div className="am-url">
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="Bağlantıyı yapıştır" aria-label="Bağlantı"
            onPaste={(e) => {
              const text = e.clipboardData.getData('text')
              const lines = text.split('\n').map((l) => l.trim()).filter((l) => URL_RE.test(l))
              if (lines.length > 1) { e.preventDefault(); setBatch(lines.join('\n')) }
            }} />
          <button className="am-ghost" onClick={paste} disabled={busy}><ClipboardPaste size={16} strokeWidth={1.8} /> Yapıştır</button>
          <button className="am-ghost" onClick={() => setBatch('')} disabled={busy}><Layers size={16} strokeWidth={1.8} /> Toplu</button>
        </div>
        <RecentStack items={store.recent} onShowAll={onShowQueue} />
      </header>

      <AnimatePresence mode="wait">
        {stage.kind === 'empty' ? (
          <motion.section key={`empty-${stage.title}`} className="am-empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: { duration: 0.15 } }}>
            <h1>{stage.title}</h1>
            <p>{stage.body}</p>
            {stage.button && (
              <button className="am-ghost am-ghost-lg" onClick={paste}><ClipboardPaste size={17} strokeWidth={1.8} /> Panodan yapıştır</button>
            )}
          </motion.section>
        ) : stage.kind === 'fetching' ? (
          <motion.section key="fetching" className="am-stage" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: { duration: 0.15 } }}>
            <div className="am-cover am-cover-skel" />
            <div className="am-skel-lines"><span /><span /><span /></div>
          </motion.section>
        ) : (
          <motion.section key={`stage-${stage.info.url}`} className="am-stage" style={{ gridTemplateColumns: `${coverW}px minmax(0, 1fr)` }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: { duration: 0.15 } }}>
            <Tilt active={mode === 'idle'}>
              {cover ? (
                <motion.img layoutId={`am-cover-${stage.info.url}`} className="am-cover" src={cover.src} alt="" style={{ width: coverW, height: coverH }}
                  initial={{ opacity: 0, filter: 'blur(18px)', scale: 0.96 }} animate={{ opacity: 1, filter: 'blur(0px)', scale: busy ? 0.97 : 1 }}
                  transition={{ type: 'spring', stiffness: 170, damping: 22 }} />
              ) : (
                <div className="am-cover am-cover-skel" style={{ width: coverW, height: coverH }} />
              )}
            </Tilt>
            <div className="am-info">
              <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.06 } } }}>
                <motion.p className="am-channel" variants={rise}>
                  {[stage.info.channel, stage.info.duration ? fmt.duration(stage.info.duration) : '', stage.info.spotify ? 'Spotify' : ''].filter(Boolean).join(', ')}
                </motion.p>
                <motion.h1 className="am-title" variants={rise}>{stage.info.title}</motion.h1>
                <motion.div variants={rise}>
                  <QualityBar options={options} selected={optionIndex} audio={audio && !stage.info.spotify}
                    onSelect={(i) => { setOptionIndex(i); setAudio(false) }} onAudio={() => setAudio(true)}
                    disabled={busy || stage.info.isLive || stage.info.spotify} audioAllowed={!stage.info.spotify} />
                </motion.div>
                {hint && <motion.p className={`am-hint${stage.info.isLive ? ' am-error-text' : ''}`} variants={rise}>{hint}</motion.p>}
                <motion.div className="am-opts" variants={rise} style={{ marginBottom: 14 }}>
                  <Switch on={subs} onToggle={() => setSubs((v) => !v)} label="Altyazı" hint="Türkçe ve İngilizce altyazı, varsa" disabled={busy} />
                  <Switch on={sponsorblock} onToggle={() => setSponsorblock((v) => !v)} label="SponsorBlock" hint="Sponsor, giriş ve tanıtım bölümlerini keser (yalnız YouTube)" disabled={busy} />
                  <Switch on={normalize} onToggle={() => setNormalize((v) => !v)} label="Ses eşitle" hint="Ses seviyesini −16 LUFS'a getirir" disabled={busy} />
                </motion.div>
                <motion.div className="am-opts" variants={rise} style={{ marginBottom: 22, position: 'relative' }}>
                  <button className="am-text-btn" style={{ color: 'var(--text-2)' }} title={outputDir} disabled={busy}
                    onClick={() => api().pick_folder(outputDir).then((d) => d && setOutputDir(d))}>
                    <Folder size={14} strokeWidth={1.8} /> {fmt.folderName(outputDir)}
                  </button>
                  {!stage.info.isLive && (
                    <button className="am-text-btn" style={{ color: 'var(--text-2)' }} onClick={() => setScheduling(true)} disabled={busy}>
                      <CalendarClock size={14} strokeWidth={1.8} /> Zamanla
                    </button>
                  )}
                  <button className="am-text-btn" style={{ color: 'var(--text-2)' }} onClick={() => setMoreOpen((v) => !v)} aria-haspopup="menu">
                    <MoreHorizontal size={14} strokeWidth={1.8} /> Diğer
                  </button>
                  <Popover open={moreOpen} onClose={() => setMoreOpen(false)} style={{ left: 0, top: 30 }}>
                    <button role="menuitemcheckbox" aria-checked={saveMeta} onClick={() => setSaveMeta((v) => !v)}>Meta verileri kaydet (JSON)</button>
                    <button role="menuitemcheckbox" aria-checked={deltaSync} onClick={() => setDeltaSync((v) => !v)}>Delta Sync: daha önce indirilenleri atla</button>
                  </Popover>
                </motion.div>
                <motion.div className="am-go" variants={rise}>
                  <MorphButton mode={mode} progress={progressFraction} onClick={onMorph}
                    label={mode === 'error' ? 'Tekrar dene' : info?.isLive ? 'Kaydı başlat' : 'İndir'}
                    detail={mode === 'idle' && selectedSize ? fmt.size(selectedSize) : undefined} />
                  <p className={`am-go-status${statusIsError ? ' am-error-text' : ''}`} aria-live="polite">{statusText}</p>
                </motion.div>
              </motion.div>
            </div>
            {hasTimeline && (
              <motion.div className="am-timeline-wrap" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25, type: 'spring', stiffness: 200, damping: 26 }}>
                <Timeline heatmap={stage.info.heatmap} total={stage.info.duration} trim={trim} setTrim={setTrim}
                  head={head} locked={busy || mode === 'done' || audio} showProgress={Boolean(job)} />
              </motion.div>
            )}
          </motion.section>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {list && (
          <ListSheet title={list.title} entries={list.entries} onClose={() => { setList(null); setUrl('') }}
            onConfirm={(urls, asAudio) => {
              urls.forEach((u) => store.startDownload({ url: u, outputDir, type: asAudio ? 'audio' : 'video', format: 'best', subs, sponsorblock,
                normalize, saveMeta, trim: null, isLive: false, title: '', channel: '', thumbnail: '', duration: 0 }, null, 'background'))
              setList(null)
              setUrl('')
              onShowQueue()
            }} />
        )}
        {scheduling && info && (
          <ScheduleSheet title={info.title} onClose={() => setScheduling(false)} onConfirm={async (when, daily) => {
            await api().add_schedule({ url: info.url, name: info.title, when, daily, type: audio && !info.spotify ? 'audio' : 'video',
              format: audio ? 'best' : selected?.data ?? 'best', outputDir })
            setScheduling(false)
            store.notify(daily ? `Her gün ${when} indirilecek.` : `${when} tarihinde indirilecek.`)
          }} />
        )}
        {batch !== null && (
          <BatchSheet initial={batch} onClose={() => setBatch(null)} onConfirm={async (urls) => {
            setBatch(null)
            for (const u of urls) {
              if (deltaSync && await api().was_downloaded(u)) continue
              await store.startDownload({ url: u, outputDir, type: audio ? 'audio' : 'video', format: 'best', subs, sponsorblock, normalize,
                saveMeta, trim: null, isLive: false, title: '', channel: '', thumbnail: '', duration: 0 }, null, 'background')
            }
            onShowQueue()
          }} />
        )}
      </AnimatePresence>
    </div>
  )
}
