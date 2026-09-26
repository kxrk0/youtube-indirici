import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// base './': derleme pywebview'in yerel sunucusundan göreli yollarla açılır.
export default defineConfig({
  base: './',
  plugins: [react()],
  build: { target: 'chrome120' },
})
