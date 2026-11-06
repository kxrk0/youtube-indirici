import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ClipboardPaste, Download, FolderOpen, History, Home, Layers, Library, Settings } from 'lucide-react'
import {
  OPTIONS, PAST_QUEUE, QUALITIES, formatBytes, formatDuration, formatSpeed,
  useDownloadSim, useOptions, type QueueItem, type Sample,
} from '../sim'
import { TitleBar } from '../TitleBar'
import './lightbox.css'

/** Şeritteki kare sayısı. Gerçekte yt-dlp storyboard (sb0, 10x10 ızgara) karelerinden eşit aralıkla seçilir. */
const FRAME_COUNT = 5
/** Renkli negatif görünümü: ters çevrilmiş görüntü + turuncu maske (C-41 film tabanı). */
const NEGATIVE = 'invert(1) sepia(1) saturate(2.6) hue-rotate(-22deg) brightness(0.72)'
const POSITIVE = 'invert(0) sepia(0) saturate(1) hue-rotate(0deg) brightness(1)'
const TRIM_MIN_FRACTION = 0.05

function pct(n: number) {
  return `%${Math.floor(n * 100)}`
}

/** Elle çizilmiş, kusurlu elips; gres kalemi işareti. */
function PencilCircle({ w, h }: { w: number; h: number }) {
  const d = `M ${w * 0.1} ${h * 0.35} C ${w * 0.02} ${h * 0.95}, ${w * 0.9} ${h * 1.05}, ${w * 0.97} ${h * 0.5} S ${w * 0.35} ${-h * 0.12}, ${w * 0.06} ${h * 0.42} L ${w * 0.16} ${h * 0.2}`
  return (
    <svg className="lb-pencil-circle" width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      <motion.path d={d} initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.45, ease: [0.4, 0, 0.2, 1] }} />
    </svg>
  )
}

function PencilCheck({ on }: { on: boolean }) {
  return (
    <svg className="lb-check" viewBox="0 0 22 22" aria-hidden="true">
      <rect x="2.5" y="2.5" width="17" height="17" rx="2" className="lb-check-box" />
      <motion.path d="M5 11.5 L9.5 16 L19 3.5" initial={false} animate={{ pathLength: on ? 1 : 0, opacity: on ? 1 : 0 }} transition={{ duration: 0.22, ease: 'easeOut' }} />
    </svg>
  )
}

function Frame({ sample, index, developed, inTrim, visible }: { sample: Sample; index: number; developed: boolean; inTrim: boolean; visible: boolean }) {
  const t = (sample.durationSec * (index + 0.5)) / FRAME_COUNT
  // Kapak karesinden farklı kırpımlar: storyboard karesi taklidi.
  const posX = (index * 37 + 12) % 100
  const posY = (index * 53 + 20) % 100
  return (
    <div className="lb-frame" data-dim={!inTrim}>
      <motion.img
        src={sample.thumb}
        alt=""
        style={{ objectPosition: `${posX}% ${posY}%`, scale: 1.25 + (index % 3) * 0.2 }}
        initial={{ opacity: 0, filter: NEGATIVE }}
        animate={{ opacity: visible ? 1 : 0, filter: developed ? POSITIVE : NEGATIVE }}
        transition={{ opacity: { delay: visible ? index * 0.07 : 0, duration: 0.3 }, filter: { duration: 0.9, ease: 'easeOut' } }}
      />
      <span className="lb-frame-tc">{formatDuration(t)}</span>
    </div>
  )
}

function Filmstrip({ sample, visible, developedUpTo, trim, setTrim, locked, flash }: {
  sample: Sample; visible: boolean; developedUpTo: number; trim: [number, number]; setTrim: (t: [number, number]) => void; locked: boolean; flash: boolean
}) {
  const ref = useRef<HTMLDivElement>(null)
  const drag = useRef<0 | 1 | null>(null)

  const onDown = (which: 0 | 1) => (e: ReactPointerEvent) => {
    if (locked) return
    drag.current = which
    ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
  }
  const onMove = (e: ReactPointerEvent) => {
    if (drag.current === null || !ref.current) return
    const r = ref.current.getBoundingClientRect()
    const x = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width))
    const next: [number, number] = [...trim]
    if (drag.current === 0) next[0] = Math.min(x, trim[1] - TRIM_MIN_FRACTION)
    else next[1] = Math.max(x, trim[0] + TRIM_MIN_FRACTION)
    setTrim(next)
  }
  const onUp = () => {
    drag.current = null
  }
  const nudge = (which: 0 | 1) => (e: React.KeyboardEvent) => {
    const step = e.shiftKey ? 0.05 : 0.01
    const dir = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!dir || locked) return
    e.preventDefault()
    const next: [number, number] = [...trim]
    if (which === 0) next[0] = Math.min(Math.max(0, trim[0] + dir * step), trim[1] - TRIM_MIN_FRACTION)
    else next[1] = Math.max(Math.min(1, trim[1] + dir * step), trim[0] + TRIM_MIN_FRACTION)
    setTrim(next)
  }

  const trimmed = trim[0] > 0 || trim[1] < 1

  return (
    <div className="lb-strip-wrap">
      <div className="lb-strip">
        <div className="lb-sprockets" />
        <div className="lb-frames" ref={ref} onPointerMove={onMove} onPointerUp={onUp}>
          {Array.from({ length: FRAME_COUNT }, (_, i) => {
            const mid = (i + 0.5) / FRAME_COUNT
            const inTrim = mid >= trim[0] && mid <= trim[1]
            return <Frame key={i} sample={sample} index={i} visible={visible} inTrim={inTrim} developed={inTrim && mid <= developedUpTo} />
          })}
          <AnimatePresence>
            {flash && <motion.div className="lb-fix-flash" initial={{ opacity: 0 }} animate={{ opacity: [0, 0.85, 0] }} exit={{ opacity: 0 }} transition={{ duration: 0.9 }} />}
          </AnimatePresence>
          {visible && (
            <>
              <div className="lb-trim-shade" style={{ left: 0, width: `${trim[0] * 100}%` }} />
              <div className="lb-trim-shade" style={{ left: `${trim[1] * 100}%`, right: 0 }} />
              {([0, 1] as const).map((w) => (
                <div
                  key={w}
                  className={`lb-handle lb-handle-${w ? 'end' : 'start'}`}
                  style={{ left: `${trim[w] * 100}%` }}
                  onPointerDown={onDown(w)}
                  onKeyDown={nudge(w)}
                  role="slider"
                  tabIndex={locked ? -1 : 0}
                  aria-label={w ? 'Bitiş' : 'Başlangıç'}
                  aria-valuemin={0}
                  aria-valuemax={sample.durationSec}
                  aria-valuenow={Math.round(trim[w] * sample.durationSec)}
                  aria-valuetext={formatDuration(trim[w] * sample.durationSec)}
                >
                  <span className="lb-handle-mark">{formatDuration(trim[w] * sample.durationSec)}</span>
                </div>
              ))}
            </>
          )}
        </div>
        <div className="lb-sprockets" />
      </div>
      <p className="lb-strip-note">
        {!visible
          ? 'Kareler bağlantıyı yapıştırınca görünür.'
          : trimmed
            ? `Yalnız işaretli bölüm indirilecek: ${formatDuration((trim[1] - trim[0]) * sample.durationSec)}.`
            : 'Kırmızı tutamaçları sürükleyerek videonun bir bölümünü seçebilirsin.'}
      </p>
    </div>
  )
}

export function Lightbox({ sample }: { sample: Sample }) {
  const [qualityId, setQualityId] = useState('1080')
  const quality = QUALITIES.find((q) => q.id === qualityId) ?? QUALITIES[1]
  const [trim, setTrim] = useState<[number, number]>([0, 1])
  const trimFraction = trim[1] - trim[0]
  const scaled = { ...quality, sizeRatio: quality.sizeRatio * trimFraction }
  const { state, paste, start, cancel, reset } = useDownloadSim(sample, scaled)
  const { on, toggle } = useOptions()
  const [prints, setPrints] = useState<QueueItem[]>(PAST_QUEUE)
  const [runId, setRunId] = useState(0)
  const [navHover, setNavHover] = useState('Ana sayfa')

  const { phase } = state
  const visible = phase !== 'empty'
  const busy = phase === 'downloading' || phase === 'merging'
  const developedUpTo = phase === 'done' || phase === 'merging' ? 1 : phase === 'downloading' ? trim[0] + state.progress * trimFraction : -1

  useEffect(() => {
    if (phase !== 'done') return
    const id = window.setTimeout(() => {
      setPrints((p) => [{ id: `run-${runId}`, title: sample.title, channel: sample.channel, thumb: sample.thumb, sizeBytes: state.totalBytes, state: 'done' as const, note: 'az önce' }, ...p].slice(0, 5))
    }, 700)
    return () => clearTimeout(id)
  }, [phase, runId, sample, state.totalBytes])

  const navItems = [
    { Icon: Home, label: 'Ana sayfa' },
    { Icon: Download, label: 'İndirilenler' },
    { Icon: Library, label: 'Kütüphane' },
    { Icon: History, label: 'Geçmiş' },
  ]

  return (
    <div className="lb">
      <TitleBar className="lb-titlebar" />
      <div className="lb-body">
        <nav className="lb-nav" aria-label="Bölümler">
          <p className="lb-app">Studio Downloader</p>
          {navItems.map(({ Icon, label }) => (
            <button key={label} className="lb-nav-btn" aria-current={label === 'Ana sayfa' ? 'page' : undefined} onMouseEnter={() => setNavHover(label)} onMouseLeave={() => setNavHover('Ana sayfa')}>
              <Icon size={17} strokeWidth={1.7} />
              <span>{label}</span>
              {navHover === label && <PencilCircle key={label} w={150} h={40} />}
              {label === 'İndirilenler' && busy && <span className="lb-nav-count">1</span>}
            </button>
          ))}
          <button className="lb-nav-btn lb-nav-bottom">
            <Settings size={17} strokeWidth={1.7} />
            <span>Ayarlar</span>
          </button>
        </nav>

        <main className="lb-main">
          <div className="lb-url">
            <input readOnly value={state.url} placeholder="YouTube, Spotify, SoundCloud, TikTok ya da başka bir bağlantı" aria-label="Bağlantı" />
            <button className="lb-btn" onClick={() => { setRunId((r) => r + 1); setTrim([0, 1]); paste() }} disabled={busy}>
              <ClipboardPaste size={16} strokeWidth={1.8} /> Yapıştır
            </button>
            <button className="lb-btn" disabled={busy}>
              <Layers size={16} strokeWidth={1.8} /> Toplu
            </button>
          </div>

          <section className="lb-meta" aria-live="polite">
            <AnimatePresence mode="wait">
              {phase === 'empty' ? (
                <motion.div key="empty" className="lb-meta-empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <h1>Bir bağlantı yapıştır.</h1>
                  <p>Panoya kopyaladığın bağlantı burada kendiliğinden belirir. Birden fazla bağlantı toplu indirilir.</p>
                </motion.div>
              ) : phase === 'fetching' ? (
                <motion.div key="fetch" className="lb-meta-row" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <div className="lb-cover lb-skel" />
                  <div className="lb-meta-text">
                    <div className="lb-skel" style={{ width: '70%', height: 26 }} />
                    <div className="lb-skel" style={{ width: '30%', height: 14, marginTop: 12 }} />
                  </div>
                </motion.div>
              ) : (
                <motion.div key="info" className="lb-meta-row" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ type: 'spring', stiffness: 300, damping: 30 }}>
                  <img className="lb-cover" src={sample.thumb} alt="" />
                  <div className="lb-meta-text">
                    <h1>{sample.title}</h1>
                    <p>
                      {sample.channel}, {formatDuration(sample.durationSec)}
                    </p>
                  </div>
                  <div className="lb-status">
                    {phase === 'ready' && (
                      <>
                        <strong>{formatBytes(state.totalBytes)}</strong>
                        <span>tahmini boyut</span>
                      </>
                    )}
                    {phase === 'downloading' && (
                      <>
                        <strong>{pct(state.progress)}</strong>
                        <span>{formatSpeed(state.speedBps)}, {formatDuration(state.etaSec)} kaldı</span>
                      </>
                    )}
                    {phase === 'merging' && (
                      <>
                        <strong>Birleştiriliyor</strong>
                        <span>görüntü ve ses tek dosyada</span>
                      </>
                    )}
                    {phase === 'done' && (
                      <>
                        <strong>İndirildi</strong>
                        <button className="lb-link"><FolderOpen size={14} strokeWidth={1.8} /> Klasörde göster</button>
                      </>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </section>

          <Filmstrip sample={sample} visible={visible} developedUpTo={developedUpTo} trim={trim} setTrim={setTrim} locked={busy || phase === 'done'} flash={phase === 'merging'} />

          <div className="lb-controls">
            <fieldset className="lb-quality">
              <legend>Kalite</legend>
              {QUALITIES.map((q) => (
                <label key={q.id} className="lb-chip" data-kind={q.kind}>
                  <input type="radio" name="lb-q" checked={q.id === qualityId} onChange={() => setQualityId(q.id)} disabled={busy} />
                  <span>{q.label}</span>
                  {q.id === qualityId && <motion.span layoutId="lb-q-mark" className="lb-chip-mark" transition={{ type: 'spring', stiffness: 500, damping: 34 }} />}
                </label>
              ))}
            </fieldset>
            <fieldset className="lb-opts">
              <legend>İşlem</legend>
              {OPTIONS.map((o) => (
                <button key={o.id} role="checkbox" aria-checked={on[o.id]} className="lb-opt" onClick={() => toggle(o.id)} title={o.hint}>
                  <PencilCheck on={on[o.id]} />
                  {o.label}
                </button>
              ))}
            </fieldset>
            <div className="lb-go">
              {phase === 'downloading' ? (
                <button className="lb-primary lb-primary-ghost" onClick={cancel}>İptal et</button>
              ) : phase === 'done' ? (
                <button className="lb-primary lb-primary-ghost" onClick={reset}>Yeni bağlantı</button>
              ) : (
                <button className="lb-primary" onClick={start} disabled={phase !== 'ready'}>
                  <Download size={17} strokeWidth={2} /> İndir
                </button>
              )}
            </div>
          </div>

          <section className="lb-sheet" aria-label="Son indirilenler">
            <h2>Son indirilenler</h2>
            <ul>
              <AnimatePresence initial={false}>
                {prints.map((p) => (
                  <motion.li
                    key={p.id}
                    layout
                    initial={{ opacity: 0, y: -60, rotate: -6, scale: 1.3 }}
                    animate={{ opacity: 1, y: 0, rotate: p.id.startsWith('run') ? -1.5 : 0, scale: 1 }}
                    transition={{ type: 'spring', stiffness: 240, damping: 22 }}
                    className="lb-print"
                    data-state={p.state}
                  >
                    <img src={p.thumb} alt="" />
                    <div>
                      <strong>{p.title}</strong>
                      <span>{p.state === 'error' ? p.note : `${formatBytes(p.sizeBytes)}, ${p.note}`}</span>
                    </div>
                  </motion.li>
                ))}
              </AnimatePresence>
            </ul>
          </section>
        </main>
      </div>
    </div>
  )
}
