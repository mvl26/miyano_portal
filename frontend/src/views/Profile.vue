<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api, { logout } from '../api'
import { store } from '../store'
import { useIsMobile } from '../useMobile'
import Icon from '../components/Icon.vue'

const router = useRouter()
const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const me = ref(null)

async function doLogout() {
  await logout()
  window.location.href = '/portal/login'
}

onMounted(async () => {
  try {
    const meRes = store.me || (await api.call('portal_me'))
    me.value = meRes
    store.setMe(meRes)
  } catch (e) {
    error.value = e.message || 'Không tải được hồ sơ.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Hồ sơ đơn vị</h2>
        <div class="sub">Thông tin do Miyano quản lý – liên hệ sales để cập nhật</div>
      </div>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>

    <div v-else class="grid2 ho-so">
      <!-- Thông tin đơn vị -->
      <div class="card hs-dv">
        <div class="row-top gap12">
          <span class="hs-ic"><Icon name="hospital" :size="22" /></span>
          <div class="grow">
            <div class="h3 mb4">{{ me.customer_name }}</div>
            <p class="tag">
              <template v-if="me.tax_id">MST: <span class="mono">{{ me.tax_id }}</span></template>
            </p>
          </div>
        </div>

        <div class="divider"></div>
        <h4 class="mb8">Địa chỉ giao hàng</h4>
        <p v-if="!me.addresses?.length" class="tag">Chưa có địa chỉ.</p>
        <ul v-else class="hs-dia-chi">
          <li v-for="a in me.addresses" :key="a.name"><Icon name="map-pin" :size="16" class="muted shrink0" /><span>{{ a.display }}</span></li>
        </ul>
      </div>

      <!-- Lối tắt: trên mobile đây là trang "Thêm" — Hoá đơn & Thông báo
           không có ô riêng ở thanh dưới nên đi qua danh sách này. -->
      <nav class="card card-flush hs-nav" aria-label="Lối tắt tài khoản">
        <!-- Hoá đơn & công nợ -->
        <button type="button" class="hs-hang" @click="router.push('/invoices')">
          <span class="hs-hang-ic"><Icon name="receipt" :size="18" /></span>
          <span class="grow">
            <span class="block fw600">Hoá đơn &amp; công nợ</span>
            <span class="tag">Xem hoá đơn &amp; công nợ</span>
          </span>
          <Icon name="chevron-right" :size="18" class="hs-chev" />
        </button>
        <router-link to="/thong-bao" class="hs-hang">
          <span class="hs-hang-ic"><Icon name="bell" :size="18" /></span>
          <span class="grow fw600">Thông báo</span>
          <span v-if="store.chuaDocThongBao" class="cartn" :aria-label="`${store.chuaDocThongBao} thông báo chưa đọc`">{{ store.chuaDocThongBao }}</span>
          <Icon name="chevron-right" :size="18" class="hs-chev" />
        </router-link>
      </nav>

      <!-- Người dùng portal -->
      <div class="card hs-o">
        <div class="h3">Người dùng portal</div>
        <!-- Nhãn "Tài khoản" trước đây gắn vào `store.me.customer` — mã
             khách hàng, KHÔNG phải tài khoản, và trên site này nó trùng
             nguyên văn tên bệnh viện ngay phía trên. Cùng một bản vá với
             khối `who` ở `App.vue`: tài khoản là email đang đăng nhập. -->
        <div class="row-top gap8 fs13">
          <Icon name="user" :size="18" class="muted shrink0" />
          <p>{{ store.me?.customer_name }}<br /><span class="tag break">Tài khoản: {{ store.me?.user }}</span></p>
        </div>
      </div>

      <!-- Sales phụ trách (placeholder) -->
      <div class="card hs-o">
        <div class="h3">Sales phụ trách</div>
        <div class="row-top gap8">
          <Icon name="phone" :size="18" class="muted shrink0" />
          <p class="tag">Liên hệ nhân viên kinh doanh Miyano phụ trách đơn vị của bạn để được hỗ trợ.</p>
        </div>
      </div>

      <!-- Đăng xuất (mobile) -->
      <button
        v-if="isMobile"
        class="btn-o btn-danger w100 hs-o"
        @click="doLogout"
      >
        <Icon name="log-out" :size="18" />Đăng xuất
      </button>
    </div>
  </div>
</template>

<style scoped>
.ho-so { align-items: start; align-content: start; gap: 14px 16px; }
.hs-dv { grid-column: 1; grid-row: 1 / span 4; }
.hs-nav, .hs-o { grid-column: 2; }
.hs-ic {
  width: 44px; height: 44px; border-radius: var(--r-md); flex-shrink: 0;
  display: grid; place-items: center; background: var(--accent-soft); color: var(--navy);
}
.hs-dia-chi { list-style: none; padding: 0; margin: 0; }
.hs-dia-chi li { display: flex; gap: 8px; align-items: flex-start; font-size: 13px; line-height: 1.5; }
.hs-dia-chi li + li { margin-top: 8px; }
.hs-dia-chi .ic { margin-top: 2px; }
.hs-hang {
  width: 100%; display: flex; align-items: center; gap: 12px; min-height: 56px;
  padding: 10px 16px; background: none; border: none; color: var(--text);
  text-align: left; font-size: 14px;
}
.hs-hang + .hs-hang { border-top: 1px solid var(--line); }
.hs-hang:hover { background: var(--surface-2); }
.hs-hang:active { background: var(--accent-soft); }
.hs-hang:focus-visible { outline: none; box-shadow: inset var(--focus); }
.hs-hang-ic {
  width: 36px; height: 36px; border-radius: var(--r-sm); flex-shrink: 0;
  display: grid; place-items: center; background: var(--surface-2); color: var(--navy);
}
.hs-chev { color: var(--text-4); }
.hs-hang:hover .hs-chev { color: var(--accent); }
@media (max-width: 900px) {
  .ho-so { display: flex; flex-direction: column; align-items: stretch; }
  .hs-nav { order: -1; }
}
</style>
