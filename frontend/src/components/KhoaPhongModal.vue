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
const form = ref({ name: '', ten_khoa_phong: '', ma_khoa: '', ghi_chu: '', active: 1 })

// US-E8.1/NL-4.13: goi_y_trung khi TÊN gần giống một khoa phòng khác của
// cùng kho. Trùng TUYỆT ĐỐI thì server chặn cứng (không tới được đây) — đây
// là cảnh báo MỀM, không chặn. Cùng khuôn NccModal.vue (đọc docstring ở đó):
// gọi TRƯỚC với chi_kiem_tra=true (server kiểm đủ, KHÔNG ghi gì) rồi mới hỏi
// "Vẫn tạo/Huỷ" — "Huỷ" đúng nghĩa vì chưa từng có bản ghi để rollback.
const duplicateWarning = ref(null)

watch(
  () => props.open,
  (v) => {
    if (!v) return
    duplicateWarning.value = null
    form.value = {
      name: '', ten_khoa_phong: '', ma_khoa: '', ghi_chu: '', active: 1,
      ...props.initial,
    }
  },
  { immediate: true }
)

async function onSave() {
  if (saving.value) return
  saving.value = true
  try {
    const payload = { ...form.value }
    if (props.mode === 'sua') {
      const out = await api.callKho('kho_khoa_phong_save', { data: payload })
      showToast('Đã lưu khoa phòng.')
      emit('saved', out)
      return
    }
    // Tạo mới: xem trước — KHÔNG ghi gì.
    const preview = await api.callKho('kho_khoa_phong_save', { data: { ...payload, chi_kiem_tra: 1 } })
    if (preview.goi_y_trung && preview.goi_y_trung.length) {
      duplicateWarning.value = preview
      return
    }
    const out = await api.callKho('kho_khoa_phong_save', { data: payload })
    showToast('Đã lưu khoa phòng.')
    emit('saved', out)
  } catch (e) {
    showToast(e.message || 'Không lưu được khoa phòng.', 'error')
  } finally {
    saving.value = false
  }
}

function huyCanhBao() {
  duplicateWarning.value = null
}

async function vanLuu() {
  if (saving.value) return
  saving.value = true
  try {
    const out = await api.callKho('kho_khoa_phong_save', { data: { ...form.value } })
    showToast('Đã lưu khoa phòng.')
    emit('saved', out)
    duplicateWarning.value = null
  } catch (e) {
    showToast(e.message || 'Không lưu được khoa phòng.', 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div v-if="open" :class="isMobile ? 'sheet' : 'modal'" @click.self="emit('close')">
    <div class="card">
      <template v-if="duplicateWarning">
        <h3>Có khoa phòng gần giống</h3>
        <div class="note" style="margin-top: 10px">
          <b>{{ duplicateWarning.ten_khoa_phong }}</b> chưa được lưu. Tên gần giống với khoa phòng có sẵn:
          <ul style="margin: 6px 0 0 18px">
            <li v-for="g in duplicateWarning.goi_y_trung" :key="g">{{ g }}</li>
          </ul>
          Nếu đây thực chất là cùng một khoa phòng, hãy huỷ rồi chọn khoa có sẵn trên phiếu thay vì tạo mới.
        </div>
        <div class="flex" style="justify-content: flex-end; margin-top: 14px; gap: 8px">
          <button class="btn-o" :disabled="saving" @click="huyCanhBao">Huỷ</button>
          <button class="btn" :disabled="saving" @click="vanLuu">
            {{ saving ? 'Đang lưu…' : 'Vẫn lưu' }}
          </button>
        </div>
      </template>

      <template v-else>
        <h3>{{ mode === 'sua' ? 'Sửa khoa phòng' : 'Thêm khoa phòng' }}</h3>

        <div class="field" style="margin-top: 10px">
          <label>Tên khoa phòng *</label>
          <input v-model="form.ten_khoa_phong" placeholder="VD: Khoa Hồi sức" />
        </div>
        <div class="field"><label>Mã khoa</label><input v-model="form.ma_khoa" placeholder="VD: HS" /></div>
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
