import { useCallback, useEffect, useRef, useState } from 'react'

export type Sample = {
  id: string
  url: string
  title: string
  channel: string
  durationSec: number
  thumb: string
  /** 1080p MP4 boyutu; diğer kaliteler bundan oranla türetilir. */
  sizeBytes: number
}

export const SAMPLES: Sample[] = [
  {
    id: 'bana-sor',
    url: 'https://www.youtube.com/watch?v=Qm1bAnaS0r4',
    title: 'ERA7CAPONE X ŞAM - BANA SOR (OFFICIAL MUSIC VIDEO)',
    channel: 'Era7capone',
    durationSec: 192,
    thumb: '/thumbs/bana-sor.jpg',
    sizeBytes: 152_969_253,
  },
  {
    id: 'mi-amor',
    url: 'https://www.youtube.com/watch?v=kSk1nMiAm0r',
    title: 'Keskin - MI AMOR (Music Video)',
    channel: 'Keskin',
    durationSec: 146,
    thumb: '/thumbs/mi-amor.jpg',
    sizeBytes: 118_402_117,
  },
  {
    id: 'cindy',
    url: 'https://www.youtube.com/watch?v=uZ1c1ndyV1d',
    title: 'UZI - CINDY (Official Video)',
    channel: 'MuzikPlay',
    durationSec: 119,
    thumb: '/thumbs/cindy.jpg',
    sizeBytes: 96_311_880,
  },
  {
    id: 'anatolia',
    url: 'https://www.youtube.com/watch?v=eCh0esAnat0',
    title: 'Echoes of Anatolia — Full Album',
    channel: 'Anatolian Sessions',
    durationSec: 2714,
    thumb: '/thumbs/anatolia.jpg',
    sizeBytes: 1_402_551_904,
  },
]

export type Quality = { id: string; label: string; kind: 'video' | 'audio'; sizeRatio: number }

// Oranlar yt-dlp'nin tipik H.264/AAC bitrate'lerinden kabaca: 1080p ~ 6.4 Mbit/s referans.
export const QUALITIES: Quality[] = [
  { id: '2160', label: '4K', kind: 'video', sizeRatio: 3.1 },
  { id: '1080', label: '1080p', kind: 'video', sizeRatio: 1 },
  { id: '720', label: '720p', kind: 'video', sizeRatio: 0.52 },
  { id: 'mp3', label: 'MP3 320k', kind: 'audio', sizeRatio: 0.05 },
  { id: 'm4a', label: 'M4A 256k', kind: 'audio', sizeRatio: 0.04 },
]

export type Phase = 'empty' | 'fetching' | 'ready' | 'downloading' | 'merging' | 'done'

export type QueueItem = {
  id: string
  title: string
  channel: string
  thumb: string
  sizeBytes: number
  state: 'done' | 'waiting' | 'error'
  note: string
}

export const PAST_QUEUE: QueueItem[] = [
  { id: 'p1', title: 'Random VHS Footage VCR Retro Tapes (Nature/Scenery)', channel: 'audioman5000', thumb: '/thumbs/q2.jpg', sizeBytes: 41_220_331, state: 'done', note: 'Dün 23:41' },
  { id: 'p2', title: 'Keskin - MI AMOR (Music Video)', channel: 'Keskin', thumb: '/thumbs/q3.jpg', sizeBytes: 8_402_117, state: 'done', note: 'MP3, dün 22:10' },
  { id: 'p3', title: 'UZI - CINDY (Official Video)', channel: 'MuzikPlay', thumb: '/thumbs/q1.jpg', sizeBytes: 0, state: 'error', note: 'HTTP 403, çerez gerekli' },
]

const FETCH_MS = 1100
const MERGE_MS = 1400
/** Demo süresi: gerçek hız ~10 MB/s olsa bile indirme ~12 sn'de bitsin diye ölçek. */
const DEMO_DOWNLOAD_MS = 12_000
/** Ekranda gösterilen hız: tipik 100 Mbit/s ev bağlantısı (~11 MB/s). Demo süresi sıkıştırılsa da sayılar gerçekçi kalsın. */
const SHOWN_BASE_BPS = 11e6

const TR = new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 1, minimumFractionDigits: 1 })
const TR2 = new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 2, minimumFractionDigits: 2 })

export function formatBytes(n: number): string {
  if (n >= 1e9) return `${TR2.format(n / 1e9)} GB`
  if (n >= 1e6) return `${TR.format(n / 1e6)} MB`
  if (n >= 1e3) return `${Math.round(n / 1e3)} KB`
  return `${n} B`
}

export function formatSpeed(bps: number): string {
  return `${TR.format(bps / 1e6)} MB/s`
}

export function formatDuration(sec: number): string {
  const s = Math.max(0, Math.round(sec))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const r = s % 60
  const mm = h ? String(m).padStart(2, '0') : String(m)
  return `${h ? h + ':' : ''}${mm}:${String(r).padStart(2, '0')}`
}

export function mulberry32(seed: number) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function seedOf(s: string) {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619)
  return h >>> 0
}

/**
 * yt-dlp `heatmap` alanını taklit eder (YouTube "en çok tekrar oynatılan" eğrisi, 100 nokta, 0..1).
 * Gerçek uygulamada info_dict['heatmap'] doğrudan kullanılır.
 */
export function heatmapFor(id: string, points = 100): number[] {
  const rnd = mulberry32(seedOf(id))
  const peaks = Array.from({ length: 3 }, () => ({ at: 0.15 + rnd() * 0.75, w: 0.03 + rnd() * 0.07, h: 0.5 + rnd() * 0.5 }))
  return Array.from({ length: points }, (_, i) => {
    const x = i / (points - 1)
    let v = 0.18 + 0.1 * Math.sin(x * 9 + rnd() * 0.4)
    for (const p of peaks) v += p.h * Math.exp(-((x - p.at) ** 2) / (2 * p.w * p.w))
    v += x < 0.04 ? 0.5 * (1 - x / 0.04) : 0
    return Math.min(1, v)
  })
}

export type SimState = {
  phase: Phase
  url: string
  progress: number
  bytesDone: number
  totalBytes: number
  speedBps: number
  etaSec: number
  /** Hız geçmişi, son 60 örnek; VU/grafik çizimleri için. */
  speedHistory: number[]
}

export function useDownloadSim(sample: Sample, quality: Quality) {
  const totalBytes = Math.round(sample.sizeBytes * quality.sizeRatio)
  const [state, setState] = useState<SimState>(() => initial(totalBytes))
  const raf = useRef<number | null>(null)
  const timer = useRef<number | null>(null)
  const noise = useRef(mulberry32(seedOf(sample.id)))

  const stopClocks = useCallback(() => {
    if (raf.current !== null) cancelAnimationFrame(raf.current)
    if (timer.current !== null) clearTimeout(timer.current)
    raf.current = null
    timer.current = null
  }, [])

  useEffect(() => () => stopClocks(), [stopClocks])

  useEffect(() => {
    setState((s) => (s.phase === 'downloading' || s.phase === 'merging' ? s : { ...s, totalBytes }))
  }, [totalBytes])

  const reset = useCallback(() => {
    stopClocks()
    setState(initial(totalBytes))
  }, [stopClocks, totalBytes])

  const paste = useCallback(() => {
    stopClocks()
    setState({ ...initial(totalBytes), phase: 'fetching', url: sample.url })
    timer.current = window.setTimeout(() => setState((s) => ({ ...s, phase: 'ready' })), FETCH_MS)
  }, [sample.url, stopClocks, totalBytes])

  const start = useCallback(() => {
    stopClocks()
    const t0 = performance.now()
    const rnd = noise.current
    let smooth = 0.6
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / DEMO_DOWNLOAD_MS)
      // Gerçekçi dalgalanma: düşük geçiren filtreli gürültü, başta TCP yavaş başlangıcı.
      smooth = smooth * 0.92 + (0.55 + rnd() * 0.9) * 0.08
      const ramp = Math.min(1, p / 0.08)
      const speed = SHOWN_BASE_BPS * smooth * (0.35 + 0.65 * ramp)
      setState((s) => ({
        ...s,
        phase: p >= 1 ? 'merging' : 'downloading',
        progress: p,
        bytesDone: Math.round(totalBytes * p),
        speedBps: p >= 1 ? 0 : speed,
        etaSec: (totalBytes * (1 - p)) / speed,
        speedHistory: [...s.speedHistory.slice(-59), speed],
      }))
      if (p < 1) raf.current = requestAnimationFrame(tick)
      else timer.current = window.setTimeout(() => setState((s) => ({ ...s, phase: 'done' })), MERGE_MS)
    }
    setState((s) => ({ ...s, phase: 'downloading', progress: 0, bytesDone: 0, speedHistory: [] }))
    raf.current = requestAnimationFrame(tick)
  }, [stopClocks, totalBytes])

  const cancel = useCallback(() => {
    stopClocks()
    setState((s) => ({ ...s, phase: 'ready', progress: 0, bytesDone: 0, speedBps: 0, speedHistory: [] }))
  }, [stopClocks])

  return { state, paste, start, cancel, reset }
}

function initial(totalBytes: number): SimState {
  return { phase: 'empty', url: '', progress: 0, bytesDone: 0, totalBytes, speedBps: 0, etaSec: 0, speedHistory: [] }
}

export type OptionId = 'subs' | 'sponsor' | 'loudnorm' | 'cover'

export const OPTIONS: { id: OptionId; label: string; hint: string }[] = [
  { id: 'subs', label: 'Altyazı', hint: 'Türkçe ve İngilizce, varsa' },
  { id: 'sponsor', label: 'SponsorBlock', hint: 'Tanıtım bölümlerini kes' },
  { id: 'loudnorm', label: 'Ses eşitle', hint: '−16 LUFS' },
  { id: 'cover', label: 'Kapağı göm', hint: 'Dosyanın içine' },
]

export function useOptions() {
  const [on, setOn] = useState<Record<OptionId, boolean>>({ subs: false, sponsor: true, loudnorm: false, cover: true })
  const toggle = useCallback((id: OptionId) => setOn((o) => ({ ...o, [id]: !o[id] })), [])
  return { on, toggle }
}
