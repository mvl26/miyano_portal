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
const contracts = ref([])
const orders = ref([])
const invoices = ref([])

const now = new Date()
const updatedAt = `${fmtDate(now.toISOString())} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`

const kpiPending = computed(() => orders.value.filter((o) => o.status_vi === 'Chờ xác nhận').length)
const kpiDelivering = computed(() => orders.value.filter((o) => o.status_vi === 'Đang giao').length)
const kpiUnpaidInvoices = computed(() => invoices.value.filter((i) => Number(i.outstanding_amount || 0) > 0).length)
const outstanding = computed(() => (me.value ? me.value.outstanding : 0))

const recentOrders = computed(() => orders.value.slice(0, 5))
const contract = computed(() => (contracts.value.length ? contracts.value[0] : null))

onMounted(async () => {
  try {
    const [meRes, contractsRes, ordersRes] = await Promise.all([
      api.call('portal_me'),
      api.call('portal_contracts'),
      api.call('portal_order_history'),
    ])
    me.value = meRes
    store.setMe(meRes)
    contracts.value = contractsRes || []
    // brief 2026-08-15 (phân trang) — portal_order_history/portal_invoices
    // giờ trả {"rows": [...], "tong": ...} thay vì list trần.
    orders.value = ordersRes?.rows || []
    // Hoá đơn dùng cho KPI "chưa thanh toán"; lỗi ở đây không chặn dashboard.
    try {
      const invRes = await api.call('portal_invoices')
      invoices.value = invRes?.rows || []
    } catch (e) {
      invoices.value = []
    }
  } catch (e) {
    error.value = e.message || 'Không tải được dữ liệu.'
  } finally {
    loading.value = false
  }
})

function openOrder(name) {
  router.push({ name: 'order-detail', params: { name } })
}

function orderByContract(contractName) {
  store.setContract(contractName)
  router.push('/catalog')
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
      <router-link to="/catalog"><button class="btn">+ Đặt hàng mới</button></router-link>
    </div>

    <div class="kpis">
      <div class="card kpi"><div class="n">{{ kpiPending }}</div><div class="t">Đơn chờ xác nhận</div></div>
      <div class="card kpi"><div class="n">{{ kpiDelivering }}</div><div class="t">Đơn đang giao</div></div>
      <div class="card kpi"><div class="n">{{ kpiUnpaidInvoices }}</div><div class="t">Hoá đơn chưa thanh toán</div></div>
      <div class="card kpi">
        <div class="n" style="color: var(--red)">{{ fmtVNDShort(outstanding) }}</div>
        <div class="t">Tổng công nợ</div>
      </div>
    </div>

    <div class="grid2">
      <!-- Đơn hàng gần đây -->
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

      <!-- Hợp đồng nguyên tắc -->
      <div class="card">
        <h3 style="margin-bottom: 10px">Hợp đồng khung</h3>
        <template v-if="contract">
          <p style="font-weight: 600">{{ contract.name }}</p>
          <p class="tag">
            Hiệu lực: {{ fmtDate(contract.from_date) }} – {{ fmtDate(contract.to_date) }} ·
            {{ contract.item_count }} mặt hàng
          </p>
          <p style="font-size: 13px; margin-top: 10px">
            Hạn mức đã sử dụng: <b>{{ contract.used_pct }}%</b>
          </p>
          <div class="bar"><i :style="{ width: Math.min(contract.used_pct, 100) + '%' }"></i></div>
          <div class="note" style="margin-top: 14px">
            💡 Đặt hàng theo đúng đơn giá và hạn mức của hợp đồng khung đã ký.
          </div>
          <button class="btn-o btn-sm" style="margin-top: 12px" @click="orderByContract(contract.name)">
            Đặt hàng theo hợp đồng này →
          </button>
        </template>
        <p v-else class="tag">Chưa có hợp đồng khung còn hiệu lực.</p>
      </div>
    </div>
  </div>
</template>
