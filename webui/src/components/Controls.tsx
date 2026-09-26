import { useEffect, useRef, useState, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import { ChevronDown } from 'lucide-react'
import type { QualityOption } from '../bridge'

export const SPRING_SEGMENT = { type: 'spring', stiffness: 500, damping: 36 } as const
export const SPRING_SWITCH = { type: 'spring', stiffness: 600, damping: 32 } as const
export const SPRING_LAYOUT = { type: 'spring', stiffness: 380, damping: 32 } as const
export const MENU_TRANSITION = { duration: 0.18 } as const

export function Switch({ on, onToggle, label, hint, disabled, ariaLabel }: { on: boolean; onToggle: () => void; label: string; hint?: string; disabled?: boolean; ariaLabel?: string }) {
  return (
    <button role="switch" aria-checked={on} aria-label={ariaLabel} className="am-opt" onClick={onToggle} title={hint} disabled={disabled}>
      <span className="am-opt-track">
        <motion.span className="am-opt-knob" animate={{ x: on ? 14 : 0 }} transition={SPRING_SWITCH} />
      </span>
      {label}
    </button>
  )
}

/** Dışarı tıklayınca ya da Esc ile kapanan açılır menü. */
export function Popover({ open, onClose, children, style }: { open: boolean; onClose: () => void; children: ReactNode; style?: React.CSSProperties }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) onClose() }
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('mousedown', onDown)
    window.addEventListener('keydown', onKey)
    return () => { window.removeEventListener('mousedown', onDown); window.removeEventListener('keydown', onKey) }
  }, [open, onClose])
  return (
    <AnimatePresence>
      {open && (
        <motion.div ref={ref} className="am-menu" style={style} role="menu"
          initial={{ opacity: 0, y: -8, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -8, scale: 0.97 }}
          transition={MENU_TRANSITION}>
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  )
}

/**
 * Kalite ön ayarları | Diğer ▾ | Ses (mock: .am-seg). Ön ayar dışındaki seçenekler "Diğer" menüsünde;
 * seçilince o segmentin etiketi seçilenin kısa adı olur.
 */
export function QualityBar({ options, selected, audio, onSelect, onAudio, disabled, audioAllowed }: {
  options: QualityOption[]
  selected: number
  audio: boolean
  onSelect: (index: number) => void
  onAudio: () => void
  disabled?: boolean
  audioAllowed: boolean
}) {
  const [moreOpen, setMoreOpen] = useState(false)
  const extras = options.map((o, i) => ({ o, i })).filter(({ o }) => !o.preset)
  const current = options[selected]
  const extraChosen = !audio && current && !current.preset
  return (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <div className="am-seg" role="radiogroup" aria-label="Kalite" aria-disabled={disabled}>
        {options.map((o, i) => o.preset && (
          <button key={o.data} role="radio" aria-checked={!audio && i === selected} onClick={() => onSelect(i)} disabled={disabled} data-kind="video" title={o.label}>
            {!audio && i === selected && <motion.span layoutId="am-seg-ind" className="am-seg-ind" transition={SPRING_SEGMENT} />}
            <span className="am-seg-text">{o.short}</span>
          </button>
        ))}
        {extras.length > 0 && (
          <button role="radio" aria-checked={Boolean(extraChosen)} aria-haspopup="menu" onClick={() => setMoreOpen((v) => !v)} disabled={disabled} data-kind="video"
            title={extraChosen ? current.label : 'Tüm çözünürlükler ve codec’ler'}>
            {extraChosen && <motion.span layoutId="am-seg-ind" className="am-seg-ind" transition={SPRING_SEGMENT} />}
            <span className="am-seg-text" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              {extraChosen ? current.short : 'Diğer'} <ChevronDown size={13} strokeWidth={2.4} />
            </span>
          </button>
        )}
        {audioAllowed && (
          <button role="radio" aria-checked={audio} onClick={onAudio} disabled={disabled} data-kind="audio" title="Yalnız ses (MP3)">
            {audio && <motion.span layoutId="am-seg-ind" className="am-seg-ind" transition={SPRING_SEGMENT} />}
            <span className="am-seg-text">Ses</span>
          </button>
        )}
      </div>
      <Popover open={moreOpen} onClose={() => setMoreOpen(false)} style={{ left: 0, top: 50, maxHeight: 320, overflow: 'auto' }}>
        {extras.map(({ o, i }) => (
          <button key={o.data} role="menuitemradio" aria-checked={!audio && i === selected} onClick={() => { onSelect(i); setMoreOpen(false) }}>
            {o.label}
          </button>
        ))}
      </Popover>
    </div>
  )
}
