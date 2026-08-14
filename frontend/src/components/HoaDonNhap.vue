<script setup>
// Khối "Hoá đơn nháp" dùng chung cho HAI màn hình (Hoá đơn & công nợ, Chi
// tiết đơn hàng). Thứ tự ưu tiên dưới đây là RÀNG BUỘC nghiệp vụ, không phải
// sở thích trình bày: thứ khách phải thấy là CHÍNH FILE PDF DO FAST DỰNG.
// Bảng dòng hàng do cổng tự vẽ chỉ là DỰ PHÒNG cho lúc Fast chưa dựng xong
// (trạng thái 01 — kế toán chưa bấm "Xem bản nháp") hoặc gọi Fast lỗi.
import { ref, onBeforeUnmount, watch } from 'vue'
import api from '../api'
import { fmtVND, fmtDate } from '../format'
import { useIsMobile } from '../useMobile'
import { showToast } from '../toast'

const props = defineProps({
  // URL endpoint tải PDF nháp (đã kèm tham số), hoặc '' khi chưa có file.
  urlPdf: { type: String, default: '' },
  // Khối dữ liệu dự phòng: { canh_bao, loai, ngay, dong[], tien_hang, ... }
  duLieu: { type: Object, default: null },
})

const isMobile = useIsMobile()
const blobUrl = ref('')
const dangTai = ref(false)

function huyBlob() {
  if (blobUrl.value) {
    URL.revokeObjectURL(blobUrl.value)
    blobUrl.value = ''
  }
}
onBeforeUnmount(huyBlob)

// Trên màn hình hẹp KHÔNG dựng <iframe>: phần lớn trình duyệt di động
// (Chrome/Safari trên Android/iOS) không render PDF trong iframe — khung sẽ
// trắng hoặc tự tải file, và một khung trắng trông y hệt "hệ thống hỏng".
// Ở đó dùng nút mở tab mới.
watch(
  () => props.urlPdf,
  async (url) => {
    huyBlob()
    if (!url || isMobile.value) return
    dangTai.value = true
    try {
      blobUrl.value = await api.fetchBlobUrl(url)
    } catch (e) {
      showToast(e.message || 'Không mở được hoá đơn nháp.', 'error')
    } finally {
      dangTai.value = false
    }
  },
  { immediate: true }
)

async function moTabMoi() {
  try {
    const url = blobUrl.value || (await api.fetchBlobUrl(props.urlPdf))
    blobUrl.value = url
    window.open(url, '_blank', 'noopener')
  } catch (e) {
    showToast(e.message || 'Không mở được hoá đơn nháp.', 'error')
  }
}

async function taiVe() {
  try {
    await api.downloadFile(props.urlPdf, 'hoa-don-nhap.pdf')
  } catch (e) {
    showToast(e.message || 'Không tải được hoá đơn nháp.', 'error')
  }
}
</script>

<template>
  <div>
    <!-- Cảnh báo pháp lý do SERVER trả (einvoice.CANH_BAO_NHAP) — không gõ
         lại ở đây: một lần sửa giao diện làm rơi mất nó là một lần khách
         tưởng mình đang cầm chứng từ thuế. -->
    <div v-if="duLieu && duLieu.canh_bao" class="note">⚠ {{ duLieu.canh_bao }}</div>

    <template v-if="urlPdf">
      <p v-if="dangTai" class="tag">Đang mở hoá đơn nháp…</p>
      <iframe
        v-else-if="blobUrl && !isMobile"
        :src="blobUrl"
        title="Hoá đơn nháp"
        style="width: 100%; height: 70vh; border: 1px solid var(--line); border-radius: 8px"
      ></iframe>
      <button v-else class="btn-o btn-sm" @click="moTabMoi">📄 Mở hoá đơn nháp</button>
      <p style="margin-top: 8px">
        <button class="btn-o btn-sm" @click="taiVe">⬇ Tải hoá đơn nháp</button>
      </p>
    </template>

    <!-- DỰ PHÒNG: Fast chưa dựng xong file. -->
    <template v-else-if="duLieu">
      <p class="tag">
        Bản in thử PDF đang được tạo — nội dung hoá đơn nháp xem đầy đủ bên dưới.
      </p>
      <p class="tag">
        {{ duLieu.loai || 'Hoá đơn gốc' }}
        <template v-if="duLieu.ngay"> · Ngày hoá đơn dự kiến: {{ fmtDate(duLieu.ngay) }}</template>
      </p>
      <div v-if="duLieu.dong && duLieu.dong.length" style="overflow-x: auto; margin-top: 8px">
        <table>
          <thead>
            <tr>
              <th>#</th><th>Mặt hàng</th><th class="right">SL</th>
              <th class="right">Đơn giá</th><th class="right">Thành tiền</th><th class="right">Thuế</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="dong in duLieu.dong" :key="dong.stt">
              <td>{{ dong.stt }}</td>
              <td>
                <b class="mono">{{ dong.ma }}</b>
                <template v-if="dong.ten"><br /><span style="font-size: 13px">{{ dong.ten }}</span></template>
              </td>
              <td class="right">{{ dong.so_luong }} {{ dong.dvt }}</td>
              <td class="right">{{ fmtVND(dong.don_gia) }}</td>
              <td class="right">{{ fmtVND(dong.thanh_tien) }}</td>
              <td class="right">
                {{ dong.thue_suat ? dong.thue_suat + '%' : '—' }}<br />
                <span class="tag">{{ fmtVND(dong.tien_thue) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p v-if="duLieu.tong_tien != null" style="margin-top: 8px; text-align: right">
        <span class="tag">
          Tiền hàng {{ fmtVND(duLieu.tien_hang) }} · Thuế GTGT {{ fmtVND(duLieu.tien_thue) }}
        </span><br />
        <b>Tổng thanh toán: {{ fmtVND(duLieu.tong_tien) }}</b>
      </p>
    </template>
  </div>
</template>
