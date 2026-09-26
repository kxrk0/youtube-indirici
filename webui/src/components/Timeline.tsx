import { useMemo, useRef, type KeyboardEvent, type PointerEvent } from 'react'
import { motion } from 'motion/react'
import { Scissors } from 'lucide-react'
import type { HeatSegment } from '../bridge'
import { duration as fmtDuration } from '../ortam/format'

const CURVE_W = 1000
const CURVE_H = 100
const CURVE_POINTS = 100
const TRIM_MIN_FRACTION = 0.04
/** "En popüler" seçimi: en yüksek noktanın çevresinden bu kadar saniye. */
const PEAK_CLIP_SEC = 30
/** YouTube eğrisi ilk anlarda hep yüksek (izleyici girişi); zirve aranırken atlanan nokta sayısı. */
const PEAK_SEARCH_SKIP = 5
/** Veri yokken düz bant yüksekliği (eğri alanına oranla). */
const FLAT_LEVEL = 0.35
const SPRING_TRIM = { type: 'spring', stiffness: 400, damping: 40 } as const

/** yt-dlp heatmap → eşit aralıklı, en yükseği 1 olan değerler. Veri yoksa null. */
export function heatmapToCurve(segments: HeatSegment[] | null, total: number): number[] | null {
  if (!segments?.length || !total) return null
  const sorted = [...segments].sort((a, b) => a.start - b.start)
  const out: number[] = []
  let j = 0
  for (let i = 0; i < CURVE_POINTS; i++) {
    const t = (total * i) / (CURVE_POINTS - 1)
    while (j < sorted.length - 1 && sorted[j].end < t) j++
    out.push(sorted[j].value)
  }
  const peak = Math.max(...out) || 1
  return out.map((v) => v / peak)
}

/** Catmull-Rom → kübik Bezier (mock'taki curvePath). */
function curvePath(values: number[], closed: boolean) {
  const pts = values.map((v, i) => [(i / (values.length - 1)) * CURVE_W, CURVE_H - v * (CURVE_H - 6)] as const)
  let d = `M ${pts[0][0]} ${pts[0][1]}`
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)]
    const p1 = pts[i]
    const p2 = pts[i + 1]
    const p3 = pts[Math.min(pts.length - 1, i + 2)]
    d += ` C ${p1[0] + (p2[0] - p0[0]) / 6} ${p1[1] + (p2[1] - p0[1]) / 6}, ${p2[0] - (p3[0] - p1[0]) / 6} ${p2[1] - (p3[1] - p1[1]) / 6}, ${p2[0]} ${p2[1]}`
  }
  return closed ? `${d} L ${CURVE_W} ${CURVE_H} L 0 ${CURVE_H} Z` : d
}

export function Timeline({ heatmap, total, trim, setTrim, head, locked, showProgress }: {
  heatmap: HeatSegment[] | null
  total: number
  trim: [number, number]
  setTrim: (t: [number, number]) => void
  /** 0..1 ilerleme başı (tüm video ölçeğinde) */
  head: number
  locked: boolean
  showProgress: boolean
}) {
  const values = useMemo(() => heatmapToCurve(heatmap, total), [heatmap, total])
  const shape = values ?? [FLAT_LEVEL, FLAT_LEVEL]
  const area = useMemo(() => curvePath(shape, true), [shape])
  const line = useMemo(() => curvePath(shape, false), [shape])
  const ref = useRef<HTMLDivElement>(null)
  const drag = useRef<0 | 1 | null>(null)
  const peakAt = useMemo(() => {
    if (!values) return 0
    let best = PEAK_SEARCH_SKIP
    for (let i = PEAK_SEARCH_SKIP; i < values.length; i++) if (values[i] > values[best]) best = i
    return best / (values.length - 1)
  }, [values])

  const move = (clientX: number) => {
    if (drag.current === null || !ref.current) return
    const r = ref.current.getBoundingClientRect()
    const x = Math.min(1, Math.max(0, (clientX - r.left) / r.width))
    const next: [number, number] = [...trim]
    if (drag.current === 0) next[0] = Math.min(x, trim[1] - TRIM_MIN_FRACTION)
    else next[1] = Math.max(x, trim[0] + TRIM_MIN_FRACTION)
    setTrim(next)
  }
  const down = (w: 0 | 1) => (e: PointerEvent) => {
    if (locked) return
    drag.current = w
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  }
  const nudge = (w: 0 | 1) => (e: KeyboardEvent) => {
    const dir = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!dir || locked || !total) return
    e.preventDefault()
    const step = (e.shiftKey ? 10 : 1) / total
    const next: [number, number] = [...trim]
    if (w === 0) next[0] = Math.min(Math.max(0, trim[0] + dir * step), trim[1] - TRIM_MIN_FRACTION)
    else next[1] = Math.max(Math.min(1, trim[1] + dir * step), trim[0] + TRIM_MIN_FRACTION)
    setTrim(next)
  }
  const takePeak = () => {
    const half = PEAK_CLIP_SEC / 2 / total
    setTrim([Math.max(0, peakAt - half), Math.min(1, peakAt + half)])
  }
  const whole = trim[0] === 0 && trim[1] === 1

  return (
    <div className="am-timeline">
      <div className="am-timeline-head">
        <span>{values ? 'En çok tekrar oynatılan bölümler' : 'Bölüm seç'}</span>
        <div className="am-timeline-actions">
          {values && (
            <button className="am-text-btn" onClick={takePeak} disabled={locked}>
              <Scissors size={14} strokeWidth={1.8} /> En popüler {PEAK_CLIP_SEC} saniyeyi al
            </button>
          )}
          {!whole && <button className="am-text-btn" onClick={() => setTrim([0, 1])} disabled={locked}>Tamamını al</button>}
        </div>
      </div>
      <div className="am-curve" ref={ref} onPointerMove={(e) => move(e.clientX)} onPointerUp={() => (drag.current = null)}>
        <svg viewBox={`0 0 ${CURVE_W} ${CURVE_H}`} preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <clipPath id="am-trim-clip">
              <motion.rect y="0" height={CURVE_H} animate={{ x: trim[0] * CURVE_W, width: (trim[1] - trim[0]) * CURVE_W }} transition={SPRING_TRIM} />
            </clipPath>
            <clipPath id="am-progress-clip">
              <rect x="0" y="0" height={CURVE_H} width={head * CURVE_W} />
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
                {values && <path d={line} className="am-curve-line" vectorEffect="non-scaling-stroke" />}
              </g>
            )}
          </g>
        </svg>
        {showProgress && head > trim[0] && head < trim[1] && <div className="am-head" style={{ left: `${head * 100}%` }} />}
        {([0, 1] as const).map((w) => (
          <div key={w} className="am-handle" style={{ left: `${trim[w] * 100}%` }} onPointerDown={down(w)} onKeyDown={nudge(w)}
            role="slider" tabIndex={locked ? -1 : 0} aria-label={w ? 'Bitiş' : 'Başlangıç'}
            aria-valuemin={0} aria-valuemax={total} aria-valuenow={Math.round(trim[w] * total)} aria-valuetext={fmtDuration(trim[w] * total)}
            data-locked={locked}>
            <span className="am-handle-knob" />
            <span className="am-handle-time" data-side={w ? 'end' : 'start'}>{fmtDuration(trim[w] * total)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
