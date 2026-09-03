<script setup>
// Khối "Hoá đơn của đơn này" + nút tải PDF đơn hàng + "Đặt lại đơn này".
// Tách khỏi `OrderDetail.vue` 03/09/2026 để màn chi tiết GỘP dùng lại
// nguyên vẹn — không chép lần hai. Template NHIỀU GỐC (không bọc `<div>`
// ngoài) — cùng lý do đã ghi ở `KhoiGiaoHang.vue`: một wrapper sẽ chèn một
// biên block giữa nút "Đặt lại đơn này" (cuối component này) và nút "Huỷ /
// Sửa đơn" (do OrderDetail.vue render ngay sau, cùng `.card`), đẩy nút đó
// xuống dòng riêng thay vì cùng hàng qua `margin-left: 8px` như bản gốc.
//
// Ruling Task 4 — nút "Huỷ / Sửa đơn" BỎ khỏi đây (đã chuyển sang registry
// `don-actions.js` ở Task 3); nút "Đặt lại đơn này" ở lại nhưng CHỈ phát sự
// kiện `dat-lai`, không tự gọi `datLai()` — hàm đó còn `router.push` sang
// màn Đặt hàng, vẫn thuộc về OrderDetail.vue.
import { fmtVND, fmtDate } from '../../format'

defineProps({
  don: { type: Object, required: true },
  dangDatLai: { type: Boolean, default: false },
})
defineEmits(['dat-lai'])

// Task 4 — chép nguyên, KHÔNG import chéo từ KhoiGiaoHang.vue/OrderDetail.vue:
// bảy dòng ánh xạ URL, cùng lý do `KIEM_HANG_BADGE` đang được giữ hai bản.
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
  <!-- Khoảng trống 2026-08-16 — trước bản này cổng chỉ có mốc "Hoá
       đơn" bật/tắt và một trang Hoá đơn TOÀN CỤC; khách muốn xem hoá
       đơn CỦA ĐƠN NÀY phải tự dò. `don.hoa_don` do
       `portal_order_track` trả về, nối qua Sales Invoice Item. -->
  <template v-if="don.hoa_don && don.hoa_don.length">
    <hr class="sep" />
    <div class="h3">Hoá đơn của đơn này</div>
    <div v-for="h in don.hoa_don" :key="h.name" class="rowline">
      <span>
        <b>{{ h.name }}</b> · {{ fmtDate(h.ngay) }}<br />
        <span class="tag">
          {{ fmtVND(h.tong_tien) }}
          <template v-if="h.con_no > 0"> · còn nợ {{ fmtVND(h.con_no) }}</template>
          <template v-if="h.han_thanh_toan"> · hạn {{ fmtDate(h.han_thanh_toan) }}</template>
        </span>
      </span>
      <a :href="pdfUrl('Sales Invoice', h.name)" target="_blank" rel="noopener">
        <button class="btn-o btn-sm">⬇ PDF</button>
      </a>
    </div>
  </template>

  <hr class="sep" />
  <a :href="pdfUrl('Sales Order', don.order)" target="_blank" rel="noopener">
    <button class="btn-o btn-sm">⬇ PDF đơn hàng</button>
  </a>
  <button
    class="btn-o btn-sm"
    style="margin-left: 8px"
    :disabled="dangDatLai"
    @click="$emit('dat-lai')"
  >
    🔁 Đặt lại đơn này
  </button>
</template>
