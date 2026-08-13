<script setup>
import { ref, watch } from 'vue'
import api from '../api'
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
const form = ref({ name: '', ten_ncc: '', mst: '', dien_thoai: '', email: '', dia_chi: '', ghi_chu: '', active: 1 })

// US-E4.1/NL-7.3: goi_y_trung khi TÊN gần giống một NCC khác của cùng kho.
// Khác trùng TUYỆT ĐỐI (server chặn cứng, không tới được đây) — đây là cảnh
// báo MỀM, không chặn.
//
// (Review E4 phần B, Gap 3 — ĐÃ SỬA) Trước bản này, kho_ncc_save() ghi ngay
// rồi mới trả cảnh báo — "Huỷ" chỉ còn cách tắt (active=0) bản vừa lỡ lưu,
// không phải rollback thật. Giờ gọi TRƯỚC với `chi_kiem_tra: true` (server
// kiểm đủ, KHÔNG ghi gì) — "Huỷ" giờ đúng nghĩa vì chưa từng có gì để rollback.
const duplicateWarning = ref(null)

watch(
  () => props.open,
  (v) => {
    if (!v) return
    duplicateWarning.value = null
    form.value = {
      name: '', ten_ncc: '', mst: '', dien_thoai: '', email: '', dia_chi: '', ghi_chu: '', active: 1,
      ...props.initial,
    }
  },
  { immediate: true }
)

// (Review E4 phần B, Gap 1 — ĐÃ SỬA) kho_ncc_list giờ trả ĐỦ
// dien_thoai/email/dia_chi/ghi_chu cho mỗi dòng, không chỉ các cột hiển thị
// bảng — `props.initial` ở chế độ Sửa vì vậy mang giá trị THẬT đang lưu, chứ
// không phải chuỗi rỗng giả. Không còn cần lược 4 trường này khỏi payload
// lúc lưu: gửi nguyên form lên là gửi đúng giá trị hiện có (hoặc giá trị
// người dùng vừa sửa), kho_ncc_save() ghi đè đúng ý, không xoá mất gì.

async function onSave() {
  if (saving.value) return
  saving.value = true
  try {
    const payload = { ...form.value }
    if (props.mode === 'sua') {
      const out = await api.callKho('kho_ncc_save', { data: payload })
      showToast('Đã lưu NCC.')
      emit('saved', out)
      return
    }
    // Tạo mới: xem trước — KHÔNG ghi gì (Gap 3).
    const preview = await api.callKho('kho_ncc_save', { data: { ...payload, chi_kiem_tra: 1 } })
    if (preview.goi_y_trung && preview.goi_y_trung.length) {
      duplicateWarning.value = preview
      return
    }
    const out = await api.callKho('kho_ncc_save', { data: payload })
    showToast('Đã lưu NCC.')
    emit('saved', out)
  } catch (e) {
    showToast(e.message || 'Không lưu được NCC.', 'error')
  } finally {
    saving.value = false
  }
}

function huyCanhBao() {
  // Chưa từng ghi gì (chi_kiem_tra không tạo bản ghi) — quay lại form, không
  // cần gọi API nào để rollback.
  duplicateWarning.value = null
}

async function vanLuu() {
  if (saving.value) return
  saving.value = true
  try {
    const out = await api.callKho('kho_ncc_save', { data: { ...form.value } })
    showToast('Đã lưu NCC.')
    emit('saved', out)
    duplicateWarning.value = null
  } catch (e) {
    showToast(e.message || 'Không lưu được NCC.', 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div v-if="open" :class="isMobile ? 'sheet' : 'modal'" @click.self="emit('close')">
    <div class="card">
      <template v-if="duplicateWarning">
        <h3>Có NCC gần giống</h3>
        <div class="note" style="margin-top: 10px">
          <b>{{ duplicateWarning.ten_ncc }}</b> chưa được lưu. Tên gần giống với NCC có sẵn:
          <ul style="margin: 6px 0 0 18px">
            <li v-for="g in duplicateWarning.goi_y_trung" :key="g">{{ g }}</li>
          </ul>
          Nếu đây thực chất là cùng một NCC, hãy huỷ rồi chọn NCC có sẵn trên phiếu thay vì tạo mới.
        </div>
        <div class="flex" style="justify-content: flex-end; margin-top: 14px; gap: 8px">
          <button class="btn-o" :disabled="saving" @click="huyCanhBao">Huỷ</button>
          <button class="btn" :disabled="saving" @click="vanLuu">
            {{ saving ? 'Đang lưu…' : 'Vẫn lưu' }}
          </button>
        </div>
      </template>

      <template v-else>
        <h3>{{ mode === 'sua' ? 'Sửa NCC' : 'Thêm NCC' }}</h3>

        <div class="field" style="margin-top: 10px">
          <label>Tên NCC *</label>
          <input v-model="form.ten_ncc" placeholder="VD: Công ty TNHH ABC" />
        </div>
        <div class="field"><label>MST</label><input v-model="form.mst" placeholder="10 hoặc 13 số" /></div>

        <div class="field"><label>Điện thoại</label><input v-model="form.dien_thoai" /></div>
        <div class="field"><label>Email</label><input v-model="form.email" type="email" /></div>
        <div class="field"><label>Địa chỉ</label><input v-model="form.dia_chi" /></div>
        <div class="field"><label>Ghi chú</label><input v-model="form.ghi_chu" /></div>
        <div v-if="mode === 'sua'" class="field">
          <label style="display: flex; align-items: center; gap: 6px">
            <input type="checkbox" :checked="form.active === 1" @change="form.active = $event.target.checked ? 1 : 0" />
            Hoạt động
          </label>
        </div>

        <div class="flex" style="justify-content: flex-end; margin-top: 14px; gap: 8px">
          <button class="btn-o" @click="emit('close')">Huỷ</button>
          <button class="btn" :disabled="saving" @click="onSave">
            {{ saving ? 'Đang lưu…' : 'Lưu' }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>
