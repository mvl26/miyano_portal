<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtVND, fmtDate, statusBadge } from '../format'
import { useIsMobile } from '../useMobile'
import { store } from '../store'
import { showToast } from '../toast'

// Mã lý do do server trả về (`30_API_Spec` §5) → thông điệp cho người đọc.
// Server trả mã chứ không trả câu chữ để một chỗ đổi câu không phải sửa hai nơi.
const LY_DO = {
  het_han_muc: 'hết hạn mức',
  ngoai_hdnt: 'ngoài hợp đồng',
  thieu_gia: 'chưa có giá',
}

const dangDatLai = ref(false)

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

// UC-14 — điền lại giỏ theo đơn cũ, theo giá hiện hành.
async function datLai() {
  if (dangDatLai.value) return
  dangDatLai.value = true
  try {
    const res = await api.call('portal_reorder', { order: name.value })
    if (!res.gio_hang.length) {
      showToast('Không mặt hàng nào của đơn này còn đặt lại được.', 'error')
      return
    }
    store.napGio(res.gio_hang)
    if (data.value?.hdnt) store.setContract(data.value.hdnt)
    if (res.bi_loai.length) {
      // Nêu ĐỦ dòng bị loại kèm lý do. Im lặng bỏ bớt là cách chắc chắn
      // khiến khách đặt thiếu hàng mà không biết.
      showToast(
        'Không đưa vào giỏ được: ' +
          res.bi_loai
            .map((d) => `${d.item_code} (${LY_DO[d.ly_do] || d.ly_do})`)
            .join(', '),
        'error'
      )
    }
    router.push('/cart')
  } catch (e) {
    showToast(e.message || 'Không đặt lại được đơn này.', 'error')
  } finally {
    dangDatLai.value = false
  }
}

// M3 (E3 phần B review): `so_dot` (BR-K16 — thứ tự DN ĐÃ GHI SỔ của SO) và
// chỉ số mảng `i+1` KHÔNG PHẢI luôn cùng một con số — `data.deliveries` lọc
// docstatus < 2 (GỒM CẢ DN nháp chưa ghi sổ), còn so_dot chỉ đếm DN đã ghi
// sổ (docstatus=1). Một đơn có DN đang soạn (nháp) xen giữa hai DN đã ghi
// sổ sẽ khiến "Đợt {{i+1}}" và so_dot lệch nhau ngay trên cùng màn hình.
// Dùng so_dot khi có (khách có kho, DN đã ghi sổ); chỉ số mảng chỉ còn là
// phương án dự phòng khi chưa có mốc nào (khách không có kho, hoặc DN còn
// nháp — chưa từng qua delivery_hook).
function dotLabel(d, i) {
  return d.so_dot || i + 1
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
                <th>MÃ</th><th>TÊN VẬT TƯ</th><th>ĐVT</th><th class="right">SL đặt</th>
                <th class="right">Đã giao</th><th class="right">Đơn giá</th><th class="right">Thành tiền</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="it in data.items" :key="it.item_code">
                <td><b>{{ it.item_code }}</b></td>
                <td>{{ it.item_name }}</td>
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
              <b>{{ it.item_code }}</b>
              <template v-if="it.item_name"><br /><span style="font-size: 13px">{{ it.item_name }}</span></template><br />
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
              <p style="font-size: 13px"><b>Đợt {{ dotLabel(d, i) }} – {{ fmtDate(d.posting_date) }} ({{ d.percent }}%)</b></p>
              <p class="tag">
                Phiếu giao: {{ d.name }}
                <template v-if="d.carrier"> · {{ d.carrier }}</template>
                <template v-if="d.awb"> · Vận đơn: {{ d.awb }}</template>
              </p>
              <!-- US-E3.4 (F-07 khối đợt giao) — chỉ hiện khi khách có kho
                   (server chỉ trả d.phieu_nhap trong trường hợp đó). -->
              <p v-if="d.phieu_nhap" class="tag" style="margin-top: 2px">
                Phiếu nhập:
                <router-link
                  v-if="d.phieu_nhap.trang_thai === 'Nháp'"
                  :to="`/kho/nhap/${d.phieu_nhap.name}`"
                  style="text-decoration: underline"
                >
                  {{ d.phieu_nhap.name }} — Nháp, chờ kiểm nhận
                </router-link>
                <span v-else-if="d.phieu_nhap.co_chenh_lech" style="color: var(--red); font-weight: 600">
                  {{ d.phieu_nhap.name }} — Có chênh lệch ⚠
                </span>
                <span v-else>{{ d.phieu_nhap.name }} — Đã ghi sổ</span>
              </p>
              <a :href="pdfUrl('Delivery Note', d.name)" target="_blank" rel="noopener">
                <button class="btn-o btn-sm" style="margin-top: 6px">⬇ Phiếu giao đợt {{ dotLabel(d, i) }}</button>
              </a>
            </div>
          </template>
          <p v-else class="tag">Chưa có đợt giao hàng nào.</p>

          <hr class="sep" />
          <a :href="pdfUrl('Sales Order', data.order)" target="_blank" rel="noopener">
            <button class="btn-o btn-sm">⬇ PDF đơn hàng</button>
          </a>
          <button
            class="btn-o btn-sm"
            style="margin-left: 8px"
            :disabled="dangDatLai"
            @click="datLai"
          >
            🔁 Đặt lại đơn này
          </button>
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
