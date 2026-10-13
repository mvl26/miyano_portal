<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { store } from '../store'
import { fmtVND, fmtVNDShort, fmtDate, statusBadge } from '../format'

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
const kpi = ref({ bao_gia_cho_dong_y: 0, don_cu_cho_dong_y: 0, don_cho_xac_nhan: 0, don_dang_giao: 0, hoa_don_chua_thanh_toan: 0 })

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
  <div v-else>
    <div class="topbar">
      <div>
        <h2>Xin chào, {{ me?.customer_name || 'Quý khách' }} 👋</h2>
        <div class="sub">{{ me?.customer_name }} – cập nhật {{ updatedAt }}</div>
      </div>
      <router-link to="/dat-hang"><button class="btn">+ Đặt hàng mới</button></router-link>
    </div>

    <div class="kpis">
      <!-- Thẻ này trỏ sang tab báo giá nên chỉ mang con số của tab đó. Đơn
           "Mua lẻ" của luồng cũ còn chờ đồng ý nằm ở tab Đơn hàng: đường dẫn
           riêng, đứng NGOÀI thẻ (thẻ đã là một liên kết). -->
      <div class="kpi-bao-gia">
        <router-link :to="{ name: 'bao-gia', query: { nhom: 'cho_dong_y' } }" class="card kpi" style="text-decoration: none; color: inherit">
          <div class="n" style="color: var(--orange)">{{ kpi.bao_gia_cho_dong_y }}</div>
          <div class="t">Báo giá chờ đồng ý</div>
        </router-link>
        <router-link v-if="kpi.don_cu_cho_dong_y > 0" :to="{ name: 'yeu-cau', query: { chip: 'cho_khach_dong_y' } }" class="tag don-cu">{{ kpi.don_cu_cho_dong_y }} đơn cũ chờ đồng ý →</router-link>
      </div>
      <div class="card kpi"><div class="n">{{ kpi.don_cho_xac_nhan }}</div><div class="t">Đơn chờ xác nhận</div></div>
      <div class="card kpi"><div class="n">{{ kpi.don_dang_giao }}</div><div class="t">Đơn đang giao</div></div>
      <div class="card kpi"><div class="n">{{ kpi.hoa_don_chua_thanh_toan }}</div><div class="t">Hoá đơn chưa thanh toán</div></div>
      <div class="card kpi">
        <div class="n" style="color: var(--red)">{{ fmtVNDShort(outstanding) }}</div>
        <div class="t">Tổng công nợ</div>
      </div>
    </div>

    <!-- Đơn hàng gần đây. Thẻ hợp đồng từng đứng bên phải đã gỡ (spec
         2026-10-09 §7 — giá theo bảng giá của khách), nên thẻ này không còn
         nằm trong lưới hai cột `.grid2`: để lại sẽ có một ô trống bên phải. -->
    <div class="card">
      <h3 style="margin-bottom: 10px">Đơn hàng gần đây</h3>
      <table v-if="recentOrders.length">
        <thead>
          <tr><th>Mã đơn</th><th>Ngày đặt</th><th class="right">Giá trị</th><th>Trạng thái</th></tr>
        </thead>
        <tbody>
          <tr v-for="o in recentOrders" :key="o.name" class="clickable" @click="openOrder(o.name)">
            <td><b>{{ o.name }}</b></td>
            <td>{{ fmtDate(o.transaction_date) }}</td>
            <td class="right">{{ fmtVND(o.grand_total) }}</td>
            <td><span class="badge" :class="statusBadge(o.status_vi)">{{ o.status_vi }}</span></td>
          </tr>
        </tbody>
      </table>
      <p v-else class="tag" style="padding: 8px 0">Chưa có đơn hàng nào.</p>
    </div>
  </div>
</template>

<style scoped>
/* Ô lưới của thẻ báo giá: thẻ giãn hết chiều cao như các thẻ bên cạnh, đường
   dẫn "đơn cũ" (chỉ hiện khi còn đơn) nằm ngay dưới. */
.kpi-bao-gia { display: flex; flex-direction: column; gap: 0.25rem; min-width: 0; }
.kpi-bao-gia > .kpi { flex: 1; }
.don-cu { padding: 0 0.25rem; color: var(--orange); }
</style>
