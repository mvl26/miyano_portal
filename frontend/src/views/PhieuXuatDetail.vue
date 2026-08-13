<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtVND, fmtDate } from '../format'
import { showToast } from '../toast'
import { phieuActions, trangThaiBadge } from '../kho-actions'
import { useIsMobile } from '../useMobile'
import { useDongPhieu } from '../useDongPhieu'
import VatTuModal from '../components/VatTuModal.vue'
import KhoaPhongModal from '../components/KhoaPhongModal.vue'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

const DOCTYPE = 'Customer Stock Issue'
const LOAI_OPTIONS = ['Xuất sử dụng', 'Xuất huỷ - hết hạn', 'Xuất trả lại', 'Điều chỉnh kiểm kê']
// "Phiếu đảo" CỐ Ý không có trong danh sách — cùng lý do với PhieuNhapDetail.

// I-3 (review E4 phần A) / BR-K20 (US-E4.4): chỉ "Xuất sử dụng" mới bắt xác
// nhận lô hết hạn. Server (customer_stock_issue.py before_submit) đã thu hẹp
// guard này từ "mọi loại xuất trừ Phiếu đảo" xuống đúng loại này — client
// PHẢI khớp, nếu không thủ kho vẫn bị chặn tick trên UI cho "Xuất huỷ - hết
// hạn" dù server đã cho qua, tức không bao giờ chạm được tới đường đã nới.
const LOAI_BAT_XAC_NHAN_HET_HAN = 'Xuất sử dụng'

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
  khoa_phong: '',
  noi_nhan: '',
  nguoi_nhan: '',
  dien_giai: '',
  docstatus: 0,
  tong_tien: 0,
  items: [],
})

const vatTuList = ref([])

// --- E8/US-E8.2/BR-CP2: Khoa phòng nhận + US-E8.3/BR-CP3: gợi ý Người nhận ---
const MUC_TAO_KHOA_MOI = '__tao_khoa_moi__'
const khoaPhongList = ref([])
const nguoiNhanGoiY = ref([])
const khoaModalOpen = ref(false)
const batBuocKhoaPhong = ref(false) // chỉ để hiện dấu * cho UX sớm — chốt chặn THẬT nằm ở server (before_submit)

async function loadKhoaPhongList() {
  try {
    khoaPhongList.value = await api.callKho('kho_khoa_phong_list')
  } catch (e) {
    // Ô chọn khoa phòng sẽ chỉ thiếu tuỳ chọn, không chặn cả form.
  }
}

async function loadTrangThaiBatBuoc() {
  try {
    const me = await api.callKho('kho_me')
    batBuocKhoaPhong.value = !!me.bat_buoc_khoa_phong
  } catch (e) {
    // Không ảnh hưởng gì tới việc lưu/ghi sổ — chỉ là gợi ý hiển thị sớm.
  }
}

async function loadNguoiNhanGoiY(tuKhoa) {
  if (!doc.khoa_phong) {
    nguoiNhanGoiY.value = []
    return
  }
  try {
    nguoiNhanGoiY.value = await api.callKho('kho_nguoi_nhan_goi_y', {
      khoa_phong: doc.khoa_phong, tu_khoa: tuKhoa || undefined,
    })
  } catch (e) {
    nguoiNhanGoiY.value = []
  }
}

// F-6 (review E8): gõ tự do vào ô Người nhận không được bắn một request cho
// MỖI ký tự — "BS. Nguyễn Văn Tuấn" là 19 request, mỗi request chạy
// _khoa_cua_kho() + một truy vấn get_all() quét 12 tháng lịch sử phía server.
// Debounce theo đúng khuôn searchTimer/clearTimeout đã có sẵn ở Kho.vue,
// không phát minh cơ chế mới.
let nguoiNhanTimer = null
function onNguoiNhanInput() {
  clearTimeout(nguoiNhanTimer)
  nguoiNhanTimer = setTimeout(() => loadNguoiNhanGoiY(doc.nguoi_nhan), 300)
}

function onKhoaPhongSelect(event) {
  const val = event.target.value
  if (val === MUC_TAO_KHOA_MOI) {
    doc.khoa_phong = ''
    khoaModalOpen.value = true
    return
  }
  doc.khoa_phong = val
  loadNguoiNhanGoiY(doc.nguoi_nhan)
}

function onKhoaPhongSaved(out) {
  khoaModalOpen.value = false
  doc.khoa_phong = out.name
  loadKhoaPhongList()
  loadNguoiNhanGoiY(doc.nguoi_nhan)
}

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
    // `ngay` (I-3, review E4 phần A): cờ het_han server tính PHẢI cùng mốc
    // với chốt chặn thật ở backend (so với NGÀY PHIẾU, không phải ngày hệ
    // thống — xem I-1). Thiếu nó, badge "⚠ QUÁ HẠN" trên form lệch khỏi kết
    // quả submit() thật sự sẽ cho.
    const out = await api.callKho('kho_lo_goi_y', { vat_tu: row.vat_tu, so_luong: row.so_luong || 0, ngay: doc.ngay })
    row._lots = out.lots || []
    if (row._lots.length) {
      // BA nhánh, không phải hai — gộp nhánh 3 vào nhánh 1 (mặc định lô đầu
      // tiên) là cách số lô THẬT của người dùng bị thay bằng lô FEFO một cách
      // âm thầm:
      //   (1) dòng CHƯA gắn với lô nào (dòng mới gõ tay, hoặc vừa đổi vật tư
      //       nên resetLotState đã xoá so_lo, hoặc đang mang sentinel
      //       LOT_KHONG_CO của một lần tải trước khi kho chưa có tồn) → mặc
      //       định lô đầu tiên, tức lô gần hết hạn nhất. Đây là tính năng gợi
      //       ý FEFO, phải giữ.
      //   (2) lô đang chọn vẫn còn trong danh sách → giữ nguyên, và đọc lại
      //       hạn/giá/cờ hết hạn từ lô đó (đổi Số lượng không được tự đổi lô
      //       người dùng đã chọn).
      //   (3) dòng ĐÃ mang một số lô thật mà lô đó không còn trong danh sách
      //       (đọc từ tệp Excel, hoặc mở lại nháp cũ sau khi lô đã xuất hết)
      //       → GIỮ NGUYÊN số lô đó và để loCanhBao() cảnh báo tại dòng
      //       (thiết kế §4.5). Ghi đè bằng _lots[0] ở đây là xuất một lô khác
      //       lô bệnh viện đã ghi mà không có gì tự lộ ra: số dư vẫn đúng vì
      //       lô thay thế chắc chắn còn tồn, chỉ vết truy xuất lô là sai.
      const chuaChonLo = !row.so_lo || row.so_lo === LOT_KHONG_CO
      if (chuaChonLo) {
        applyLotToRow(row, row._lots[0].so_lo)
      } else if (row._lots.some((l) => l.so_lo === row.so_lo)) {
        applyLotToRow(row, row.so_lo)
      } else {
        // Không biết gì về hạn/giá của một lô không còn tồn: xoá phần xem
        // trước của lô CŨ thay vì để nó nằm lại trên dòng này. Không đụng tới
        // xac_nhan_het_han — tick đó vẫn thuộc đúng số lô đang giữ.
        row.han_su_dung = null
        row.don_gia = 0
        row._hetHan = false
      }
    } else {
      // Nhánh này chạy cho HAI tình huống khác nhau, không được gộp làm một:
      // (1) vật tư chưa từng có lô nào (vừa tạo nhanh, hoặc dòng đọc từ tệp mà
      //     ô Số lô để trống) — row.so_lo đang rỗng vì onVatTuChange đã
      //     resetLotState trước khi gọi hàm này, hoặc đang mang sentinel
      //     LOT_KHONG_CO do backend gán cho ô Số lô trống.
      // (2) dòng ĐÃ có lô thật từ trước (đang mở lại nháp cũ, vừa lưu xong,
      //     hoặc vừa đọc số lô đó từ tệp) mà lô đó không còn tồn —
      //     kho_lo_goi_y lọc so_luong > EPS nên lô không còn xuất hiện trong
      //     _lots nữa, nhưng row.so_lo vẫn đang giữ số lô thật đó
      //     (loadLotsForRow được gọi trực tiếp từ load()/save()/
      //     onSoLuongChange()/onRowImported, KHÔNG qua resetLotState trước).
      // Phải lưu lại so_lo TRƯỚC khi resetLotState xoá nó, rồi chỉ thay bằng
      // sentinel ở tình huống (1) — nếu không, tình huống (2) sẽ bị GHI ĐÈ
      // mất số lô thật ngay khi Lưu nháp, dù trước đó dòng vẫn hợp lệ.
      const soLoTruoc = row.so_lo
      resetLotState(row)
      row.so_lo = soLoTruoc && soLoTruoc !== LOT_KHONG_CO ? soLoTruoc : LOT_KHONG_CO
    }
  } catch (e) {
    showToast(e.message || 'Không tải được danh sách lô.', 'error')
  } finally {
    row._lotsLoading = false
  }
}

// I-3 (review E4 phần A): đổi Ngày phiếu phải nạp lại _hetHan/_lots của MỌI
// dòng đã chọn vật tư — cờ het_han của kho_lo_goi_y phụ thuộc `ngay` (xem
// chú thích trong loadLotsForRow). Không có watcher này, badge "⚠ QUÁ HẠN"
// và yêu cầu tick xác nhận trên form sẽ đứng yên ở lần tải đầu, lệch khỏi
// kết quả submit() thật khi người dùng đổi ngày SAU khi đã chọn lô.
// loadLotsForRow() tự giữ nguyên so_lo đang chọn (nhánh (2) trong chú thích
// của nó), nên gọi lại ở đây không làm mất lựa chọn của người dùng.
watch(
  () => doc.ngay,
  () => {
    if (!editable.value) return
    for (const row of doc.items) {
      if (row.vat_tu) loadLotsForRow(row)
    }
  },
)

// Cảnh báo lô của MỘT dòng, TÍNH RA từ _lots chứ không lưu thành cờ trên dòng
// (thiết kế §4.5: "số lô không tồn tại hoặc đã hết tồn → cảnh báo tại dòng;
// vẫn lưu nháp được, vẫn bị _chan_xuat_qua_ton chặn ở bước ghi sổ").
//
// Vì sao tính ra chứ không lưu: một cờ đặt lúc import sẽ vẫn còn đó sau khi
// người dùng đổi sang lô khác — đúng loại trạng thái ôi thiu đã làm dòng đỏ
// không bao giờ xoá được. Hàm này tự đúng lại sau MỌI thay đổi so_lo/_lots.
// Trả về chuỗi rỗng khi không có gì để cảnh báo, để dùng luôn làm điều kiện
// v-if trong <template>.
function loCanhBao(r) {
  if (!r.vat_tu || r._lotsLoading) return ''
  // Chưa gắn lô nào: ô chọn đã tự nói ("Chọn vật tư trước" / "chưa còn tồn lô
  // nào"), không chồng thêm một câu nữa.
  if (!r.so_lo || r.so_lo === LOT_KHONG_CO) return ''
  if ((r._lots || []).some((l) => l.so_lo === r.so_lo)) return ''
  return `Lô ${r.so_lo} không còn tồn trong kho. Vẫn lưu nháp được, nhưng ghi sổ sẽ bị chặn — chọn lô khác hoặc nhập kho lô này trước.`
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
  //
  // Gọi THẲNG loadLotsForRow, KHÔNG qua onVatTuChange: hợp đồng của
  // onVatTuChange là "người dùng vừa đổi sang vật tư khác, bỏ hết trạng thái
  // của vật tư cũ", nên việc đầu tiên nó làm là resetLotState() — xoá luôn số
  // lô vừa đọc từ tệp. Dùng nó làm móc import là đem nguyên nghĩa "bỏ hết"
  // đó áp lên một dòng mà số lô CHÍNH LÀ dữ liệu người dùng vừa nhập vào.
  // loadLotsForRow() giữ nguyên so_lo và tự xử lý cả ba tình huống (lô còn
  // tồn / lô hết tồn / ô Số lô để trống → sentinel → mặc định FEFO).
  onRowImported: (row) => {
    if (row.vat_tu) loadLotsForRow(row)
  },
})

function onSoLuongChange(row, val) {
  row.so_luong = Number(val) || 0
  loadLotsForRow(row)
}
function onSoLoChange(row) {
  // Ô chọn có thể đang chứa cả mục "không còn tồn" (số lô đọc từ tệp hoặc từ
  // nháp cũ mà lô đã hết) — applyLotToRow() không tìm thấy lô đó nên tự thoát,
  // để lại hạn/giá của lô TRƯỚC ĐÓ trên dòng. Xoá tường minh ở đây.
  if (row._lots.some((l) => l.so_lo === row.so_lo)) {
    applyLotToRow(row, row.so_lo)
  } else {
    row.han_su_dung = null
    row.don_gia = 0
    row._hetHan = false
  }
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
    // Xem chú thích cùng chốt này ở PhieuNhapDetail.vue: dòng đọc từ tệp có
    // thể mang Số lượng ≤ 0, và sau khi người dùng sửa dòng đỏ tại chỗ thì
    // danh sách lý do lỗi của tệp đã được xoá — chốt này thay chỗ cho nó.
    if (!(Number(r.so_luong) > 0)) {
      showToast(`Dòng ${i + 1}: số lượng phải lớn hơn 0.`, 'error')
      return false
    }
    if (doc.loai_xuat === LOAI_BAT_XAC_NHAN_HET_HAN && r._hetHan && !r.xac_nhan_het_han) {
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
    // E8/BR-CP2 — PHẢI có mặt ở đây: backend (kho_phieu_xuat_save) đã hỗ
    // trợ khoa_phong từ trước, nhưng đường lưu THẬT của form này là payload()
    // -> kho_phieu_xuat_save, không phải frappe.get_doc().save() mà test
    // backend hay dùng. Thiếu dòng này thì trường không bao giờ tới được
    // server dù cả hai đầu (DB field + endpoint) đều đã sẵn sàng — đúng lỗ
    // đã trả giá ở E5 (xem brief E8).
    khoa_phong: doc.khoa_phong || null,
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
    showToast(`Còn ${dongChuaXuLy.value} dòng lỗi trong tệp chưa được xử lý — chọn vật tư cho dòng đó, hoặc xoá dòng.`, 'error')
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
  await Promise.all([loadVatTu(), load(), loadKhoaPhongList(), loadTrangThaiBatBuoc()])
  if (doc.khoa_phong) loadNguoiNhanGoiY(doc.nguoi_nhan)
})

onUnmounted(() => clearTimeout(nguoiNhanTimer))
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
            <label>
              Khoa phòng nhận
              <span v-if="batBuocKhoaPhong && doc.loai_xuat === 'Xuất sử dụng'">*</span>
            </label>
            <select :value="doc.khoa_phong" :disabled="!editable" @change="onKhoaPhongSelect">
              <option value="">— Chưa chọn —</option>
              <option v-for="k in khoaPhongList" :key="k.name" :value="k.name">
                {{ k.ten_khoa_phong }}
              </option>
              <option :value="MUC_TAO_KHOA_MOI">➕ Tạo khoa phòng…</option>
            </select>
            <p v-if="batBuocKhoaPhong && doc.loai_xuat === 'Xuất sử dụng'" class="tag" style="margin-top: 4px">
              Kho đang bật bắt buộc chọn khoa phòng cho phiếu Xuất sử dụng (chỉ áp phiếu tạo sau khi bật — BR-CP2).
            </p>
          </div>
          <div class="field">
            <label>Nơi nhận</label>
            <input v-model="doc.noi_nhan" :disabled="!editable" placeholder="VD: Khoa Hồi sức tích cực" />
          </div>
          <div class="field">
            <label>Người nhận</label>
            <input
              v-model="doc.nguoi_nhan"
              :disabled="!editable"
              maxlength="100"
              list="nguoi-nhan-goi-y"
              @input="onNguoiNhanInput"
              placeholder="Gõ để xem gợi ý theo khoa đã chọn"
            />
            <datalist id="nguoi-nhan-goi-y">
              <option v-for="n in nguoiNhanGoiY" :key="n" :value="n" />
            </datalist>
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
                    <!-- Số lô đang giữ nhưng không còn tồn (đọc từ tệp, hoặc
                         nháp cũ có lô đã xuất hết): phải có mặt trong danh
                         sách, nếu không v-model không khớp option nào và ô
                         chọn hiện trống — trông như dòng chưa chọn lô trong
                         khi dữ liệu vẫn mang đúng số lô đó. -->
                    <option v-if="loCanhBao(r)" :value="r.so_lo">{{ r.so_lo }} · không còn tồn</option>
                  </select>
                  <span v-else-if="r.vat_tu" class="tag">
                    Vật tư này chưa còn tồn lô nào.
                    <template v-if="r._vua_tao">
                      Đây là vật tư vừa tạo — phải nhập kho trước khi ghi sổ phiếu xuất này.
                    </template>
                  </span>
                  <span v-else class="tag">Chọn vật tư trước</span>
                  <div v-if="loCanhBao(r)" class="warn" style="margin-top: 4px">⚠ {{ loCanhBao(r) }}</div>
                  <!-- I-3: chỉ bắt tick cho "Xuất sử dụng" (BR-K20) — các loại
                       xuất khác, kể cả "Xuất huỷ - hết hạn", không hỏi, nên
                       không hiện ô tick gây hiểu nhầm có một chốt chặn ở đây. -->
                  <div v-if="r._hetHan && doc.loai_xuat === LOAI_BAT_XAC_NHAN_HET_HAN" class="warn" style="margin-top: 4px; display: flex; align-items: center; gap: 4px">
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
      <KhoaPhongModal
        :open="khoaModalOpen"
        mode="tao"
        @saved="onKhoaPhongSaved"
        @close="khoaModalOpen = false"
      />
    </template>
  </div>
</template>
