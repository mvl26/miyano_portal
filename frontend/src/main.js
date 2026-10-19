import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

// Phông chữ tự host (bệnh viện có thể chặn Google Fonts) — chỉ nạp các độ
// đậm đang dùng, subset tiếng Việt + Latin.
import '@fontsource/noto-sans/vietnamese-400.css'
import '@fontsource/noto-sans/latin-400.css'
import '@fontsource/noto-sans/vietnamese-500.css'
import '@fontsource/noto-sans/latin-500.css'
import '@fontsource/noto-sans/vietnamese-600.css'
import '@fontsource/noto-sans/latin-600.css'
import '@fontsource/noto-sans/vietnamese-700.css'
import '@fontsource/noto-sans/latin-700.css'
import '@fontsource/noto-sans/vietnamese-800.css'
import '@fontsource/noto-sans/latin-800.css'
import '@fontsource/jetbrains-mono/vietnamese-500.css'
import '@fontsource/jetbrains-mono/latin-500.css'
import '@fontsource/jetbrains-mono/vietnamese-600.css'
import '@fontsource/jetbrains-mono/latin-600.css'

import './style.css'

const app = createApp(App)
app.use(router)
app.mount('#app')
