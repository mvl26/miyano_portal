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

// Chủ đầu tư chốt 05/09/2026 — nút PDF của HOÁ ĐƠN phải giao BẢN THỂ HIỆN
// HOÁ ĐƠN ĐIỆN TỬ của Fast, không phải bản in của ERP. Trước bản này khối
// dưới dùng `pdfUrl('Sales Invoice', …)`, tức `portal_document_download` —
// cùng một nút "PDF" trên hai màn hình giao hai tờ giấy khác nhau cho cùng
// một hoá đơn, và tờ ở đây không phải chứng từ thuế.
//
// ĐÚNG endpoint mà trang "Hoá đơn & công nợ" (`Invoices.vue`) đang dùng —
// không dựng đường tải thứ hai. KHÔNG truyền `fei`: bỏ trống thì server tự
// chọn bản ghi chính qua `chon_ban_ghi_chinh()`, đúng bản mà `hddt_tai_duoc`
// vừa tính cờ cho. Truyền tay một tên ở đây là mở chỗ cho hai bên lệch nhau.
//
// `pdfUrl('Sales Order', …)` bên dưới GIỮ NGUYÊN bản in ERP — đơn hàng vốn
// là chứng từ của ERP, không phải hoá đơn.
function hddtUrl(invoiceName) {
  return (
    '/api/method/miyano_portal.api.portal.portal_einvoice_download?invoice=' +
    encodeURIComponent(invoiceName)
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
        <!-- Số hoá đơn BẤM ĐƯỢC (chủ đầu tư chốt 05/09/2026) — mở trang Hoá
             đơn & công nợ với đúng dòng này đã xổ sẵn. KHÔNG dựng màn chi
             tiết hoá đơn riêng: trang đó đã có đủ trạng thái HĐĐT, bản
             chính, mọi bản điều chỉnh/thay thế và nút yêu cầu hỗ trợ —
             dựng màn thứ hai làm cùng một việc đúng là lỗi mà
             `docs/BAN-DO-CHUC-NANG.md` mục 4 ghi nhận đã lọt bốn lần. -->
        <router-link :to="{ name: 'invoices', query: { 'hoa-don': h.name } }">
          <b>{{ h.name }}</b>
        </router-link>
        · {{ fmtDate(h.ngay) }}<br />
        <span class="tag">
          {{ fmtVND(h.tong_tien) }}
          <template v-if="h.con_no > 0"> · còn nợ {{ fmtVND(h.con_no) }}</template>
          <template v-if="h.han_thanh_toan"> · hạn {{ fmtDate(h.han_thanh_toan) }}</template>
          <template v-if="h.hddt_so"> · số {{ h.hddt_so }}</template>
        </span>
      </span>
      <!-- Chưa phát hành thì KHÔNG hiện nút, hiện trạng thái — "hide, don't
           disable" (xem đầu `de-xuat-actions.js`): một nút bấm vào là lỗi
           dạy người dùng sợ thanh công cụ. -->
      <a
        v-if="h.hddt_tai_duoc"
        :href="hddtUrl(h.name)"
        target="_blank"
        rel="noopener"
      >
        <button class="btn-o btn-sm">⬇ PDF</button>
      </a>
      <span v-else class="tag">{{ h.hddt_nhan || 'Miyano đang xử lý hoá đơn điện tử' }}</span>
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
