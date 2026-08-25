<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api, { logout } from '../api'
import { store } from '../store'
import { fmtDate } from '../format'
import { useIsMobile } from '../useMobile'

const router = useRouter()
const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const me = ref(null)
const contracts = ref([])

async function doLogout() {
  await logout()
  window.location.href = '/portal/login'
}

onMounted(async () => {
  try {
    const [meRes, contractsRes] = await Promise.all([
      store.me ? Promise.resolve(store.me) : api.call('portal_me'),
      api.call('portal_contracts'),
    ])
    me.value = meRes
    store.setMe(meRes)
    contracts.value = contractsRes || []
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

    <div v-else class="grid2">
      <div>
        <!-- Thông tin đơn vị -->
        <div class="card mb10" style="margin-bottom: 14px">
          <div class="h3">🏥 {{ me.customer_name }}</div>
          <p class="tag">
            <template v-if="me.tax_id">MST: {{ me.tax_id }}</template>
          </p>

          <h4 style="margin: 16px 0 8px">Địa chỉ giao hàng</h4>
          <p v-if="!me.addresses?.length" class="tag">Chưa có địa chỉ.</p>
          <p v-for="a in me.addresses" :key="a.name" style="font-size: 13px">• {{ a.display }}</p>
        </div>

        <!-- Hợp đồng nguyên tắc -->
        <div class="card">
          <div class="h3">Hợp đồng khung</div>
          <p v-if="!contracts.length" class="tag">Chưa có hợp đồng còn hiệu lực.</p>
          <div v-else style="overflow-x: auto">
            <table>
              <thead>
                <tr><th>Số HĐ</th><th>Hiệu lực</th><th>Mặt hàng</th><th style="min-width: 120px">Hạn mức đã dùng</th></tr>
              </thead>
              <tbody>
                <tr v-for="c in contracts" :key="c.name">
                  <td><b>{{ c.name }}</b></td>
                  <td>{{ fmtDate(c.from_date) }} – {{ fmtDate(c.to_date) }}</td>
                  <td>{{ c.item_count }}</td>
                  <td>
                    {{ c.used_pct }}%
                    <div class="bar"><i :style="{ width: Math.min(c.used_pct, 100) + '%' }"></i></div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div>
        <!-- Người dùng portal -->
        <div class="card mb10" style="margin-bottom: 14px">
          <div class="h3">Người dùng portal</div>
          <!-- Nhãn "Tài khoản" trước đây gắn vào `store.me.customer` — mã
               khách hàng, KHÔNG phải tài khoản, và trên site này nó trùng
               nguyên văn tên bệnh viện ngay phía trên. Cùng một bản vá với
               khối `who` ở `App.vue`: tài khoản là email đang đăng nhập. -->
          <p style="font-size: 13px">👤 {{ store.me?.customer_name }}<br /><span class="tag">Tài khoản: {{ store.me?.user }}</span></p>
        </div>

        <!-- Hoá đơn & công nợ -->
        <div class="card mb10" style="margin-bottom: 14px">
          <div class="h3">Hoá đơn &amp; công nợ</div>
          <button class="btn-o" @click="router.push('/invoices')">Xem hoá đơn &amp; công nợ →</button>
        </div>

        <!-- Sales phụ trách (placeholder) -->
        <div class="card mb10" style="margin-bottom: 14px">
          <div class="h3">Sales phụ trách</div>
          <p class="tag">Liên hệ nhân viên kinh doanh Miyano phụ trách đơn vị của bạn để được hỗ trợ.</p>
        </div>

        <!-- Đăng xuất (mobile) -->
        <button
          v-if="isMobile"
          class="btn-o"
          style="width: 100%; color: var(--red); border-color: var(--red)"
          @click="doLogout"
        >
          Đăng xuất
        </button>
      </div>
    </div>
  </div>
</template>
