<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { store } from './store'
import { logout } from './api'
import api from './api'
import ToastHost from './ToastHost.vue'

const route = useRoute()

const NAV = [
  { to: '/dashboard', icon: '🏠', label: 'Tổng quan', short: 'Tổng quan', key: 'dashboard' },
  { to: '/catalog', icon: '🛒', label: 'Đặt hàng', short: 'Đặt hàng', key: 'catalog' },
  { to: '/cart', icon: '📦', label: 'Giỏ hàng', short: 'Giỏ', key: 'cart', cart: true },
  { to: '/orders', icon: '📋', label: 'Đơn hàng của tôi', short: 'Đơn', key: 'orders' },
  { to: '/kho', icon: '🏭', label: 'Kho của tôi', short: 'Kho', key: 'kho' },
  { to: '/invoices', icon: '🧾', label: 'Hoá đơn & công nợ', short: 'Hoá đơn', key: 'invoices' },
  // Brief 2026-08-15 (trang thông báo) — mục nav MỚI, badge = số chưa đọc.
  { to: '/thong-bao', icon: '🔔', label: 'Thông báo', short: 'Thông báo', key: 'thong-bao', thongBao: true },
  { to: '/profile', icon: '🏥', label: 'Hồ sơ đơn vị', short: 'Hồ sơ', key: 'profile' },
]

// Bottom nav (mobile): Thông báo truy cập qua "Thêm" (Hồ sơ) như Hoá đơn,
// để giữ đúng 6 mục cố định của mockup — badge vẫn hiện trên chính mục
// "Thêm" (xem isActive/`thongBaoQuaThem` bên dưới) để không mất tín hiệu.
const BNAV = [
  { to: '/dashboard', icon: '🏠', short: 'Tổng quan', key: 'dashboard' },
  { to: '/catalog', icon: '🛒', short: 'Đặt hàng', key: 'catalog' },
  { to: '/cart', icon: '🧺', short: 'Giỏ hàng', key: 'cart', cart: true },
  { to: '/orders', icon: '📋', short: 'Đơn hàng', key: 'orders' },
  { to: '/kho', icon: '🏭', short: 'Kho', key: 'kho' },
  { to: '/profile', icon: '☰', short: 'Thêm', key: 'profile', thongBao: true },
]

const pageTitle = computed(() => route.meta.title || 'Cổng khách hàng')
const cartCount = computed(() => store.cartCount)
const chuaDocThongBao = computed(() => store.chuaDocThongBao)

function isActive(key) {
  const name = route.name || ''
  if (key === 'orders') return name === 'orders' || name === 'order-detail'
  if (key === 'kho') {
    return [
      'kho', 'kho-import', 'kho-nhap', 'kho-nhap-detail', 'kho-xuat', 'kho-xuat-detail',
      'kho-bao-cao', 'kho-ncc', 'kho-nhat-ky', 'kho-vat-tu', 'kho-vat-tu-import',
    ].includes(name)
  }
  if (key === 'profile') return name === 'profile' || name === 'invoices' || name === 'thong-bao'
  return name === key
}

async function doLogout() {
  await logout()
  window.location.href = '/portal/login'
}

// Badge chưa đọc: nạp MỘT LẦN ở shell (mọi trang), khỏi phụ thuộc khách có
// mở trang Thông báo hay không. `ThongBao.vue` tự nạp lại số chính xác khi
// khách vào trang đó, và tự giảm tại chỗ khi khách đọc — ở đây chỉ cần một
// con số ban đầu cho badge.
onMounted(async () => {
  try {
    const res = await api.call('portal_thong_bao_list', { limit: 1 })
    store.setChuaDocThongBao(res.chua_doc || 0)
  } catch {
    // Badge chỉ là gợi ý phụ — im lặng bỏ qua, không được chặn cả trang vì
    // một lần gọi thất bại.
  }
})
</script>

<template>
  <div class="mp-shell">
    <!-- Desktop sidebar (>=900px) -->
    <aside class="side">
      <div class="logo">MIYANO<span>◆</span> Portal</div>
      <nav class="nav">
        <router-link
          v-for="n in NAV"
          :key="n.key"
          :to="n.to"
          :class="{ on: isActive(n.key) }"
        >
          <span>{{ n.icon }} {{ n.label }}<span v-if="n.newtag" class="newtag">MỚI</span></span>
          <span v-if="n.cart && cartCount" class="cartn">{{ cartCount }}</span>
          <span v-if="n.thongBao && chuaDocThongBao" class="cartn">{{ chuaDocThongBao }}</span>
        </router-link>
      </nav>
      <div class="who">
        <div>👤 {{ store.me?.customer_name || '…' }}</div>
        <div class="tag" style="color: #cbd5e1">{{ store.me?.customer || '' }}</div>
        <a href="#" @click.prevent="doLogout">Đăng xuất</a>
      </div>
    </aside>

    <!-- Mobile header (<900px) -->
    <header class="hdr">
      <span class="ttl">{{ pageTitle }}</span>
      <router-link to="/cart" class="cartbtn">
        🧺<span v-if="cartCount" class="cartn">{{ cartCount }}</span>
      </router-link>
    </header>

    <!-- Content -->
    <main class="main">
      <router-view />
    </main>

    <!-- Mobile bottom nav (<900px) -->
    <nav class="bnav">
      <router-link
        v-for="n in BNAV"
        :key="n.key"
        :to="n.to"
        :class="{ on: isActive(n.key) }"
      >
        <span class="ic">{{ n.icon }}</span>
        <span>{{ n.short }}</span>
        <span v-if="n.cart && cartCount" class="cartn2">{{ cartCount }}</span>
        <span v-if="n.thongBao && chuaDocThongBao" class="cartn2">{{ chuaDocThongBao }}</span>
      </router-link>
    </nav>

    <ToastHost />
  </div>
</template>
