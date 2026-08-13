<script setup>
// E6/F-22 [MỚI] — Form tạo/sửa Yêu cầu hàng hoá (m-yc trong prototype).
// Mở từ NHIỀU đường vào (QT11): danh mục "Không tìm thấy?", dòng mua lẻ
// thiếu giá "[Yêu cầu báo giá]", danh sách yêu cầu "+ Gửi yêu cầu", chi tiết
// yêu cầu "Sửa" (chỉ khi còn "Mới") — mỗi nơi gọi truyền `initial` khác nhau,
// component không tự biết ngữ cảnh, chỉ hiển thị những gì được truyền vào.
import { computed, ref, watch } from 'vue'
import api from '../api'
import { showToast } from '../toast'
import { useIsMobile } from '../useMobile'

const props = defineProps({
  open: { type: Boolean, default: false },
  initial: { type: Object, default: () => ({}) },
  mode: { type: String, default: 'tao' }, // 'tao' | 'sua'
  // Đính kèm ĐÃ có sẵn trên yêu cầu đang sửa — chỉ để hiển thị/đếm vào giới
  // hạn 5 file cộng dồn (BR-Y3), KHÔNG gửi lại lên server (đã gắn từ trước).
  existingAttachments: { type: Array, default: () => [] },
})
const emit = defineEmits(['saved', 'close'])

const isMobile = useIsMobile()
const saving = ref(false)
const error = ref('')

const LOAI_OPTIONS = ['Bổ sung HĐNT', 'Báo giá mua lẻ', 'Tìm nguồn hàng mới']
const TAN_SUAT_OPTIONS = ['Một lần', 'Định kỳ']
const DUOI_HOP_LE = ['.pdf', '.jpg', '.jpeg', '.png', '.xlsx']
const TOI_DA_FILE = 5
const TOI_DA_MB = 10
// NL-11.6 — nguyên văn thông điệp chuẩn (khớp `THONG_DIEP_DINH_KEM_SAI` phía
// server) để lỗi tại trường và lỗi server không lệch câu chữ.
const THONG_DIEP_DINH_KEM_SAI = 'Tối đa 5 file, mỗi file ≤ 10MB, định dạng pdf/jpg/png/xlsx.'

function ngayCanMacDinh() {
  const d = new Date()
  d.setDate(d.getDate() + 7)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const form = ref({
  loai: 'Tìm nguồn hàng mới',
  ten_hang: '',
  quy_cach: '',
  dvt: '',
  so_luong_du_kien: '',
  tan_suat: 'Một lần',
  chu_ky_thang: '',
  ngay_can: '',
  hang_xuat_xu: '',
  ghi_chu: '',
  vat_tu_kho: '',
})
const newFiles = ref([]) // File[] chưa upload, chọn ở lần mở modal này
const fileError = ref('')

watch(
  () => props.open,
  (v) => {
    if (!v) return
    error.value = ''
    fileError.value = ''
    newFiles.value = []
    form.value = {
      loai: 'Tìm nguồn hàng mới',
      ten_hang: '',
      quy_cach: '',
      dvt: '',
      so_luong_du_kien: '',
      tan_suat: 'Một lần',
      chu_ky_thang: '',
      ngay_can: ngayCanMacDinh(),
      hang_xuat_xu: '',
      ghi_chu: '',
      vat_tu_kho: '',
      ...props.initial,
    }
  },
  { immediate: true }
)

const soFileHienCo = computed(() => (props.existingAttachments || []).length)
const tongSoFile = computed(() => soFileHienCo.value + newFiles.value.length)
const ghiChuConLai = computed(() => 1000 - (form.value.ghi_chu || '').length)

function onPickFiles(e) {
  fileError.value = ''
  const picked = Array.from(e.target.files || [])
  e.target.value = '' // cho chọn lại đúng file đó lần sau nếu cần bỏ rồi thêm lại
  if (!picked.length) return
  if (tongSoFile.value + picked.length > TOI_DA_FILE) {
    fileError.value = THONG_DIEP_DINH_KEM_SAI
    return
  }
  for (const f of picked) {
    const ext = '.' + (f.name.split('.').pop() || '').toLowerCase()
    if (!DUOI_HOP_LE.includes(ext) || f.size > TOI_DA_MB * 1024 * 1024) {
      fileError.value = THONG_DIEP_DINH_KEM_SAI
      return
    }
  }
  newFiles.value = [...newFiles.value, ...picked]
}
function removeNewFile(idx) {
  newFiles.value = newFiles.value.filter((_, i) => i !== idx)
  fileError.value = ''
}

function validate() {
  if (!form.value.loai) return 'Vui lòng chọn loại yêu cầu.'
  if (!(form.value.ten_hang || '').trim()) return 'Vui lòng nhập tên hàng hoá.'
  if ((form.value.ten_hang || '').length > 200) return 'Tên hàng hoá không quá 200 ký tự.'
  if (!(form.value.dvt || '').trim()) return 'Vui lòng nhập ĐVT.'
  if (!form.value.so_luong_du_kien || Number(form.value.so_luong_du_kien) <= 0) {
    return 'Số lượng dự kiến phải lớn hơn 0.'
  }
  if (form.value.tan_suat === 'Định kỳ' && !(Number(form.value.chu_ky_thang) >= 1)) {
    return 'Yêu cầu định kỳ phải khai Chu kỳ (tháng) ≥ 1.'
  }
  if ((form.value.ghi_chu || '').length > 1000) return 'Ghi chú không quá 1000 ký tự.'
  return ''
}

async function onSave() {
  if (saving.value) return
  const loiSom = validate()
  if (loiSom) {
    error.value = loiSom
    return
  }
  saving.value = true
  error.value = ''
  try {
    // Tải TRƯỚC mọi file mới lên (upload_file?is_private=1) rồi mới gửi
    // file_urls — endpoint chỉ nhận URL của file ĐÃ tồn tại trên server,
    // không nhận multipart trực tiếp (API Spec §0: "client tải trước").
    const fileUrls = []
    for (const f of newFiles.value) {
      const uploaded = await api.uploadFile(f)
      fileUrls.push(uploaded.file_url)
    }
    const payload = { ...form.value }
    if (payload.tan_suat !== 'Định kỳ') payload.chu_ky_thang = null
    const res = await api.call('portal_yeu_cau_save', {
      data: JSON.stringify(payload),
      name: props.initial?.name || undefined,
      file_urls: JSON.stringify(fileUrls),
    })
    emit('saved', res)
  } catch (e) {
    error.value = e.message || 'Không gửi được yêu cầu. Vui lòng thử lại.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div v-if="open" :class="isMobile ? 'sheet' : 'modal'" @click.self="emit('close')">
    <div class="card" style="max-height: 88vh; overflow: auto">
      <h3>{{ mode === 'sua' ? 'Sửa yêu cầu hàng hoá' : 'Gửi yêu cầu hàng hoá' }} <span class="newtag">MỚI</span></h3>

      <div v-if="error" class="note note-r" style="margin-top: 10px">{{ error }}</div>

      <div class="field" style="margin-top: 10px">
        <label>Loại yêu cầu *</label>
        <select v-model="form.loai">
          <option v-for="o in LOAI_OPTIONS" :key="o" :value="o">{{ o }}</option>
        </select>
      </div>

      <div class="field">
        <label>Tên hàng hoá *</label>
        <input v-model="form.ten_hang" maxlength="200" placeholder="VD: Test nhanh HbA1c" />
      </div>

      <div class="flex" style="align-items: flex-start">
        <div class="field" style="flex: 1"><label>Quy cách đóng gói</label><input v-model="form.quy_cach" maxlength="100" placeholder="VD: Hộp 25 test" /></div>
        <div class="field" style="width: 110px"><label>ĐVT *</label><input v-model="form.dvt" placeholder="cái/hộp..." /></div>
        <div class="field" style="width: 120px"><label>SL dự kiến *</label><input v-model="form.so_luong_du_kien" type="number" min="0" step="any" inputmode="decimal" /></div>
      </div>

      <div class="flex" style="align-items: flex-start">
        <div class="field" style="flex: 1">
          <label>Tần suất *</label>
          <select v-model="form.tan_suat">
            <option v-for="o in TAN_SUAT_OPTIONS" :key="o" :value="o">{{ o }}</option>
          </select>
        </div>
        <div v-if="form.tan_suat === 'Định kỳ'" class="field" style="flex: 1">
          <label>Chu kỳ (tháng) *</label>
          <input v-model="form.chu_ky_thang" type="number" min="1" step="1" />
        </div>
        <div class="field" style="flex: 1">
          <label>Ngày cần hàng</label>
          <input v-model="form.ngay_can" type="date" />
        </div>
      </div>

      <div class="field"><label>Hãng / xuất xứ mong muốn</label><input v-model="form.hang_xuat_xu" maxlength="200" placeholder="VD: Abbott" /></div>

      <div class="field">
        <label>Ghi chú</label>
        <textarea v-model="form.ghi_chu" rows="2" maxlength="1000" placeholder="Thông tin thêm cho Miyano..."></textarea>
        <div class="tag" style="text-align: right; margin-top: 2px">{{ ghiChuConLai }} ký tự còn lại</div>
      </div>

      <div class="field">
        <label>Đính kèm (≤5 file × 10MB — pdf/jpg/png/xlsx)</label>
        <input type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.xlsx" :disabled="tongSoFile >= TOI_DA_FILE" @change="onPickFiles" />
        <div v-if="fileError" class="err" style="color: var(--red); font-size: 12px; margin-top: 4px">{{ fileError }}</div>
        <p v-if="soFileHienCo" class="tag" style="margin-top: 4px">{{ soFileHienCo }} file đã đính kèm sẵn trên yêu cầu này.</p>
        <ul v-if="newFiles.length" style="margin: 6px 0 0 18px; font-size: 13px">
          <li v-for="(f, i) in newFiles" :key="i">
            {{ f.name }} <a href="#" style="color: var(--red)" @click.prevent="removeNewFile(i)">✕</a>
          </li>
        </ul>
      </div>

      <div class="flex" style="justify-content: flex-end; margin-top: 8px; gap: 8px">
        <button class="btn-o" :disabled="saving" @click="emit('close')">Huỷ</button>
        <button class="btn" :disabled="saving" @click="onSave">{{ saving ? 'Đang gửi…' : 'Gửi yêu cầu' }}</button>
      </div>
    </div>
  </div>
</template>
