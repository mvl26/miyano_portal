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
import NccModal from '../components/NccModal.vue'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

// Khớp EPS phía server (miyano_portal.kho.ledger.EPS) — chỉ để so sánh float
// cho ĐÚNG cùng ngưỡng khi báo lỗi sớm ở client; chốt chặn thật vẫn ở server
// (_validate_doi_soat_giao_nhan, BR-K17).
const EPS = 0.0005

const DOCTYPE = 'Customer Stock Receipt'
const LOAI_MUA_NGOAI = 'Mua ngoài (NCC khác)'
const LOAI_OPTIONS = [
  'Nhập khác', 'Tồn đầu kỳ', 'Từ đơn hàng Miyano', LOAI_MUA_NGOAI, 'Điều chỉnh kiểm kê (tăng)',
]
// "Phiếu đảo" CỐ Ý không có trong danh sách: backend chặn tự tạo phiếu loại
// này bằng flags.dang_tao_dao (in-memory, không thể forge), nên hiện nó ra
// làm lựa chọn chỉ để rồi báo lỗi khi lưu là đúng kiểu "nút sẽ lỗi khi bấm"
// mà declaring-document-actions cảnh báo.

// Giá trị đặc biệt cho mục "+ Tạo NCC mới…" trong ô chọn NCC — cùng khuôn
// MUC_TAO_MOI của useDongPhieu.js nhưng cho NCC (không phải dòng vật tư nên
// không hợp để nhét chung vào composable đó).
const MUC_TAO_NCC = '__tao_ncc_moi__'

const isNew = computed(() => route.params.name === 'moi')

const loading = ref(true)
const error = ref('')
const saving = ref(false)
const submitting = ref(false)
const cancelling = ref(false)

const doc = reactive({
  name: '',
  ngay: new Date().toISOString().slice(0, 10),
  loai_nhap: 'Nhập khác',
  nguoi_giao: '',
  chung_tu_kem: '',
  dien_giai: '',
  docstatus: 0,
  tong_tien: 0,
  items: [],
  // E4/BR-N1,N2: chỉ có ý nghĩa khi loai_nhap = "Mua ngoài (NCC khác)" —
  // server tự xoá ba trường này khi đổi sang loại khác (customer_stock_
  // receipt.py._validate_ncc), template chỉ ẩn/hiện theo loai_nhap.
  ncc: '',
  so_chung_tu_ncc: '',
  ngay_chung_tu: '',
  thieu_chung_tu: 0,
})

const vatTuList = ref([])
const vatTuLoading = ref(true)
const nccList = ref([])
const nccModalOpen = ref(false)

async function loadNcc() {
  try {
    // ca_inactive=1: một phiếu CŨ có thể đang trỏ tới một NCC đã bị tắt SAU
    // khi phiếu được lập — tải cả NCC tắt để ô chọn còn hiển thị đúng tên
    // (không rơi về rỗng), chỉ disable lựa chọn đó cho phiếu MỚI/còn sửa
    // (server chặn lại lần nữa nếu client lách qua được — BR-N3).
    nccList.value = await api.callKho('kho_ncc_list', { ca_inactive: 1 })
  } catch (e) {
    showToast(e.message || 'Không tải được danh mục NCC.', 'error')
  }
}

function onNccSelect() {
  if (doc.ncc !== MUC_TAO_NCC) return
  doc.ncc = ''
  nccModalOpen.value = true
}

function onNccSaved(row) {
  // Nhánh "Đây là trùng — tắt bản này" của NccModal trả về NCC với active=0
  // (kho_ncc_save không xoá, chỉ tắt) — không được tự gán vào phiếu: server
  // chặn cứng chọn NCC tắt trên phiếu mới (BR-N3), và ô chọn active-only sẽ
  // không còn thấy nó ở lần tải lại nào sau này.
  if (!row.active) {
    nccList.value = nccList.value.filter((n) => n.name !== row.name)
    if (doc.ncc === row.name) doc.ncc = ''
    nccModalOpen.value = false
    return
  }
  if (!nccList.value.some((n) => n.name === row.name)) nccList.value.push(row)
  doc.ncc = row.name
  nccModalOpen.value = false
}

// Tạo nhanh vật tư ngay trong ô chọn (mục "➕ Tạo vật tư mới…") VÀ toàn bộ
// luồng import/export Excel của bảng dòng — dùng chung với PhieuXuatDetail,
// xem useDongPhieu.js. Phiếu nhập không cần bước gì thêm sau khi gán vật tư
// nên không truyền onAssigned/onRowImported; điểm riêng của phiếu nhập là
// don_gia/han_su_dung đọc được từ tệp, tiêm vào qua extraRowFields.
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
  loai: 'nhap',
  DOCTYPE,
  extraRowFields: (r) => ({
    han_su_dung: r.han_su_dung || '',
    don_gia: r.don_gia || 0,
  }),
})

const editable = computed(() => isNew.value || doc.docstatus === 0)
const actions = computed(() => phieuActions(doc))
const badge = computed(() => trangThaiBadge(doc.docstatus))

function tenVatTu(vatTu) {
  const vt = vatTuList.value.find((v) => v.name === vatTu)
  return vt ? vt.ten_vat_tu : ''
}
function dvtVatTu(vatTu) {
  const vt = vatTuList.value.find((v) => v.name === vatTu)
  return vt ? vt.dvt : ''
}

function rowThanhTien(row) {
  return (Number(row.so_luong) || 0) * (Number(row.don_gia) || 0)
}
const tongTienPreview = computed(() => doc.items.reduce((s, r) => s + rowThanhTien(r), 0))

// BR-K17 chỉ áp cho dòng có nguồn gốc Miyano (hook điền sl_giao > 0 khi tạo
// phiếu từ Delivery Note) — kiểm bằng GIÁ TRỊ của sl_giao, không đoán theo
// loai_nhap, đúng nguyên tắc mà server dùng (customer_stock_receipt.py).
// Dòng gõ tay (Nhập khác/Tồn đầu kỳ) hoặc dòng đọc từ Excel không có
// sl_giao — Number(undefined) || 0 = 0 nên tự động rơi ra ngoài quy tắc này.
function slGiao(row) {
  return Number(row.sl_giao) || 0
}
function coChenhLech(row) {
  const giao = slGiao(row)
  if (!giao) return false
  return Math.abs((Number(row.so_luong) || 0) - giao) > EPS
}
function thieuLyDo(row) {
  return coChenhLech(row) && !(row.ly_do_chenh_lech || '').trim()
}

function addRow() {
  doc.items.push({
    vat_tu: '', so_lo: '', han_su_dung: '', so_luong: 1, don_gia: 0, ghi_chu: '',
    // Dòng gõ tay không bao giờ có sl_giao (chỉ hook tạo từ Delivery Note mới
    // có) — khai rõ 0/'' ở đây để khỏi lẫn với dòng do hook sinh.
    sl_giao: 0, ly_do_chenh_lech: '', thieu_lo_han: 0,
  })
}
function removeRow(idx) {
  doc.items.splice(idx, 1)
}

async function loadVatTu() {
  vatTuLoading.value = true
  try {
    vatTuList.value = await api.callKho('kho_vat_tu_list')
  } catch (e) {
    showToast(e.message || 'Không tải được danh mục vật tư.', 'error')
  } finally {
    vatTuLoading.value = false
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
  } catch (e) {
    error.value = e.message || 'Không tải được phiếu nhập.'
  } finally {
    loading.value = false
  }
}

function validateClient() {
  // US-E4.2/BR-N1: server chặn cứng thiếu NCC khi Mua ngoài — kiểm sớm ở đây
  // để lỗi hiện ngay tại chỗ, không đợi một vòng gọi mạng rồi mới biết.
  if (doc.loai_nhap === LOAI_MUA_NGOAI && !doc.ncc) {
    showToast('Chọn nhà cung cấp cho phiếu mua ngoài.', 'error')
    return false
  }
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
      showToast(`Dòng ${i + 1}: chưa nhập số lô.`, 'error')
      return false
    }
    // Dòng đọc từ tệp có thể mang Số lượng ≤ 0 (ô trống thành 0, hoặc số âm).
    // Server đã chặn bằng voucher._check_so_luong; kiểm ở đây để người dùng
    // đang sửa một dòng đỏ tại chỗ biết ngay còn thiếu gì, không phải đợi một
    // vòng gọi mạng.
    //
    // C1 (E3 phần B review): so_luong = 0 giờ HỢP LỆ, nhưng CHỈ trên dòng
    // nguồn Miyano (sl_giao > 0 — "nhận 0" đi qua đúng đường BR-K17 bên
    // dưới, bắt lý do, không phải bị chặn cứng buộc thủ kho phải xoá cả
    // dòng để lưu được). Khai `giao` TRƯỚC để dùng ở cả hai chỗ.
    const giao = slGiao(r)
    const soLuongRaw = Number(r.so_luong) || 0
    if (soLuongRaw < 0 || (soLuongRaw === 0 && !giao)) {
      showToast(`Dòng ${i + 1}: số lượng phải lớn hơn 0.`, 'error')
      return false
    }
    // BR-K17 (US-E3.3) — chặn sớm cho đỡ mất công gửi, NHƯNG server vẫn là
    // chốt cuối (_validate_doi_soat_giao_nhan chạy lại y hệt trên save/submit
    // dù client có bỏ sót gì). Nguyên văn thông điệp khớp server để người
    // dùng không thấy hai câu khác nhau cho cùng một lỗi.
    if (giao > 0) {
      const soLuong = soLuongRaw
      if (soLuong > giao + EPS) {
        showToast(
          `Dòng ${i + 1}: thực nhận (${soLuong}) không được vượt SL giao (${giao}). ` +
            'Nhận thừa thật sự thì lập phiếu "Nhập khác" riêng, không sửa số trên phiếu tự sinh này.',
          'error'
        )
        return false
      }
      if (Math.abs(soLuong - giao) > EPS && !(r.ly_do_chenh_lech || '').trim()) {
        showToast(
          `Dòng ${i + 1}: thực nhận ${soLuong} / giao ${giao}. Nhập lý do chênh lệch để tiếp tục.`,
          'error'
        )
        return false
      }
    }
  }
  return true
}

function payload() {
  const p = {
    ngay: doc.ngay,
    loai_nhap: doc.loai_nhap,
    nguoi_giao: doc.nguoi_giao,
    chung_tu_kem: doc.chung_tu_kem,
    dien_giai: doc.dien_giai,
    // E4/BR-N1,N2 — chỉ có ý nghĩa khi loai_nhap = "Mua ngoài (NCC khác)";
    // server tự xoá lại nếu gửi kèm loại khác (_validate_ncc).
    ncc: doc.ncc || null,
    so_chung_tu_ncc: doc.so_chung_tu_ncc || null,
    ngay_chung_tu: doc.ngay_chung_tu || null,
    items: doc.items.map((r) => ({
      // `name` của dòng con (có sẵn từ lần load qua kho_phieu_get) — server
      // khớp lại mốc đối soát sl_giao/thieu_lo_han theo ĐÚNG danh tính này,
      // không phải theo giá trị vat_tu/so_lo (sửa Số lô sẽ không còn làm mất
      // mốc). Dòng mới thêm tay/nhập Excel không có name — gửi undefined,
      // JSON bỏ qua field đó, server hiểu là dòng mới (không có mốc).
      name: r.name || undefined,
      vat_tu: r.vat_tu, so_lo: r.so_lo, han_su_dung: r.han_su_dung || null,
      so_luong: r.so_luong, don_gia: r.don_gia, ghi_chu: r.ghi_chu,
      // BR-K17: server bắt buộc field này khi so_luong lệch sl_giao. CHỈ gửi
      // khi dòng THẬT SỰ đang lệch — thủ kho gõ "vỡ 2 hộp" lúc so_luong=48
      // rồi sửa lại 50 (hết lệch) không được để lý do cũ trôi theo lên phiếu:
      // ô nhập đã ẩn khỏi màn hình (coChenhLech(r) false) nhưng
      // r.ly_do_chenh_lech vẫn còn giá trị cũ trong bộ nhớ nếu không dọn ở
      // đây — sẽ hiện sai trên report "Đối soát giao nhận" (cột Lý do có
      // giá trị dù cột Chênh = 0).
      ly_do_chenh_lech: coChenhLech(r) ? r.ly_do_chenh_lech || null : null,
    })),
  }
  if (!isNew.value) p.name = doc.name
  return p
}

async function save({ silent } = {}) {
  if (dongChuaXuLy.value) {
    showToast(`Còn ${dongChuaXuLy.value} dòng lỗi trong tệp chưa được xử lý — chọn vật tư cho dòng đó, hoặc xoá dòng.`, 'error')
    return null
  }
  if (!validateClient()) return null
  saving.value = true
  try {
    const out = await api.callKho('kho_phieu_nhap_save', { payload: payload() })
    Object.assign(doc, out)
    if (isNew.value) {
      router.replace(`/kho/nhap/${out.name}`)
    }
    if (!silent) {
      // BR-N2 (F-15): "hỏi nhẹ" — KHÔNG chặn lưu, chỉ báo để thủ kho biết
      // phiếu sẽ mang cờ "Thiếu chứng từ" cho tới khi bổ sung số chứng từ.
      // Một toast DUY NHẤT (không phải một 'error' chồng lên một 'success')
      // — save() đã thành công thật, đây chỉ là ghi chú thêm.
      showToast(
        out.thieu_chung_tu
          ? 'Đã lưu phiếu nháp — chưa có số chứng từ NCC nên phiếu sẽ gắn cờ "Thiếu chứng từ" (bổ sung sau được).'
          : 'Đã lưu phiếu nháp.'
      )
    }
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
  if (!window.confirm(`Ghi sổ phiếu ${saved.name}? Sau khi ghi sổ chỉ có thể huỷ, không sửa được nữa.`)) return
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
    showToast('Đã huỷ phiếu.')
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
  await Promise.all([loadVatTu(), loadNcc(), load()])
})
</script>

<template>
  <div>
    <div class="topbar" v-if="!isMobile">
      <div>
        <h2>{{ isNew ? 'Tạo phiếu nhập kho' : doc.name }}</h2>
        <div class="sub" v-if="!isNew">
          <span class="badge" :class="badge.cls">{{ badge.label }}</span>
          <span v-if="doc.co_chenh_lech" class="badge b-orange" style="margin-left: 6px">Có chênh lệch ⚠</span>
          <span v-if="doc.thieu_chung_tu" class="badge b-orange" style="margin-left: 6px">Thiếu chứng từ</span>
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
        <router-link to="/kho/nhap" class="btn-o">Quay lại</router-link>
      </div>
    </div>
    <div v-else style="margin-bottom: 12px">
      <div class="sb">
        <h2>{{ isNew ? 'Tạo phiếu nhập' : doc.name }}</h2>
        <span v-if="!isNew" class="badge" :class="badge.cls">{{ badge.label }}</span>
        <span v-if="doc.co_chenh_lech" class="badge b-orange" style="margin-left: 6px">Có chênh lệch ⚠</span>
        <span v-if="doc.thieu_chung_tu" class="badge b-orange" style="margin-left: 6px">Thiếu chứng từ</span>
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
            <label>Loại nhập</label>
            <select v-model="doc.loai_nhap" :disabled="!editable">
              <option v-for="o in LOAI_OPTIONS" :key="o" :value="o">{{ o }}</option>
              <!-- Phiếu vào bằng cách khác (import, hook DN) có thể mang loại
                   không nằm trong LOAI_OPTIONS — vẫn hiển thị đúng giá trị đó. -->
              <option v-if="!LOAI_OPTIONS.includes(doc.loai_nhap)" :value="doc.loai_nhap">{{ doc.loai_nhap }}</option>
            </select>
          </div>
          <div class="field">
            <label>Người giao hàng</label>
            <input v-model="doc.nguoi_giao" :disabled="!editable" />
          </div>
          <div class="field">
            <label>Chứng từ kèm theo</label>
            <input v-model="doc.chung_tu_kem" :disabled="!editable" />
          </div>
        </div>
        <div class="field" style="margin-top: 10px">
          <label>Diễn giải</label>
          <textarea v-model="doc.dien_giai" :disabled="!editable" rows="2"></textarea>
        </div>

        <!-- US-E4.2/BR-N1,N2 — chỉ hiện khi Mua ngoài (NCC khác), khớp pn-ncc/
             pn-ct của bản mẫu (pnLoai()). -->
        <div v-if="doc.loai_nhap === LOAI_MUA_NGOAI" class="grid2" style="margin-top: 10px">
          <div class="field">
            <label>NCC (bắt buộc khi Mua ngoài) *</label>
            <select v-model="doc.ncc" :disabled="!editable" @change="onNccSelect">
              <option value="" disabled>-- Chọn NCC --</option>
              <option v-for="n in nccList" :key="n.name" :value="n.name" :disabled="!n.active">
                {{ n.ten_ncc }}{{ n.active ? '' : ' (đã tắt)' }}
              </option>
              <option :value="MUC_TAO_NCC">+ Tạo NCC mới…</option>
            </select>
            <p v-if="!nccList.length" class="tag" style="margin-top: 4px">
              Chưa có NCC nào — chọn "+ Tạo NCC mới…" để thêm.
            </p>
          </div>
          <div class="flex" style="gap: 14px">
            <div class="field" style="flex: 1">
              <label>Số chứng từ NCC</label>
              <input v-model="doc.so_chung_tu_ncc" :disabled="!editable" placeholder="HĐ/PXK của NCC" />
            </div>
            <div class="field" style="flex: 1">
              <label>Ngày chứng từ</label>
              <input type="date" v-model="doc.ngay_chung_tu" :disabled="!editable" />
            </div>
          </div>
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
              <th>Số lô</th>
              <th>Hạn dùng</th>
              <th class="right">SL giao</th>
              <th class="right">Số lượng</th>
              <th style="min-width: 140px">Lý do chênh lệch</th>
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
                <select v-if="editable" v-model="r.vat_tu" style="width: 100%" @change="onVatTuSelect(r, idx)">
                  <option value="" disabled>-- Chọn vật tư --</option>
                  <option v-for="v in vatTuList" :key="v.name" :value="v.name">
                    {{ v.ma_vat_tu }} — {{ v.ten_vat_tu }}
                  </option>
                  <option :value="MUC_TAO_MOI">➕ Tạo vật tư mới…</option>
                </select>
                <span v-else>{{ r.ten_vat_tu || tenVatTu(r.vat_tu) }}</span>

                <div v-if="editable && r._trang_thai === 'ma_moi' && !r.vat_tu" class="warn" style="margin-top: 4px">
                  ⚠ Mã <b>{{ r._ma_vat_tu }}</b> chưa có trong kho.
                  <button class="btn-o btn-sm" @click="moTaoTuDong(r, idx)">Tạo vật tư mới</button>
                </div>
                <div v-if="r._loi && r._loi.length" class="tag" style="color: #cf1322; margin-top: 4px">
                  ✗ Dòng {{ r._loi_line }} trong tệp: {{ r._loi.join('; ') }}
                </div>
              </td>
              <td>
                <input v-if="editable" v-model="r.so_lo" style="width: 110px" />
                <span v-else>{{ r.so_lo }}</span>
                <div v-if="r.thieu_lo_han" class="warn" style="margin-top: 4px">
                  ⚠ Thiếu lô/hạn (Miyano chưa bật theo dõi lô cho vật tư này)
                </div>
              </td>
              <td>
                <input v-if="editable" type="date" v-model="r.han_su_dung" style="width: 140px" />
                <span v-else>{{ r.han_su_dung ? fmtDate(r.han_su_dung) : '—' }}</span>
              </td>
              <td class="right">
                <!-- Chỉ đọc: mốc đối soát BR-K16, hook điền từ Delivery Note.
                     Dòng gõ tay/nhập Excel không có sl_giao (0) → hiện '—'. -->
                <span v-if="slGiao(r)">{{ slGiao(r).toLocaleString('vi-VN') }}</span>
                <span v-else class="tag">—</span>
              </td>
              <td class="right">
                <input
                  v-if="editable"
                  :value="r.so_luong"
                  @change="r.so_luong = Number($event.target.value) || 0"
                  inputmode="numeric"
                  style="width: 80px; text-align: right"
                  :style="coChenhLech(r) ? 'border-color: #cf1322' : ''"
                />
                <span v-else>{{ Number(r.so_luong).toLocaleString('vi-VN') }}</span>
              </td>
              <td>
                <template v-if="coChenhLech(r)">
                  <input
                    v-if="editable"
                    v-model="r.ly_do_chenh_lech"
                    placeholder="VD: thiếu 2 hộp, vỡ 1 chai…"
                    style="width: 160px"
                    :style="thieuLyDo(r) ? 'border-color: #cf1322' : ''"
                  />
                  <span v-else>{{ r.ly_do_chenh_lech || '—' }}</span>
                  <div v-if="editable && thieuLyDo(r)" class="warn" style="margin-top: 4px">
                    ⚠ Bắt buộc — SL thực nhận khác SL giao ({{ slGiao(r).toLocaleString('vi-VN') }})
                  </div>
                </template>
                <span v-else class="tag">—</span>
              </td>
              <td class="right">
                <input
                  v-if="editable"
                  :value="r.don_gia"
                  @change="r.don_gia = Number($event.target.value) || 0"
                  inputmode="numeric"
                  style="width: 100px; text-align: right"
                />
                <span v-else>{{ fmtVND(r.don_gia) }}</span>
              </td>
              <td class="right">{{ fmtVND(editable ? rowThanhTien(r) : r.thanh_tien) }}</td>
              <td v-if="editable">
                <!-- C1 (E3 phần B review): dòng do hook sinh (sl_giao > 0)
                     KHÔNG được xoá — xoá làm mất mốc đối soát BR-K17 vĩnh
                     viễn (sổ append-only), report "Đối soát giao nhận" sẽ
                     không bao giờ thấy hàng đã mất. Nhận thiếu/mất hoàn toàn
                     thì ghi số lượng 0 + lý do (server chấp nhận từ bản
                     này), không xoá dòng. -->
                <button v-if="!slGiao(r)" class="btn-o btn-sm" @click="removeRow(idx)">✕</button>
                <span v-else class="tag" title="Dòng do phiếu giao hàng Miyano sinh ra — không xoá được">🔒</span>
              </td>
            </tr>
          </tbody>
          <tfoot>
            <tr>
              <td colspan="7" style="text-align: right"><b>Tổng cộng</b></td>
              <td class="right"><b>{{ fmtVND(editable ? tongTienPreview : doc.tong_tien) }}</b></td>
              <td v-if="editable"></td>
            </tr>
          </tfoot>
        </table>
      </div>
      <button v-if="editable" class="btn-o btn-sm" style="margin-top: 10px" @click="addRow">+ Thêm dòng</button>

      <!-- Nút hành động (mobile) -->
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
      <NccModal :open="nccModalOpen" mode="tao" @saved="onNccSaved" @close="nccModalOpen = false" />
    </template>
  </div>
</template>
