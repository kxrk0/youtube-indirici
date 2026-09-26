import { AnimatePresence, motion } from 'motion/react'
import { Check, Download, RotateCcw, Square } from 'lucide-react'
import { SPRING_LAYOUT } from './Controls'

export type MorphMode = 'disabled' | 'idle' | 'progress' | 'merging' | 'done' | 'error'

const RING_R = 25
const RING_C = 2 * Math.PI * RING_R
/** Belirsiz halkada görünen yay: çevrenin %28'i (mock: dashoffset %72). */
const SPIN_VISIBLE = 0.28

/**
 * Biçim değiştiren ana düğme (mock: MorphButton). Boşta vurgu hapı, indirirken yüzdeli halka,
 * işlenirken dönen halka, bitince beyaz "Klasörde göster" hapı.
 */
export function MorphButton({ mode, progress, label, detail, onClick }: {
  mode: MorphMode
  progress: number
  label: string
  detail?: string
  onClick: () => void
}) {
  const round = mode === 'progress' || mode === 'merging'
  const pct = Math.floor(progress * 100)
  return (
    <motion.button
      layout
      className="am-morph"
      data-mode={mode}
      disabled={mode === 'disabled'}
      onClick={onClick}
      style={{ borderRadius: 999 }}
      transition={SPRING_LAYOUT}
      aria-label={mode === 'progress' ? `İndiriliyor, %${pct}. Durdurmak için tıkla` : undefined}
    >
      <AnimatePresence mode="popLayout" initial={false}>
        {round ? (
          <motion.span key="ring" className="am-ring" initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.6 }}>
            <svg viewBox="0 0 60 60" className={mode === 'merging' ? 'am-ring-spin' : undefined}>
              <circle cx="30" cy="30" r={RING_R} className="am-ring-track" />
              <circle cx="30" cy="30" r={RING_R} className="am-ring-fill" strokeDasharray={RING_C}
                strokeDashoffset={mode === 'merging' ? RING_C * (1 - SPIN_VISIBLE) : RING_C * (1 - progress)} />
            </svg>
            <span className="am-ring-label">{mode === 'merging' ? '' : pct}</span>
            <Square className="am-ring-stop" size={14} fill="currentColor" strokeWidth={0} />
          </motion.span>
        ) : mode === 'done' ? (
          <motion.span key="done" className="am-morph-label" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <Check size={18} strokeWidth={2.4} /> Klasörde göster
          </motion.span>
        ) : (
          <motion.span key={`go-${mode}`} className="am-morph-label" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            {mode === 'error' ? <RotateCcw size={18} strokeWidth={2.2} /> : <Download size={18} strokeWidth={2.2} />}
            {label} {detail ? <em>{detail}</em> : null}
          </motion.span>
        )}
      </AnimatePresence>
    </motion.button>
  )
}
