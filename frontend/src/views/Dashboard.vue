<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { store } from '../store'
import { fmtVND, fmtVNDShort, fmtDate, statusBadge } from '../format'
import Icon from '../components/Icon.vue'

const router = useRouter()

const loading = ref(true)
const error = ref('')
const me = ref(null)
const orders = ref([])
// Brief 2026-08-16 (vá hồi quy phân trang) — trước bản này 3 ô KPI dưới
// đây tính từ `orders.value`/`invoices.value` (danh sách đã PHÂN TRANG,
// limit 10/20) — SAI ngay khi khách có nhiều hơn một trang dữ liệu. Giờ
// lấy từ `portal_dashboard_kpi`, một truy vấn đếm/cộng RIÊNG trên TOÀN BỘ
// dữ liệu của khách, không phụ thuộc cỡ trang. Không còn cần gọi
// `portal_invoices` ở màn này — danh sách hoá đơn không hiện ở Dashboard.
const kpi = ref({ bao_gia_cho_dong_y: 0, don_cho_xac_nhan: 0, don_dang_giao: 0, hoa_don_chua_thanh_toan: 0 })

const now = new Date()
const updatedAt = `${fmtDate(now.toISOString())} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`

const outstanding = computed(() => (me.value ? me.value.outstanding : 0))

const recentOrders = computed(() => orders.value.slice(0, 5))

onMounted(async () => {
  try {
    const [meRes, ordersRes, kpiRes] = await Promise.all([
      api.call('portal_me'),
      api.call('portal_order_history'),
      api.call('portal_dashboard_kpi'),
    ])
    me.value = meRes
    store.setMe(meRes)
    // brief 2026-08-15 (phân trang) — portal_order_history/portal_invoices
    // giờ trả {"rows": [...], "tong": ...} thay vì list trần.
    orders.value = ordersRes?.rows || []
    kpi.value = kpiRes || kpi.value
  } catch (e) {
    error.value = e.message || 'Không tải được dữ liệu.'
  } finally {
    loading.value = false
  }
})

function openOrder(name) {
  router.push({ name: 'order-detail', params: { name } })
}
</script>

<template>
  <div v-if="loading" class="loading">Đang tải…</div>
  <div v-else-if="error" class="empty">{{ error }}</div>
  <div v-else class="dash">
    <div class="topbar">
      <div class="grow">
        <h2>Xin chào, {{ me?.customer_name || 'Quý khách' }}</h2>
        <div class="sub">{{ me?.customer_name }} – cập nhật {{ updatedAt }}</div>
      </div>
      <router-link to="/dat-hang" class="btn"><Icon name="plus" :size="18" />Đặt hàng mới</router-link>
    </div>

    <div class="kpis anim">
      <!-- Thẻ này trỏ sang tab báo giá nên chỉ mang con số của tab đó. -->
      <router-link :to="{ name: 'bao-gia', query: { nhom: 'cho_dong_y' } }" class="card kpi">
        <span class="kpi-ic t-orange"><Icon name="file-text" :size="19" /></span>
        <span class="kpi-lb">Báo giá chờ đồng ý</span>
        <span class="n">{{ kpi.bao_gia_cho_dong_y }}</span>
        <span class="kpi-ctx">Cần đơn vị xem và đồng ý</span>
        <Icon class="kpi-go" name="chevron-right" :size="18" />
      </router-link>
      <!-- Ba thẻ dưới KHÔNG bấm được: con số đếm theo trạng thái Sales
           Order, còn chip ở "Danh sách đơn hàng" lọc theo giai đoạn yêu cầu —
           dẫn sang đó là hai con số khác nhau cho cùng một câu hỏi. -->
      <div class="card kpi">
        <span class="kpi-ic t-navy"><Icon name="clock" :size="19" /></span>
        <span class="kpi-lb">Đơn chờ xác nhận</span>
        <span class="n">{{ kpi.don_cho_xac_nhan }}</span>
        <span class="kpi-ctx">Miyano đang xác nhận</span>
      </div>
      <div class="card kpi">
        <span class="kpi-ic"><Icon name="truck" :size="19" /></span>
        <span class="kpi-lb">Đơn đang giao</span>
        <span class="n">{{ kpi.don_dang_giao }}</span>
        <span class="kpi-ctx">Đang trên đường tới đơn vị</span>
      </div>
      <div class="card kpi">
        <span class="kpi-ic t-green"><Icon name="receipt" :size="19" /></span>
        <span class="kpi-lb">Hoá đơn chưa thanh toán</span>
        <span class="n">{{ kpi.hoa_don_chua_thanh_toan }}</span>
        <span class="kpi-ctx">Tính trên toàn bộ hoá đơn</span>
      </div>
      <router-link to="/invoices" class="card kpi kpi-debt">
        <span class="kpi-ic t-red"><Icon name="wallet" :size="19" /></span>
        <span class="kpi-lb">Tổng công nợ</span>
        <span class="n">{{ fmtVNDShort(outstanding) }}</span>
        <span class="kpi-ctx">Xem chi tiết công nợ</span>
        <Icon class="kpi-go" name="chevron-right" :size="18" />
      </router-link>
    </div>

    <!-- Đơn hàng gần đây. Thẻ hợp đồng từng đứng bên phải đã gỡ (spec
         2026-10-09 §7 — giá theo bảng giá của khách), nên thẻ này không còn
         nằm trong lưới hai cột `.grid2`: để lại sẽ có một ô trống bên phải. -->
    <div class="card card-flush">
      <div class="card-hd"><h3>Đơn hàng gần đây</h3></div>
      <div v-if="recentOrders.length" class="tbl-scroll hide-m">
        <table>
          <thead>
            <tr><th>Mã đơn</th><th>Ngày đặt</th><th class="right">Giá trị</th><th>Trạng thái</th></tr>
          </thead>
          <tbody>
            <tr v-for="o in recentOrders" :key="o.name" class="clickable" tabindex="0" @click="openOrder(o.name)" @keydown.enter="openOrder(o.name)">
              <td class="cell-code">{{ o.name }}</td>
              <td>{{ fmtDate(o.transaction_date) }}</td>
              <td class="right">{{ fmtVND(o.grand_total) }}</td>
              <td><span class="badge" :class="statusBadge(o.status_vi)">{{ o.status_vi }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
      <ul v-if="recentOrders.length" class="ds-m hide-d">
        <li v-for="o in recentOrders" :key="o.name">
          <button type="button" class="ds-m-row" @click="openOrder(o.name)">
            <span class="grow">
              <span class="cell-code block">{{ o.name }}</span>
              <span class="tag">{{ fmtDate(o.transaction_date) }}</span>
            </span>
            <span class="col ai-end">
              <span class="fw600 tnum">{{ fmtVND(o.grand_total) }}</span>
              <span class="badge" :class="statusBadge(o.status_vi)">{{ o.status_vi }}</span>
            </span>
          </button>
        </li>
      </ul>
      <p v-else class="tag empty-line">Chưa có đơn hàng nào.</p>
    </div>
  </div>
</template>

<style scoped>
.card-hd { padding: 16px 20px 4px; margin: 0; }
.empty-line { padding: 8px 20px 20px; }
.kpi .n { margin-top: 2px; }
.ds-m { list-style: none; padding: 0 0 4px; }
.ds-m li + li { border-top: 1px solid var(--line); }
.ds-m-row {
  width: 100%; display: flex; align-items: center; gap: 12px; text-align: left;
  background: none; border: none; padding: 12px 16px; min-height: 56px; color: inherit;
}
.ds-m-row:active { background: var(--accent-soft); }
.ai-end { align-items: flex-end; }
@media (max-width: 900px) {
  .topbar .btn { width: 100%; }
  .kpi .kpi-lb { font-size: 12.5px; }
  .kpi .kpi-ctx { display: none; }
  .kpi-debt { grid-column: 1 / -1; }
}
</style>
