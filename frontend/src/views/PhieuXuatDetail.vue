<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtVND, fmtDate } from '../format'
import { showToast } from '../toast'
import { phieuActions, trangThaiBadge } from '../kho-actions'
import { useIsMobile } from '../useMobile'
import { useDongPhieu } from '../useDongPhieu'
import VatTuModal from '../components/VatTuModal.vue'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

const DOCTYPE = 'Customer Stock Issue'
const LOAI_OPTIONS = ['Xuất sử dụng', 'Xuất huỷ - hết hạn', 'Xuất trả lại', 'Điều chỉnh kiểm kê']
// "Phiếu đảo" CỐ Ý không có trong danh sách — cùng lý do với PhieuNhapDetail.

// Phải khớp ledger.LOT_KHONG_CO ở backend (miyano_portal/kho/ledger.py) —
// sentinel gán cho so_lo khi vật tư CÓ (r.vat_tu hợp lệ) nhưng CHƯA CÒN tồn
// lô nào (vừa tạo nhanh, hoặc đã xuất hết). so_lo là trường reqd ở cả
// _validate_items_present (api/kho.py) lẫn Customer Stock Issue Item, nên để
// trống sẽ bị chặn ngay từ Lưu nháp — chốt tồn thật sự chỉ chạy ở
// before_submit (_chan_xuat_qua_ton), đúng như constraint "lưu nháp được,
// ghi sổ mới bị chặn".
const LOT_KHONG_CO = 'KHONG-LO'

const isNew = computed(() => route.params.name === 'moi')

const loading = ref(true)
const error = ref('')
const saving = ref(false)
const submitting = ref(false)
const cancelling = ref(false)

const doc = reactive({
  name: '',
  ngay: new Date().toISOString().slice(0, 10),
  loai_xuat: 'Xuất sử dụng',
  noi_nhan: '',
  nguoi_nhan: '',
  dien_giai: '',
  docstatus: 0,
  tong_tien: 0,
  items: [],
})

const vatTuList = ref([])

const editable = computed(() => isNew.value || doc.docstatus === 0)
const actions = computed(() => phieuActions(doc))
const badge = computed(() => trangThaiBadge(doc.docstatus))

function blankRow() {
  return {
    vat_tu: '', so_lo: '', so_luong: 1, xac_nhan_het_han: false, ghi_chu: '',
    han_su_dung: null, don_gia: 0, // chỉ để xem trước — server luôn tính lại từ lô
    _lots: [], _lotsLoading: false, _hetHan: false,
  }
}
function addRow() {
  doc.items.push(blankRow())
}
function removeRow(idx) {
  doc.items.splice(idx, 1)
}

function applyLotToRow(row, soLo) {
  const lot = row._lots.find((l) => l.so_lo === soLo)
  if (!lot) return
  row.so_lo = lot.so_lo
  row.han_su_dung = lot.han_su_dung
  row.don_gia = lot.don_gia
  row._hetHan = !!lot.het_han
  if (!row._hetHan) row.xac_nhan_het_han = false
}

// Đặt lại TOÀN BỘ trạng thái phụ thuộc lô của một dòng về mặc định — dùng ở
// mọi nơi dòng không còn gắn với đúng một lô cụ thể (chưa có vật tư, hoặc
// vật tư vừa chọn không còn tồn lô nào). Reset từng phần riêng lẻ (như bản
// trước chỉ xoá _lots) để sót _hetHan/xac_nhan_het_han của vật tư CŨ: dòng
// vừa hiện "Chọn vật tư trước" vừa hiện sẵn checkbox "Xác nhận xuất lô đã
// hết hạn" đã tích, và nếu vật tư gán sau đó (kể cả vật tư "đã có sẵn" khi
// tạo nhanh) cũng có lô hết hạn, applyLotToRow() không tự xoá được cờ tích
// sẵn đó (guard của nó chỉ chạy khi lô MỚI còn hạn) — vô hiệu hoá chốt an
// toàn ở validateClient() cho một lô người dùng chưa từng nhìn thấy.
function resetLotState(row) {
  row._lots = []
  row.so_lo = ''
  row.han_su_dung = null
  row.don_gia = 0
  row._hetHan = false
  row.xac_nhan_het_han = false
}

// Gọi kho_lo_goi_y() để lấy danh sách lô theo thứ tự FEFO (hạn gần nhất
// trước, lô không hạn xếp cuối) kèm số lượng đề xuất lấy từ mỗi lô — và mặc
// định chọn lô đầu tiên trả về, tức lô gần hết hạn nhất.
async function loadLotsForRow(row) {
  if (!row.vat_tu) {
    resetLotState(row)
    return
  }
  row._lotsLoading = true
  try {
    const out = await api.callKho('kho_lo_goi_y', { vat_tu: row.vat_tu, so_luong: row.so_luong || 0 })
    row._lots = out.lots || []
    if (row._lots.length) {
      // Giữ lựa chọn cũ nếu lô đó vẫn còn trong danh sách (đổi so_luong không
      // nên tự đổi lô người dùng đã chọn); nếu chưa chọn hoặc lô cũ hết
      // tồn thì mặc định lô đầu tiên (gần hết hạn nhất).
      const stillThere = row._lots.some((l) => l.so_lo === row.so_lo)
      applyLotToRow(row, stillThere ? row.so_lo : row._lots[0].so_lo)
    } else {
      resetLotState(row)
      // Vật tư có thật (row.vat_tu đã set — hàm đã return sớm nếu không) mà
      // chưa còn tồn lô nào: gán sentinel để Lưu nháp qua được cả rào client
      // (!r.so_lo) lẫn rào server (_validate_items_present) — người dùng vẫn
      // thấy đúng cảnh báo "chưa còn tồn lô nào" ở ô Lô vì nhánh hiển thị dựa
      // vào r._lots.length, không dựa vào r.so_lo.
      row.so_lo = LOT_KHONG_CO
    }
  } catch (e) {
    showToast(e.message || 'Không tải được danh sách lô.', 'error')
  } finally {
    row._lotsLoading = false
  }
}

function onVatTuChange(row) {
  // Đổi hẳn sang vật tư khác: lô/hạn dùng/đơn giá của vật tư CŨ hết ý nghĩa
  // — và quan trọng hơn, một tick "đã xác nhận hết hạn" của lô cũ không được
  // sống sót sang một lô hoàn toàn khác mà người dùng chưa từng nhìn thấy,
  // KỂ CẢ khi lô mới cũng hết hạn. Chỉ dựa vào guard trong applyLotToRow()
  // (`if (!row._hetHan) ...`) là không đủ: guard đó chỉ tự xoá tick khi lô
  // MỚI còn hạn, nên nếu lô mới cũng hết hạn thì tick cũ lọt qua. Xoá thẳng
  // ở đây — TRƯỚC khi nạp lô mới — để applyLotToRow() luôn khởi động từ
  // xac_nhan_het_han = false, không phụ thuộc lô mới hết hạn hay không.
  //
  // KHÔNG đặt reset này trong loadLotsForRow(): hàm đó còn được gọi từ
  // onSoLuongChange() khi người dùng chỉ sửa SỐ LƯỢNG trên CÙNG một lô — lúc
  // đó phải GIỮ NGUYÊN tick đã xác nhận cho đúng lô đang chọn, không phải
  // xoá vô điều kiện.
  resetLotState(row)
  loadLotsForRow(row)
}

// Tạo nhanh vật tư ngay trong ô chọn (mục "➕ Tạo vật tư mới…") — trạng thái
// modal và xử lý gán dùng chung với PhieuNhapDetail, xem useDongPhieu.js.
// Khác PhieuNhapDetail ở một điểm: vật tư vừa tạo chưa có lô nào, nên sau khi
// gán phải nạp lô cho dòng đó như khi người dùng tự đổi ô chọn (onVatTuChange)
// — để cảnh báo "chưa có tồn" hiện ra từ chính dữ liệu trả về. Đồng thời đánh
// dấu row._vua_tao = true: modal luôn ở mode="tao" nên mọi lần onAssigned
// được gọi đều là vừa tạo vật tư mới, chưa từng nhập kho lần nào.
function onVatTuAssigned(row) {
  row._vua_tao = true
  onVatTuChange(row)
}

// Task 11: nối luồng import/export Excel — dùng chung composable với
// PhieuNhapDetail (xem useDongPhieu.js). Khác phiếu nhập: dòng đọc từ tệp
// KHÔNG mang don_gia/han_su_dung (controller Customer Stock Issue luôn lấy
// hai giá trị đó từ lô đã chọn), nên extraRowFields ở đây không đụng tới hai
// trường đó, chỉ khởi tạo bốn trường trạng thái lô mà bảng dòng cần cho MỌI
// dòng import (kể cả "ma_moi"/"loi", vat_tu rỗng) — <template> đọc
// r._lots.length không phòng thủ ở ô chọn lô, thiếu bốn trường này là vỡ
// render ngay khi Vue vẽ dòng đó, trước khi bất kỳ callback nào kịp chạy.
const {
  MUC_TAO_MOI,
  modalOpen,
  modalInitial,
  onVatTuSelect,
  onVatTuSaved,
  importing,
  importInput,
  mauUrl,
  exportUrl,
  dongChuaXuLy,
  onImportFile,
  moTaoTuDong,
} = useDongPhieu({
  doc,
  vatTuList,
  onAssigned: onVatTuAssigned,
  loai: 'xuat',
  DOCTYPE,
  extraRowFields: () => ({
    xac_nhan_het_han: false,
    _lots: [],
    _lotsLoading: false,
    _hetHan: false,
  }),
  // Nạp lô ngay cho dòng đã khớp mã (có vat_tu) để người dùng thấy lô nào còn
  // tồn; dòng "ma_moi"/"loi" chưa có vat_tu thì bỏ qua, sẽ nạp khi tạo nhanh
  // xong (qua onVatTuAssigned). Composable gọi callback này cho MỌI dòng —
  // việc lọc theo vat_tu là trách nhiệm của chính callback, không phải
  // composable.
  onRowImported: (row) => {
    if (row.vat_tu) onVatTuChange(row)
  },
})

function onSoLuongChange(row, val) {
  row.so_luong = Number(val) || 0
  loadLotsForRow(row)
}
function onSoLoChange(row) {
  applyLotToRow(row, row.so_lo)
}

function rowThanhTien(row) {
  return (Number(row.so_luong) || 0) * (Number(row.don_gia) || 0)
}
const tongTienPreview = computed(() => doc.items.reduce((s, r) => s + rowThanhTien(r), 0))

async function loadVatTu() {
  try {
    vatTuList.value = await api.callKho('kho_vat_tu_list')
  } catch (e) {
    showToast(e.message || 'Không tải được danh mục vật tư.', 'error')
  }
}

async function load() {
  if (isNew.value) {
    loading.value = false
    if (!doc.items.length) addRow()
    return
  }
  loading.value = true
  error.value = ''
  try {
    const out = await api.callKho('kho_phieu_get', { doctype: DOCTYPE, name: route.params.name })
    Object.assign(doc, out)
    doc.items = (out.items || []).map((r) => ({
      ...r, _lots: [], _lotsLoading: false, _hetHan: false,
    }))
    // Nháp đã có dòng sẵn (ví dụ do Delivery Note sinh, hoặc lưu dở lần
    // trước): nạp lại danh sách lô cho từng dòng để select không trống —
    // loadLotsForRow() tự giữ nguyên so_lo hiện tại nếu nó còn trong tồn.
    if (doc.docstatus === 0) {
      await Promise.all(doc.items.map((r) => loadLotsForRow(r)))
    }
  } catch (e) {
    error.value = e.message || 'Không tải được phiếu xuất.'
  } finally {
    loading.value = false
  }
}

function validateClient() {
  if (!doc.items.length) {
    showToast('Phiếu phải có ít nhất một dòng vật tư.', 'error')
    return false
  }
  for (const [i, r] of doc.items.entries()) {
    if (!r.vat_tu) {
      showToast(`Dòng ${i + 1}: chưa chọn vật tư.`, 'error')
      return false
    }
    if (!r.so_lo) {
      showToast(`Dòng ${i + 1}: chưa chọn lô.`, 'error')
      return false
    }
    if (r._hetHan && !r.xac_nhan_het_han) {
      showToast(`Dòng ${i + 1}: lô ${r.so_lo} đã hết hạn — tích xác nhận trước khi xuất.`, 'error')
      return false
    }
  }
  return true
}

function payload() {
  const p = {
    ngay: doc.ngay,
    loai_xuat: doc.loai_xuat,
    noi_nhan: doc.noi_nhan,
    nguoi_nhan: doc.nguoi_nhan,
    dien_giai: doc.dien_giai,
    items: doc.items.map((r) => ({
      vat_tu: r.vat_tu, so_lo: r.so_lo, so_luong: r.so_luong,
      xac_nhan_het_han: r.xac_nhan_het_han ? 1 : 0, ghi_chu: r.ghi_chu,
    })),
  }
  if (!isNew.value) p.name = doc.name
  return p
}

async function save({ silent } = {}) {
  if (dongChuaXuLy.value) {
    showToast(`Còn ${dongChuaXuLy.value} dòng chưa xử lý (thiếu vật tư hoặc sai dữ liệu).`, 'error')
    return null
  }
  if (!validateClient()) return null
  saving.value = true
  try {
    const before = doc.items // giữ tham chiếu TRƯỚC khi Object.assign ghi đè
    const out = await api.callKho('kho_phieu_xuat_save', { payload: payload() })
    const savedItems = out.items
    Object.assign(doc, out)
    // Giữ lại danh sách lô (_lots) đã tải của mỗi dòng theo (vat_tu, so_lo) —
    // tránh gọi lại kho_lo_goi_y() cho những dòng không đổi, chỉ nạp thêm
    // cho dòng thật sự thiếu (dòng mới, hoặc lô vừa đổi).
    doc.items = savedItems.map((r) => {
      const cu = before.find((old) => old.vat_tu === r.vat_tu && old.so_lo === r.so_lo)
      return {
        ...r,
        _lots: cu ? cu._lots : [],
        _lotsLoading: false,
        _hetHan: cu ? cu._hetHan : false,
        // Giữ cờ "vừa tạo" qua vòng lưu — không thì cảnh báo "phải nhập kho
        // trước khi ghi sổ" biến mất ngay lúc người dùng cần thấy nó nhất:
        // vừa lưu nháp xong, đang nhìn phiếu chưa ghi sổ được.
        _vua_tao: cu ? cu._vua_tao : false,
      }
    })
    if (doc.docstatus === 0) {
      await Promise.all(doc.items.filter((r) => !r._lots.length).map((r) => loadLotsForRow(r)))
    }
    if (isNew.value) {
      router.replace(`/kho/xuat/${out.name}`)
    }
    if (!silent) showToast('Đã lưu phiếu nháp.')
    return out
  } catch (e) {
    showToast(e.message || 'Không lưu được phiếu.', 'error')
    return null
  } finally {
    saving.value = false
  }
}

async function doSubmit() {
  const saved = await save({ silent: true })
  if (!saved) return
  if (!window.confirm(`Ghi sổ phiếu ${saved.name}? Tồn kho sẽ bị trừ ngay. Sau khi ghi sổ chỉ có thể huỷ, không sửa được nữa.`)) return
  submitting.value = true
  try {
    const out = await api.callKho('kho_phieu_submit', { doctype: DOCTYPE, name: saved.name })
    Object.assign(doc, out)
    showToast(`Đã ghi sổ phiếu ${out.name}.`)
  } catch (e) {
    showToast(e.message || 'Không ghi sổ được phiếu.', 'error')
  } finally {
    submitting.value = false
  }
}

async function doCancel() {
  if (!window.confirm(`Huỷ phiếu ${doc.name}? Hệ thống sẽ sinh một phiếu đảo để hoàn tồn.`)) return
  cancelling.value = true
  try {
    const out = await api.callKho('kho_phieu_cancel', { doctype: DOCTYPE, name: doc.name })
    Object.assign(doc, out)
    showToast('Đã huỷ phiếu, tồn kho đã được hoàn trả.')
  } catch (e) {
    showToast(e.message || 'Không huỷ được phiếu.', 'error')
  } finally {
    cancelling.value = false
  }
}

const printUrl = computed(
  () =>
    `/api/method/miyano_portal.api.kho.kho_phieu_pdf?doctype=${encodeURIComponent(DOCTYPE)}&name=${encodeURIComponent(doc.name)}`
)

function onAction(key) {
  if (key === 'submit') doSubmit()
  else if (key === 'cancel') doCancel()
  else if (key === 'print') window.open(printUrl.value, '_blank')
}

onMounted(async () => {
  await Promise.all([loadVatTu(), load()])
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>{{ isNew ? 'Tạo phiếu xuất kho' : doc.name }}</h2>
        <div class="sub" v-if="!isNew">
          <span class="badge" :class="badge.cls">{{ badge.label }}</span>
        </div>
      </div>
      <div class="flex" style="gap: 8px">
        <button
          v-for="a in actions"
          :key="a.key"
          class="btn"
          :class="{ 'btn-o': a.variant !== 'primary', 'btn-danger': a.variant === 'danger' }"
          :disabled="submitting || cancelling"
          @click="onAction(a.key)"
        >
          {{ a.label }}
        </button>
        <button v-if="editable" class="btn-o" :disabled="saving" @click="save()">
          {{ saving ? 'Đang lưu…' : 'Lưu nháp' }}
        </button>
        <router-link to="/kho/xuat" class="btn-o">Quay lại</router-link>
      </div>
    </div>
    <div v-else style="margin-bottom: 12px">
      <div class="sb">
        <h2>{{ isNew ? 'Tạo phiếu xuất' : doc.name }}</h2>
        <span v-if="!isNew" class="badge" :class="badge.cls">{{ badge.label }}</span>
      </div>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>

    <template v-else>
      <div class="card mb10">
        <div class="grid2">
          <div class="field">
            <label>Ngày</label>
            <input type="date" v-model="doc.ngay" :disabled="!editable" />
          </div>
          <div class="field">
            <label>Loại xuất</label>
            <select v-model="doc.loai_xuat" :disabled="!editable">
              <option v-for="o in LOAI_OPTIONS" :key="o" :value="o">{{ o }}</option>
              <option v-if="!LOAI_OPTIONS.includes(doc.loai_xuat)" :value="doc.loai_xuat">{{ doc.loai_xuat }}</option>
            </select>
          </div>
          <div class="field">
            <label>Nơi nhận</label>
            <input v-model="doc.noi_nhan" :disabled="!editable" placeholder="VD: Khoa Hồi sức tích cực" />
          </div>
          <div class="field">
            <label>Người nhận</label>
            <input v-model="doc.nguoi_nhan" :disabled="!editable" />
          </div>
        </div>
        <div class="field" style="margin-top: 10px">
          <label>Lý do xuất</label>
          <textarea v-model="doc.dien_giai" :disabled="!editable" rows="2"></textarea>
        </div>
      </div>

      <div v-if="editable" class="flex mb10" style="gap: 8px; flex-wrap: wrap">
        <a class="btn-o btn-sm" :href="mauUrl">Tải file mẫu</a>
        <button class="btn-o btn-sm" :disabled="importing" @click="importInput.click()">
          {{ importing ? 'Đang đọc…' : '⬆ Nhập từ Excel' }}
        </button>
        <a v-if="doc.name" class="btn-o btn-sm" :href="exportUrl">⬇ Xuất Excel</a>
        <input ref="importInput" type="file" accept=".xlsx" style="display: none" @change="onImportFile" />
      </div>

      <div class="card" style="padding: 0; overflow-x: auto">
        <table>
          <thead>
            <tr>
              <th style="min-width: 180px">Vật tư</th>
              <th style="min-width: 220px">Lô (FEFO)</th>
              <th>Hạn dùng</th>
              <th class="right">Tồn lô</th>
              <th class="right">Số lượng xuất</th>
              <th class="right">Đơn giá</th>
              <th class="right">Thành tiền</th>
              <th v-if="editable"></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(r, idx) in doc.items"
              :key="idx"
              :style="r._trang_thai === 'loi' ? 'background:#fff1f0' : (r._trang_thai === 'ma_moi' ? 'background:#fffbe6' : '')"
            >
              <td>
                <select
                  v-if="editable"
                  v-model="r.vat_tu"
                  style="width: 100%"
                  @change="onVatTuSelect(r, idx); onVatTuChange(r)"
                >
                  <option value="" disabled>-- Chọn vật tư --</option>
                  <option v-for="v in vatTuList" :key="v.name" :value="v.name">
                    {{ v.ma_vat_tu }} — {{ v.ten_vat_tu }}
                  </option>
                  <option :value="MUC_TAO_MOI">➕ Tạo vật tư mới…</option>
                </select>
                <span v-else>{{ r.ten_vat_tu }}</span>

                <div v-if="editable && r._trang_thai === 'ma_moi' && !r.vat_tu" class="warn" style="margin-top: 4px">
                  ⚠ Mã <b>{{ r._ma_vat_tu }}</b> chưa có trong kho.
                  <button class="btn-o btn-sm" @click="moTaoTuDong(r, idx)">Tạo vật tư mới</button>
                </div>
                <div v-if="r._loi && r._loi.length" class="tag" style="color: #cf1322; margin-top: 4px">
                  ✗ Dòng {{ r._loi_line }} trong tệp: {{ r._loi.join('; ') }}
                </div>
              </td>
              <td>
                <template v-if="editable">
                  <div v-if="r._lotsLoading" class="tag">Đang tải lô…</div>
                  <select v-else-if="r._lots.length" v-model="r.so_lo" style="width: 100%" @change="onSoLoChange(r)">
                    <option v-for="l in r._lots" :key="l.so_lo" :value="l.so_lo">
                      {{ l.so_lo }} · còn {{ Number(l.so_luong_ton).toLocaleString('vi-VN') }}
                      {{ l.han_su_dung ? '· HSD ' + fmtDate(l.han_su_dung) : '· không hạn' }}
                      {{ l.het_han ? ' ⚠ QUÁ HẠN' : '' }}
                    </option>
                  </select>
                  <span v-else-if="r.vat_tu" class="tag">
                    Vật tư này chưa còn tồn lô nào.
                    <template v-if="r._vua_tao">
                      Đây là vật tư vừa tạo — phải nhập kho trước khi ghi sổ phiếu xuất này.
                    </template>
                  </span>
                  <span v-else class="tag">Chọn vật tư trước</span>
                  <div v-if="r._hetHan" class="warn" style="margin-top: 4px; display: flex; align-items: center; gap: 4px">
                    <label style="display: flex; align-items: center; gap: 4px; font-weight: 600">
                      <input type="checkbox" v-model="r.xac_nhan_het_han" />
                      Xác nhận xuất lô đã hết hạn
                    </label>
                  </div>
                </template>
                <span v-else>
                  {{ r.so_lo }}
                  <span v-if="r.xac_nhan_het_han" class="badge b-red" style="margin-left: 4px">Đã xác nhận hết hạn</span>
                </span>
              </td>
              <td>{{ r.han_su_dung ? fmtDate(r.han_su_dung) : '—' }}</td>
              <td class="right">
                <span v-if="editable && r._lots.length">
                  {{ Number((r._lots.find((l) => l.so_lo === r.so_lo) || {}).so_luong_ton || 0).toLocaleString('vi-VN') }}
                </span>
                <span v-else>—</span>
              </td>
              <td class="right">
                <input
                  v-if="editable"
                  :value="r.so_luong"
                  @change="onSoLuongChange(r, $event.target.value)"
                  inputmode="numeric"
                  style="width: 80px; text-align: right"
                />
                <span v-else>{{ Number(r.so_luong).toLocaleString('vi-VN') }}</span>
              </td>
              <td class="right">{{ fmtVND(r.don_gia) }}</td>
              <td class="right">{{ fmtVND(rowThanhTien(r)) }}</td>
              <td v-if="editable">
                <button class="btn-o btn-sm" @click="removeRow(idx)">✕</button>
              </td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td colspan="6" style="text-align: right"><b>Tổng cộng</b></td>
              <td class="right"><b>{{ fmtVND(editable ? tongTienPreview : doc.tong_tien) }}</b></td>
              <td v-if="editable"></td>
            </tr>
          </tfoot>
        </table>
      </div>
      <p class="tag" style="margin-top: 6px" v-if="editable">
        Đơn giá và hạn dùng lấy tự động theo lô đã chọn, không thể sửa tay.
      </p>
      <button v-if="editable" class="btn-o btn-sm" style="margin-top: 10px" @click="addRow">+ Thêm dòng</button>

      <div v-if="isMobile" class="flex" style="gap: 8px; margin-top: 16px; flex-wrap: wrap">
        <button
          v-for="a in actions"
          :key="a.key"
          class="btn"
          :class="{ 'btn-o': a.variant !== 'primary', 'btn-danger': a.variant === 'danger' }"
          :disabled="submitting || cancelling"
          @click="onAction(a.key)"
        >
          {{ a.label }}
        </button>
        <button v-if="editable" class="btn-o" :disabled="saving" @click="save()">
          {{ saving ? 'Đang lưu…' : 'Lưu nháp' }}
        </button>
      </div>

      <VatTuModal
        :open="modalOpen"
        :initial="modalInitial"
        mode="tao"
        @saved="onVatTuSaved"
        @close="modalOpen = false"
      />
    </template>
  </div>
</template>
