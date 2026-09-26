import { useState } from 'react'
import { AnimatePresence, motion } from 'motion/react'
import type { LucideIcon } from 'lucide-react'
import { api, type RecentItem, type UpdateOffer } from '../bridge'
import type { Toast } from '../store'
import { MENU_TRANSITION } from './Controls'

/** Tüm pencereyi kaplayan bulanık kapak + koyulaşan örtü + gren (mock: .am-bg). */
export function Background({ cover, busy }: { cover: string | null; busy: boolean }) {
  return (
    <div className="am-bg" aria-hidden="true" data-busy={busy}>
      <AnimatePresence>
        {cover && (
          <motion.img key={cover} src={cover} alt="" initial={{ opacity: 0 }} animate={{ opacity: 0.55 }} exit={{ opacity: 0 }}
            transition={{ duration: 1.2 }} />
        )}
      </AnimatePresence>
      <div className="am-grain" />
    </div>
  )
}

export type RailItem = { id: string; label: string; Icon: LucideIcon; badge?: number; bottom?: boolean }

export function Rail({ items, current, onSelect }: { items: RailItem[]; current: string; onSelect: (id: string) => void }) {
  return (
    <nav className="am-rail" aria-label="Bölümler">
      {items.map(({ id, label, Icon, badge, bottom }) => (
        <button key={id} className={`am-rail-btn${bottom ? ' am-rail-bottom' : ''}`} aria-current={id === current ? 'page' : undefined}
          aria-label={label} title={label} onClick={() => onSelect(id)}>
          <Icon size={20} strokeWidth={1.7} />
          {badge ? <span className="am-rail-badge">{badge > 9 ? '9+' : badge}</span> : null}
        </button>
      ))}
    </nav>
  )
}

function cover(item: RecentItem): string | undefined {
  return item.image ?? item.thumbnail ?? undefined
}

/** Son indirilenler yığını + açılır liste (mock: .am-stack). */
export function RecentStack({ items, onShowAll }: { items: RecentItem[]; onShowAll?: () => void }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="am-stack-wrap">
      <button className="am-stack" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-label={`Son indirilenler, ${items.length}`}>
        {items.slice(0, 3).map((r, i) => (
          <motion.img key={r.key} layoutId={`am-cover-${r.url}`} src={cover(r)} alt="" style={{ zIndex: 3 - i, background: 'var(--glass)' }}
            onError={(e) => { e.currentTarget.removeAttribute('src') }}
            transition={{ type: 'spring', stiffness: 170, damping: 22 }} />
        ))}
        <span>{items.length}</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.ul className="am-stack-list" initial={{ opacity: 0, y: -8, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.97 }} transition={MENU_TRANSITION} onMouseLeave={() => setOpen(false)}>
            {items.length === 0 && <li><div><span>Henüz indirme yok.</span></div></li>}
            {items.slice(0, 8).map((r) => (
              <li key={r.key} data-state={r.failed ? 'error' : 'done'} role="button" tabIndex={0}
                onClick={() => { if (r.file) api().reveal(r.file); setOpen(false) }}>
                <img src={cover(r)} alt="" onError={(e) => { e.currentTarget.removeAttribute('src') }} />
                <div>
                  <strong>{r.title}</strong>
                  <span>{r.note}</span>
                </div>
              </li>
            ))}
            {onShowAll && (
              <li style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <button className="am-text-btn" onClick={() => { onShowAll(); setOpen(false) }}>Tüm indirilenler</button>
              </li>
            )}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  )
}

/** Alt ortada kısa bildirimler (dışa aktarıldı, silindi, hata). */
export function Toasts({ items }: { items: Toast[] }) {
  return (
    <div className="am-toasts" aria-live="polite">
      <AnimatePresence initial={false}>
        {items.map((t) => (
          <motion.div key={t.id} className="am-toast" data-tone={t.tone} layout
            initial={{ opacity: 0, y: 16, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8 }}
            transition={{ type: 'spring', stiffness: 380, damping: 32 }}>
            {t.text}
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

/**
 * Yeni sürüm bandı: açılışta denetlenir, "Güncelle" indirip kurar (uygulama kapanıp yeniden açılır).
 * İndirme yüzdesi Python'dan 'update' olaylarıyla gelir.
 */
export function UpdateBar({ offer, percent, installing, error, onInstall, onDismiss }: {
  offer: UpdateOffer
  percent: number | null
  installing: boolean
  error: string | null
  onInstall: () => void
  onDismiss: () => void
}) {
  return (
    <motion.div className="am-update" role="status" initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -12 }}
      transition={{ type: 'spring', stiffness: 380, damping: 32 }}>
      <div style={{ minWidth: 0 }}>
        <strong>Sürüm {offer.version} hazır</strong>
        <span className={error ? 'am-error-text' : undefined}>
          {error ?? (installing ? `İndiriliyor${percent != null ? `, %${percent}` : ''}. Bitince uygulama yeniden açılacak.` : offer.notes || `Şu an ${offer.current} kullanıyorsun.`)}
        </span>
      </div>
      {!installing && <button className="am-text-btn" onClick={onDismiss}>Sonra</button>}
      <button className="am-primary" onClick={onInstall} disabled={installing}>{error ? 'Tekrar dene' : 'Güncelle'}</button>
    </motion.div>
  )
}
