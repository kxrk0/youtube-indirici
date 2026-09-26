/**
 * Kapaktan palet (design-mocks/src/color.ts ile aynı algoritma) ve siyah şerit kırpma.
 * Kapak Python'dan data URL olarak gelir; aynı kaynaktan sayıldığı için tuval pikselleri okunabilir.
 */

export type Palette = {
  deep: string
  mid: string
  accent: string
  onAccent: string
  /** Başlık çubuğu için #rrggbb (Windows DWM hsl kabul etmiyor). */
  deepHex: string
  saturated: boolean
}

export const NEUTRAL: Palette = {
  deep: 'hsl(220 8% 9%)',
  mid: 'hsl(220 6% 15%)',
  accent: 'hsl(0 0% 92%)',
  onAccent: 'hsl(0 0% 8%)',
  deepHex: hslToHex(220, 8, 9),
  saturated: false,
}

const SAMPLE_EDGE_PX = 40
const HUE_BUCKETS = 12
/** Ortalama canlılık bunun altındaysa kapak gri sayılır (siyah-beyaz klip kapakları). */
const MIN_AVERAGE_VIVIDNESS = 0.04
/** Baskın tonun doygunluğu bunun altındaysa vurgu beyaza düşer. */
const MIN_ACCENT_SATURATION = 0.18
/** Siyah şerit: kenar sütunundaki en açık piksel bunun altındaysa şerit sayılır (0–255 açıklık). */
const LETTERBOX_MAX_LIGHTNESS = 28
/** Kırpma sonrası görüntü en az bu oranda kalmalı; yoksa koyu bir sahne yanlışlıkla kesilir. */
const LETTERBOX_MIN_KEEP = 0.5
const LETTERBOX_PROBE_WIDTH = 256

function rgbToHsl(r: number, g: number, b: number): [number, number, number] {
  r /= 255
  g /= 255
  b /= 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const l = (max + min) / 2
  if (max === min) return [0, 0, l]
  const d = max - min
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
  let h = 0
  if (max === r) h = (g - b) / d + (g < b ? 6 : 0)
  else if (max === g) h = (b - r) / d + 2
  else h = (r - g) / d + 4
  return [h * 60, s, l]
}

function hslToHex(h: number, s: number, l: number): string {
  s /= 100
  l /= 100
  const k = (n: number) => (n + h / 30) % 12
  const a = s * Math.min(l, 1 - l)
  const f = (n: number) => Math.round(255 * (l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)))))
  return `#${[f(0), f(8), f(4)].map((v) => v.toString(16).padStart(2, '0')).join('')}`
}

export function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error(`Kapak çözümlenemedi (${src.slice(0, 40)}…)`))
    img.src = src
  })
}

export function extractPalette(img: HTMLImageElement | HTMLCanvasElement): Palette {
  const c = document.createElement('canvas')
  c.width = c.height = SAMPLE_EDGE_PX
  const ctx = c.getContext('2d', { willReadFrequently: true })
  if (!ctx) throw new Error('extractPalette: 2d tuval bağlamı alınamadı')
  ctx.drawImage(img, 0, 0, SAMPLE_EDGE_PX, SAMPLE_EDGE_PX)
  const { data } = ctx.getImageData(0, 0, SAMPLE_EDGE_PX, SAMPLE_EDGE_PX)
  const weights = new Array(HUE_BUCKETS).fill(0)
  const satSums = new Array(HUE_BUCKETS).fill(0)
  let totalVivid = 0
  for (let i = 0; i < data.length; i += 4) {
    const [h, s, l] = rgbToHsl(data[i], data[i + 1], data[i + 2])
    const vivid = s * (1 - Math.abs(l - 0.5) * 2)
    totalVivid += vivid
    const b = Math.floor(h / 30) % HUE_BUCKETS
    weights[b] += vivid
    satSums[b] += s * vivid
  }
  // Komşu kovalar yarım ağırlıkla: turuncu-sarı gibi sınırda kalan tonlar bölünüp kaybolmasın.
  const score = (i: number) => weights[i] + 0.5 * (weights[(i + HUE_BUCKETS - 1) % HUE_BUCKETS] + weights[(i + 1) % HUE_BUCKETS])
  let best = 0
  for (let i = 1; i < HUE_BUCKETS; i++) if (score(i) > score(best)) best = i
  const averageVivid = totalVivid / (data.length / 4)
  if (weights[best] === 0 || averageVivid < MIN_AVERAGE_VIVIDNESS) return NEUTRAL
  const sat = satSums[best] / weights[best]
  if (sat < MIN_ACCENT_SATURATION) return NEUTRAL
  const hue = best * 30 + 15
  const s = Math.round(Math.min(0.9, sat) * 100)
  const deepS = Math.round(s * 0.45)
  return {
    deep: `hsl(${hue} ${deepS}% 7%)`,
    mid: `hsl(${hue} ${Math.round(s * 0.35)}% 15%)`,
    accent: `hsl(${hue} ${Math.max(60, s)}% 62%)`,
    onAccent: `hsl(${hue} 40% 8%)`,
    deepHex: hslToHex(hue, deepS, 7),
    saturated: true,
  }
}

/** YouTube kapaklarındaki siyah şeritleri keser (4:3 video 16:9 kapakta). Kesilecek bir şey yoksa kaynağı döndürür. */
export function trimLetterbox(img: HTMLImageElement): { canvas: HTMLCanvasElement; width: number; height: number } | null {
  const scale = Math.min(1, LETTERBOX_PROBE_WIDTH / img.naturalWidth)
  const w = Math.max(1, Math.round(img.naturalWidth * scale))
  const h = Math.max(1, Math.round(img.naturalHeight * scale))
  const probe = document.createElement('canvas')
  probe.width = w
  probe.height = h
  const ctx = probe.getContext('2d', { willReadFrequently: true })
  if (!ctx) throw new Error('trimLetterbox: 2d tuval bağlamı alınamadı')
  ctx.drawImage(img, 0, 0, w, h)
  const { data } = ctx.getImageData(0, 0, w, h)
  const light = (x: number, y: number) => {
    const i = (y * w + x) * 4
    return (Math.max(data[i], data[i + 1], data[i + 2]) + Math.min(data[i], data[i + 1], data[i + 2])) / 2
  }
  const darkCol = (x: number) => { for (let y = 0; y < h; y += 2) if (light(x, y) >= LETTERBOX_MAX_LIGHTNESS) return false; return true }
  const darkRow = (y: number) => { for (let x = 0; x < w; x += 2) if (light(x, y) >= LETTERBOX_MAX_LIGHTNESS) return false; return true }
  let left = 0
  while (left < w / 2 && darkCol(left)) left++
  let right = 0
  while (right < w / 2 && darkCol(w - 1 - right)) right++
  let top = 0
  while (top < h / 2 && darkRow(top)) top++
  let bottom = 0
  while (bottom < h / 2 && darkRow(h - 1 - bottom)) bottom++
  const keepW = w - left - right
  const keepH = h - top - bottom
  if ((left + right + top + bottom === 0) || keepW < w * LETTERBOX_MIN_KEEP || keepH < h * LETTERBOX_MIN_KEEP) return null
  // Küçük kopyadaki kenarları asıl boyuta taşı; yuvarlama artığı için bir piksel içeri al.
  const inv = 1 / scale
  const sx = left ? Math.round((left + 1) * inv) : 0
  const sy = top ? Math.round((top + 1) * inv) : 0
  const ex = img.naturalWidth - (right ? Math.round((right + 1) * inv) : 0)
  const ey = img.naturalHeight - (bottom ? Math.round((bottom + 1) * inv) : 0)
  const out = document.createElement('canvas')
  out.width = ex - sx
  out.height = ey - sy
  const octx = out.getContext('2d')
  if (!octx) throw new Error('trimLetterbox: çıktı tuvali alınamadı')
  octx.drawImage(img, sx, sy, out.width, out.height, 0, 0, out.width, out.height)
  return { canvas: out, width: out.width, height: out.height }
}

export type PreparedCover = { src: string; width: number; height: number; palette: Palette }

/** data URL → kırpılmış kapak + palet. */
export async function prepareCover(dataUrl: string): Promise<PreparedCover> {
  const img = await loadImage(dataUrl)
  const trimmed = trimLetterbox(img)
  if (trimmed) {
    return { src: trimmed.canvas.toDataURL('image/jpeg', 0.92), width: trimmed.width, height: trimmed.height, palette: extractPalette(trimmed.canvas) }
  }
  return { src: dataUrl, width: img.naturalWidth, height: img.naturalHeight, palette: extractPalette(img) }
}
