import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Fail loudly if 5173 is taken instead of silently moving to another port.
  server: { port: 5173, strictPort: true },
})
