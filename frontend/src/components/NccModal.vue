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
const deactivating = ref(false)
const form = ref({ name: '', ten_ncc: '', mst: '', dien_thoai: '', email: '', dia_chi: '', ghi_chu: '', active: 1 })

// US-E4.1/NL-7.3: kết quả kho_ncc_save vừa lưu XONG (bản ghi đã tồn tại thật
// sự), kèm goi_y_trung nếu server phát hiện tên GẦN GIỐNG một NCC khác của
// cùng kho. Khác trùng TUYỆT ĐỐI (server chặn cứng, không tới được đây) —
// đây là cảnh báo MỀM sau khi đã lưu, vì kho_ncc_save không có bước "thử
// trước rồi huỷ": bản ghi đã có thật trong DB ngay khi hàm trả về. "Huỷ" ở
// đây vì vậy nghĩa là tắt (active=0) bản vừa lưu — đúng cơ chế "không xoá,
// chỉ tắt" mà toàn bộ NCC/vật tư của portal đã dùng — không phải rollback.
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

async function onSave() {
  if (saving.value) return
  saving.value = true
  try {
    const out = await api.callKho('kho_ncc_save', { data: { ...form.value } })
    if (out.goi_y_trung && out.goi_y_trung.length) {
      duplicateWarning.value = out
    } else {
      showToast('Đã lưu NCC.')
      emit('saved', out)
    }
  } catch (e) {
    showToast(e.message || 'Không lưu được NCC.', 'error')
  } finally {
    saving.value = false
  }
}

function giuLai() {
  showToast('Đã lưu NCC.')
  emit('saved', duplicateWarning.value)
  duplicateWarning.value = null
}

async function tatBanNay() {
  if (deactivating.value) return
  deactivating.value = true
  try {
    const out = await api.callKho('kho_ncc_save', {
      data: { name: duplicateWarning.value.name, ten_ncc: duplicateWarning.value.ten_ncc, active: 0 },
    })
    showToast('Đã tắt NCC vừa tạo — chọn NCC có sẵn thay thế trên phiếu.')
    emit('saved', out)
    duplicateWarning.value = null
  } catch (e) {
    showToast(e.message || 'Không tắt được NCC.', 'error')
  } finally {
    deactivating.value = false
  }
}
</script>

<template>
  <div v-if="open" :class="isMobile ? 'sheet' : 'modal'" @click.self="emit('close')">
    <div class="card">
      <template v-if="duplicateWarning">
        <h3>Có NCC gần giống</h3>
        <div class="note" style="margin-top: 10px">
          Đã lưu <b>{{ duplicateWarning.ten_ncc }}</b>. Tên gần giống với NCC có sẵn:
          <ul style="margin: 6px 0 0 18px">
            <li v-for="g in duplicateWarning.goi_y_trung" :key="g">{{ g }}</li>
          </ul>
          Nếu đây thực chất là cùng một NCC, hãy tắt bản vừa lưu và chọn NCC có sẵn trên phiếu.
        </div>
        <div class="flex" style="justify-content: flex-end; margin-top: 14px; gap: 8px">
          <button class="btn-o btn-danger" :disabled="deactivating" @click="tatBanNay">
            {{ deactivating ? 'Đang tắt…' : 'Đây là trùng — tắt bản này' }}
          </button>
          <button class="btn" @click="giuLai">Giữ NCC này</button>
        </div>
      </template>

      <template v-else>
        <h3>{{ mode === 'sua' ? 'Sửa NCC' : 'Thêm NCC' }}</h3>

        <div class="field" style="margin-top: 10px">
          <label>Tên NCC *</label>
          <input v-model="form.ten_ncc" placeholder="VD: Công ty TNHH ABC" />
        </div>
        <div class="grid2">
          <div class="field"><label>MST</label><input v-model="form.mst" placeholder="10 hoặc 13 số" /></div>
          <div class="field"><label>Điện thoại</label><input v-model="form.dien_thoai" /></div>
        </div>
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
