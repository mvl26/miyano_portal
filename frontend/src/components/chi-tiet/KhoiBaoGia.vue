<script setup>
// Banner "Chờ bạn đồng ý" (E6/F-07 [MỚI — QĐ-6]) + khối sửa số lượng trước
// khi gửi lại báo giá (Việc 1/brief 2026-08-15). Tách khỏi `OrderDetail.vue`
// 03/09/2026 để màn chi tiết GỘP dùng lại nguyên vẹn — không chép lần hai.
//
// Ruling Task 4 — ba nút hành động (Đồng ý / Không đồng ý / Huỷ đơn) KHÔNG
// vào đây: chúng chuyển sang registry `don-actions.js` (Task 3) và Task 7 sẽ
// dựng thanh hành động chung render chúng. Cho tới lúc đó `OrderDetail.vue`
// vẫn phải TỰ hiện ba nút này (không được mất chức năng giữa chừng), nên
// component này để lỗ hai slot đúng vị trí cũ của chúng thay vì ôm luôn —
// vị trí DOM/flex phải giữ y hệt bản gốc, không phải thứ tự mới do ghép lại.
import { computed, ref, watch } from 'vue'
import { fmtVND, fmtDate } from '../../format'
import { showToast } from '../../toast'

const props = defineProps({
  don: { type: Object, required: true },
  dangGui: { type: Boolean, default: false },
})
const emit = defineEmits(['sua-so-luong'])

// LOAI_DON_BAO_GIA — bản sao THÊM của giá trị `"Mua lẻ"` (xem chú thích đầy
// đủ về các bản khác ở `OrderDetail.vue`, nơi giữ bản dùng cho
// `coHangChoBaoGia`). Component này cần riêng một bản vì `suaDuocSoLuong` —
// cái CHỐT bật/tắt khối sửa số lượng — chỉ dùng ở đây sau khi tách.
const LOAI_DON_BAO_GIA = 'Mua lẻ'
// CHỐT — soi gương HAI trong các điều kiện của
// `portal.portal_order_sua_so_luong`. Nói cho hết, vì một chú thích khai
// khống "soi gương chốt server" còn tệ hơn không có chú thích:
//   * chốt loại đơn (`portal_mua_le.di_vong_bao_gia`) — soi qua `loai_don`;
//   * guard VAI TRÒ `dam_bao_duoc_sua_don_da_duyet` (Task 9) — soi qua
//     `duoc_sua_da_duyet`, câu TRẢ LỜI server tự tính và trả ra
//     (`portal_context.duoc_sua_don_da_duyet`). KHÔNG suy lại từ dữ kiện:
//     `ma_tra_cuu` KHÔNG phải bản sao của `custom_de_xuat` (quản lý đặt
//     thẳng cho khách chưa khai Mã ngắn thì `custom_de_xuat` có mà
//     `ma_tra_cuu` rỗng), và nhánh thiếu cột thì mọi dữ kiện client đều nói
//     "được sửa" trong khi server chặn;
//   * `workflow_state == "Chờ khách đồng ý"` — KHÔNG soi ở đây, component
//     này chỉ được dựng khi `chap_nhan.can_dong_y` đã đúng ở cha;
//   * hiệu lực báo giá — `chap_nhan.can_dong_y` đã mang câu trả lời đó.
// `!== false` chứ không `=== true`, CÓ CHỦ Ý và KHÁC với `portal_context.py`
// (nơi thiếu cột thì CHẶN chứ không thả). Bất đối xứng đó đúng vì hai bên
// canh hai rủi ro khác nhau: server là nơi cuối cùng, thả nhầm ở đó là lỗ
// hổng THẬT; còn ở đây khoá vắng mặt chỉ có thể do phục vụ một bản backend
// cũ hơn bundle này, và khi đó `=== true` sẽ giấu khối sửa số lượng khỏi CẢ
// quản lý — lấy mất một chức năng đang chạy để phòng một lỗi mà server vẫn
// tự chặn được. Server không bao giờ mất quyền nói không.
const suaDuocSoLuong = computed(
  () => props.don?.loai_don === LOAI_DON_BAO_GIA && props.don?.duoc_sua_da_duyet !== false
)

// Việc 1/brief 2026-08-15 (bao-gia-hai-chieu) — khách sửa số lượng ngay
// trong khối "Chờ bạn đồng ý". Hai map RIÊNG (items theo item_code,
// dat_ngoai theo `name`) — khớp đúng khoá endpoint `portal_order_sua_so_
// luong` dùng để tìm dòng ĐÃ CÓ trên đơn (server chỉ đọc item_code/name +
// qty, mọi field khác trong payload đều bị bỏ qua/từ chối).
const soLuongMoiItems = ref({})
const soLuongMoiDatNgoai = ref({})
function initSoLuongMoi() {
  soLuongMoiItems.value = Object.fromEntries((props.don?.items || []).map((it) => [it.item_code, it.qty]))
  soLuongMoiDatNgoai.value = Object.fromEntries((props.don?.dat_ngoai || []).map((d) => [d.name, d.so_luong]))
}
// Bản gốc gọi `initSoLuongMoi()` trong `load()` của OrderDetail.vue (mọi lần
// tải lại đơn) — ở đây `don` là prop, nên dùng watch (immediate để phủ cả
// lần mount đầu) để cùng một chốt: sửa số lượng luôn khởi từ dữ liệu MỚI
// NHẤT, không phải dữ liệu lúc component dựng.
watch(() => props.don, initSoLuongMoi, { immediate: true })

// Việc 1/brief 2026-08-15 — "Gửi lại để báo giá": chỉ gửi CÁC DÒNG THẬT SỰ
// đổi số lượng (không gửi nguyên giỏ) — payload gọn, và tránh gửi field
// `rate`/`item_code` mà server không cần.
//
// Task 4 — trước bản này hàm này chỉ validate rồi mở modal xác nhận NGAY
// tại đây; modal xác nhận (ReasonModal) và lời gọi API thật vẫn ở
// `OrderDetail.vue` (controller ruling 2026-08-16 đòi modal KHÔNG đóng khi
// API lỗi, để khách bấm lại từ modal — cha `await` được API, component này
// thì không), nên hàm này giờ tính sẵn phần chênh lệch rồi PHÁT sự kiện,
// cha nhận `dong` để mở modal.
function moGuiLai() {
  const coDoi =
    (props.don.items || []).some(
      (it) => Number(soLuongMoiItems.value[it.item_code]) !== Number(it.qty)
    ) ||
    (props.don.dat_ngoai || []).some(
      (d) => Number(soLuongMoiDatNgoai.value[d.name]) !== Number(d.so_luong)
    )
  if (!coDoi) {
    showToast('Chưa sửa số lượng dòng nào.', 'error')
    return
  }
  const doiItems = (props.don.items || [])
    .filter((it) => Number(soLuongMoiItems.value[it.item_code]) !== Number(it.qty))
    .map((it) => ({ item_code: it.item_code, qty: Number(soLuongMoiItems.value[it.item_code]) }))
  const doiDatNgoai = (props.don.dat_ngoai || [])
    .filter((d) => Number(soLuongMoiDatNgoai.value[d.name]) !== Number(d.so_luong))
    .map((d) => ({ name: d.name, qty: Number(soLuongMoiDatNgoai.value[d.name]) }))
  emit('sua-so-luong', { items: doiItems, dat_ngoai: doiDatNgoai })
}
</script>

<template>
  <div class="card mb10" style="margin-bottom: 14px">
    <div class="note" style="background: #fff7ed; border-color: #fed7aa; color: #9a3412">
      ⏳ <b>Báo giá hiệu lực đến {{ fmtDate(don.chap_nhan.han_hieu_luc) }}.</b>
      Sau ngày này đơn tự đóng — cần hàng phải yêu cầu báo giá lại. <span class="newtag">MỚI</span>
    </div>
    <p style="font-size: 13px; margin: 8px 0 10px">
      Bấm <b>Đồng ý</b> = chấp nhận đặt hàng theo giá trên. Hệ thống ghi lại người bấm và thời điểm.
    </p>
    <div class="flex" style="flex-wrap: wrap">
      <!-- Ruling Task 4 — hai nút Đồng ý / Không đồng ý do OrderDetail.vue
           render, giữ đúng vị trí cùng hàng với link PDF như bản gốc. -->
      <slot name="hanh-dong" />
      <a
        class="btn-o"
        :href="`/api/method/miyano_portal.api.portal.portal_bao_gia_pdf?order=${encodeURIComponent(don.order)}`"
        target="_blank"
        rel="noopener"
      >⬇ Tải báo giá (PDF)</a>
    </div>

    <!-- Việc 1/brief 2026-08-15 — sửa số lượng NGAY tại đây, chỉ cho
         đơn đi vòng báo giá (đúng điều kiện server
         `portal_order_sua_so_luong` đòi, xem `portal_mua_le.
         di_vong_bao_gia`). Đơn giá cho N hộp không còn đúng ở M hộp —
         gửi lại là để sales báo giá lại, KHÔNG giữ giá cũ (server tự
         đặt rate = 0 cho dòng đã đổi). -->
    <div v-if="suaDuocSoLuong" style="margin-top: 14px; border-top: 1px solid var(--line); padding-top: 12px">
      <p style="font-size: 13px; margin-bottom: 8px">
        Số lượng chưa đúng? Sửa rồi bấm <b>Gửi lại để báo giá</b> — đơn sẽ
        về Miyano báo giá lại theo số lượng mới (giá hiện tại của dòng đã
        đổi không còn áp dụng).
      </p>
      <div v-for="it in don.items" :key="'sl-' + it.item_code" class="rowline">
        <span>
          <b>{{ it.item_code }}</b> — {{ it.item_name }}
          <br /><span class="tag">{{ it.uom }} · hiện {{ it.qty }} · {{ fmtVND(it.rate) }}/{{ it.uom }}</span>
        </span>
        <input
          type="number" min="0" step="any"
          v-model.number="soLuongMoiItems[it.item_code]"
          style="width: 90px; text-align: right"
        />
      </div>
      <div v-for="d in don.dat_ngoai" :key="'sl-dn-' + d.name" class="rowline">
        <span>
          <b>{{ d.ten_hang }}</b>
          <br /><span class="tag">{{ d.dvt }} · hiện {{ d.so_luong }} (đặt ngoài)</span>
        </span>
        <input
          type="number" min="0" step="any"
          v-model.number="soLuongMoiDatNgoai[d.name]"
          style="width: 90px; text-align: right"
        />
      </div>
      <button class="btn-o" style="margin-top: 8px" :disabled="dangGui" @click="moGuiLai">
        {{ dangGui ? 'Đang gửi…' : '✎ Gửi lại để báo giá' }}
      </button>
    </div>

    <!-- Việc 2/brief 2026-08-15 — Huỷ đơn = HUỶ THẬT (khác requestCancel
         ở OrderDetail.vue — đó chỉ ghi yêu cầu chờ xử lý, dùng cho đơn đã xác
         nhận). Áp cho MỌI loại đơn đang ở trạng thái này (server không
         giới hạn theo custom_loai_don), không chỉ Mua lẻ. Nút thật do
         OrderDetail.vue render (ruling Task 4) — xem slot "huy". -->
    <div style="margin-top: 10px; border-top: 1px solid var(--line); padding-top: 10px">
      <slot name="huy" />
    </div>
  </div>
</template>
