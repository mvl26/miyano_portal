import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// Build vào miyano_portal/public/frontend/ để Frappe serve qua
// /assets/miyano_portal/frontend/. Single JS entry (src/main.js); trang shell
// HTML do Frappe www (www/portal/index.html) cung cấp.
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 8081,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/assets': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: '../miyano_portal/public/frontend',
    emptyOutDir: true,
    rollupOptions: {
      input: 'src/main.js',
      output: {
        entryFileNames: 'index.js',
        chunkFileNames: 'chunks/[name]-[hash].js',
        // Tên file ổn định để www shell tham chiếu cố định index.css.
        assetFileNames: (info) =>
          info.name && info.name.endsWith('.css')
            ? 'index.css'
            : 'assets/[name]-[hash][extname]',
      },
    },
  },
  base: '/assets/miyano_portal/frontend/',
})
