import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { Mini } from './pages/Mini'
import './styles.css'

const root = document.getElementById('root')
if (!root) throw new Error('index.html içinde #root bulunamadı')
// Mini pencere aynı derlemeyi #mini adresiyle açar (src/web/app.py).
const isMini = window.location.hash === '#mini'
createRoot(root).render(
  <StrictMode>
    {isMini ? <Mini /> : <App />}
  </StrictMode>,
)
