<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import api from '../api'
import { showToast } from '../toast'

// Task 13 — dropdown chọn MÁY (Customer Equipment), gọi ĐÚNG kho_thiet_bi_list
// (không bao giờ Link field chuẩn/search_link — endpoint đó là lỗ chưa vá của
// site này, và nó bỏ qua bộ lọc tầng hai của kho_thiet_bi_list). Bốn quy tắc
// của khuôn "tạo nhanh trong form" (task-13-brief.md):
//   1. Nút "+ Tạo nhanh máy" GHIM dòng đầu dropdown, hiện cả khi đã có kết quả.
//   2. @mousedown.prevent, KHÔNG @click — blur của input đóng dropdown TRƯỚC
//      khi click kịp chạy, nút sẽ trông như hỏng nếu dùng @click.
//   3. Điền sẵn chữ vừa gõ vào ô Tên máy của form tạo nhanh (xem createNew).
//   4. Form tạo nhanh đúng NĂM ô — component đó (ThietBiQuickCreate.vue)
//      không thuộc file này, chỉ nhận `search` qua sự kiện createNew.
const props = defineProps({
  modelValue: { type: String, default: null },
  // Bật lọc tầng hai (kho_thiet_bi_list nhận `vat_tu`) — null/'' = không lọc,
  // hiện mọi máy active của khoa/bệnh viện theo phạm vi phiên (tầng 1 vẫn do
  // server áp, không phải client tự khai được).
  vatTu: { type: String, default: null },
  // true: KHÔNG hiện ô nhập/dropdown — chỉ hiện TÊN máy đã chọn (đọc lại từ
  // kho_thiet_bi_list vì Customer Stock Issue/Item không có field ten_thiet_bi
  // đi kèm thiet_bi — khác vat_tu vốn có sẵn ten_vat_tu do voucher.py tự điền).
  // Dùng cho: dòng phiếu đã ghi sổ, và đầu phiếu khi !editable.
  disabled: { type: Boolean, default: false },
  // Task 13, "Ba việc trên màn phiếu xuất": "chỉ còn đúng một máy hợp lệ →
  // tự điền" — ĐÚNG cho picker của một DÒNG/Ô có modelValue phản ánh lựa
  // chọn thật (còn trống thì tự điền là giúp). SAI khi picker được dùng làm ô
  // "thêm vào danh sách" mà modelValue LUÔN cố định null (VatTuModal.vue,
  // "Máy sử dụng") — khi đó component sẽ hiểu nhầm "modelValue trống" là
  // "chưa chọn gì, cần tự điền" ở MỌI LẦN MỞ MODAL, tự thêm máy vào danh sách
  // mà người dùng chưa hề bấm gì, mỗi khi đơn vị chỉ có đúng một máy active.
  // VatTuModal.vue tắt cờ này.
  autoSelectSingle: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue', 'createNew', 'picked'])

const open = ref(false)
const tuKhoa = ref('')
const options = ref([])
const loading = ref(false)
let searchTimer = null
let loadSeq = 0

function labelOf(o) {
  if (!o) return ''
  let s =
    o.ma_thiet_bi && o.ten_thiet_bi
      ? `${o.ma_thiet_bi} — ${o.ten_thiet_bi}`
      : o.ten_thiet_bi || o.ma_thiet_bi || o.name || ''
  if (!o.active) s += ' (đã tắt)'
  return s
}

// --- Nhãn hiển thị của modelValue hiện tại ---------------------------------
// Trước hết tìm trong `options` đang tải (rẻ, không round-trip thêm). Nếu
// không có (máy nằm NGOÀI bộ lọc tầng hai, hoặc component đang ở mode
// `disabled` nên chưa từng tải `options`), gọi một lần kho_thiet_bi_list
// KHÔNG lọc gì để suy tên — đúng một round-trip mỗi khi modelValue đổi sang
// một docname chưa biết tên, có bảo vệ giá trị cũ (resolvedFor) để không hiện
// nhầm tên của lần trước trong lúc đang tải lần này.
//
// QUAN TRỌNG (vòng sửa 1, Critical): dù gọi `ca_inactive: 1` và không kèm
// `khoa_phong`, `thiet_bi.list_rows()` VẪN luôn áp bộ lọc theo khoa của
// PHIÊN đăng nhập hiện tại (Nhân viên khoa chỉ thấy máy khoa mình + máy dùng
// chung — server-side, client không khai báo được để tắt). Vì vậy "không tìm
// thấy trong danh sách trả về" KHÔNG có nghĩa "máy không tồn tại/chưa chọn"
// — rất có thể máy có thật (BR-TB-4 cho phép máy khác khoa với khoa nhận
// trên phiếu, chỉ cảnh báo mềm) nhưng người xem hiện tại bị lọc quyền không
// thấy nó. Ba trạng thái dưới đây PHẢI phân biệt được, không được gộp lại
// thành một chuỗi rỗng như trước (khiến "có máy nhưng bị lọc" hiển thị y hệt
// "chưa chọn máy" — sai với thực trạng dữ liệu, đặc biệt nguy hiểm trên dòng
// đã ghi sổ vì không còn sửa được nữa).
const resolvedLabel = ref('') // suy xong, TÌM THẤY trong danh sách đầy đủ
const resolveNotFound = ref(false) // suy xong, KHÔNG thấy — có thể bị lọc theo khoa, không hẳn là không tồn tại
const resolveError = ref('') // lỗi thật từ server lúc suy tên — hiện nguyên văn, không nuốt
let resolvedFor = null

function resetResolveState() {
  resolvedLabel.value = ''
  resolveNotFound.value = false
  resolveError.value = ''
}

async function resolveLabel(name) {
  try {
    const list = await api.callKho('kho_thiet_bi_list', { ca_inactive: 1 })
    if (resolvedFor !== name) return // đã có một modelValue mới hơn xen vào
    const found = (list || []).find((o) => o.name === name)
    if (found) {
      resolvedLabel.value = labelOf(found)
    } else {
      resolveNotFound.value = true // KHÔNG suy ra là "chưa chọn" — xem chú thích ở trên
    }
  } catch (e) {
    if (resolvedFor === name) resolveError.value = e.message || 'Không tải được tên máy.'
  }
}

function kiemTraCanSuyNhan() {
  const val = props.modelValue
  if (!val) {
    resetResolveState()
    resolvedFor = null
    return
  }
  if (options.value.some((o) => o.name === val)) {
    // Đã tìm thấy qua đường rẻ (options) — chỉ dọn cờ not-found/error của lần
    // suy trước, KHÔNG đụng `resolvedLabel`: nếu `resolvedFor === val`,
    // `resolvedLabel` đang mang đúng nhãn đã suy được cho CHÍNH giá trị này
    // (vòng sửa 1, phát hiện qua advisor — bản trước gọi resetResolveState()
    // ở đây, xoá luôn resolvedLabel; đổi vatTu qua lại đủ ba lần — lần 1 máy
    // NGOÀI options nên suy qua round-trip, lần 2 máy LỌT vào options (xoá
    // nhãn vừa suy), lần 3 máy lại NGOÀI options nhưng `resolvedFor` không
    // đổi nên `resolveLabel()` không gọi lại — displayLabel kẹt vĩnh viễn ở
    // "đang tải tên…" dù không còn round-trip nào đang chạy — CÙNG HỌ LỖI
    // với Critical đang vá: một dòng có máy thật nhưng câu hiển thị nói khác).
    resolveNotFound.value = false
    resolveError.value = ''
    return
  }
  if (resolvedFor === val) return // đang suy hoặc đã suy xong đúng giá trị này
  resolvedFor = val
  resetResolveState()
  resolveLabel(val)
}
watch(() => props.modelValue, kiemTraCanSuyNhan, { immediate: true })
watch(options, kiemTraCanSuyNhan)

// Không bao giờ trả '' khi modelValue có giá trị — mọi nhánh dưới đây đều
// phải nói đúng thực trạng: "đã ghi máy X" (kèm lý do nếu không xem được chi
// tiết), không được đọc như "chưa chọn máy".
const displayLabel = computed(() => {
  if (!props.modelValue) return ''
  const o = options.value.find((x) => x.name === props.modelValue)
  if (o) return labelOf(o)
  if (resolvedLabel.value) return resolvedLabel.value
  if (resolveError.value) return `Đã ghi máy ${props.modelValue} — lỗi tải tên: ${resolveError.value}`
  if (resolveNotFound.value) return `Đã ghi máy ${props.modelValue} — không xem được chi tiết (ngoài khoa/quyền của bạn)`
  return `Đã ghi máy ${props.modelValue} — đang tải tên…`
})

// --- Tải danh sách gợi ý (dropdown) -----------------------------------------
async function loadOptions() {
  const seq = ++loadSeq
  loading.value = true
  try {
    const res = await api.callKho('kho_thiet_bi_list', {
      tim_kiem: tuKhoa.value.trim() || undefined,
      ca_inactive: 1,
      vat_tu: props.vatTu || undefined,
    })
    if (seq !== loadSeq) return
    options.value = res || []
  } catch (e) {
    if (seq !== loadSeq) return
    showToast(e.message || 'Không tải được danh sách máy.', 'error')
    options.value = []
  } finally {
    if (seq === loadSeq) loading.value = false
  }
}

// Tải NGAY khi vatTu đổi (kể cả lần đầu mount) — không chờ người dùng mở
// dropdown — để còn kịp tự điền khi "chỉ còn đúng một máy hợp lệ" (Task 13,
// mục "Ba việc trên màn phiếu xuất"). Không tự điền đè lên một lựa chọn đã
// có (chỉ khi modelValue đang rỗng).
//
// Tự điền CHỈ khi `vatTu` THẬT (đã bật lọc tầng hai) — không áp cho danh
// sách KHÔNG lọc (vatTu rỗng, vd. ô "Máy mặc định" hoặc một dòng chưa chọn
// vật tư). Thiếu điều kiện này: một đơn vị chỉ có ĐÚNG MỘT máy active sẽ bị
// tự điền máy đó vào MỌI ô — kể cả "Máy mặc định" lúc mới mở form và mọi
// dòng còn trống trước khi người dùng kịp chọn vật tư — dù họ chưa hề bấm gì
// (bug thật, phát hiện lúc kiểm bằng tay: tạo xong một máy khiến nó thành máy
// active DUY NHẤT của bệnh viện demo, dòng thứ hai — vật tư còn để trống —
// lập tức tự mang máy đó). Câu "chỉ còn đúng một máy hợp lệ" trong brief đi
// liền sau "chọn vật tư xong", tức chỉ đúng khi có một bộ lọc thật đang áp.
watch(
  () => props.vatTu,
  async () => {
    if (props.disabled) return
    await loadOptions()
    if (props.autoSelectSingle && props.vatTu && !props.modelValue && options.value.length === 1) {
      emit('update:modelValue', options.value[0].name)
      emit('picked', options.value[0])
    }
  },
  { immediate: true }
)

function onFocus() {
  if (props.disabled) return
  open.value = true
  tuKhoa.value = ''
  loadOptions()
}
function onInput(e) {
  tuKhoa.value = e.target.value
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadOptions, 250)
}
function onBlur() {
  open.value = false
}
// `o` rỗng ({name: ''}) ứng với mục "— Không chọn máy —".
function selectOption(o) {
  emit('update:modelValue', o.name || null)
  if (o.name) emit('picked', o)
  tuKhoa.value = ''
  open.value = false
}
function onCreateNewClick() {
  emit('createNew', { search: tuKhoa.value.trim() })
  open.value = false
}

onUnmounted(() => clearTimeout(searchTimer))
</script>

<template>
  <input v-if="disabled" type="text" disabled :value="displayLabel || '—'" :title="displayLabel" />
  <div v-else class="tb-picker">
    <input
      type="text"
      :value="open ? tuKhoa : displayLabel"
      :title="!open ? displayLabel : ''"
      placeholder="Tìm hoặc chọn máy…"
      autocomplete="off"
      @focus="onFocus"
      @input="onInput"
      @blur="onBlur"
    />
    <div v-if="open" class="tb-picker-menu">
      <!-- Quy tắc 1+2: ghim dòng đầu, hiện cả khi đã có kết quả; mousedown.prevent
           bắt buộc — @click sẽ thua sự kiện blur của input ở trên. -->
      <button type="button" class="tb-picker-create" @mousedown.prevent="onCreateNewClick">
        + Tạo nhanh máy{{ tuKhoa.trim() ? ` "${tuKhoa.trim()}"` : '' }}
      </button>
      <div v-if="loading" class="tb-picker-empty">Đang tải…</div>
      <template v-else>
        <button type="button" class="tb-picker-opt" @mousedown.prevent="selectOption({ name: '' })">
          — Không chọn máy —
        </button>
        <button
          v-for="o in options"
          :key="o.name"
          type="button"
          class="tb-picker-opt"
          :class="{ on: o.name === modelValue }"
          @mousedown.prevent="selectOption(o)"
        >
          {{ labelOf(o) }}
        </button>
        <div v-if="!options.length" class="tb-picker-empty">Không có máy nào khớp — dùng nút tạo nhanh phía trên.</div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.tb-picker { position: relative; }
.tb-picker-menu {
  position: absolute;
  z-index: 95;
  left: 0;
  right: 0;
  top: calc(100% + 2px);
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.12);
  max-height: 260px;
  overflow-y: auto;
}
.tb-picker-create {
  display: block;
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  font-size: 13px;
  font-weight: 600;
  color: var(--blue);
  background: #eff6ff;
  border: none;
  border-bottom: 1px solid var(--line);
  cursor: pointer;
}
.tb-picker-create:hover { background: #dbeafe; }
.tb-picker-opt {
  display: block;
  width: 100%;
  text-align: left;
  padding: 7px 10px;
  font-size: 13px;
  color: var(--dark);
  background: #fff;
  border: none;
  border-bottom: 1px solid #f1f5f9;
  cursor: pointer;
}
.tb-picker-opt:last-child { border-bottom: none; }
.tb-picker-opt:hover { background: #f8fafc; }
.tb-picker-opt.on { background: #eff6ff; font-weight: 600; }
.tb-picker-empty { padding: 8px 10px; font-size: 12px; color: var(--gray); }
</style>
