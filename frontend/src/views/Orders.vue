<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { fmtVND, fmtDate, statusBadge } from '../format'
import { useIsMobile } from '../useMobile'
import PhanTrang from '../components/PhanTrang.vue'

const router = useRouter()
const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const orders = ref([])
const filter = ref('')
// Brief 2026-08-15 (phân trang) — server-side, thay cho limit:100 cố định.
const trang = ref(1)
const soDong = ref(20)
const tong = ref(0)

const FILTERS = ['', 'Chờ xác nhận', 'Đang xử lý', 'Đang giao', 'Hoàn thành', 'Đã huỷ']

function pct(o) {
  return Math.round(Number(o.per_delivered || 0))
}
function open(name) {
  router.push({ name: 'order-detail', params: { name } })
}

async function load() {
  loading.value = true
  try {
    const res = await api.call('portal_order_history', {
      start: (trang.value - 1) * soDong.value,
      limit: soDong.value,
      // Brief 2026-08-16 (vá hồi quy) — lọc trạng thái đẩy XUỐNG SERVER,
      // cùng start/limit của trang đang xem. `filter.value || undefined`:
      // '' (chip "Tất cả") bị JSON.stringify loại khỏi body, backend nhận
      // trang_thai=None -> không lọc, đúng hành vi "Tất cả".
      trang_thai: filter.value || undefined,
    })
    orders.value = res?.rows || []
    tong.value = res?.tong || 0
  } catch (e) {
    error.value = e.message || 'Không tải được đơn hàng.'
  } finally {
    loading.value = false
  }
}

// Đổi chip lọc -> về trang 1 (kết quả lọc mới có thể ít hơn trang đang
// xem). Watcher [trang, soDong, filter] gộp cả hai thay đổi đồng bộ trong
// cùng tick thành MỘT lần gọi `load()` (Vue dedupe theo watcher instance),
// không phải hai round-trip.
watch(filter, () => {
  trang.value = 1
})
watch([trang, soDong, filter], load)

onMounted(load)
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Đơn hàng của tôi</h2>
        <div class="sub">Toàn bộ đơn hàng của đơn vị</div>
      </div>
    </div>

    <div class="chips">
      <button
        v-for="f in FILTERS"
        :key="f"
        class="chip"
        :class="{ on: filter === f }"
        @click="filter = f"
      >
        {{ f || 'Tất cả' }}
      </button>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!orders.length" class="empty">Không có đơn hàng nào.</div>

    <!-- DESKTOP: bảng -->
    <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
      <table>
        <thead>
          <tr>
            <th>Mã đơn</th><th>Ngày đặt</th><th class="right">Giá trị</th>
            <th style="min-width: 130px">Đã giao</th><th>Trạng thái</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in orders" :key="o.name" class="clickable" @click="open(o.name)">
            <td><b>{{ o.name }}</b></td>
            <td>{{ fmtDate(o.transaction_date) }}</td>
            <td class="right">{{ fmtVND(o.grand_total) }}</td>
            <td>
              {{ pct(o) }}%
              <div class="bar"><i :style="{ width: pct(o) + '%', background: 'var(--orange)' }"></i></div>
            </td>
            <td><span class="badge" :class="statusBadge(o.status_vi)">{{ o.status_vi }}</span></td>
            <td><button class="btn-o btn-sm" @click.stop="open(o.name)">Chi tiết</button></td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- MOBILE: thẻ -->
    <template v-else>
      <div v-for="o in orders" :key="o.name" class="card mb10 clickable" @click="open(o.name)">
        <div class="sb"><b>{{ o.name }}</b><span class="badge" :class="statusBadge(o.status_vi)">{{ o.status_vi }}</span></div>
        <p class="tag" style="margin-top: 4px">Đặt {{ fmtDate(o.transaction_date) }} · {{ fmtVND(o.grand_total) }}</p>
        <template v-if="pct(o) > 0">
          <p style="font-size: 12px; margin-top: 6px">Đã giao <b>{{ pct(o) }}%</b></p>
          <div class="bar"><i :style="{ width: pct(o) + '%', background: 'var(--orange)' }"></i></div>
        </template>
      </div>
    </template>

    <PhanTrang v-if="!loading && !error" v-model:trang="trang" v-model:so-dong="soDong" :tong="tong" />
  </div>
</template>
