import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useAnimationFrame, useMotionValue, useSpring, useTransform } from 'motion/react'
import { ClipboardPaste, Download, History, Home, Layers, Library, Settings, Square, Timer } from 'lucide-react'
import {
  OPTIONS, PAST_QUEUE, QUALITIES, formatBytes, formatDuration, formatSpeed,
  useDownloadSim, useOptions, type QueueItem, type Sample,
} from '../sim'
import { TitleBar } from '../TitleBar'
import './tape.css'

/** Makara geometrisi (px, SVG viewBox içinde). Bant alanı korunur: r² = rHub² + (rFull² − rHub²)·oran. */
const R_HUB = 22
const R_FULL = 64
/** Bant çizgisel hızı, ekran px/s; açısal hız = v / r olduğundan dolu makara yavaş, boş makara hızlı döner. */
const TAPE_PX_PER_SEC = 70
/** Hız göstergesinin tam sapması; ev bağlantısında tipik üst sınır. */
const METER_MAX_BPS = 20e6
const EJECT_DELAY_MS = 1300

function packRadius(fill: number) {
  return Math.sqrt(R_HUB * R_HUB + (R_FULL * R_FULL - R_HUB * R_HUB) * fill)
}

function Reel({ cx, cy, fill, running, speedFactor }: { cx: number; cy: number; fill: number; running: boolean; speedFactor: number }) {
  const angle = useMotionValue(0)
  const r = packRadius(fill)
  useAnimationFrame((_, dt) => {
    if (!running) return
    const omega = (TAPE_PX_PER_SEC * speedFactor) / r
    angle.set((angle.get() + (omega * dt * 180) / (Math.PI * 1000)) % 360)
  })
  const transform = useTransform(angle, (a) => `rotate(${a} ${cx} ${cy})`)
  return (
    <g>
      <circle cx={cx} cy={cy} r={r} className="tp-pack" />
      <circle cx={cx} cy={cy} r={r} className="tp-pack-sheen" />
      <motion.g transform={transform}>
        <circle cx={cx} cy={cy} r={R_HUB} className="tp-hub" />
        {Array.from({ length: 6 }, (_, i) => (
          <rect key={i} x={cx - 2.5} y={cy - R_HUB + 3} width={5} height={8} rx={1.5} className="tp-hub-tooth" transform={`rotate(${i * 60} ${cx} ${cy})`} />
        ))}
        <circle cx={cx} cy={cy} r={9} className="tp-hub-hole" />
      </motion.g>
    </g>
  )
}

function Cassette({ sample, qualityLabel, fill, running, speedFactor, fetching }: {
  sample: Sample; qualityLabel: string; fill: number; running: boolean; speedFactor: number; fetching: boolean
}) {
  return (
    <div className="tp-cassette">
      <span className="tp-screw" style={{ left: 10, top: 10 }} />
      <span className="tp-screw" style={{ right: 10, top: 10 }} />
      <span className="tp-screw" style={{ left: 10, bottom: 10 }} />
      <span className="tp-screw" style={{ right: 10, bottom: 10 }} />
      <div className="tp-label">
        <div className="tp-label-stripe" />
        <AnimatePresence mode="wait">
          {fetching ? (
            <motion.div key="blank" className="tp-label-blank" exit={{ opacity: 0 }}>
              <span /> <span />
            </motion.div>
          ) : (
            <motion.div key="text" className="tp-label-text" initial={{ clipPath: 'inset(0 100% 0 0)' }} animate={{ clipPath: 'inset(0 0% 0 0)' }} transition={{ duration: 0.7, ease: [0.3, 0, 0.2, 1] }}>
              <img src={sample.thumb} alt="" />
              <div>
                <strong>{sample.title}</strong>
                <span>{sample.channel}</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <svg className="tp-window" viewBox="0 0 520 120" aria-hidden="true">
          <defs>
            <clipPath id="tp-window-clip">
              <rect x="70" y="10" width="380" height="100" rx="50" />
            </clipPath>
          </defs>
          <rect x="70" y="10" width="380" height="100" rx="50" className="tp-window-bg" />
          <g clipPath="url(#tp-window-clip)">
            <Reel cx={150} cy={60} fill={1 - fill} running={running} speedFactor={speedFactor} />
            <Reel cx={370} cy={60} fill={fill} running={running} speedFactor={speedFactor} />
          </g>
          <rect x="70" y="10" width="380" height="100" rx="50" className="tp-window-glass" />
        </svg>
        <div className="tp-label-foot">
          <span>{qualityLabel}</span>
          <span>{fetching ? '–:––' : formatDuration(sample.durationSec)}</span>
        </div>
      </div>
      <div className="tp-cassette-foot">
        <span /><span /><span /><span />
      </div>
    </div>
  )
}

function Meter({ bps }: { bps: number }) {
  const target = useMotionValue(0)
  const spring = useSpring(target, { stiffness: 120, damping: 11, mass: 0.6 })
  useEffect(() => {
    target.set(Math.min(1, bps / METER_MAX_BPS))
  }, [bps, target])
  const needle = useTransform(spring, (v) => `rotate(${-48 + v * 96} 180 168)`)
  const ticks = [0, 5, 10, 15, 20]
  return (
    <div className="tp-meter">
      <svg viewBox="0 0 360 130" aria-label={`İndirme hızı ${formatSpeed(bps)}`} role="img">
        {Array.from({ length: 21 }, (_, i) => {
          const a = ((-48 + (i / 20) * 96) * Math.PI) / 180
          const long = i % 5 === 0
          const r1 = long ? 118 : 124
          return <line key={i} x1={180 + Math.sin(a) * r1} y1={168 - Math.cos(a) * r1} x2={180 + Math.sin(a) * 132} y2={168 - Math.cos(a) * 132} className={long ? 'tp-tick tp-tick-long' : 'tp-tick'} />
        })}
        {ticks.map((t) => {
          const a = ((-48 + (t / 20) * 96) * Math.PI) / 180
          return <text key={t} x={180 + Math.sin(a) * 104} y={168 - Math.cos(a) * 104 + 4} className="tp-tick-num">{t}</text>
        })}
        <text x="180" y="96" className="tp-meter-unit">MB/s</text>
        <motion.line x1="180" y1="168" x2="180" y2="40" className="tp-needle" transform={needle} />
        <circle cx="180" cy="168" r="30" className="tp-needle-cap" />
      </svg>
    </div>
  )
}

function Vfd({ lines, big }: { big: string; lines: [string, string] }) {
  return (
    <div className="tp-vfd" aria-live="polite">
      <div className="tp-vfd-big">{big}</div>
      <div className="tp-vfd-row">
        <span>{lines[0]}</span>
        <span>{lines[1]}</span>
      </div>
    </div>
  )
}

function Spine({ item }: { item: QueueItem }) {
  return (
    <motion.li layout className={`tp-spine tp-spine-${item.state}`} layoutId={`tp-${item.id}`} transition={{ type: 'spring', stiffness: 260, damping: 28 }}>
      <img src={item.thumb} alt="" />
      <div>
        <strong>{item.title}</strong>
        <span>{item.state === 'error' ? item.note : `${formatBytes(item.sizeBytes)}, ${item.note}`}</span>
      </div>
    </motion.li>
  )
}

export function Tape({ sample }: { sample: Sample }) {
  const [qualityId, setQualityId] = useState('1080')
  const quality = QUALITIES.find((q) => q.id === qualityId) ?? QUALITIES[1]
  const { state, paste, start, cancel, reset } = useDownloadSim(sample, quality)
  const { on, toggle } = useOptions()
  const [shelf, setShelf] = useState<QueueItem[]>(PAST_QUEUE)
  const [typed, setTyped] = useState('')
  const ejected = useRef(false)
  const [runId, setRunId] = useState(0)

  const { phase } = state
  const loaded = phase !== 'empty'
  const running = phase === 'downloading'

  // Yuvaya yazılan bağlantı: yapıştırmada hızlı daktilo efekti, gerçek uygulamada anında dolar.
  useEffect(() => {
    if (!state.url) return setTyped('')
    let i = 0
    const id = window.setInterval(() => {
      i += 3
      setTyped(state.url.slice(0, i))
      if (i >= state.url.length) clearInterval(id)
    }, 16)
    return () => clearInterval(id)
  }, [state.url])

  useEffect(() => {
    if (phase !== 'done' || ejected.current) return
    ejected.current = true
    const id = window.setTimeout(() => {
      setShelf((s) => [{ id: `run-${runId}`, title: sample.title, channel: sample.channel, thumb: sample.thumb, sizeBytes: state.totalBytes, state: 'done' as const, note: 'az önce' }, ...s].slice(0, 4))
      reset()
    }, EJECT_DELAY_MS)
    return () => clearTimeout(id)
  }, [phase, reset, runId, sample, state.totalBytes])

  useEffect(() => {
    if (phase === 'fetching') ejected.current = false
  }, [phase])

  // Makaralar gösterilen hıza göre döner; 11 MB/s ≈ 1x.
  const speedFactor = running ? state.speedBps / 11e6 : 0

  const vfd: { big: string; lines: [string, string] } = (() => {
    switch (phase) {
      case 'empty':
        return shelf[0]?.id.startsWith('run-')
          ? { big: 'Rafa kondu', lines: ['Sıradaki bağlantıyı yapıştır', ''] }
          : { big: 'Boş', lines: ['Bağlantı bekleniyor', ''] }
      case 'fetching':
        return { big: 'Okunuyor', lines: ['Bilgiler alınıyor', ''] }
      case 'ready':
        return { big: formatBytes(state.totalBytes), lines: ['Tahmini boyut', `${quality.label}`] }
      case 'downloading':
        return { big: `${String(Math.floor(state.progress * 100)).padStart(3, '0')}%`, lines: [formatSpeed(state.speedBps), `${formatDuration(state.etaSec)} kaldı`] }
      case 'merging':
        return { big: 'Birleşiyor', lines: ['Görüntü ve ses tek dosyada', ''] }
      case 'done':
        return { big: 'Tamam', lines: [formatBytes(state.totalBytes), 'İndirilenler klasöründe'] }
    }
  })()

  const video = QUALITIES.filter((q) => q.kind === 'video')
  const audio = QUALITIES.filter((q) => q.kind === 'audio')

  return (
    <div className="tp">
      <TitleBar className="tp-titlebar" />
      <div className="tp-body">
        <nav className="tp-rail" aria-label="Bölümler">
          {[
            { Icon: Home, label: 'Ana sayfa', active: true },
            { Icon: Download, label: 'İndirilenler', badge: running ? 1 : 0 },
            { Icon: Library, label: 'Kütüphane' },
            { Icon: History, label: 'Geçmiş' },
          ].map(({ Icon, label, active, badge }) => (
            <button key={label} className="tp-rail-btn" aria-current={active ? 'page' : undefined}>
              <span className="tp-led" data-on={active || !!badge} />
              <Icon size={18} strokeWidth={1.6} />
              {label}
            </button>
          ))}
          <button className="tp-rail-btn tp-rail-bottom">
            <Settings size={18} strokeWidth={1.6} />
            Ayarlar
          </button>
        </nav>

        <main className="tp-main">
          <div className="tp-slot-row">
            <label className="tp-slot">
              <span className="tp-silk">Bağlantı</span>
              <input readOnly value={typed} placeholder="YouTube, Spotify, SoundCloud, TikTok… Birden fazla bağlantı toplu indirilir." />
            </label>
            <button className="tp-key tp-key-wide" onClick={() => { setRunId((r) => r + 1); paste() }} disabled={running}>
              <ClipboardPaste size={16} strokeWidth={1.8} /> Yapıştır
            </button>
            <button className="tp-key tp-key-wide" disabled={running}>
              <Layers size={16} strokeWidth={1.8} /> Toplu
            </button>
          </div>

          <div className="tp-deck-row">
            <div className="tp-bay">
              <AnimatePresence>
                {loaded && (
                  <motion.div
                    key="cassette"
                    layoutId={`tp-run-${runId}`}
                    initial={{ y: -340, rotate: -2 }}
                    animate={phase === 'done' ? { y: -18, rotate: 0 } : { y: 0, rotate: 0 }}
                    transition={{ type: 'spring', stiffness: 210, damping: 20, mass: 0.9 }}
                  >
                    <Cassette sample={sample} qualityLabel={quality.label} fill={state.progress} running={running} speedFactor={speedFactor} fetching={phase === 'fetching'} />
                  </motion.div>
                )}
              </AnimatePresence>
              {!loaded && (
                <div className="tp-bay-empty">
                  <p>Bağlantıyı yuvaya yapıştır.</p>
                  <p>Panoda bağlantı varsa kendiliğinden gelir.</p>
                </div>
              )}
            </div>
            <div className="tp-readout">
              <Meter bps={state.speedBps} />
              <Vfd big={vfd.big} lines={vfd.lines} />
            </div>
          </div>

          <div className="tp-controls-row">
            <div className="tp-keygroup">
              <span className="tp-silk">Görüntü</span>
              <div className="tp-keys">
                {video.map((q) => (
                  <button key={q.id} className="tp-key tp-key-tall" aria-pressed={q.id === qualityId} onClick={() => setQualityId(q.id)} disabled={running}>
                    <span className="tp-led" data-on={q.id === qualityId} />
                    {q.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="tp-keygroup">
              <span className="tp-silk">Yalnız ses</span>
              <div className="tp-keys">
                {audio.map((q) => (
                  <button key={q.id} className="tp-key tp-key-tall" aria-pressed={q.id === qualityId} onClick={() => setQualityId(q.id)} disabled={running}>
                    <span className="tp-led" data-on={q.id === qualityId} />
                    {q.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="tp-keygroup tp-switches">
              <span className="tp-silk">İşlem</span>
              <div className="tp-keys">
                {OPTIONS.map((o) => (
                  <button key={o.id} role="switch" aria-checked={on[o.id]} className="tp-switch" onClick={() => toggle(o.id)} title={o.hint}>
                    <span className="tp-switch-track"><motion.span className="tp-switch-lever" animate={{ y: on[o.id] ? 0 : 18 }} transition={{ type: 'spring', stiffness: 700, damping: 30 }} /></span>
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="tp-transport">
              <button className="tp-key tp-key-small" disabled={phase !== 'ready'}>
                <Timer size={15} strokeWidth={1.8} /> Zamanla
              </button>
              {running ? (
                <button className="tp-rec" data-live="true" onClick={cancel}>
                  <Square size={16} fill="currentColor" /> Durdur
                </button>
              ) : (
                <button className="tp-rec" onClick={start} disabled={phase !== 'ready'}>
                  <span className="tp-rec-dot" /> Kaydet
                </button>
              )}
            </div>
          </div>

          <section className="tp-shelf" aria-label="Son indirilenler">
            <span className="tp-silk">Raf</span>
            <ul>
              <AnimatePresence initial={false}>
                {shelf.map((item) => <Spine key={item.id} item={item} />)}
              </AnimatePresence>
            </ul>
          </section>
        </main>
      </div>
    </div>
  )
}
