import { useEffect, useState } from 'react'

export type Palette = {
  /** Arka planın en koyu tonu (OKLCH benzeri: düşük açıklık, kaynak tonunda). */
  deep: string
  /** Orta katman, kartlar ve yüzeyler. */
  mid: string
  /** Kapaktaki en canlı renk; vurgu. Gri kapaklarda nötr kalır. */
  accent: string
  /** Vurgunun üstünde okunacak metin rengi. */
  onAccent: string
  hue: number
  saturated: boolean
}

const NEUTRAL: Palette = { deep: 'hsl(220 8% 7%)', mid: 'hsl(220 6% 14%)', accent: 'hsl(0 0% 92%)', onAccent: 'hsl(0 0% 8%)', hue: 220, saturated: false }

const SAMPLE_EDGE_PX = 40
/** Bu doygunluğun altındaki kapaklar "renksiz" sayılır; vurgu beyaza düşer. */
const MIN_ACCENT_SATURATION = 0.18

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

/**
 * Kapağı 40x40'a indirir, 12 ton kovasına dağıtır, doygunluk*canlılık ağırlıklı en baskın tonu seçer.
 * Komşu kovalar yarım ağırlıkla sayılır: turuncu-sarı gibi sınırda kalan tonlar bölünüp kaybolmasın.
 */
export function extractPalette(img: HTMLImageElement): Palette {
  const c = document.createElement('canvas')
  c.width = c.height = SAMPLE_EDGE_PX
  const ctx = c.getContext('2d', { willReadFrequently: true })
  if (!ctx) throw new Error('extractPalette: 2d canvas bağlamı alınamadı')
  ctx.drawImage(img, 0, 0, SAMPLE_EDGE_PX, SAMPLE_EDGE_PX)
  const { data } = ctx.getImageData(0, 0, SAMPLE_EDGE_PX, SAMPLE_EDGE_PX)
  const buckets = Array.from({ length: 12 }, () => ({ w: 0, s: 0, l: 0 }))
  let totalSat = 0
  for (let i = 0; i < data.length; i += 4) {
    const [h, s, l] = rgbToHsl(data[i], data[i + 1], data[i + 2])
    const vivid = s * (1 - Math.abs(l - 0.5) * 2)
    totalSat += vivid
    const b = buckets[Math.floor(h / 30) % 12]
    b.w += vivid
    b.s += s * vivid
    b.l += l * vivid
  }
  const score = (i: number) => buckets[i].w + 0.5 * (buckets[(i + 11) % 12].w + buckets[(i + 1) % 12].w)
  const bestIndex = buckets.reduce((a, _, i) => (score(i) > score(a) ? i : a), 0)
  const best = { b: buckets[bestIndex], i: bestIndex }
  const avgVivid = totalSat / (data.length / 4)
  if (best.b.w === 0 || avgVivid < 0.04) return NEUTRAL
  const hue = best.i * 30 + 15
  const sat = best.b.s / best.b.w
  if (sat < MIN_ACCENT_SATURATION) return { ...NEUTRAL, hue }
  const s = Math.round(Math.min(0.9, sat) * 100)
  return {
    deep: `hsl(${hue} ${Math.round(s * 0.45)}% 7%)`,
    mid: `hsl(${hue} ${Math.round(s * 0.35)}% 15%)`,
    accent: `hsl(${hue} ${Math.max(60, s)}% 62%)`,
    onAccent: `hsl(${hue} 40% 8%)`,
    hue,
    saturated: true,
  }
}

export function usePalette(src: string): Palette {
  const [palette, setPalette] = useState<Palette>(NEUTRAL)
  useEffect(() => {
    let alive = true
    const img = new Image()
    img.onload = () => alive && setPalette(extractPalette(img))
    img.onerror = () => {
      throw new Error(`usePalette: kapak yüklenemedi: ${src}`)
    }
    img.src = src
    return () => {
      alive = false
    }
  }, [src])
  return palette
}
