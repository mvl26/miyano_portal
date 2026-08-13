<script setup>
// E6/F-22 [MỚI] — Danh sách Yêu cầu hàng hoá (pg-yeucau trong prototype).
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { fmtDate, fmtDateTime, yeuCauBadge } from '../format'
import { useIsMobile } from '../useMobile'
import { showToast } from '../toast'
import YeuCauModal from '../components/YeuCauModal.vue'

const router = useRouter()
const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const rows = ref([])
const chip = ref('tat_ca')
const modalOpen = ref(false)

// Nhóm hiển thị (chip lọc) — gộp các trạng thái chi tiết thành 3 nhóm lớn
// như prototype "Tất cả / Đang xử lý / Đã báo giá / Kết thúc". Nhóm "Kết
// thúc" khớp NGUYÊN VĂN tập `TRANG_THAI_KET_THUC` phía server
// (portal_item_request.py) — lặp lại hằng số này ở client vì danh sách chỉ
// gọi MỘT lần `portal_yeu_cau_list()` (không filter theo trạng thái) rồi lọc
// tại chỗ cho cả 4 chip, thay vì gọi lại API 4 lần.
const NHOM = {
  dang_xu_ly: new Set(['Mới', 'Đang tìm nguồn', 'Cần thêm thông tin']),
  da_bao_gia: new Set(['Đã báo giá', 'Đã có hàng']),
  ket_thuc: new Set(['Đã chuyển thành đơn', 'Không đáp ứng được', 'Khách huỷ', 'Hết hạn']),
}

function dem(nhom) {
  if (nhom === 'tat_ca') return rows.value.length
  return rows.value.filter((r) => NHOM[nhom]?.has(r.trang_thai)).length
}

const filtered = computed(() => {
  if (chip.value === 'tat_ca') return rows.value
  return rows.value.filter((r) => NHOM[chip.value]?.has(r.trang_thai))
})

function open(name) {
  router.push({ name: 'yeu-cau-detail', params: { name } })
}
// "Đã báo giá" → đơn ĐÃ có (don_lien_ket) ngay từ danh sách, không bắt khách
// đi qua chi tiết yêu cầu trước — khớp `go('accept')` của prototype.
function xemDon(r) {
  if (r.don_lien_ket) router.push({ name: 'order-detail', params: { name: r.don_lien_ket } })
  else open(r.name)
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = (await api.call('portal_yeu_cau_list')) || []
  } catch (e) {
    error.value = e.message || 'Không tải được danh sách yêu cầu.'
  } finally {
    loading.value = false
  }
}

function onSaved(res) {
  modalOpen.value = false
  showToast(`Đã gửi ${res.name} — Miyano phản hồi trong 48h làm việc.`)
  if (res.canh_bao_trung && res.canh_bao_trung.length) {
    // NL-11.1 — cảnh báo trùng KHÔNG chặn gửi, chỉ nêu thêm sau khi đã gửi
    // thành công (server chỉ biết trùng SAU khi bản ghi mới đã tồn tại để
    // so sánh với chính nó bị loại trừ).
    showToast(
      `Lưu ý: bạn có yêu cầu ${res.canh_bao_trung.join(', ')} cho hàng tương tự đang xử lý.`,
      'error'
    )
  }
  load()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>Yêu cầu hàng hoá <span class="newtag">MỚI</span></h2>
        <div class="sub">Hàng ngoài HĐNT / cần tìm nguồn / cần báo giá — Miyano phản hồi trong 48h làm việc</div>
      </div>
      <button class="btn" @click="modalOpen = true">+ Gửi yêu cầu</button>
    </div>
    <button v-else class="btn" style="width: 100%; margin-bottom: 12px" @click="modalOpen = true">+ Gửi yêu cầu</button>

    <div class="chips">
      <button class="chip" :class="{ on: chip === 'tat_ca' }" @click="chip = 'tat_ca'">Tất cả ({{ dem('tat_ca') }})</button>
      <button class="chip" :class="{ on: chip === 'dang_xu_ly' }" @click="chip = 'dang_xu_ly'">Đang xử lý ({{ dem('dang_xu_ly') }})</button>
      <button class="chip" :class="{ on: chip === 'da_bao_gia' }" @click="chip = 'da_bao_gia'">Đã báo giá ({{ dem('da_bao_gia') }})</button>
      <button class="chip" :class="{ on: chip === 'ket_thuc' }" @click="chip = 'ket_thuc'">Kết thúc ({{ dem('ket_thuc') }})</button>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>
    <div v-else-if="!filtered.length" class="card" style="color: var(--gray)">
      Chưa có yêu cầu hàng hoá nào —
      <a href="#" style="color: var(--blue2)" @click.prevent="modalOpen = true">gửi yêu cầu đầu tiên</a>.
    </div>

    <!-- DESKTOP: bảng -->
    <div v-else-if="!isMobile" class="card" style="padding: 0; overflow-x: auto">
      <table>
        <thead>
          <tr>
            <th>Mã</th><th>Ngày</th><th>Tên hàng</th><th>Loại</th><th class="right">SL</th>
            <th>Trạng thái</th><th>Hạn phản hồi</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in filtered" :key="r.name" class="clickable" @click="open(r.name)">
            <td><b class="mono">{{ r.name }}</b></td>
            <td>{{ fmtDate(r.ngay) }}</td>
            <td>{{ r.ten_hang }}</td>
            <td>{{ r.loai }}</td>
            <td class="right">{{ r.so_luong_du_kien }}</td>
            <td><span class="badge" :class="yeuCauBadge(r.trang_thai)">{{ r.trang_thai }}</span></td>
            <td>
              <span v-if="r.trang_thai === 'Mới' && r.sla_den_han" :style="{ color: r.qua_sla ? 'var(--red)' : '' }">
                {{ fmtDateTime(r.sla_den_han) }}
              </span>
              <span v-else class="tag">—</span>
            </td>
            <td>
              <button v-if="r.trang_thai === 'Đã báo giá'" class="btn btn-sm" @click.stop="xemDon(r)">Xem đơn →</button>
              <button v-else-if="r.trang_thai === 'Đã có hàng'" class="btn btn-sm" @click.stop="router.push('/catalog')">Đặt ngay</button>
              <button v-else-if="r.trang_thai === 'Cần thêm thông tin'" class="btn-o btn-sm" @click.stop="open(r.name)">Bổ sung</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- MOBILE: thẻ -->
    <template v-else>
      <div v-for="r in filtered" :key="r.name" class="card mb10 clickable" @click="open(r.name)">
        <div class="sb"><b class="mono">{{ r.name }}</b><span class="badge" :class="yeuCauBadge(r.trang_thai)">{{ r.trang_thai }}</span></div>
        <p class="tag" style="margin: 4px 0">{{ fmtDate(r.ngay) }} · {{ r.loai }}</p>
        <p style="font-size: 13px">{{ r.ten_hang }} <span class="tag">· SL {{ r.so_luong_du_kien }}</span></p>
        <p v-if="r.trang_thai === 'Mới' && r.sla_den_han" class="tag" :style="{ color: r.qua_sla ? 'var(--red)' : '' }" style="margin-top: 4px">
          Hạn phản hồi: {{ fmtDateTime(r.sla_den_han) }}
        </p>
      </div>
    </template>

    <YeuCauModal :open="modalOpen" mode="tao" @close="modalOpen = false" @saved="onSaved" />
  </div>
</template>
