import { useEffect, useReducer, useRef, useState } from 'react'
import { AnimatePresence, MotionConfig, motion } from 'motion/react'
import { Maximize2, Square, X } from 'lucide-react'
import { api, onBridgeEvent, waitForBridge } from '../bridge'
import { NEUTRAL, prepareCover, type Palette } from '../ortam/color'
import { jobsReducer, newJob, type Job } from '../store'
import { Background } from '../components/Shell'
import { jobStatus } from './Queue'

/** Biten satırın listeden düşmeden önce görünür kaldığı süre. */
const DONE_LINGER_MS = 2500
const ROW_SPRING = { type: 'spring', stiffness: 380, damping: 32 } as const

const isActive = (j: Job) => j.phase === 'queued' || j.phase === 'downloading' || j.phase === 'merging'

/**
 * Her zaman üstte duran küçük indirme penceresi (src/web/app.py, #mini). Ana pencereyle aynı
 * Python olaylarını dinler; açıldığında süren işleri active_jobs() ile alır.
 */
export function Mini() {
  const [jobs, dispatch] = useReducer(jobsReducer, [])
  const [ready, setReady] = useState(false)
  const [palette, setPalette] = useState<Palette>(NEUTRAL)
  const [cover, setCover] = useState<string | null>(null)
  const images = useRef(new Map<number, string>())
  const [, bumpImages] = useReducer((n: number) => n + 1, 0)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    waitForBridge().then((a) => a.active_jobs()).then((list) => {
      for (const { added, last } of list) {
        dispatch({ type: 'add', job: newJob(added.job, added.url, added.title, added.thumbnail, 'background') })
        if (last) dispatch({ type: 'event', e: last })
      }
      setReady(true)
    }).catch((err) => console.error('Süren indirmeler alınamadı', err))
  }, [])

  useEffect(() => onBridgeEvent((e) => {
    if (e.type === 'added') dispatch({ type: 'add', job: newJob(e.job, e.url, e.title, e.thumbnail, 'background') })
    if (e.type === 'progress' || e.type === 'done') dispatch({ type: 'event', e })
    if (e.type === 'done') window.setTimeout(() => dispatch({ type: 'remove', id: e.job }), DONE_LINGER_MS)
  }), [])

  // Kapaklar data URL olarak gelir (palet için piksel okumak gerekiyor); her iş için bir kez.
  useEffect(() => {
    for (const job of jobs) {
      if (!job.thumbnail || images.current.has(job.id)) continue
      images.current.set(job.id, '')
      api().thumbnail(job.thumbnail).then((src) => {
        if (!src) return
        images.current.set(job.id, src)
        bumpImages()
      }).catch((err) => console.error(`Kapak alınamadı: ${job.thumbnail}`, err))
    }
  }, [jobs])

  // Ortam: renkler en üstteki işin kapağından gelir.
  const leadImage = jobs.length ? images.current.get(jobs[0].id) || null : null
  useEffect(() => {
    if (!leadImage) return
    let alive = true
    prepareCover(leadImage).then((c) => { if (alive) { setPalette(c.palette); setCover(c.src) } })
      .catch((err) => console.error('Mini pencere paleti çıkarılamadı', err))
    return () => { alive = false }
  }, [leadImage])

  // Pencere yüksekliği içeriğe uyar; alt kenar ekranda sabit kalır.
  useEffect(() => {
    const el = root.current
    if (!el) return
    const observer = new ResizeObserver(() => {
      api().fit_mini(Math.ceil(el.scrollHeight)).catch((err) => console.error('Mini pencere boyutlanamadı', err))
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [ready])

  const active = jobs.filter(isActive).length
  const vars = { '--deep': palette.deep, '--mid': palette.mid, '--accent': palette.accent, '--on-accent': palette.onAccent } as React.CSSProperties

  return (
    <MotionConfig reducedMotion="user">
      <div className="am am-mini" style={vars}>
        <Background cover={cover} busy={active > 0} />
        <div ref={root} className="am-mini-body">
          <header className="am-mini-head pywebview-drag-region">
            <strong className="pywebview-drag-region">{active ? `${active} indiriliyor` : 'İndirme yok'}</strong>
            <button className="am-icon-btn" aria-label="Uygulamayı aç" title="Uygulamayı aç" onClick={() => api().show_main('queue')}>
              <Maximize2 size={14} strokeWidth={1.9} />
            </button>
            <button className="am-icon-btn" aria-label="Gizle" title="Gizle (Ctrl+M)" onClick={() => api().hide_mini()}>
              <X size={15} strokeWidth={1.9} />
            </button>
          </header>
          {ready && jobs.length === 0 && <p className="am-mini-empty">Süren indirme yok. Ana pencerede bir bağlantı yapıştır.</p>}
          <ul className="am-mini-list">
            <AnimatePresence initial={false}>
              {jobs.map((job) => {
                const image = images.current.get(job.id)
                return (
                  <motion.li key={job.id} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, x: 24 }}
                    transition={ROW_SPRING}>
                    {image ? <img src={image} alt="" /> : <div className="am-job-ph" />}
                    <div style={{ minWidth: 0 }}>
                      <strong title={job.title}>{job.title}</strong>
                      <div className={`am-job-status${job.phase === 'error' ? ' am-error-text' : ''}`}>{jobStatus(job)}</div>
                      {isActive(job) && (
                        <div className="am-job-bar" data-indeterminate={job.phase !== 'downloading'}>
                          <motion.span animate={{ scaleX: job.phase === 'downloading' ? job.fraction : 1 }} transition={{ duration: 0.25, ease: 'linear' }}
                            style={job.phase === 'downloading' ? { width: '100%' } : undefined} />
                        </div>
                      )}
                    </div>
                    {isActive(job) && (
                      <button className="am-icon-btn" aria-label="Durdur" title="Durdur" onClick={() => api().cancel(job.id)}>
                        <Square size={13} strokeWidth={2} />
                      </button>
                    )}
                  </motion.li>
                )
              })}
            </AnimatePresence>
          </ul>
        </div>
      </div>
    </MotionConfig>
  )
}
