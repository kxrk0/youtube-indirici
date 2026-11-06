import { useEffect, useState } from 'react'
import { MotionConfig } from 'motion/react'
import { SAMPLES } from './sim'
import { Tape } from './directions/Tape'
import { Lightbox } from './directions/Lightbox'
import { Ambient } from './directions/Ambient'
import './chrome.css'

/** Mock pencere boyutu: uygulamanın varsayılan açılış boyutu (main_window.py: max(cfg, 1100x720)). */
const WINDOW_W = 1100
const WINDOW_H = 720
const CHROME_H = 132

const DIRECTIONS = [
  {
    id: 'tape',
    name: 'Bant',
    pov: 'İndirmek kayıt almaktır. Uygulama bir kaset deck’i: bağlantı yuvaya girer, makaralar döner.',
    qt: 'Qt’de en kolayı. Makara, VU iğnesi ve nokta-matris ekran QPainter ile çizilir; bulanıklık yok.',
    Component: Tape,
  },
  {
    id: 'lightbox',
    name: 'Işık masası',
    pov: 'Video bir film şerididir. Kesme, kalite ve ilerleme aynı şerit üstünde, kareler banyo edilir gibi belirir.',
    qt: 'Kolay-orta. Kareler yt-dlp storyboard (sb0) formatından gelir; negatif→pozitif geçişi QPainter compositing.',
    Component: Lightbox,
  },
  {
    id: 'ambient',
    name: 'Ortam',
    pov: 'Arayüz indirdiğin şeyin rengine bürünür. İlerleme çubuğu videonun “en çok tekrar oynatılan” eğrisidir.',
    qt: 'Orta. Renk çıkarımı ve eğri kolay; arka plan bulanıklığı önceden bulanıklaştırılmış QPixmap ile taklit edilir.',
    Component: Ambient,
  },
] as const

type DirectionId = (typeof DIRECTIONS)[number]['id']

function useFitScale() {
  const [scale, setScale] = useState(1)
  useEffect(() => {
    const fit = () => {
      const s = Math.min((window.innerWidth - 32) / WINDOW_W, (window.innerHeight - CHROME_H - 24) / WINDOW_H, 1)
      setScale(Math.max(0.4, s))
    }
    fit()
    window.addEventListener('resize', fit)
    return () => window.removeEventListener('resize', fit)
  }, [])
  return scale
}

export default function App() {
  const [dirId, setDirId] = useState<DirectionId>(() => (localStorage.getItem('dir') as DirectionId) || 'tape')
  const [sampleId, setSampleId] = useState(SAMPLES[0].id)
  const [runKey, setRunKey] = useState(0)
  const scale = useFitScale()
  const dir = DIRECTIONS.find((d) => d.id === dirId) ?? DIRECTIONS[0]
  const sample = SAMPLES.find((s) => s.id === sampleId) ?? SAMPLES[0]

  useEffect(() => {
    localStorage.setItem('dir', dirId)
  }, [dirId])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return
      const i = Number(e.key) - 1
      if (i >= 0 && i < DIRECTIONS.length) setDirId(DIRECTIONS[i].id)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const { Component } = dir

  return (
    <MotionConfig reducedMotion="user">
      <div className="chrome">
        <header className="chrome-bar">
          <nav className="chrome-dirs" aria-label="Tasarım yönü">
            {DIRECTIONS.map((d, i) => (
              <button key={d.id} className="chrome-dir" aria-pressed={d.id === dirId} onClick={() => setDirId(d.id)}>
                <kbd>{i + 1}</kbd>
                {d.name}
              </button>
            ))}
          </nav>
          <div className="chrome-notes">
            <p>{dir.pov}</p>
            <p className="chrome-qt">{dir.qt}</p>
          </div>
          <div className="chrome-controls">
            <label>
              Örnek bağlantı
              <select value={sampleId} onChange={(e) => { setSampleId(e.target.value); setRunKey((k) => k + 1) }}>
                {SAMPLES.map((s) => (
                  <option key={s.id} value={s.id}>{s.title}</option>
                ))}
              </select>
            </label>
            <button className="chrome-restart" onClick={() => setRunKey((k) => k + 1)}>Baştan oynat</button>
          </div>
        </header>
        <main className="chrome-stage" style={{ height: WINDOW_H * scale }}>
          <div className="chrome-window" style={{ width: WINDOW_W, height: WINDOW_H, transform: `scale(${scale})` }}>
            <Component key={`${dir.id}-${sample.id}-${runKey}`} sample={sample} />
          </div>
        </main>
      </div>
    </MotionConfig>
  )
}
