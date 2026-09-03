<script setup>
// Khối truy vết của phiếu đề xuất: ai xin, xin lúc nào, vì sao, ai duyệt.
// Tách khỏi `DeXuatDetail.vue` 03/09/2026 cho màn chi tiết GỘP.
//
// Bọc `<details>` vì trên màn gộp khối này KHÔNG phải lúc nào cũng là câu
// hỏi đang sống. Đơn đã giao xong thì thứ người ta mở trang để đọc là "hàng
// đâu, hoá đơn đâu"; con số duyệt là chuyện đã xong. Nhưng nó là dữ liệu
// ĐỐI CHIẾU khi có tranh cãi ("khoa xin 100, ai hạ xuống 40?"), nên THU
// GỌN, không giấu — một cú bấm là ra, và chữ trên nhãn nói sẵn nó chứa gì.
import { computed } from 'vue'
import { fmtDateTime } from '../../format'

const props = defineProps({
  phieu: { type: Object, required: true },
  moSan: { type: Boolean, default: true },
})

// Chủ đầu tư chốt 25/08 — hiện CẢ tên hiển thị LẪN tên tài khoản. Lý do đo
// được trên site: tài khoản cổng của bệnh viện đặt `User.full_name` bằng
// chính tên bệnh viện/khoa, nên chỉ hiện tên là khối truy vết mất sạch giá
// trị nhận dạng NGƯỜI. Chỉ ghép khi hai thứ KHÁC nhau (tài khoản đã xoá thì
// server lui về chính email, ghép nữa sẽ thành "a@b.com (a@b.com)").
const nguoiYeuCau = computed(() => {
  const d = props.phieu
  const taiKhoan = d.nguoi_yeu_cau || d.owner || ''
  const ten = d.nguoi_yeu_cau_ten || taiKhoan
  return { ten, taiKhoan: ten === taiKhoan ? '' : taiKhoan }
})
</script>

<template>
  <details class="card mb10" :open="moSan" style="margin-bottom: 14px">
    <summary style="cursor: pointer; font-weight: 600">
      Yêu cầu &amp; duyệt
      <span class="tag" style="font-weight: 400">
        — ai xin, xin lúc nào, ai duyệt
      </span>
    </summary>
    <div style="margin-top: 12px; border-top: 1px solid var(--line); padding-top: 10px">
      <p class="tag" style="font-size: 12px; text-transform: uppercase; letter-spacing: 0.03em; margin-bottom: 6px">
        Truy vết yêu cầu
      </p>
      <p style="font-size: 13px; margin-bottom: 2px">
        <!-- Chủ đầu tư chốt 21/08 — TÊN NGƯỜI, không phải email; chốt
             25/08 — kèm TÊN TÀI KHOẢN, vì `full_name` của tài khoản cổng
             chính là tên bệnh viện. Tên do server suy
             (`de_xuat_chi_tiet` → `portal_context.ten_nguoi_dung`),
             KHÔNG tra ở đây: hai nơi cùng quyết định "hiện tên thế nào"
             sớm muộn cũng lệch, và tầng này không đọc được `tabUser`.
             Đường lui về email vẫn còn trong `nguoiYeuCau` cho một
             payload cũ trong bộ nhớ đệm — ô trống ở khối truy vết là
             mất dấu vết. -->
        <b>Người yêu cầu:</b>
        {{ nguoiYeuCau.ten }}
        <span v-if="nguoiYeuCau.taiKhoan" class="tag">({{ nguoiYeuCau.taiKhoan }})</span>
      </p>
      <p style="font-size: 13px; margin-bottom: 2px">
        <b>Thời điểm gửi:</b> {{ phieu.thoi_diem_gui ? fmtDateTime(phieu.thoi_diem_gui) : 'Chưa gửi' }}
      </p>
      <p style="font-size: 13px">
        <b>Lý do yêu cầu:</b>
        <span v-if="phieu.ly_do_yeu_cau"> {{ phieu.ly_do_yeu_cau }}</span>
        <span v-else class="tag"> Chưa có</span>
      </p>
    </div>
  </details>
</template>
