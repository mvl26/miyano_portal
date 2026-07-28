<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'
import { store } from '../store'
import { fmtVND, fmtDate, invoiceBadge, daysUntil } from '../format'
import { useIsMobile } from '../useMobile'

const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const invoices = ref([])
const outstanding = ref(0)

const overdueTotal = computed(() =>
  invoices.value.reduce((a, inv) => {
    const d = daysUntil(inv.due_date)
    return a + (d !== null && d < 0 ? Number(inv.outstanding_amount || 0) : 0)
  }, 0)
)
const dueSoonCount = computed(() =>
  invoices.value.filter((inv) => {
    const d = daysUntil(inv.due_date)
    return d !== null && d >= 0 && d <= 7 && Number(inv.outstanding_amount || 0) > 0
  }).length
)

function pdfUrl(name) {
  return (
    '/api/method/miyano_portal.api.portal.portal_document_download?doctype=' +
    encodeURIComponent('Sales Invoice') +
    '&name=' +
    encodeURIComponent(name)
  )
}

onMounted(async () => {
  try {
    const [me, invs] = await Promise.all([
      store.me ? Promise.resolve(store.me) : api.call('portal_me'),
      api.call('portal_invoices', { limit: 100 }),
    ])
    store.setMe(me)
    outstanding.value = me.outstanding
    invoices.value = invs || []
  } catch (e) {
    error.value = e.message || 'Không tải được hoá đơn.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Hoá đơn &amp; công nợ</h2>
        <div class="sub">{{ store.me?.customer_name || '' }}</div>
      </div>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <template v-else>
      <div class="kpis">
        <div class="card kpi"><div class="n" style="color: var(--red)">{{ fmtVND(outstanding) }}</div><div class="t">Tổng công nợ hiện tại</div></div>
        <div class="card kpi"><div class="n" style="color: var(--orange)">{{ fmtVND(overdueTotal) }}</div><div class="t">Quá hạn thanh toán</div></div>
        <div class="card kpi"><div class="n">{{ dueSoonCount }}</div><div class="t">Hoá đơn đến hạn trong 7 ngày</div></div>
      </div>

      <div v-if="!invoices.length" class="empty">Chưa có hoá đơn nào.</div>

      <!-- DESKTOP: bảng -->
      <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
        <table>
          <thead>
            <tr>
              <th>Số hoá đơn</th><th>Ngày</th><th class="right">Giá trị</th>
              <th class="right">Còn phải trả</th><th>Hạn TT</th><th>Trạng thái</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="inv in invoices" :key="inv.name">
              <td><b>{{ inv.name }}</b></td>
              <td>{{ fmtDate(inv.posting_date) }}</td>
              <td class="right">{{ fmtVND(inv.grand_total) }}</td>
              <td class="right">{{ fmtVND(inv.outstanding_amount) }}</td>
              <td>{{ fmtDate(inv.due_date) }}</td>
              <td><span class="badge" :class="invoiceBadge(inv.status_vi)">{{ inv.status_vi }}</span></td>
              <td><a :href="pdfUrl(inv.name)" target="_blank" rel="noopener"><button class="btn-o btn-sm">⬇ PDF</button></a></td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- MOBILE: thẻ -->
      <template v-else>
        <div v-for="inv in invoices" :key="inv.name" class="card mb10">
          <div class="sb"><b>{{ inv.name }}</b><span class="badge" :class="invoiceBadge(inv.status_vi)">{{ inv.status_vi }}</span></div>
          <p class="tag" style="margin-top: 4px">
            {{ fmtDate(inv.posting_date) }} · Hạn TT {{ fmtDate(inv.due_date) }}
            <template v-if="Number(inv.outstanding_amount) > 0"> · Còn {{ fmtVND(inv.outstanding_amount) }}</template>
          </p>
          <div class="sb" style="margin-top: 6px">
            <b style="font-size: 15px">{{ fmtVND(inv.grand_total) }}</b>
            <a :href="pdfUrl(inv.name)" target="_blank" rel="noopener"><button class="btn-o btn-sm">⬇ PDF</button></a>
          </div>
        </div>
      </template>
    </template>
  </div>
</template>
