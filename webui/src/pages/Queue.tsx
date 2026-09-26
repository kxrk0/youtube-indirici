import { AnimatePresence, motion } from 'motion/react'
import { FolderOpen, Play, Square, X } from 'lucide-react'
import { api } from '../bridge'
import * as fmt from '../ortam/format'
import { useStore, type Job } from '../store'

export function jobStatus(job: Job): string {
  switch (job.phase) {
    case 'queued': return 'Sırada, başka indirmelerin bitmesi bekleniyor'
    case 'downloading': {
      const parts = [job.total ? `${fmt.size(job.done)} / ${fmt.size(job.total)}` : fmt.size(job.done), fmt.speed(job.speed)]
      if (job.eta) parts.push(`${fmt.duration(job.eta)} kaldı`)
      return parts.join(', ')
    }
    case 'merging': return job.statusText
    case 'done': return `${fmt.size(job.size)}, ${fmt.folderName(job.file ?? '')} klasöründe`
    case 'error': return job.error ?? 'İndirme başarısız oldu.'
    case 'cancelled': return 'İptal edildi'
  }
}

export function Queue() {
  const { jobs, cancel, dismiss } = useStore()
  return (
    <div className="am-page-pad">
      <h1 className="am-page-title">İndirilenler</h1>
      {jobs.length === 0 && (
        <p className="am-empty-note">Bu oturumda henüz indirme yok. Ana sayfaya bir bağlantı yapıştır.</p>
      )}
      <ul className="am-jobs">
        <AnimatePresence initial={false}>
          {jobs.map((job) => {
            const active = job.phase === 'queued' || job.phase === 'downloading' || job.phase === 'merging'
            return (
              <motion.li key={job.id} className="am-job" layout initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: 24 }} transition={{ type: 'spring', stiffness: 380, damping: 32 }}>
                {job.image || job.thumbnail ? <img src={job.image ?? job.thumbnail} alt="" /> : <div className="am-job-ph" />}
                <div style={{ minWidth: 0 }}>
                  <strong title={job.title}>{job.title}</strong>
                  <div className={`am-job-status${job.phase === 'error' ? ' am-error-text' : ''}`}>{jobStatus(job)}</div>
                  {active && (
                    <div className="am-job-bar" data-indeterminate={job.phase !== 'downloading'}>
                      <motion.span animate={{ scaleX: job.phase === 'downloading' ? job.fraction : 1 }} transition={{ duration: 0.25, ease: 'linear' }}
                        style={job.phase === 'downloading' ? { width: '100%' } : undefined} />
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 2 }}>
                  {active && <button className="am-icon-btn" aria-label="Durdur" title="Durdur" onClick={() => cancel(job.id)}><Square size={15} strokeWidth={2} /></button>}
                  {job.phase === 'done' && job.file && (
                    <>
                      <button className="am-icon-btn" aria-label="Aç" title="Aç" onClick={() => api().open_file(job.file!)}><Play size={16} strokeWidth={1.8} /></button>
                      <button className="am-icon-btn" aria-label="Klasörde göster" title="Klasörde göster" onClick={() => api().reveal(job.file!)}><FolderOpen size={16} strokeWidth={1.8} /></button>
                    </>
                  )}
                  {!active && <button className="am-icon-btn" aria-label="Listeden kaldır" title="Listeden kaldır" onClick={() => dismiss(job.id)}><X size={16} strokeWidth={1.8} /></button>}
                </div>
              </motion.li>
            )
          })}
        </AnimatePresence>
      </ul>
    </div>
  )
}
