/** Türkçe biçimler: ondalık virgül, 1024 tabanı (Gezgin ile aynı), baştaki sıfırsız süre ("3:12"). */

const UNITS = ['B', 'KB', 'MB', 'GB', 'TB']
const ONE = new Intl.NumberFormat('tr-TR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const TWO = new Intl.NumberFormat('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

export function size(n: number | null | undefined): string {
  if (n == null || n < 0) return ''
  let v = n
  let u = 0
  while (v >= 1024 && u < UNITS.length - 1) {
    v /= 1024
    u++
  }
  if (u === 0) return `${Math.round(v)} B`
  return `${(u >= 3 ? TWO : ONE).format(v)} ${UNITS[u]}`
}

export function speed(bps: number | null | undefined): string {
  return `${size(bps ?? 0)}/s`
}

export function duration(sec: number | null | undefined): string {
  if (sec == null || sec < 0 || !Number.isFinite(sec)) return '–:––'
  const s = Math.round(sec)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const r = s % 60
  return h ? `${h}:${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}` : `${m}:${String(r).padStart(2, '0')}`
}

export function folderName(path: string): string {
  const parts = path.replace(/[\\/]+$/, '').split(/[\\/]/)
  return parts[parts.length - 1] || path
}
