<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { store } from './store'
import { logout } from './api'
import ToastHost from './ToastHost.vue'

const route = useRoute()

const NAV = [
  { to: '/dashboard', icon: '🏠', label: 'Tổng quan', short: 'Tổng quan', key: 'dashboard' },
  { to: '/catalog', icon: '🛒', label: 'Đặt hàng', short: 'Đặt hàng', key: 'catalog' },
  { to: '/cart', icon: '📦', label: 'Giỏ hàng', short: 'Giỏ', key: 'cart', cart: true },
  { to: '/orders', icon: '📋', label: 'Đơn hàng của tôi', short: 'Đơn', key: 'orders' },
  { to: '/invoices', icon: '🧾', label: 'Hoá đơn & công nợ', short: 'Hoá đơn', key: 'invoices' },
  { to: '/profile', icon: '🏥', label: 'Hồ sơ đơn vị', short: 'Hồ sơ', key: 'profile' },
]

// Bottom nav (mobile): 5 mục — Hoá đơn truy cập qua "Thêm" (Hồ sơ) như mockup.
const BNAV = [
  { to: '/dashboard', icon: '🏠', short: 'Tổng quan', key: 'dashboard' },
  { to: '/catalog', icon: '🛒', short: 'Đặt hàng', key: 'catalog' },
  { to: '/cart', icon: '🧺', short: 'Giỏ hàng', key: 'cart', cart: true },
  { to: '/orders', icon: '📋', short: 'Đơn hàng', key: 'orders' },
  { to: '/profile', icon: '☰', short: 'Thêm', key: 'profile' },
]

const pageTitle = computed(() => route.meta.title || 'Cổng khách hàng')
const cartCount = computed(() => store.cartCount)

function isActive(key) {
  const name = route.name || ''
  if (key === 'orders') return name === 'orders' || name === 'order-detail'
  if (key === 'profile') return name === 'profile' || name === 'invoices'
  return name === key
}

async function doLogout() {
  await logout()
  window.location.href = '/portal/login'
}
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
          <span>{{ n.icon }} {{ n.label }}</span>
          <span v-if="n.cart && cartCount" class="cartn">{{ cartCount }}</span>
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
      </router-link>
    </nav>

    <ToastHost />
  </div>
</template>
