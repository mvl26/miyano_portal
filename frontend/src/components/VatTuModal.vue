<script setup>
import { ref, watch, computed } from 'vue'
import api from '../api'
import { showToast } from '../toast'
import { useIsMobile } from '../useMobile'
import ThietBiPicker from './ThietBiPicker.vue'
import ThietBiQuickCreate from './ThietBiQuickCreate.vue'

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
const form = ref({
  ma_vat_tu: '', ten_vat_tu: '', dvt: '', quy_cach: '', nhom: '', ghi_chu: '', active: 1,
  // Task 13 — "Máy sử dụng" (danh mục tương thích). Dạng NỘI BỘ của form luôn
  // là [{thiet_bi, ten_thiet_bi}] (khớp hình dạng vat_tu.ra_dict() trả ra, để
  // còn tên hiển thị) — CHỈ đổi sang mảng docname trần lúc build payload gửi
  // đi (xem payloadRaGui). Đây chính là "bẫy hình dạng dữ liệu" đã ghi từ
  // Task 2: ra_dict() TRẢ [{thiet_bi, ten_thiet_bi}], nhưng tao()/sua() NHẬN
  // may_su_dung là danh sách docname trần — gửi nguyên response ngược lại sẽ
  // đưa cả dict vào một Link field và vỡ.
  may_su_dung: [],
})

// Task 13 (GHI NHẬN — xem task-13-report.md) — `kho_vat_tu_list` (nguồn dữ
// liệu của màn Danh mục vật tư) KHÔNG chọn cột `may_su_dung`, và không có
// endpoint đọc riêng một vật tư (chỉ `kho_vat_tu_sua`/`kho_vat_tu_tao`, cả
// hai đều GHI, mới trả `may_su_dung` qua ra_dict()). Vì vậy `props.initial`
// khi mở "Sửa" từ DanhMucVatTu.vue CHỈ có `may_su_dung` nếu vật tư đó vừa
// được lưu trong CHÍNH PHIÊN này (DanhMucVatTu.vue vá lại sau mỗi lần lưu —
// xem onSaved() ở đó). Với mode "tao", thiếu khoá này ĐÚNG LÀ "chưa có máy
// nào" (vật tư chưa tồn tại thì không thể có phát sinh trước đó), nên luôn
// coi là ĐÃ BIẾT. Với "sửa" mà chưa biết, KHÔNG bịa một danh sách rỗng rồi
// cho sửa — sẽ xoá mất danh sách máy thật của vật tư ngay khi người dùng lưu
// một thay đổi không liên quan gì đến máy. Ẩn hẳn phần sửa, hiện lý do thay
// vì im lặng hoặc báo sai (bài học Task 12: câu hiển thị phải đúng thực
// trạng dữ liệu, không phải chỉ đúng cú pháp).
const bietDanhSachMay = computed(
  () => props.mode === 'tao' || Array.isArray(props.initial.may_su_dung)
)

// US-E4.5/NL-4.5: kho_vat_tu_tao trả canh_bao_trung khi TÊN vừa tạo giống
// ≥85% (so không dấu) một vật tư đã có trong kho — cảnh báo MỀM, không chặn.
//
// (Review E4 phần B, Gap 3 — ĐÃ SỬA) Trước bản này, onSave() gọi thẳng
// kho_vat_tu_tao NGAY, nên vật tư đã tồn tại thật trong DB trước khi người
// dùng kịp thấy cảnh báo — "Huỷ" chỉ còn cách "chữa cháy" bằng tắt
// (active=0) bản vừa lỡ tạo, không phải huỷ thật. Giờ gọi TRƯỚC với
// `chi_kiem_tra: true` (server chạy đủ kiểm tra, KHÔNG ghi gì) — nếu có
// cảnh báo, hỏi "[Vẫn tạo]/[Huỷ]" TRƯỚC KHI bản ghi tồn tại; "Huỷ" giờ đúng
// nghĩa — không có gì để rollback vì chưa từng ghi.
const duplicateWarning = ref(null)

watch(
  () => props.open,
  (v) => {
    if (!v) return
    duplicateWarning.value = null
    form.value = {
      ma_vat_tu: '', ten_vat_tu: '', dvt: '', quy_cach: '', nhom: '', ghi_chu: '', active: 1,
      ...props.initial,
      // Chuẩn hoá về ĐÚNG MỘT hình dạng nội bộ [{thiet_bi, ten_thiet_bi}],
      // dù props.initial.may_su_dung đến từ ra_dict() (đã đúng hình dạng này)
      // hay (phòng hờ) là mảng docname trần.
      may_su_dung: (props.initial.may_su_dung || []).map((m) =>
        typeof m === 'string' ? { thiet_bi: m, ten_thiet_bi: '' } : { thiet_bi: m.thiet_bi, ten_thiet_bi: m.ten_thiet_bi || '' }
      ),
    }
  },
  { immediate: true }
)

// --- Task 13: thêm/bỏ máy trong "Máy sử dụng" -------------------------------
function themMay(o) {
  if (form.value.may_su_dung.some((m) => m.thiet_bi === o.name)) {
    showToast('Máy này đã có trong danh sách.', 'error')
    return
  }
  form.value.may_su_dung.push({ thiet_bi: o.name, ten_thiet_bi: o.ten_thiet_bi || o.ma_thiet_bi || o.name })
}
function boMay(idx) {
  form.value.may_su_dung.splice(idx, 1)
}
const quickCreateOpen = ref(false)
const quickCreateGoiY = ref('')
function moTaoNhanhMay({ search }) {
  quickCreateGoiY.value = search || ''
  quickCreateOpen.value = true
}
function onMayTaoXong(tb) {
  quickCreateOpen.value = false
  themMay(tb)
}

// Chỉ đính kèm `may_su_dung` vào payload khi ĐÃ BIẾT danh sách hiện tại
// (bietDanhSachMay) — thiếu chốt này, một lần lưu "sửa" mở từ danh sách chưa
// vá (chưa từng lưu trong phiên) sẽ gửi mảng RỖNG và XOÁ MẤT máy thật đang
// gắn với vật tư, dù người dùng chỉ định sửa một ô hoàn toàn khác.
function payloadRaGui(extra) {
  const { may_su_dung, ...rest } = form.value
  const p = { ...rest, ...extra }
  if (bietDanhSachMay.value) {
    p.may_su_dung = may_su_dung.map((m) => m.thiet_bi)
  }
  return p
}

// Mã và ĐVT khoá lại khi vật tư đã có dòng sổ: số liệu cũ đã tính theo giá trị
// hiện tại và hệ thống không quy đổi. Backend chặn lần nữa — đây chỉ là lớp
// hiển thị để người dùng biết TRƯỚC KHI gõ, kèm lý do đọc được.
const khoa = computed(() => props.mode === 'sua' && props.coPhatSinh)

async function onSave() {
  if (saving.value) return
  saving.value = true
  try {
    if (props.mode === 'sua') {
      const row = await api.callKho('kho_vat_tu_sua', { name: props.vatTu, payload: payloadRaGui() })
      showToast('Đã lưu vật tư.')
      emit('saved', row)
      return
    }
    // Tạo mới: xem trước — KHÔNG ghi gì (Gap 3).
    const preview = await api.callKho('kho_vat_tu_tao', { payload: payloadRaGui({ chi_kiem_tra: 1 }) })
    if (preview.da_co) {
      // Trùng MÃ với vật tư có sẵn: server đã tự chọn bản ghi cũ, không có
      // gì để "vẫn tạo" — đây không phải nhánh cảnh báo tên gần giống.
      showToast(`Mã ${preview.ma_vat_tu} đã có sẵn — đã chọn vật tư đó.`)
      emit('saved', preview)
      return
    }
    if (preview.canh_bao_trung && preview.canh_bao_trung.length) {
      duplicateWarning.value = preview
      return
    }
    const row = await api.callKho('kho_vat_tu_tao', { payload: payloadRaGui() })
    showToast('Đã lưu vật tư.')
    emit('saved', row)
  } catch (e) {
    showToast(e.message || 'Không lưu được vật tư.', 'error')
  } finally {
    saving.value = false
  }
}

function huyCanhBao() {
  // Chưa từng ghi gì (chi_kiem_tra không tạo bản ghi) — "Huỷ" chỉ đơn giản
  // quay lại form, không cần gọi API nào để rollback.
  duplicateWarning.value = null
}

async function vanTao() {
  if (saving.value) return
  saving.value = true
  try {
    const row = await api.callKho('kho_vat_tu_tao', { payload: payloadRaGui() })
    showToast('Đã tạo vật tư.')
    emit('saved', row)
    duplicateWarning.value = null
  } catch (e) {
    showToast(e.message || 'Không lưu được vật tư.', 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div v-if="open" :class="isMobile ? 'sheet' : 'modal'" @click.self="emit('close')">
    <div class="card">
      <template v-if="duplicateWarning">
        <h3>Có vật tư tên gần giống</h3>
        <div class="note" style="margin-top: 10px">
          <b>{{ duplicateWarning.ma_vat_tu }} — {{ duplicateWarning.ten_vat_tu }}</b> chưa được tạo.
          Tên gần giống vật tư có sẵn:
          <ul style="margin: 6px 0 0 18px">
            <li v-for="g in duplicateWarning.canh_bao_trung" :key="g">{{ g }}</li>
          </ul>
          Nếu đây thực chất là cùng một vật tư, hãy huỷ rồi dùng vật tư có sẵn thay vì tạo mới.
        </div>
        <div class="flex" style="justify-content: flex-end; margin-top: 14px; gap: 8px">
          <button class="btn-o" :disabled="saving" @click="huyCanhBao">Huỷ</button>
          <button class="btn" :disabled="saving" @click="vanTao">
            {{ saving ? 'Đang tạo…' : 'Vẫn tạo' }}
          </button>
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

      <!-- Task 13 — "Máy sử dụng": danh mục máy TƯƠNG THÍCH của vật tư này
           (bảng may_su_dung), gợi ý dropdown máy khi lập phiếu xuất. KHÔNG
           bắt buộc, KHÔNG tham gia phép cộng tồn kho nào. -->
      <div class="field">
        <label>Máy sử dụng (gợi ý khi lập phiếu xuất — không bắt buộc)</label>
        <template v-if="bietDanhSachMay">
          <div v-if="form.may_su_dung.length" class="chips" style="flex-wrap: wrap; margin-bottom: 8px">
            <span
              v-for="(m, i) in form.may_su_dung"
              :key="m.thiet_bi"
              class="chip"
              style="display: flex; align-items: center; gap: 6px"
            >
              {{ m.ten_thiet_bi || m.thiet_bi }}
              <button type="button" class="btn-o btn-sm" style="padding: 1px 7px" @click="boMay(i)">✕</button>
            </span>
          </div>
          <ThietBiPicker
            :model-value="null"
            :vat-tu="null"
            :auto-select-single="false"
            @picked="themMay"
            @create-new="moTaoNhanhMay"
          />
        </template>
        <p v-else class="tag">
          Chưa tải được danh sách máy hiện đang gắn với vật tư này ở màn danh mục — không sửa được ở đây để
          tránh xoá nhầm máy đã gắn từ trước. Mở lại "Sửa" sau khi vừa lưu một lần trong phiên này để sửa được,
          hoặc liên hệ bộ phận quản trị hệ thống nếu tình trạng này lặp lại.
        </p>
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
  <ThietBiQuickCreate
    :open="quickCreateOpen"
    :goi-y="quickCreateGoiY"
    @created="onMayTaoXong"
    @close="quickCreateOpen = false"
  />
</template>
