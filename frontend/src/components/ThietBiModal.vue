<script setup>
import { ref, watch, computed, onMounted } from 'vue'
import api from '../api'
import { store } from '../store'
import { showToast } from '../toast'
import { useIsMobile } from '../useMobile'

const props = defineProps({
  open: { type: Boolean, default: false },
  initial: { type: Object, default: () => ({}) },
  mode: { type: String, default: 'tao' }, // 'tao' | 'sua'
})
const emit = defineEmits(['saved', 'close'])

const isMobile = useIsMobile()
const saving = ref(false)

// 11 ô nhận từ client (`ma_thiet_bi`..`ghi_chu`) + `name`/`active` — brief gốc
// nói "12 ô" nhưng liệt kê đúng 11 (cùng khuôn "sáu ô" hoá ra năm của
// `thiet_bi.py` TRUONG_TAO_NHANH — đếm sai chứ không phải thiếu trường).
const form = ref({
  name: '', ma_thiet_bi: '', ten_thiet_bi: '', khoa_phong: '', active: 1,
  hang_san_xuat: '', xuat_xu: '', model: '', so_serial: '', nam_san_xuat: '',
  ngay_lap_dat: '', ghi_chu: '',
})

// BR-TB-6 — server ÉP khoa phòng theo phiên cho Nhân viên khoa, KHÔNG NHẬN
// giá trị client gửi. Đây là khoá RIÊNG (`la_quan_ly`, giống mọi màn khác
// của cổng — App.vue/LapPhieu.vue), KHÔNG tự suy từ `vai_tro === 'Quản lý'`.
const laNhanVienKhoa = computed(() => !store.me?.la_quan_ly)

// Danh sách khoa phòng cho Ô CHỌN của Quản lý — GỌI kho_khoa_phong_list_khach
// (Task 12b), KHÔNG PHẢI kho_khoa_phong_list mà PhieuXuat.vue/NhatKy.vue/...
// dùng. kho_khoa_phong_list suy kho qua get_portal_kho() và ném lỗi khi
// khách chưa mở kho trên cổng — đúng cho các màn phiếu nhưng SAI ở đây:
// spec đề án §4.1 cố ý treo Customer Equipment vào Customer (không Customer
// Warehouse) CHÍNH VÌ "Bệnh viện chưa mở kho trên cổng vẫn khai được máy".
// kho_khoa_phong_list_khach suy khách hàng thẳng từ phiên, không cần kho.
const khoaPhongList = ref([])
const khoaPhongLoi = ref(false)
onMounted(async () => {
  try {
    khoaPhongList.value = await api.callKho('kho_khoa_phong_list_khach', { ca_inactive: 1 })
  } catch (e) {
    // Không nuốt câm — ghiChuKhoaRong bên dưới phân biệt "gọi lỗi" với
    // "danh sách rỗng thật", hai câu giải thích khác nhau.
    khoaPhongLoi.value = true
  }
})

// Ô Khoa phòng rỗng có BA nguyên nhân khác nhau — bài học Task 12
// (ThietBiList.vue): câu giải thích phải đúng NGUYÊN NHÂN thật, không gộp
// chung một câu cho mọi trường hợp trống.
const ghiChuKhoaRong = computed(() => {
  if (khoaPhongList.value.length > 0) return ''
  if (khoaPhongLoi.value) {
    return 'Không tải được danh sách khoa phòng. Thử lại hoặc liên hệ nhân viên kinh doanh Miyano.'
  }
  if (laNhanVienKhoa.value) {
    // pham_vi_don() ở server fail-closed (ném lỗi) khi tài khoản Nhân viên
    // khoa active mà thiếu khoa_phong — nên gọi thành công mà vẫn rỗng ở
    // đây nghĩa là khoa của họ không còn tồn tại/đã đổi, một sự cố cấu
    // hình, không phải "đơn vị chưa khai khoa nào".
    return 'Không tìm thấy khoa phòng của bạn. Liên hệ quản lý đơn vị bạn để kiểm tra lại.'
  }
  return 'Đơn vị bạn chưa khai khoa phòng nào. Có thể lưu máy là "Dùng chung" — liên hệ nhân viên kinh doanh Miyano nếu cần khai khoa phòng.'
})

watch(
  () => props.open,
  (v) => {
    if (!v) return
    form.value = {
      name: '', ma_thiet_bi: '', ten_thiet_bi: '', khoa_phong: '', active: 1,
      hang_san_xuat: '', xuat_xu: '', model: '', so_serial: '', nam_san_xuat: '',
      ngay_lap_dat: '', ghi_chu: '',
      ...props.initial,
    }
    // Tạo mới bởi Nhân viên khoa: ô Khoa phòng đặt sẵn khoa của họ — GIAO
    // DIỆN CHỈ PHẢN ÁNH sự thật server sẽ ép, không phải cơ chế bảo vệ (server
    // ép lại dù client gửi gì đi nữa, xem `_khoa_ep_theo_phien()` trong
    // `kho/thiet_bi.py`).
    if (laNhanVienKhoa.value && props.mode === 'tao') {
      form.value.khoa_phong = store.me?.khoa_phong || ''
    }
  },
  { immediate: true }
)

// Máy dùng chung (`khoa_phong` rỗng) đang SỬA bởi Nhân viên khoa: server ném
// PermissionError (`_chan_sua_ngoai_pham_vi`, "Máy dùng chung không thuộc
// khoa nào — chỉ quản lý đơn vị sửa được."). Để họ bấm rồi ăn lỗi đó là thiết
// kế tồi — khoá toàn bộ ô NGAY TỪ ĐẦU và không hiện nút Lưu.
const khoaHoanToan = computed(
  () => laNhanVienKhoa.value && props.mode === 'sua' && !form.value.khoa_phong
)

async function onSave() {
  if (saving.value || khoaHoanToan.value) return
  saving.value = true
  try {
    // Gửi nguyên form — kể cả `khoa_phong` của Nhân viên khoa (ô đã disabled,
    // giá trị luôn là khoa của chính họ). Server ÉP LẠI giá trị này bất kể
    // client gửi gì (`_khoa_ep_theo_phien()`), nên gửi thẳng không phải một lỗ
    // hổng — cùng khuôn mọi modal khác của cổng (KhoaPhongModal/NccModal/
    // VatTuModal đều gửi `{ ...form.value }` nguyên vẹn, không lược trường).
    const payload = { ...form.value }
    const out = await api.callKho('kho_thiet_bi_save', { payload })
    showToast('Đã lưu thiết bị.')
    emit('saved', out)
  } catch (e) {
    showToast(e.message || 'Không lưu được thiết bị.', 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div v-if="open" :class="isMobile ? 'sheet' : 'modal'" @click.self="emit('close')">
    <div class="card" :style="!isMobile ? 'width: 640px' : ''">
      <h3>{{ mode === 'sua' ? 'Sửa thiết bị' : 'Thêm thiết bị' }}</h3>

      <div v-if="khoaHoanToan" class="note" style="margin-top: 10px">
        Máy dùng chung — liên hệ quản lý đơn vị để sửa
      </div>

      <div
        :style="isMobile ? 'margin-top: 10px' : 'display: flex; gap: 20px; align-items: flex-start; margin-top: 10px'"
      >
        <div :style="isMobile ? '' : 'flex: 1'">
          <div class="field">
            <label>Mã máy *</label>
            <input v-model="form.ma_thiet_bi" :disabled="khoaHoanToan" placeholder="VD: MAY-XN-01" />
          </div>
          <div class="field">
            <label>Tên máy *</label>
            <input v-model="form.ten_thiet_bi" :disabled="khoaHoanToan" placeholder="VD: Máy xét nghiệm sinh hoá" />
          </div>
          <div class="field">
            <label>Khoa phòng</label>
            <select v-model="form.khoa_phong" :disabled="laNhanVienKhoa || khoaHoanToan">
              <option value="">— Dùng chung —</option>
              <option v-for="k in khoaPhongList" :key="k.name" :value="k.name">
                {{ k.ten_khoa_phong }}{{ k.active ? '' : ' (đã tắt)' }}
              </option>
            </select>
            <p v-if="laNhanVienKhoa && !ghiChuKhoaRong" class="tag">Đặt theo khoa của bạn — do hệ thống ép, không tự đổi được.</p>
            <p v-if="ghiChuKhoaRong" class="tag">{{ ghiChuKhoaRong }}</p>
          </div>
          <div v-if="mode === 'sua'" class="field">
            <label style="display: flex; align-items: center; gap: 6px">
              <input
                type="checkbox"
                :disabled="khoaHoanToan"
                :checked="form.active === 1"
                @change="form.active = $event.target.checked ? 1 : 0"
              />
              Đang hoạt động
            </label>
          </div>
        </div>

        <div :style="isMobile ? '' : 'flex: 1'">
          <div class="field"><label>Hãng sản xuất</label><input v-model="form.hang_san_xuat" :disabled="khoaHoanToan" /></div>
          <div class="field"><label>Xuất xứ</label><input v-model="form.xuat_xu" :disabled="khoaHoanToan" /></div>
          <div class="field"><label>Model</label><input v-model="form.model" :disabled="khoaHoanToan" /></div>
          <div class="field"><label>Số serial</label><input v-model="form.so_serial" :disabled="khoaHoanToan" /></div>
          <div class="field"><label>Năm sản xuất</label><input v-model="form.nam_san_xuat" type="number" :disabled="khoaHoanToan" /></div>
          <div class="field"><label>Ngày lắp đặt</label><input v-model="form.ngay_lap_dat" type="date" :disabled="khoaHoanToan" /></div>
        </div>
      </div>

      <div class="field"><label>Ghi chú</label><input v-model="form.ghi_chu" :disabled="khoaHoanToan" /></div>

      <div class="flex" style="justify-content: flex-end; margin-top: 14px; gap: 8px">
        <button class="btn-o" @click="emit('close')">{{ khoaHoanToan ? 'Đóng' : 'Huỷ' }}</button>
        <button v-if="!khoaHoanToan" class="btn" :disabled="saving" @click="onSave">
          {{ saving ? 'Đang lưu…' : 'Lưu' }}
        </button>
      </div>
    </div>
  </div>
</template>
