import { useEffect, useState } from 'react'
import { LayoutGroup, MotionConfig, AnimatePresence, motion } from 'motion/react'
import { Download, History as HistoryIcon, Home as HomeIcon, Library as LibraryIcon, Settings as SettingsIcon } from 'lucide-react'
import { api, onBridgeEvent, waitForBridge, type RecentItem, type UpdateOffer } from './bridge'
import { StoreProvider, useStore } from './store'
import { Background, Rail, Toasts, UpdateBar, type RailItem } from './components/Shell'
import { Home } from './pages/Home'
import { Queue } from './pages/Queue'
import { History } from './pages/History'
import { Library } from './pages/Library'
import { Settings } from './pages/Settings'

const URL_RE = /^https?:\/\/\S+$/i
type PageId = 'home' | 'queue' | 'library' | 'history' | 'settings'
const PAGES: PageId[] = ['home', 'queue', 'library', 'history', 'settings']
const PAGE_TRANSITION = { type: 'spring', stiffness: 380, damping: 32, opacity: { duration: 0.18 } } as const
/** Güncelleme denetimi açılışı yavaşlatmasın; arayüz oturduktan sonra. */
const UPDATE_CHECK_DELAY_MS = 3000

const hasUrl = (text: string) => text.split('\n').some((l) => URL_RE.test(l.trim()))

type UpdateState = { offer: UpdateOffer; percent: number | null; installing: boolean; error: string | null }

function Shell() {
  const store = useStore()
  const [page, setPage] = useState<PageId>('home')
  // nonce: aynı bağlantı ikinci kez gelse de ana sayfa yeniden işlesin. Birden çok satır toplu indirme açar.
  const [incoming, setIncoming] = useState<{ text: string; nonce: number } | null>(null)
  const openInHome = (text: string) => { setIncoming({ text, nonce: Date.now() }); setPage('home') }
  const busy = store.activeCount > 0
  const [update, setUpdate] = useState<UpdateState | null>(null)

  // Tepsi menüsünden gelen yönlendirme ve güncelleme indirme yüzdesi.
  useEffect(() => onBridgeEvent((e) => {
    if (e.type === 'navigate' && PAGES.includes(e.page as PageId)) setPage(e.page as PageId)
    if (e.type === 'update') setUpdate((u) => (u ? { ...u, percent: e.percent } : u))
  }), [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      api().check_update().then((offer) => { if (offer) setUpdate({ offer, percent: null, installing: false, error: null }) })
        .catch((err) => console.error('Güncelleme denetlenemedi', err))
    }, UPDATE_CHECK_DELAY_MS)
    return () => window.clearTimeout(timer)
  }, [])

  const install = () => {
    setUpdate((u) => (u ? { ...u, installing: true, error: null, percent: null } : u))
    api().install_update().catch((err) => setUpdate((u) => (u ? { ...u, installing: false, error: String(err?.message ?? err) } : u)))
  }

  // Ctrl+V (yazı alanı dışında): panodaki bağlantıyı ana sayfada aç. Ctrl+M mini pencere, Ctrl+Q çıkış.
  const { notify } = store
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!e.ctrlKey || e.altKey || e.metaKey) return
      const key = e.key.toLowerCase()
      const typing = e.target instanceof HTMLElement && e.target.matches('input, textarea, [contenteditable="true"]')
      if (key === 'v' && !typing) {
        e.preventDefault()
        api().clipboard().then((text) => {
          if (hasUrl(text)) openInHome(text)
          else notify('Panoda bağlantı yok.')
        }).catch((err) => notify(`Pano okunamadı: ${err?.message ?? err}`, 'error'))
      } else if (key === 'm') {
        e.preventDefault()
        api().toggle_mini().catch((err) => notify(`Mini pencere açılamadı: ${err?.message ?? err}`, 'error'))
      } else if (key === 'q') {
        e.preventDefault()
        api().quit_app().catch((err) => notify(`Çıkılamadı: ${err?.message ?? err}`, 'error'))
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [notify])

  const items: RailItem[] = [
    { id: 'home', label: 'Ana sayfa', Icon: HomeIcon },
    { id: 'queue', label: 'İndirilenler', Icon: Download, badge: store.activeCount },
    { id: 'library', label: 'Kütüphane', Icon: LibraryIcon },
    { id: 'history', label: 'Geçmiş', Icon: HistoryIcon },
    { id: 'settings', label: 'Ayarlar', Icon: SettingsIcon, bottom: true },
  ]

  // Palet değişince CSS değişkenleri 1.2 sn'de geçer (@property + transition, styles.css).
  const vars = {
    '--deep': store.palette.deep, '--mid': store.palette.mid,
    '--accent': store.palette.accent, '--on-accent': store.palette.onAccent,
  } as React.CSSProperties

  return (
    <div className="am" style={vars}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault()
        const text = e.dataTransfer.getData('text/uri-list') || e.dataTransfer.getData('text/plain')
        if (hasUrl(text)) openInHome(text)
      }}>
      <Background cover={store.cover} busy={busy} />
      <div className="am-body">
        <Rail items={items} current={page} onSelect={(id) => setPage(id as PageId)} />
        <div className="am-pages">
          {/* Ana sayfa hep bellekte: süren indirme, yapıştırılan bağlantı ve seçimler sayfa değişince kaybolmasın. */}
          <motion.div className="am-page" hidden={page !== 'home'} animate={page === 'home' ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
            transition={PAGE_TRANSITION}>
            <Home incoming={incoming} onShowQueue={() => setPage('queue')} />
          </motion.div>
          <AnimatePresence mode="wait" initial={false}>
            {page !== 'home' && (
              <motion.div key={page} className="am-page" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                transition={PAGE_TRANSITION}>
                {page === 'queue' ? <Queue /> : page === 'library' ? <Library /> : page === 'settings' ? <Settings />
                  : <History onShowQueue={() => setPage('queue')} onOpenInHome={openInHome} />}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
      <AnimatePresence>
        {update && (
          <UpdateBar offer={update.offer} percent={update.percent} installing={update.installing} error={update.error}
            onInstall={install} onDismiss={() => setUpdate(null)} />
        )}
      </AnimatePresence>
      <Toasts items={store.toasts} />
    </div>
  )
}

export default function App() {
  const [boot, setBoot] = useState<{ downloadDir: string; recent: RecentItem[] } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    waitForBridge().then((a) => a.bootstrap()).then(setBoot).catch((err) => setError(String(err?.message ?? err)))
  }, [])

  if (error) {
    return (
      <div className="am am-fatal">
        <h1>Uygulama başlatılamadı.</h1>
        <p>{error}</p>
      </div>
    )
  }
  if (!boot) return <div className="am" />
  return (
    <MotionConfig reducedMotion="user">
      <LayoutGroup>
        <StoreProvider downloadDir={boot.downloadDir} recent={boot.recent}>
          <Shell />
        </StoreProvider>
      </LayoutGroup>
    </MotionConfig>
  )
}
