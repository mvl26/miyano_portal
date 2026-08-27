<script setup>
import { ref, watch } from 'vue'
import api from '../api'
import { showToast } from '../toast'
import { useIsMobile } from '../useMobile'

// Task 13, Quy tắc 4 — form "tạo nhanh máy" ngay trong ThietBiPicker.vue,
// ĐÚNG NĂM ô (khớp `TRUONG_TAO_NHANH` ở miyano_portal/kho/thiet_bi.py):
// Tên máy · Mã máy · Hãng · Xuất xứ · Số serial. Model/năm sản xuất/ngày lắp
// đặt để màn danh mục Thiết bị (ThietBiModal.vue) sửa sau. "Nhanh" nói về SỐ
// Ô phải điền, KHÔNG nói về độ lỏng validate — kho_thiet_bi_tao_nhanh đi qua
// ĐÚNG validate() đầy đủ của Customer Equipment (mã/tên trùng vẫn bị chặn),
// và server tự ép khoa_phong theo phiên (BR-TB-6) — form này không có ô khoa.
const props = defineProps({
  open: { type: Boolean, default: false },
  // Chữ người dùng vừa gõ trong ô tìm của ThietBiPicker khi bấm "+ Tạo nhanh
  // máy" — điền sẵn vào Tên máy. Bắt gõ lại là chỗ làm tính năng có cảm giác
  // dở dang (Quy tắc 3, task-13-brief.md).
  goiY: { type: String, default: '' },
})
const emit = defineEmits(['created', 'close'])

const isMobile = useIsMobile()
const saving = ref(false)
const form = ref({ ten_thiet_bi: '', ma_thiet_bi: '', hang_san_xuat: '', xuat_xu: '', so_serial: '' })

watch(
  () => props.open,
  (v) => {
    if (!v) return
    form.value = {
      ten_thiet_bi: props.goiY || '', ma_thiet_bi: '', hang_san_xuat: '', xuat_xu: '', so_serial: '',
    }
  },
  { immediate: true }
)

async function onSave() {
  if (saving.value) return
  saving.value = true
  try {
    const out = await api.callKho('kho_thiet_bi_tao_nhanh', { payload: { ...form.value } })
    showToast('Đã tạo máy mới.')
    emit('created', out)
  } catch (e) {
    // Nguyên văn — thông điệp trùng mã/trùng tên/thiếu ô đều đã là tiếng Việt
    // soạn sẵn ở customer_equipment.py, không thay bằng câu chung chung.
    showToast(e.message || 'Không tạo được máy.', 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div v-if="open" :class="isMobile ? 'sheet' : 'modal'" @click.self="emit('close')">
    <div class="card">
      <h3>Tạo nhanh máy</h3>
      <div class="field">
        <label>Tên máy *</label>
        <input v-model="form.ten_thiet_bi" placeholder="VD: Máy xét nghiệm sinh hoá" />
      </div>
      <div class="field">
        <label>Mã máy *</label>
        <input v-model="form.ma_thiet_bi" placeholder="VD: MAY-XN-01" />
      </div>
      <div class="grid2">
        <div class="field"><label>Hãng sản xuất</label><input v-model="form.hang_san_xuat" /></div>
        <div class="field"><label>Xuất xứ</label><input v-model="form.xuat_xu" /></div>
      </div>
      <div class="field"><label>Số serial</label><input v-model="form.so_serial" /></div>
      <p class="tag">Model, năm sản xuất, ngày lắp đặt: bổ sung sau ở Danh mục thiết bị.</p>

      <div class="flex" style="justify-content: flex-end; margin-top: 14px; gap: 8px">
        <button class="btn-o" @click="emit('close')">Huỷ</button>
        <button class="btn" :disabled="saving" @click="onSave">
          {{ saving ? 'Đang lưu…' : 'Lưu' }}
        </button>
      </div>
    </div>
  </div>
</template>
