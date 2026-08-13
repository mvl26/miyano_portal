<script setup>
import { ref, watch, computed } from 'vue'
import api from '../api'
import { showToast } from '../toast'
import { useIsMobile } from '../useMobile'

const props = defineProps({
  open: { type: Boolean, default: false },
  // Giá trị điền sẵn — khi mở từ một dòng import thì đây là dữ liệu đọc từ file.
  initial: { type: Object, default: () => ({}) },
  mode: { type: String, default: 'tao' }, // 'tao' | 'sua'
  vatTu: { type: String, default: '' },
  coPhatSinh: { type: Boolean, default: false },
})
const emit = defineEmits(['saved', 'close'])

const isMobile = useIsMobile()
const saving = ref(false)
const deactivating = ref(false)
const form = ref({ ma_vat_tu: '', ten_vat_tu: '', dvt: '', quy_cach: '', nhom: '', ghi_chu: '', active: 1 })

// US-E4.5/NL-4.5: kho_vat_tu_tao trả canh_bao_trung khi TÊN vừa tạo giống
// ≥85% (so không dấu) một vật tư đã có trong kho — cảnh báo MỀM, không chặn
// (vật tư đã được tạo thật khi hàm trả về, không có bước "thử trước"). Cùng
// khuôn với goi_y_trung của NccModal.vue: "huỷ" ở đây nghĩa là tắt bản vừa
// tạo (active=0, luôn cho phép vì vật tư mới tạo chưa có phát sinh nào) chứ
// không phải xoá.
const duplicateWarning = ref(null)

watch(
  () => props.open,
  (v) => {
    if (!v) return
    duplicateWarning.value = null
    form.value = {
      ma_vat_tu: '', ten_vat_tu: '', dvt: '', quy_cach: '', nhom: '', ghi_chu: '', active: 1,
      ...props.initial,
    }
  },
  { immediate: true }
)

// Mã và ĐVT khoá lại khi vật tư đã có dòng sổ: số liệu cũ đã tính theo giá trị
// hiện tại và hệ thống không quy đổi. Backend chặn lần nữa — đây chỉ là lớp
// hiển thị để người dùng biết TRƯỚC KHI gõ, kèm lý do đọc được.
const khoa = computed(() => props.mode === 'sua' && props.coPhatSinh)

async function onSave() {
  if (saving.value) return
  saving.value = true
  try {
    const payload = { ...form.value }
    const row =
      props.mode === 'sua'
        ? await api.callKho('kho_vat_tu_sua', { name: props.vatTu, payload })
        : await api.callKho('kho_vat_tu_tao', { payload })
    if (row.canh_bao_trung && row.canh_bao_trung.length) {
      duplicateWarning.value = row
      return
    }
    showToast(row.da_co ? `Mã ${row.ma_vat_tu} đã có sẵn — đã chọn vật tư đó.` : 'Đã lưu vật tư.')
    emit('saved', row)
  } catch (e) {
    showToast(e.message || 'Không lưu được vật tư.', 'error')
  } finally {
    saving.value = false
  }
}

function giuLai() {
  showToast('Đã lưu vật tư.')
  emit('saved', duplicateWarning.value)
  duplicateWarning.value = null
}

async function tatBanNay() {
  if (deactivating.value) return
  deactivating.value = true
  try {
    const row = await api.callKho('kho_vat_tu_sua', {
      name: duplicateWarning.value.name, payload: { active: 0 },
    })
    showToast('Đã tắt vật tư vừa tạo — chọn vật tư có sẵn thay thế.')
    emit('saved', row)
    duplicateWarning.value = null
  } catch (e) {
    showToast(e.message || 'Không tắt được vật tư.', 'error')
  } finally {
    deactivating.value = false
  }
}
</script>

<template>
  <div v-if="open" :class="isMobile ? 'sheet' : 'modal'" @click.self="emit('close')">
    <div class="card">
      <template v-if="duplicateWarning">
        <h3>Có vật tư tên gần giống</h3>
        <div class="note" style="margin-top: 10px">
          Đã tạo <b>{{ duplicateWarning.ma_vat_tu }} — {{ duplicateWarning.ten_vat_tu }}</b>. Tên gần giống vật tư có sẵn:
          <ul style="margin: 6px 0 0 18px">
            <li v-for="g in duplicateWarning.canh_bao_trung" :key="g">{{ g }}</li>
          </ul>
          Nếu đây thực chất là cùng một vật tư, hãy tắt bản vừa tạo và dùng vật tư có sẵn.
        </div>
        <div class="flex" style="justify-content: flex-end; margin-top: 14px; gap: 8px">
          <button class="btn-o btn-danger" :disabled="deactivating" @click="tatBanNay">
            {{ deactivating ? 'Đang tắt…' : 'Đây là trùng — tắt bản này' }}
          </button>
          <button class="btn" @click="giuLai">Giữ vật tư mới</button>
        </div>
      </template>

      <template v-else>
      <h3>{{ mode === 'sua' ? 'Sửa vật tư' : 'Tạo vật tư mới' }}</h3>

      <div class="field">
        <label>Mã vật tư *</label>
        <input v-model="form.ma_vat_tu" :disabled="khoa" placeholder="VD: BV-KIM-22G" />
        <p v-if="khoa" class="tag">🔒 Vật tư đã có phát sinh trong sổ — không đổi được mã.</p>
      </div>
      <div class="field">
        <label>Tên vật tư *</label>
        <input v-model="form.ten_vat_tu" />
      </div>
      <div class="field">
        <label>ĐVT *</label>
        <input v-model="form.dvt" :disabled="khoa" placeholder="VD: Hộp" />
        <p v-if="khoa" class="tag">🔒 Đã có phát sinh — đổi ĐVT sẽ làm sai số tồn cũ.</p>
      </div>
      <div class="grid2">
        <div class="field"><label>Quy cách</label><input v-model="form.quy_cach" /></div>
        <div class="field"><label>Nhóm</label><input v-model="form.nhom" /></div>
      </div>
      <div class="field"><label>Ghi chú</label><input v-model="form.ghi_chu" /></div>
      <div v-if="mode === 'sua'" class="field">
        <label style="display: flex; align-items: center; gap: 6px">
          <input type="checkbox" :checked="form.active === 1" @change="form.active = $event.target.checked ? 1 : 0" />
          Đang dùng
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
