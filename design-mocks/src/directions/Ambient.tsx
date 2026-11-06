import { useEffect, useMemo, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react'
import { AnimatePresence, LayoutGroup, motion, useMotionValue, useSpring, useTransform } from 'motion/react'
import { Check, ClipboardPaste, Download, History, Home, Layers, Library, Scissors, Settings, Square } from 'lucide-react'
import {
  OPTIONS, PAST_QUEUE, QUALITIES, formatBytes, formatDuration, formatSpeed, heatmapFor,
  useDownloadSim, useOptions, type QueueItem, type Sample,
} from '../sim'
import { usePalette } from '../color'
import { TitleBar } from '../TitleBar'
import './ambient.css'

const CURVE_W = 1000
const CURVE_H = 100
const TRIM_MIN_FRACTION = 0.04
/** "Zirveyi al" seçimi: en yüksek noktanın çevresinden bu kadar saniye. */
const PEAK_CLIP_SEC = 30
const RING_R = 25
const RING_C = 2 * Math.PI * RING_R
const TILT_DEG = 7

/** Catmull-Rom → kübik Bezier; heatmap noktalarından yumuşak eğri. */
function curvePath(values: number[], closed: boolean) {
  const pts = values.map((v, i) => [(i / (values.length - 1)) * CURVE_W, CURVE_H - v * (CURVE_H - 6)] as const)
  let d = `M ${pts[0][0]} ${pts[0][1]}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[Math.min(pts.length - 1, i + 2)]
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6]
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6]
    d += ` C ${c1[0]} ${c1[1]}, ${c2[0]} ${c2[1]}, ${p2[0]} ${p2[1]}`
  }
  return closed ? `${d} L ${CURVE_W} ${CURVE_H} L 0 ${CURVE_H} Z` : d
}

function Timeline({ sample, trim, setTrim, headAt, locked, showProgress }: {
  sample: Sample; trim: [number, number]; setTrim: (t: [number, number]) => void; headAt: number; locked: boolean; showProgress: boolean
}) {
  const values = useMemo(() => heatmapFor(sample.id), [sample.id])
  const area = useMemo(() => curvePath(values, true), [values])
  const line = useMemo(() => curvePath(values, false), [values])
  const ref = useRef<HTMLDivElement>(null)
  const drag = useRef<0 | 1 | null>(null)
  const peakAt = values.indexOf(Math.max(...values.slice(5))) / (values.length - 1)

  const setFromX = (clientX: number) => {
    if (drag.current === null || !ref.current) return
    const r = ref.current.getBoundingClientRect()
    const x = Math.min(1, Math.max(0, (clientX - r.left) / r.width))
    const next: [number, number] = [...trim]
    if (drag.current === 0) next[0] = Math.min(x, trim[1] - TRIM_MIN_FRACTION)
    else next[1] = Math.max(x, trim[0] + TRIM_MIN_FRACTION)
    setTrim(next)
  }
  const onDown = (w: 0 | 1) => (e: ReactPointerEvent) => {
    if (locked) return
    drag.current = w
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  }
  const nudge = (w: 0 | 1) => (e: React.KeyboardEvent) => {
    const dir = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!dir || locked) return
    e.preventDefault()
    const step = (e.shiftKey ? 10 : 1) / sample.durationSec
    const next: [number, number] = [...trim]
    if (w === 0) next[0] = Math.min(Math.max(0, trim[0] + dir * step), trim[1] - TRIM_MIN_FRACTION)
    else next[1] = Math.max(Math.min(1, trim[1] + dir * step), trim[0] + TRIM_MIN_FRACTION)
    setTrim(next)
  }
  const takePeak = () => {
    const half = PEAK_CLIP_SEC / 2 / sample.durationSec
    setTrim([Math.max(0, peakAt - half), Math.min(1, peakAt + half)])
  }
  const whole = trim[0] === 0 && trim[1] === 1

  return (
    <div className="am-timeline">
      <div className="am-timeline-head">
        <span>En çok tekrar oynatılan bölümler</span>
        <div className="am-timeline-actions">
          <button className="am-text-btn" onClick={takePeak} disabled={locked}>
            <Scissors size={14} strokeWidth={1.8} /> En popüler {PEAK_CLIP_SEC} saniyeyi al
          </button>
          {!whole && (
            <button className="am-text-btn" onClick={() => setTrim([0, 1])} disabled={locked}>Tamamını al</button>
          )}
        </div>
      </div>
      <div className="am-curve" ref={ref} onPointerMove={(e) => setFromX(e.clientX)} onPointerUp={() => (drag.current = null)}>
        <svg viewBox={`0 0 ${CURVE_W} ${CURVE_H}`} preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <clipPath id="am-trim-clip">
              <motion.rect y="0" height={CURVE_H} animate={{ x: trim[0] * CURVE_W, width: (trim[1] - trim[0]) * CURVE_W }} transition={{ type: 'spring', stiffness: 400, damping: 40 }} />
            </clipPath>
            <clipPath id="am-progress-clip">
              <rect x="0" y="0" height={CURVE_H} width={headAt * CURVE_W} />
            </clipPath>
            <linearGradient id="am-fill" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0" stopColor="var(--accent)" stopOpacity="0.95" />
              <stop offset="1" stopColor="var(--accent)" stopOpacity="0.25" />
            </linearGradient>
          </defs>
          <path d={area} className="am-curve-base" />
          <g clipPath="url(#am-trim-clip)">
            <path d={area} className="am-curve-sel" />
            {showProgress && (
              <g clipPath="url(#am-progress-clip)">
                <path d={area} fill="url(#am-fill)" />
                <path d={line} className="am-curve-line" vectorEffect="non-scaling-stroke" />
              </g>
            )}
          </g>
        </svg>
        {showProgress && headAt > trim[0] && headAt < trim[1] && <div className="am-head" style={{ left: `${headAt * 100}%` }} />}
        {([0, 1] as const).map((w) => (
          <div
            key={w}
            className="am-handle"
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
            data-locked={locked}
          >
            <span className="am-handle-knob" />
            <span className="am-handle-time" data-side={w ? 'end' : 'start'}>{formatDuration(trim[w] * sample.durationSec)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

type ButtonMode = 'idle' | 'disabled' | 'progress' | 'merging' | 'done'

function MorphButton({ mode, progress, onStart, onCancel, onReveal, sizeLabel }: {
  mode: ButtonMode; progress: number; onStart: () => void; onCancel: () => void; onReveal: () => void; sizeLabel: string
}) {
  const round = mode === 'progress' || mode === 'merging'
  return (
    <motion.button
      layout
      className="am-morph"
      data-mode={mode}
      disabled={mode === 'disabled'}
      onClick={mode === 'idle' ? onStart : mode === 'progress' ? onCancel : mode === 'done' ? onReveal : undefined}
      style={{ borderRadius: 999 }}
      transition={{ type: 'spring', stiffness: 380, damping: 32 }}
      aria-label={mode === 'progress' ? `İndiriliyor, %${Math.floor(progress * 100)}. Durdurmak için tıkla` : undefined}
    >
      <AnimatePresence mode="popLayout" initial={false}>
        {round ? (
          <motion.span key="ring" className="am-ring" initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.6 }}>
            <svg viewBox="0 0 60 60" className={mode === 'merging' ? 'am-ring-spin' : undefined}>
              <circle cx="30" cy="30" r={RING_R} className="am-ring-track" />
              <circle
                cx="30" cy="30" r={RING_R} className="am-ring-fill"
                strokeDasharray={RING_C}
                strokeDashoffset={mode === 'merging' ? RING_C * 0.72 : RING_C * (1 - progress)}
              />
            </svg>
            <span className="am-ring-label">{mode === 'merging' ? '' : Math.floor(progress * 100)}</span>
            <Square className="am-ring-stop" size={14} fill="currentColor" strokeWidth={0} />
          </motion.span>
        ) : mode === 'done' ? (
          <motion.span key="done" className="am-morph-label" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <Check size={18} strokeWidth={2.4} /> Klasörde göster
          </motion.span>
        ) : (
          <motion.span key="go" className="am-morph-label" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <Download size={18} strokeWidth={2.2} /> İndir <em>{sizeLabel}</em>
          </motion.span>
        )}
      </AnimatePresence>
    </motion.button>
  )
}

function Tilt({ children, active }: { children: React.ReactNode; active: boolean }) {
  const mx = useMotionValue(0)
  const my = useMotionValue(0)
  const rx = useSpring(useTransform(my, [-0.5, 0.5], [TILT_DEG, -TILT_DEG]), { stiffness: 150, damping: 15 })
  const ry = useSpring(useTransform(mx, [-0.5, 0.5], [-TILT_DEG, TILT_DEG]), { stiffness: 150, damping: 15 })
  return (
    <motion.div
      className="am-tilt"
      style={{ rotateX: active ? rx : 0, rotateY: active ? ry : 0 }}
      onPointerMove={(e) => {
        const r = e.currentTarget.getBoundingClientRect()
        mx.set((e.clientX - r.left) / r.width - 0.5)
        my.set((e.clientY - r.top) / r.height - 0.5)
      }}
      onPointerLeave={() => {
        mx.set(0)
        my.set(0)
      }}
    >
      {children}
    </motion.div>
  )
}

export function Ambient({ sample }: { sample: Sample }) {
  const [qualityId, setQualityId] = useState('1080')
  const quality = QUALITIES.find((q) => q.id === qualityId) ?? QUALITIES[1]
  const [trim, setTrim] = useState<[number, number]>([0, 1])
  const trimFraction = trim[1] - trim[0]
  const { state, paste, start, cancel } = useDownloadSim(sample, { ...quality, sizeRatio: quality.sizeRatio * trimFraction })
  const { on, toggle } = useOptions()
  const palette = usePalette(sample.thumb)
  const [recent, setRecent] = useState<QueueItem[]>(PAST_QUEUE)
  const [runId, setRunId] = useState(0)
  const [flown, setFlown] = useState(false)
  const [stackOpen, setStackOpen] = useState(false)

  const { phase } = state
  const loaded = phase !== 'empty'
  const busy = phase === 'downloading' || phase === 'merging'
  const headAt = phase === 'downloading' ? trim[0] + state.progress * trimFraction : phase === 'merging' || phase === 'done' ? trim[1] : trim[0]
  const vars = loaded
    ? { '--deep': palette.deep, '--mid': palette.mid, '--accent': palette.accent, '--on-accent': palette.onAccent }
    : { '--deep': 'hsl(220 8% 9%)', '--mid': 'hsl(220 6% 15%)', '--accent': 'hsl(0 0% 92%)', '--on-accent': 'hsl(0 0% 8%)' }

  // Bitince kapak küçülüp sağ üstteki yığına uçar (paylaşılan layoutId).
  useEffect(() => {
    if (phase !== 'done') return
    const id = window.setTimeout(() => {
      setRecent((r) => [{ id: `run-${runId}`, title: sample.title, channel: sample.channel, thumb: sample.thumb, sizeBytes: state.totalBytes, state: 'done' as const, note: 'az önce' }, ...r])
      setFlown(true)
    }, 1600)
    return () => clearTimeout(id)
  }, [phase, runId, sample, state.totalBytes])

  const onPaste = () => {
    setRunId((r) => r + 1)
    setFlown(false)
    setTrim([0, 1])
    paste()
  }

  const mode: ButtonMode = phase === 'downloading' ? 'progress' : phase === 'merging' ? 'merging' : phase === 'done' ? 'done' : phase === 'ready' ? 'idle' : 'disabled'
  const showStage = loaded && !flown

  return (
    <LayoutGroup>
      <div className="am" style={vars as React.CSSProperties} data-busy={busy}>
        <div className="am-bg" aria-hidden="true">
          <AnimatePresence>
            {showStage && phase !== 'fetching' && (
              <motion.img key={sample.thumb} src={sample.thumb} alt="" initial={{ opacity: 0 }} animate={{ opacity: 0.55 }} exit={{ opacity: 0 }} transition={{ duration: 1.2 }} />
            )}
          </AnimatePresence>
          <div className="am-grain" />
        </div>
        <TitleBar className="am-titlebar" />
        <div className="am-body">
          <nav className="am-rail" aria-label="Bölümler">
            {[
              { Icon: Home, label: 'Ana sayfa', active: true },
              { Icon: Download, label: 'İndirilenler' },
              { Icon: Library, label: 'Kütüphane' },
              { Icon: History, label: 'Geçmiş' },
            ].map(({ Icon, label, active }) => (
              <button key={label} className="am-rail-btn" aria-current={active ? 'page' : undefined} aria-label={label} title={label}>
                <Icon size={20} strokeWidth={1.7} />
              </button>
            ))}
            <button className="am-rail-btn am-rail-bottom" aria-label="Ayarlar" title="Ayarlar">
              <Settings size={20} strokeWidth={1.7} />
            </button>
          </nav>

          <main className="am-main">
            <header className="am-top">
              <div className="am-url">
                <input readOnly value={flown ? "" : state.url} placeholder="Bağlantıyı yapıştır" aria-label="Bağlantı" />
                <button className="am-ghost" onClick={onPaste} disabled={busy}>
                  <ClipboardPaste size={16} strokeWidth={1.8} /> Yapıştır
                </button>
                <button className="am-ghost" disabled={busy}>
                  <Layers size={16} strokeWidth={1.8} /> Toplu
                </button>
              </div>
              <div className="am-stack-wrap">
                <button className="am-stack" onClick={() => setStackOpen((o) => !o)} aria-expanded={stackOpen} aria-label={`Son indirilenler, ${recent.length}`}>
                  {recent.slice(0, 3).map((r, i) => (
                    <motion.img key={r.id} layoutId={`am-cover-${r.id}`} src={r.thumb} alt="" style={{ zIndex: 3 - i }} transition={{ type: 'spring', stiffness: 170, damping: 22 }} />
                  ))}
                  <span>{recent.length}</span>
                </button>
                <AnimatePresence>
                  {stackOpen && (
                    <motion.ul className="am-stack-list" initial={{ opacity: 0, y: -8, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -8, scale: 0.97 }} transition={{ duration: 0.18 }}>
                      {recent.map((r) => (
                        <li key={r.id} data-state={r.state}>
                          <img src={r.thumb} alt="" />
                          <div>
                            <strong>{r.title}</strong>
                            <span>{r.state === 'error' ? r.note : `${formatBytes(r.sizeBytes)}, ${r.note}`}</span>
                          </div>
                        </li>
                      ))}
                    </motion.ul>
                  )}
                </AnimatePresence>
              </div>
            </header>

            <AnimatePresence mode="wait">
              {!showStage ? (
                <motion.section key="empty" className="am-empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0, transition: { duration: 0.15 } }}>
                  <h1>{flown ? 'İndirildi. Sıradaki?' : 'Ne indirmek istersin?'}</h1>
                  <p>Bir bağlantı kopyala, gerisini uygulama halleder. YouTube, Spotify, SoundCloud, TikTok ve 1000’den fazla site.</p>
                  <button className="am-ghost am-ghost-lg" onClick={onPaste}>
                    <ClipboardPaste size={17} strokeWidth={1.8} /> Panodan yapıştır
                  </button>
                </motion.section>
              ) : (
                <motion.section key={`stage-${runId}`} className="am-stage" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                  <Tilt active={phase === 'ready'}>
                    {phase === 'fetching' ? (
                      <div className="am-cover am-cover-skel" />
                    ) : (
                      <motion.img
                        layoutId={`am-cover-run-${runId}`}
                        className="am-cover"
                        src={sample.thumb}
                        alt=""
                        initial={{ opacity: 0, filter: 'blur(18px)', scale: 0.96 }}
                        animate={{ opacity: 1, filter: 'blur(0px)', scale: phase === 'downloading' ? 0.97 : 1 }}
                        transition={{ type: 'spring', stiffness: 170, damping: 22 }}
                      />
                    )}
                  </Tilt>
                  <div className="am-info">
                    {phase === 'fetching' ? (
                      <div className="am-skel-lines"><span /><span /><span /></div>
                    ) : (
                      <motion.div initial="hidden" animate="show" variants={{ show: { transition: { staggerChildren: 0.06 } } }}>
                        <motion.p className="am-channel" variants={rise}>{sample.channel}, {formatDuration(sample.durationSec)}</motion.p>
                        <motion.h1 className="am-title" variants={rise}>{sample.title}</motion.h1>
                        <motion.div className="am-seg" variants={rise} role="radiogroup" aria-label="Kalite">
                          {QUALITIES.map((q) => (
                            <button key={q.id} role="radio" aria-checked={q.id === qualityId} onClick={() => setQualityId(q.id)} disabled={busy} data-kind={q.kind}>
                              {q.id === qualityId && <motion.span layoutId="am-seg-ind" className="am-seg-ind" transition={{ type: 'spring', stiffness: 500, damping: 36 }} />}
                              <span className="am-seg-text">{q.label}</span>
                            </button>
                          ))}
                        </motion.div>
                        <motion.div className="am-opts" variants={rise}>
                          {OPTIONS.map((o) => (
                            <button key={o.id} role="switch" aria-checked={on[o.id]} className="am-opt" onClick={() => toggle(o.id)} title={o.hint}>
                              <span className="am-opt-track"><motion.span className="am-opt-knob" animate={{ x: on[o.id] ? 14 : 0 }} transition={{ type: 'spring', stiffness: 600, damping: 32 }} /></span>
                              {o.label}
                            </button>
                          ))}
                        </motion.div>
                        <motion.div className="am-go" variants={rise}>
                          <MorphButton mode={mode} progress={state.progress} onStart={start} onCancel={cancel} onReveal={() => setStackOpen(true)} sizeLabel={formatBytes(state.totalBytes)} />
                          <p className="am-go-status" aria-live="polite">
                            {phase === 'downloading' && `${formatBytes(state.bytesDone)} / ${formatBytes(state.totalBytes)}, ${formatSpeed(state.speedBps)}, ${formatDuration(state.etaSec)} kaldı`}
                            {phase === 'merging' && 'Görüntü ve ses birleştiriliyor'}
                            {phase === 'done' && `${formatBytes(state.totalBytes)} İndirilenler klasörüne kaydedildi`}
                            {phase === 'ready' && trimFraction < 1 && `Yalnız ${formatDuration(trimFraction * sample.durationSec)} indirilecek`}
                          </p>
                        </motion.div>
                      </motion.div>
                    )}
                  </div>
                  {phase !== 'fetching' && (
                    <motion.div className="am-timeline-wrap" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.25, type: 'spring', stiffness: 200, damping: 26 }}>
                      <Timeline sample={sample} trim={trim} setTrim={setTrim} headAt={headAt} locked={busy || phase === 'done'} showProgress={phase !== 'ready'} />
                    </motion.div>
                  )}
                </motion.section>
              )}
            </AnimatePresence>
          </main>
        </div>
      </div>
    </LayoutGroup>
  )
}

const rise = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { type: 'spring' as const, stiffness: 260, damping: 26 } },
}
