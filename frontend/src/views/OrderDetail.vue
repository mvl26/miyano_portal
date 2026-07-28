<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtVND, fmtDate, statusBadge } from '../format'
import { useIsMobile } from '../useMobile'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const data = ref(null)
const name = computed(() => route.params.name)

// Bước hiện tại = mốc đầu tiên chưa hoàn thành (để tô cam như mockup).
const currentIdx = computed(() => {
  if (!data.value) return -1
  const i = data.value.milestones.findIndex((m) => !m.done)
  return i
})
function stepClass(m, idx) {
  if (m.done) return 'done'
  if (idx === currentIdx.value) return 'cur'
  return ''
}

function pdfUrl(doctype, docname) {
  return (
    '/api/method/miyano_portal.api.portal.portal_document_download?doctype=' +
    encodeURIComponent(doctype) +
    '&name=' +
    encodeURIComponent(docname)
  )
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await api.call('portal_order_track', { order: name.value })
  } catch (e) {
    error.value = e.message || 'Không tải được chi tiết đơn hàng.'
  } finally {
    loading.value = false
  }
}

async function requestCancel() {
  const reason = window.prompt('Lý do yêu cầu huỷ / sửa đơn:')
  if (!reason) return
  try {
    await api.call('portal_request_cancel', { order: name.value, reason })
    window.alert('Đã gửi yêu cầu huỷ/sửa đơn đến Miyano.')
    load()
  } catch (e) {
    window.alert(e.message || 'Không gửi được yêu cầu.')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="topbar">
      <div>
        <router-link to="/orders" v-if="!isMobile"><button class="btn-o" style="margin-bottom: 8px">← Quay lại</button></router-link>
      </div>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>

    <template v-else-if="data">
      <!-- Header -->
      <div class="card mb10" style="margin-bottom: 14px">
        <div class="sb">
          <b style="font-size: 16px">{{ data.order }}</b>
          <span class="badge" :class="statusBadge(data.status_vi)">{{ data.status_vi }}</span>
        </div>
        <p class="tag" style="margin-top: 4px">
          Đặt ngày {{ fmtDate(data.order_date) }}
          <template v-if="data.hdnt"> · {{ data.hdnt }}</template>
          <template v-if="data.po_khach"> · Số dự trù: {{ data.po_khach }}</template>
        </p>
      </div>

      <!-- Tiến trình -->
      <div class="card mb10" style="margin-bottom: 14px">
        <div class="h3">Tiến trình</div>
        <!-- desktop: ngang -->
        <div v-if="!isMobile" class="tl">
          <div v-for="(m, i) in data.milestones" :key="m.key" class="st" :class="stepClass(m, i)">
            <div class="dot">{{ m.done ? '✓' : i + 1 }}</div>
            <div class="lb">{{ m.label }}</div>
          </div>
        </div>
        <!-- mobile: dọc -->
        <div v-else class="vtl">
          <div v-for="(m, i) in data.milestones" :key="m.key" class="vst" :class="stepClass(m, i)">
            <div class="vdot">{{ m.done ? '✓' : i + 1 }}</div>
            <div class="vlb"><b>{{ m.label }}</b>{{ m.done ? 'Hoàn thành' : (i === currentIdx ? 'Đang thực hiện' : 'Chưa thực hiện') }}</div>
          </div>
        </div>
      </div>

      <div class="grid2">
        <!-- Mặt hàng -->
        <div v-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
          <table>
            <thead>
              <tr>
                <th>Mặt hàng</th><th>ĐVT</th><th class="right">SL đặt</th>
                <th class="right">Đã giao</th><th class="right">Đơn giá</th><th class="right">Thành tiền</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="it in data.items" :key="it.item_code">
                <td><b>{{ it.item_code }}</b> {{ it.item_name }}</td>
                <td>{{ it.uom }}</td>
                <td class="right">{{ it.qty }}</td>
                <td class="right">{{ it.delivered_qty }}</td>
                <td class="right">{{ fmtVND(it.rate) }}</td>
                <td class="right">{{ fmtVND(it.amount) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-else class="card">
          <div class="h3">Mặt hàng</div>
          <div v-for="it in data.items" :key="it.item_code" class="rowline">
            <span>
              <b>{{ it.item_code }}</b> {{ it.item_name }}<br />
              <span class="tag">{{ it.qty }} {{ it.uom }} × {{ fmtVND(it.rate) }} · đã giao {{ it.delivered_qty }}</span>
            </span>
            <b>{{ fmtVND(it.amount) }}</b>
          </div>
        </div>

        <!-- Giao hàng -->
        <div class="card">
          <div class="h3">Giao hàng</div>
          <template v-if="data.deliveries.length">
            <div v-for="(d, i) in data.deliveries" :key="d.name" style="margin-bottom: 12px">
              <p style="font-size: 13px"><b>Đợt {{ i + 1 }} – {{ fmtDate(d.posting_date) }} ({{ d.percent }}%)</b></p>
              <p class="tag">
                Phiếu giao: {{ d.name }}
                <template v-if="d.carrier"> · {{ d.carrier }}</template>
                <template v-if="d.awb"> · Vận đơn: {{ d.awb }}</template>
              </p>
              <a :href="pdfUrl('Delivery Note', d.name)" target="_blank" rel="noopener">
                <button class="btn-o btn-sm" style="margin-top: 6px">⬇ Phiếu giao đợt {{ i + 1 }}</button>
              </a>
            </div>
          </template>
          <p v-else class="tag">Chưa có đợt giao hàng nào.</p>

          <hr class="sep" />
          <a :href="pdfUrl('Sales Order', data.order)" target="_blank" rel="noopener">
            <button class="btn-o btn-sm">⬇ PDF đơn hàng</button>
          </a>
          <button
            v-if="data.status_vi === 'Chờ xác nhận'"
            class="btn-o btn-sm"
            style="margin-left: 8px; color: var(--red); border-color: var(--red)"
            @click="requestCancel"
          >
            Huỷ / Sửa đơn
          </button>
        </div>
      </div>
    </template>
  </div>
</template>
