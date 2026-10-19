<script setup>
// Một báo giá gửi khách (spec 2026-10-12 §6.3, 2026-10-15 §5.2): cả phiếu khi
// chưa tách đợt, hoặc MỘT đợt. Server quyết định thấy gì, làm gì
// (`hien_gia`, `duoc_dong_y`, `duoc_sua_so_luong`); khối này không tự suy.
import { ref, toRef, computed, watch } from 'vue'
import api from '../api'
import { fmtVND, fmtDate } from '../format'
import { showToast } from '../toast'
import {
  nhanNhomBaoGia, nhomBaoGiaBadge, hanhDongBaoGia, dongDaSua, loiSoLuong,
} from '../bao-gia'
import ReasonModal from './ReasonModal.vue'
import CotTenHang from './CotTenHang.vue'

const props = defineProps({
  bg: { type: Object, required: true },
  // Có tiêu đề = khối của một đợt: vẽ đầu khối riêng (hạn, đơn, nhãn).
  tieuDe: { type: String, default: '' },
})
const emit = defineEmits(['xong'])
const bg = toRef(props, 'bg')

const dangChay = ref('')
const moTuChoi = ref(false)
const dangSua = ref(false)
const soLuongMoi = ref({})

const hanhDong = computed(() => hanhDongBaoGia(bg.value))
const pdfUrl = computed(() =>
  `/api/method/miyano_portal.api.portal.portal_bao_gia_pdf?quotation=${encodeURIComponent(bg.value?.bao_gia || '')}`)

function datLaiSoLuong() {
  soLuongMoi.value = Object.fromEntries((bg.value?.items || []).map((it) => [it.name, it.qty]))
}

// Server trả bản mới sau mỗi thao tác: ô sửa về số lượng đang có.
watch(bg, () => { datLaiSoLuong(); dangSua.value = false }, { immediate: true })

// Tắt chế độ sửa là HUỶ: các ô trở về số lượng đang có, để lần mở sau không
// mang theo con số gõ dở của lần trước.
function batTatSua() {
  if (dangSua.value) datLaiSoLuong()
  dangSua.value = !dangSua.value
}

async function chay(ten, viec, thanhCong) {
  if (dangChay.value) return
  dangChay.value = ten
  try {
    await viec()
    showToast(thanhCong)
    emit('xong')
  } catch (e) {
    showToast(e.message || 'Không thực hiện được thao tác này.', 'error')
  } finally {
    dangChay.value = ''
  }
}

const dongY = () => chay(
  'dong_y',
  () => api.call('portal_bao_gia_dong_y', { ten: bg.value.bao_gia }),
  'Đã đồng ý — đơn hàng đã được tạo và chuyển cho Miyano xác nhận.',
)

// Hộp lý do chỉ đóng khi server đã nhận: lỗi thì hộp còn mở, lý do vừa gõ còn
// nguyên để gửi lại.
function tuChoi(lyDo) {
  return chay(
    'tu_choi',
    async () => {
      await api.call('portal_bao_gia_tu_choi', { ten: bg.value.bao_gia, ly_do: lyDo || undefined })
      moTuChoi.value = false
    },
    'Đã từ chối báo giá.',
  )
}

function guiSuaSoLuong() {
  // Số 0, số âm, ô trống: chặn và nói rõ dòng nào, không lặng lẽ bỏ dòng đó
  // khỏi lời gửi rồi báo thành công.
  const loi = loiSoLuong(bg.value.items, soLuongMoi.value)
  if (loi) return showToast(loi, 'error')
  const dong = dongDaSua(bg.value.items, soLuongMoi.value)
  if (!dong.length) return showToast('Chưa sửa số lượng dòng nào.', 'error')
  return chay(
    'sua_so_luong',
    () => api.call('portal_bao_gia_sua_so_luong', { ten: bg.value.bao_gia, dong: JSON.stringify(dong) }),
    'Đã gửi lại — Miyano sẽ xem lại giá theo số lượng mới.',
  )
}
</script>

<template>
  <div class="mb10">
    <div v-if="tieuDe" class="card mb10">
      <div class="sb">
        <div class="h3" style="margin: 0">{{ tieuDe }}</div>
        <span class="badge" :class="bg.da_tra_ve ? 'b-gray' : nhomBaoGiaBadge(bg.nhom)">
          {{ bg.da_tra_ve ? 'Đã trả về phiếu' : nhanNhomBaoGia(bg.nhom) }}
        </span>
      </div>
      <p class="tag" style="margin-top: 4px">
        Báo giá {{ bg.bao_gia }}
        <template v-if="bg.han_hieu_luc"> · hiệu lực đến <b>{{ fmtDate(bg.han_hieu_luc) }}</b></template>
      </p>
      <p v-if="bg.da_tra_ve" class="tag" style="margin-top: 6px">
        Các mặt hàng của đợt này đã trả về phiếu để Miyano báo giá lại.
      </p>
      <p v-if="bg.ly_do_tu_choi" class="tag" style="margin-top: 6px; color: var(--red)">
        Lý do từ chối: {{ bg.ly_do_tu_choi }}
      </p>
      <p v-if="bg.sales_order" style="margin-top: 6px">
        <router-link :to="{ name: 'order-detail', params: { name: bg.sales_order } }">
          Xem đơn hàng {{ bg.sales_order }} →
        </router-link>
      </p>
    </div>

    <div v-if="hanhDong.length" class="card mb10">
      <div class="h3">Việc đang chờ bạn</div>
      <p class="tag" style="margin-bottom: 10px">
        Bấm <b>Đồng ý</b> = chấp nhận đặt hàng theo giá dưới đây. Hệ thống ghi lại người bấm và thời điểm.
      </p>
      <div class="flex" style="flex-wrap: wrap">
        <button class="btn-g" :disabled="!!dangChay" @click="dongY">
          {{ dangChay === 'dong_y' ? 'Đang gửi…' : (tieuDe ? '✔ Đồng ý cả đợt' : '✔ Đồng ý báo giá') }}
        </button>
        <button class="btn-o" :disabled="!!dangChay" @click="moTuChoi = true">✕ Từ chối…</button>
        <button v-if="hanhDong.includes('sua_so_luong')" class="btn-o" :disabled="!!dangChay"
                @click="batTatSua">{{ dangSua ? '✕ Huỷ sửa số lượng' : '✎ Sửa số lượng' }}</button>
        <a class="btn-o nut-pdf" :href="pdfUrl" target="_blank" rel="noopener">⬇ Tải báo giá (PDF)</a>
      </div>
    </div>
    <!-- Hết việc phải làm nhưng vẫn được xem giá: báo giá còn tải về được. -->
    <div v-else-if="bg.hien_gia" class="mb10">
      <a class="btn-o nut-pdf" :href="pdfUrl" target="_blank" rel="noopener">⬇ Tải báo giá (PDF)</a>
    </div>

    <div v-if="!bg.hien_gia && bg.nhom === 'dang_bao_gia'" class="card mb10">
      <span class="badge b-blue">Miyano đang báo giá</span>
      <span class="tag"> Đơn giá sẽ hiện khi Miyano gửi báo giá cho quý vị.</span>
    </div>

    <!-- Ba cột Mã / Tên mặt hàng / Tên thường gọi theo quy tắc chung của mọi
         bảng mặt hàng trên cổng (`CotTenHang`, `ten-hang.js`); bảng rộng hơn
         khung thì cuộn ngang trong thẻ. Cột giá CHỈ vẽ khi server cho xem
         (`bg.hien_gia`) — lúc đó `rate`/`amount` mới khác `null`. -->
    <div class="card mb10" style="padding: 0; overflow-x: auto">
      <div class="h3" style="padding: 12px 14px 0">Mặt hàng</div>
      <table>
        <thead>
          <tr>
            <CotTenHang head />
            <th>ĐVT</th><th class="right">Số lượng</th>
            <th v-if="bg.hien_gia" class="right">Đơn giá</th>
            <th v-if="bg.hien_gia" class="right">Thành tiền</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="it in bg.items" :key="it.name">
            <CotTenHang :ma="it.item_code" :ten="it.item_name || ''" />
            <td>{{ it.uom }}</td>
            <td class="right">
              <input v-if="dangSua" v-model.number="soLuongMoi[it.name]" type="number" min="0.001"
                     step="any" style="width: 90px; text-align: right" />
              <template v-else>{{ it.qty }}</template>
            </td>
            <td v-if="bg.hien_gia" class="right">{{ fmtVND(it.rate) }}</td>
            <td v-if="bg.hien_gia" class="right">{{ fmtVND(it.amount) }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="bg.hien_gia" class="right" style="padding: 10px 14px">
        <b>Tổng cộng: {{ fmtVND(bg.tong_tien) }}</b>
      </p>
      <div v-if="dangSua" class="flex" style="padding: 0 14px 12px; flex-wrap: wrap">
        <button class="btn" :disabled="!!dangChay" @click="guiSuaSoLuong">
          {{ dangChay === 'sua_so_luong' ? 'Đang gửi…' : 'Gửi lại để báo giá' }}
        </button>
        <span class="tag">Miyano xem lại giá theo số lượng mới rồi gửi báo giá lại. Muốn bỏ hẳn thì từ chối báo giá.</span>
      </div>
    </div>

    <ReasonModal
      :open="moTuChoi"
      title="Từ chối báo giá"
      desc="Lý do không bắt buộc, nhưng giúp Miyano báo giá sát hơn ở lần sau."
      placeholder="VD: Giá cao hơn nhà cung cấp hiện tại…"
      :min-len="0"
      :submitting="dangChay === 'tu_choi'"
      submit-label="Từ chối báo giá"
      @submit="tuChoi"
      @close="moTuChoi = false"
    />
  </div>
</template>

<style scoped>
/* Liên kết tải PDF mang dáng nút `.btn-o` (vốn viết cho <button>). */
.nut-pdf {
  display: inline-block;
  text-decoration: none;
  font-size: 14px;
}
</style>
