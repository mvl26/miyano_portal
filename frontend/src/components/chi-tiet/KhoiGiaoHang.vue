<script setup>
// Khối "Giao hàng": lời hẹn giao, các đợt đã giao (phiếu giao/phiếu nhập/
// kiểm hàng/hoá đơn nháp). Tách khỏi `OrderDetail.vue` 03/09/2026 để màn
// chi tiết GỘP dùng lại nguyên vẹn — không chép lần hai. Template NHIỀU
// GỐC (không bọc `<div>` ngoài): một wrapper sẽ chèn thêm một biên block
// vào giữa nút "Đặt lại đơn này" (cuối `KhoiHoaDonTaiLieu`) và nút "Huỷ /
// Sửa đơn" (do OrderDetail.vue render ngay sau) — hai nút đó vốn cùng hàng
// nhờ `margin-left: 8px` trên các phần tử inline liền kề, một `<div>` chen
// giữa sẽ đẩy "Huỷ / Sửa đơn" xuống dòng riêng. OrderDetail.vue giữ MỘT
// `.card` chung cho khối này và `KhoiHoaDonTaiLieu`, để `grid2` không nảy
// sinh thêm ô con VÀ để chuỗi phần tử con của `.card` giữ nguyên như bản gốc.
import { ref } from 'vue'
import api from '../../api'
import { fmtDate } from '../../format'
import { showToast } from '../../toast'
import HoaDonNhap from '../HoaDonNhap.vue'

defineProps({ don: { type: Object, required: true } })

// E9 — màu badge trạng thái biên bản kiểm hàng. Cùng bảng màu với
// KiemHang.vue; giữ hai bản vì hai màn đọc hai nguồn khác nhau và một import
// chéo giữa hai view chỉ vì bảy dòng ánh xạ là một cạnh phụ thuộc không đáng.
const KIEM_HANG_BADGE = {
  'Chờ xử lý': 'b-orange',
  'Đã xác nhận': 'b-green',
  'Đã duyệt trả': 'b-blue',
  'Đã thu hồi': 'b-green',
  'Đã xử lý': 'b-green',
  'Từ chối': 'b-red',
}
function kiemHangBadge(tt) {
  return KIEM_HANG_BADGE[tt] || 'b-gray'
}

// --- Hoá đơn nháp đính theo phiếu giao (E7b) --------------------------------
// Cờ `d.co_hoa_don_nhap` đi sẵn trong `portal_order_track`; NỘI DUNG chỉ nạp
// khi khách bấm xem — khác khối HĐĐT ở trang Hoá đơn (nhúng sẵn): ở đây có
// thể có nhiều đợt giao, nhét sẵn dòng hàng của mọi bản nháp vào response chi
// tiết đơn là trả về một đống dữ liệu hầu như không ai mở tới.
const nhapMo = ref(null)
const nhapData = ref({})
const nhapDangTai = ref(null)

async function toggleNhap(dnName) {
  if (nhapMo.value === dnName) {
    nhapMo.value = null
    return
  }
  nhapMo.value = dnName
  if (dnName in nhapData.value) return
  nhapDangTai.value = dnName
  try {
    const khoi = await api.call('portal_einvoice_nhap', { delivery_note: dnName })
    nhapData.value = { ...nhapData.value, [dnName]: khoi }
  } catch (e) {
    showToast(e.message || 'Không xem được hoá đơn nháp.', 'error')
    nhapMo.value = null
  } finally {
    nhapDangTai.value = null
  }
}

function urlPdfNhap(dnName) {
  const khoi = nhapData.value[dnName]
  if (!khoi || !khoi.nhap_tai_duoc) return ''
  return (
    '/api/method/miyano_portal.api.portal.portal_einvoice_nhap_pdf?delivery_note=' +
    encodeURIComponent(dnName)
  )
}

// M3 (E3 phần B review): `so_dot` (BR-K16 — thứ tự DN ĐÃ GHI SỔ của SO) và
// chỉ số mảng `i+1` KHÔNG PHẢI luôn cùng một con số — `don.deliveries` lọc
// docstatus < 2 (GỒM CẢ DN nháp chưa ghi sổ), còn so_dot chỉ đếm DN đã ghi
// sổ (docstatus=1). Một đơn có DN đang soạn (nháp) xen giữa hai DN đã ghi
// sổ sẽ khiến "Đợt {{i+1}}" và so_dot lệch nhau ngay trên cùng màn hình.
// Dùng so_dot khi có (khách có kho, DN đã ghi sổ); chỉ số mảng chỉ còn là
// phương án dự phòng khi chưa có mốc nào (khách không có kho, hoặc DN còn
// nháp — chưa từng qua delivery_hook).
function dotLabel(d, i) {
  return d.so_dot || i + 1
}

// Task 4 — chép nguyên, KHÔNG import chéo từ OrderDetail.vue/KhoiHoaDonTaiLieu:
// bảy dòng ánh xạ URL, cùng lý do `KIEM_HANG_BADGE` ở trên đang giữ hai bản.
function pdfUrl(doctype, docname) {
  return (
    '/api/method/miyano_portal.api.portal.portal_document_download?doctype=' +
    encodeURIComponent(doctype) +
    '&name=' +
    encodeURIComponent(docname)
  )
}
</script>

<template>
  <div class="h3">Giao hàng</div>
  <!-- Miyano hẹn lại lịch giao (2026-08-16). Đặt Ở ĐẦU khối giao
       hàng: khi có lời hẹn thì đó là thứ khách vào trang này để đọc,
       không phải danh sách đợt đã giao. -->
  <div
    v-if="don.hen_giao"
    style="border: 1px solid var(--orange); border-radius: 8px; padding: 10px; margin-bottom: 12px"
  >
    <p style="margin: 0 0 4px">
      <span class="badge b-orange">{{ don.hen_giao.loai }}</span>
      <b style="margin-left: 8px">Dự kiến giao {{ fmtDate(don.hen_giao.ngay) }}</b>
    </p>
    <p v-if="don.hen_giao.ly_do" class="tag" style="margin: 0">
      {{ don.hen_giao.ly_do }}
    </p>
  </div>
  <template v-if="don.deliveries.length">
    <div v-for="(d, i) in don.deliveries" :key="d.name" style="margin-bottom: 12px">
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
      <!-- E9 (2026-08-16) — kiểm hàng khi nhận. KHÔNG gắn với việc
           khách có kho hay không: `d.kiem_hang` luôn có mặt trên mọi
           đợt giao, `null` nghĩa là khách chưa lập biên bản. -->
      <p class="tag" style="margin-top: 4px">
        <template v-if="d.kiem_hang">
          Kiểm hàng:
          <router-link :to="`/kiem-hang/${d.name}`" style="text-decoration: underline">
            {{ d.kiem_hang.name }}
          </router-link>
          <span
            class="badge"
            :class="kiemHangBadge(d.kiem_hang.trang_thai)"
            style="margin-left: 6px"
          >{{ d.kiem_hang.trang_thai }}</span>
        </template>
        <template v-else>
          <router-link :to="`/kiem-hang/${d.name}`">
            <button class="btn-o btn-sm">Kiểm hàng đợt này</button>
          </router-link>
        </template>
      </p>

      <!-- E7b — hoá đơn nháp lập từ chính phiếu giao này. Neo ở đây
           chứ không ở trang Hoá đơn: chứng từ HĐĐT sinh từ phiếu giao
           có thể chưa có Sales Invoice nào để bám vào. -->
      <template v-if="d.co_hoa_don_nhap">
        <p class="tag" style="margin-top: 4px">
          <span class="badge b-gray">Hoá đơn nháp</span>
          <button class="btn-o btn-sm" style="margin-left: 8px" @click="toggleNhap(d.name)">
            {{ nhapMo === d.name ? '▾ Ẩn hoá đơn nháp' : '▸ Xem hoá đơn nháp' }}
          </button>
        </p>
        <div
          v-if="nhapMo === d.name"
          style="border: 1px solid var(--line); border-radius: 8px; padding: 10px; margin-top: 6px"
        >
          <p v-if="nhapDangTai === d.name" class="tag">Đang tải hoá đơn nháp…</p>
          <HoaDonNhap
            v-else-if="nhapData[d.name]"
            :du-lieu="nhapData[d.name]"
            :url-pdf="urlPdfNhap(d.name)"
          />
          <p v-else class="tag">Phiếu giao này chưa có hoá đơn nháp.</p>
        </div>
      </template>
      <a :href="pdfUrl('Delivery Note', d.name)" target="_blank" rel="noopener">
        <button class="btn-o btn-sm" style="margin-top: 6px">⬇ Phiếu giao đợt {{ dotLabel(d, i) }}</button>
      </a>
    </div>
  </template>
  <p v-else class="tag">Chưa có đợt giao hàng nào.</p>
</template>
