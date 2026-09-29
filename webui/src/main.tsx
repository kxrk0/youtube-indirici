import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { Mini } from './pages/Mini'
import './styles.css'

// Yakalanmamış arayüz hataları Python günlüğüne (src/utils/app_log.py); yoksa WebView içinde kaybolur.
function reportClientError(message: string) {
  // Köprü yöntemleri geç eklenir (bridge.ts); yoksa konsolda kalır.
  const bridge = window.pywebview?.api
  if (bridge?.log_client_error) bridge.log_client_error(message).catch((err) => console.error('Hata günlüğe yazılamadı', err))
  else console.error(message)
}
window.addEventListener('error', (e) => reportClientError(`${e.message} (${e.filename}:${e.lineno})\n${e.error?.stack ?? ''}`))
window.addEventListener('unhandledrejection', (e) => reportClientError(`Yakalanmamış Promise hatası: ${e.reason?.stack ?? e.reason}`))

const root = document.getElementById('root')
if (!root) throw new Error('index.html içinde #root bulunamadı')
// Mini pencere aynı derlemeyi #mini adresiyle açar (src/web/app.py).
const isMini = window.location.hash === '#mini'
createRoot(root).render(
  <StrictMode>
    {isMini ? <Mini /> : <App />}
  </StrictMode>,
)
