import { useMemo, useRef, useState, type ReactNode } from 'react'
import { motion } from 'motion/react'
import { FileText } from 'lucide-react'
import { Switch } from './Controls'

export function Sheet({ children, onClose }: { children: ReactNode; onClose: () => void }) {
  return (
    <motion.div className="am-scrim" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.18 }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }} onKeyDown={(e) => { if (e.key === 'Escape') onClose() }}>
      <motion.div className="am-sheet" role="dialog" aria-modal="true"
        initial={{ y: 40, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 40, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 380, damping: 32 }}>
        {children}
      </motion.div>
    </motion.div>
  )
}

/** Oynatma listesi / kanal: indirilecek videoları seç. */
export function ListSheet({ title, entries, onClose, onConfirm }: {
  title: string
  entries: { title: string; url: string }[]
  onClose: () => void
  onConfirm: (urls: string[], audio: boolean) => void
}) {
  const [picked, setPicked] = useState<Set<string>>(() => new Set(entries.map((e) => e.url)))
  const [audio, setAudio] = useState(false)
  const all = picked.size === entries.length
  return (
    <Sheet onClose={onClose}>
      <div>
        <h2>{title}</h2>
        <p>{entries.length} video bulundu. İndirmek istediklerini seç.</p>
      </div>
      <ul className="am-sheet-list">
        {entries.map((e) => (
          <li key={e.url}>
            <label>
              <input type="checkbox" checked={picked.has(e.url)} onChange={() => setPicked((p) => {
                const n = new Set(p)
                if (n.has(e.url)) n.delete(e.url)
                else n.add(e.url)
                return n
              })} />
              <span>{e.title}</span>
            </label>
          </li>
        ))}
      </ul>
      <div className="am-sheet-foot">
        <button className="am-text-btn" onClick={() => setPicked(all ? new Set() : new Set(entries.map((e) => e.url)))}>
          {all ? 'Seçimi kaldır' : 'Tümünü seç'}
        </button>
        <Switch on={audio} onToggle={() => setAudio((a) => !a)} label="Yalnız ses" />
        <span className="am-grow" />
        <button className="am-ghost" onClick={onClose}>Vazgeç</button>
        <button className="am-primary" disabled={picked.size === 0} onClick={() => onConfirm([...picked], audio)}>
          {picked.size} videoyu indir
        </button>
      </div>
    </Sheet>
  )
}

const URL_LINE = /^https?:\/\/\S+$/i

/** Toplu indirme: her satıra bir bağlantı ya da .txt içe aktar. */
export function BatchSheet({ initial, onClose, onConfirm }: { initial: string; onClose: () => void; onConfirm: (urls: string[]) => void }) {
  const [text, setText] = useState(initial)
  const [readError, setReadError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const urls = useMemo(() => [...new Set(text.split('\n').map((l) => l.trim()).filter((l) => URL_LINE.test(l)))], [text])
  return (
    <Sheet onClose={onClose}>
      <div>
        <h2>Toplu indirme</h2>
        <p>Her satıra bir bağlantı yaz ya da yapıştır. Geçersiz satırlar atlanır.</p>
      </div>
      <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={'https://youtube.com/watch?v=…\nhttps://soundcloud.com/…'} autoFocus />
      <div className="am-sheet-foot">
        <button className="am-text-btn" onClick={() => fileRef.current?.click()}><FileText size={14} strokeWidth={1.8} /> .txt içe aktar</button>
        <input ref={fileRef} type="file" accept=".txt,text/plain" hidden onChange={async (e) => {
          const f = e.target.files?.[0]
          if (!f) return
          try {
            const content = await f.text()
            setText((t) => (t ? `${t}\n` : '') + content)
            setReadError(null)
          } catch (err) {
            setReadError(`${f.name} okunamadı: ${(err as Error).message}`)
          }
        }} />
        {readError && <span className="am-error-text" style={{ fontSize: 12.5 }}>{readError}</span>}
        <span className="am-grow" />
        <button className="am-ghost" onClick={onClose}>Vazgeç</button>
        <button className="am-primary" disabled={urls.length === 0} onClick={() => onConfirm(urls)}>{urls.length} bağlantıyı indir</button>
      </div>
    </Sheet>
  )
}

/** Geri alınamaz işlemler için onay (ör. geçmişi temizle). */
export function ConfirmSheet({ title, body, confirmLabel, onConfirm, onClose }: {
  title: string
  body: string
  confirmLabel: string
  onConfirm: () => void
  onClose: () => void
}) {
  return (
    <Sheet onClose={onClose}>
      <div>
        <h2>{title}</h2>
        <p>{body}</p>
      </div>
      <div />
      <div className="am-sheet-foot">
        <span className="am-grow" />
        <button className="am-ghost" onClick={onClose} autoFocus>Vazgeç</button>
        <button className="am-primary" data-danger="true" onClick={onConfirm}>{confirmLabel}</button>
      </div>
    </Sheet>
  )
}

/** Ana sayfadaki videoyu belirli bir anda ya da her gün aynı saatte indirmek için. */
export function ScheduleSheet({ title, onClose, onConfirm }: {
  title: string
  onClose: () => void
  onConfirm: (when: string, daily: boolean) => Promise<void>
}) {
  const [daily, setDaily] = useState(false)
  const [time, setTime] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const confirm = () => {
    // Günlük görev "SS:DD", tek seferlik "YYYY-AA-GG SS:DD" (datetime-local 'T' ile gelir).
    const when = daily ? time.slice(-5) : time.replace('T', ' ')
    setSaving(true)
    setError(null)
    onConfirm(when, daily).catch((err) => { setError(String(err?.message ?? err)); setSaving(false) })
  }
  return (
    <Sheet onClose={onClose}>
      <div>
        <h2>Zamanla</h2>
        <p>{title}</p>
      </div>
      <div className="am-opts" style={{ gap: 16 }}>
        <input className="am-set-input" style={{ width: 240 }} type={daily ? 'time' : 'datetime-local'} value={time}
          onChange={(e) => setTime(e.target.value)} aria-label={daily ? 'Saat' : 'Tarih ve saat'} autoFocus />
        <Switch on={daily} onToggle={() => { setDaily((d) => !d); setTime('') }} label="Her gün" />
      </div>
      <p className={error ? 'am-error-text' : undefined} style={{ margin: 0 }}>
        {error ?? 'Seçili kalite ve klasörle indirilir. Uygulama o saatte açık olmalı (tepsideyken de çalışır).'}
      </p>
      <div className="am-sheet-foot">
        <span className="am-grow" />
        <button className="am-ghost" onClick={onClose}>Vazgeç</button>
        <button className="am-primary" disabled={!time || saving} onClick={confirm}>Zamanla</button>
      </div>
    </Sheet>
  )
}
