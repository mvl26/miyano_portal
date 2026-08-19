<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtDateTime, deXuatBadge } from '../format'
import { useIsMobile } from '../useMobile'
import { store } from '../store'
import { showToast } from '../toast'
import { hanhDongChoPhep } from '../de-xuat-actions'
import { capNhatChoDuyetCount } from '../cho-duyet'
import ReasonModal from '../components/ReasonModal.vue'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const doc = ref(null)
const ten = computed(() => route.params.ten)

const khoaPhongList = ref([])
async function loadKhoaPhongList() {
  try {
    khoaPhongList.value = await api.callKho('kho_khoa_phong_list', { ca_inactive: 1 })
  } catch (e) {
    // Best-effort — cùng khuôn DeXuatList.vue: một khách chưa mở kho vẫn
    // phải xem được chi tiết phiếu, chỉ mất phần dịch tên khoa.
  }
}
const tenKhoa = computed(() => {
  if (!doc.value) return ''
  if (!doc.value.khoa_phong) return 'Toàn viện'
  const k = khoaPhongList.value.find((x) => x.name === doc.value.khoa_phong)
  return k ? k.ten_khoa_phong : doc.value.khoa_phong
})

// Toolbar hành động — DỮ LIỆU, không rải v-if khắp template (xem
// de-xuat-actions.js). hanhDongChoPhep() đã tự bọc when() trong try/catch.
const actions = computed(() => hanhDongChoPhep(doc.value, store.me))

// C3 — nút "Quay lại" phải quay về ĐÚNG NƠI ĐÃ TỚI. Trước bản này nó cứng
// `/de-xuat`: quản lý mở /duyet, lọc khoa "Huyết học", duyệt phiếu, bấm Quay
// lại → rơi vào một danh sách KHÁC, mất bộ lọc, phải đi vòng qua menu cho
// từng phiếu trong tám phiếu.
//
// Dùng query (`?tu=`, `?khoa=`, `?chip=`) chứ KHÔNG `router.back()`: người
// dùng vào thẳng bằng URL (link trong thông báo, tab được ghim) không có
// bước lịch sử nào để lùi — `back()` sẽ ném họ ra khỏi cổng. Query luôn
// dựng lại được một đích ĐÚNG, kể cả khi lịch sử rỗng.
const quayLaiTo = computed(() => {
  const q = route.query
  if (q.tu === 'duyet') return { name: 'duyet', query: q.khoa ? { khoa: String(q.khoa) } : {} }
  return { name: 'de-xuat', query: q.chip ? { chip: String(q.chip) } : {} }
})
const quayLaiNhan = computed(() => (route.query.tu === 'duyet' ? '← Về hàng chờ duyệt' : '← Quay lại'))

async function load() {
  loading.value = true
  error.value = ''
  try {
    doc.value = await api.callDeXuat('de_xuat_chi_tiet', { ten: ten.value })
    dungLaiDieuChinh()
  } catch (e) {
    error.value = e.message || 'Không tải được chi tiết phiếu đề xuất.'
  } finally {
    loading.value = false
  }
}

// M1 (Task 4) — "hạ về 0" chỉ có nghĩa SAU khi quản lý đã thật sự cầm phiếu
// lên xử lý (`_ap_dieu_chinh` chỉ chạy trong đường duyệt). Ở "Nháp"/"Chờ
// duyệt", `so_luong_duyet` mới chỉ là bản sao mặc định của `so_luong_de_
// xuat` (đóng dấu lúc Gửi duyệt) — coi nó là "Không duyệt" ở hai trạng thái
// đó sẽ gắn badge sai cho MỌI dòng của MỌI phiếu chưa ai đụng tới. Máy trạng
// thái (`portal_de_xuat_mua.py` CHUYEN_HOP_LE) chỉ cho "Đã huỷ" đi ra từ
// "Chờ duyệt"/"Từ chối" — không đi qua "Đã duyệt" — nên khỏi cần liệt kê nó.
const daDieuChinh = computed(() => ['Đã duyệt', 'Chờ duyệt sửa'].includes(doc.value?.trang_thai))
function khongDuyet(row) {
  return daDieuChinh.value && Number(row.so_luong_duyet) === 0
}

// --- C1: quản lý SỬA rồi mới duyệt --------------------------------------
//
// Chủ đầu tư: "nhân viên gửi yêu cầu mua hàng cho quản lý, quản lý có thể
// SỬA VÀ DUYỆT". Backend đã đủ từ Task 9 (`de_xuat_duyet_phieu(ten,
// dieu_chinh)` → `_ap_dieu_chinh`); trước bản này KHÔNG có ô nhập nào gửi
// `dieu_chinh`, nên trên cổng chỉ còn hai đường: Duyệt NGUYÊN SỐ, hoặc Từ
// chối CẢ PHIẾU. Khoa xin 100 mà quản lý chỉ đồng ý 40 thì không có đường
// nào đúng — và họ là Website User, không vào được màn quản trị để làm thay.
//
// Hình dạng payload đọc TRỰC TIẾP từ `_ap_dieu_chinh` (api/de_xuat.py:179):
//   { "items": [ { "item_code": str,
//                  "so_luong_duyet": float,
//                  "ghi_chu_quan_ly": str (tuỳ chọn) } ] }
// Ba luật của hàm đó quyết định cách dựng payload ở đây:
//   1. Khớp dòng theo `item_code`. Mã KHÔNG có sẵn trên phiếu → dòng MỚI
//      (`so_luong_de_xuat = 0`, `nguon_dong = "Quản lý thêm"`).
//   2. `so_luong_duyet = float(row.get("so_luong_duyet") or 0)` — GHI ĐÈ vô
//      điều kiện cho MỌI dòng có mặt trong payload. Hệ quả bắt buộc: dòng
//      chỉ đổi ghi chú VẪN phải mang theo số HIỆN TẠI, bỏ trống khoá đó là
//      lặng lẽ hạ mặt hàng về 0.
//   3. `ghi_chu_quan_ly` chỉ ghi khi khoá đó `is not None` → không đổi thì
//      KHÔNG đưa khoá vào, đừng gửi chuỗi rỗng.
// Dòng KHÔNG có trong payload thì không bị chạm — đó là cách "ô để trống =
// không đổi dòng này" thành hiện thực ở tầng dữ liệu.
const quanLyDangDuyet = computed(
  () => doc.value?.trang_thai === 'Chờ duyệt' && !!store.me?.la_quan_ly
)

// CỐ Ý giữ CHUỖI THÔ, không `v-model.number` — cùng lý do (và cùng cái bẫy
// đã dính một lần) với modal "Xin sửa số lượng" bên dưới: `Number('')` = 0,
// nên để Vue tự ép kiểu sẽ biến một ô KHÔNG ĐỘNG TỚI (hoặc bị xoá trắng)
// thành SỐ 0 — mà 0 ở đây mang nghĩa THẬT và KHÔNG ĐẢO NGƯỢC ĐƯỢC: "bỏ mặt
// hàng này khỏi đơn" (§5.3). Ô trống = "giữ nguyên dòng này"; CHỈ số 0 gõ
// tường minh mới là bỏ mặt hàng.
const slDuyetSua = ref({})
const ghiChuSua = ref({})
function dungLaiDieuChinh() {
  // SL duyệt để TRỐNG (placeholder hiện số đang có) — không prefill: một ô
  // đã điền sẵn số cũ rồi so sánh "có khác không" vẫn chạy đúng, nhưng nó
  // mời người dùng sửa đè lên một con số trông như đã được xác nhận.
  slDuyetSua.value = {}
  // Ghi chú thì prefill từ giá trị đang có — nó là VĂN BẢN, ô trống ở đây
  // không mang nghĩa gì nguy hiểm, và quản lý phải thấy ghi chú cũ để sửa
  // tiếp thay vì gõ lại từ đầu.
  ghiChuSua.value = Object.fromEntries(
    (doc.value?.items || []).map((it) => [it.item_code, it.ghi_chu_quan_ly || ''])
  )
}

// Số MỚI của một dòng, hoặc `null` nghĩa "không đổi". Trả `null` cho cả ô
// trống, ô chỉ có khoảng trắng (`Number(' ')` = 0 — đúng cái bẫy đang tránh),
// giá trị không hợp lệ, và giá trị TRÙNG số hiện tại.
function soDuyetMoi(it) {
  const raw = slDuyetSua.value[it.item_code]
  if (raw === undefined || raw === null) return null
  const chuoi = String(raw).trim()
  if (!chuoi) return null
  const n = Number(chuoi)
  if (!Number.isFinite(n) || n < 0) return null
  return n === (Number(it.so_luong_duyet) || 0) ? null : n
}
function laBoMatHang(it) {
  return soDuyetMoi(it) === 0
}
function ghiChuDoi(it) {
  return (ghiChuSua.value[it.item_code] || '').trim() !== (it.ghi_chu_quan_ly || '').trim()
}

const dieuChinhItems = computed(() => {
  if (!quanLyDangDuyet.value) return []
  const ra = []
  for (const it of doc.value?.items || []) {
    const so = soDuyetMoi(it)
    const doiGhiChu = ghiChuDoi(it)
    if (so === null && !doiGhiChu) continue // dòng không đổi → KHÔNG gửi
    // Luật 2 ở trên: dòng có mặt trong payload luôn bị ghi đè số lượng.
    const dong = { item_code: it.item_code, so_luong_duyet: so === null ? Number(it.so_luong_duyet) || 0 : so }
    // Luật 3: chỉ đưa khoá khi thật sự đổi.
    if (doiGhiChu) dong.ghi_chu_quan_ly = ghiChuSua.value[it.item_code] || ''
    ra.push(dong)
  }
  return ra
})

// Bấm "Duyệt": không đổi gì thì chạy Y NHƯ CŨ (duyệt nguyên trạng, KHÔNG
// gửi `dieu_chinh`) — không bắt buộc nhập gì cả. Có đổi thì xác nhận trước,
// vì hạ một dòng về 0 là bỏ hẳn mặt hàng khỏi đơn gửi Miyano.
function nhanDuyet(action) {
  const items = dieuChinhItems.value
  if (!items.length) return chayHanhDong(action)
  const theoMa = Object.fromEntries((doc.value.items || []).map((it) => [it.item_code, it]))
  const dong = items.map((r) => {
    const it = theoMa[r.item_code]
    const cu = Number(it?.so_luong_duyet) || 0
    if (Number(r.so_luong_duyet) === 0 && cu !== 0) return `• ${r.item_code}: BỎ khỏi đơn (đang ${cu})`
    if (Number(r.so_luong_duyet) !== cu) return `• ${r.item_code}: ${cu} → ${r.so_luong_duyet}`
    return `• ${r.item_code}: giữ ${cu}, thêm ghi chú`
  })
  const xacNhan = window.confirm(
    `Duyệt phiếu với ${items.length} điều chỉnh:\n\n${dong.join('\n')}\n\n` +
      'Đơn hàng gửi Miyano sẽ theo SỐ ĐÃ DUYỆT ở trên. Tiếp tục?'
  )
  if (!xacNhan) return
  chayHanhDong(action, { dieu_chinh: JSON.stringify({ items }) })
}

// Cột "SL xin sửa" chỉ hiện khi phiếu ở "Chờ duyệt sửa" (backend đã đổi mốc
// "chưa có yêu cầu" (-1) thành null ở de_xuat_chi_tiet — chỉ dòng có giá trị
// thật mới hiện số).
const hienCotXinSua = computed(() => doc.value?.trang_thai === 'Chờ duyệt sửa')

// --- Dispatch hành động chung -----------------------------------------
const dangChay = ref('')
const TOAST_THANH_CONG = {
  de_xuat_xoa_nhap: 'Đã xoá phiếu.',
  de_xuat_duyet_phieu: 'Đã duyệt phiếu — đơn hàng đã được tạo.',
  de_xuat_tu_choi: 'Đã từ chối phiếu.',
  de_xuat_huy: 'Đã huỷ phiếu.',
  de_xuat_duyet_sua: 'Đã đồng ý sửa số lượng — đơn hàng đã cập nhật.',
  de_xuat_tu_choi_sua: 'Đã từ chối yêu cầu xin sửa.',
}

async function chayHanhDong(action, extraArgs) {
  if (dangChay.value) return
  dangChay.value = action.method
  try {
    await api.callDeXuat(action.method, { ten: ten.value, ...(extraArgs || {}) })
    showToast(TOAST_THANH_CONG[action.method] || `Đã ${action.label}.`)
    // Xoá nháp thì phiếu không còn tồn tại nữa — quay lại danh sách thay vì
    // tải lại một chi tiết đã bị xoá.
    if (action.method === 'de_xuat_xoa_nhap') {
      router.push(quayLaiTo.value)
    } else {
      argModalAction.value = null
      await load()
    }
    // C3 — badge "Duyệt" trên nav phải nói đúng NGAY SAU thao tác. Trước bản
    // này nó giữ con số nạp lúc mount shell: quản lý duyệt phiếu thứ tám vẫn
    // thấy badge "8". Best-effort, không được làm hỏng một thao tác ĐÃ THÀNH
    // CÔNG nếu riêng lời gọi đếm này lỗi.
    try {
      await capNhatChoDuyetCount(store)
    } catch (e) {
      console.warn('Không cập nhật lại được số phiếu chờ duyệt:', e)
    }
  } catch (e) {
    showToast(e.message || 'Không thực hiện được thao tác này.', 'error')
  } finally {
    dangChay.value = ''
  }
}

// Hành động có `args` (hiện chỉ một textarea bắt buộc — Từ chối/Không đồng ý
// sửa) → mở modal chung trước khi gọi, kiểm required qua chính ReasonModal.
const argModalAction = ref(null)
function onSubmitArgModal(gia_tri) {
  const key = argModalAction.value.args[0].key
  chayHanhDong(argModalAction.value, { [key]: gia_tri })
}

// Ruling coordinator (1) — nút "Gửi duyệt" KHÔNG ẩn dù `ly_do_yeu_cau` trống
// (when() của registry không phản ánh điều kiện này). Bấm mà thiếu lý do →
// mở modal hỏi lý do (bắt buộc), lưu qua `de_xuat_luu_nhap` rồi mới gửi —
// KHÔNG hỏi lại nếu phiếu đã có lý do từ trước.
const lyDoYeuCauOpen = ref(false)
const dangLuuLyDo = ref(false)
function nhanGuiDuyet(action) {
  if ((doc.value?.ly_do_yeu_cau || '').trim()) {
    chayHanhDong(action)
    return
  }
  lyDoYeuCauOpen.value = true
}
async function xacNhanLyDoRoiGui(lyDo) {
  dangLuuLyDo.value = true
  try {
    await api.callDeXuat('de_xuat_luu_nhap', { ten: ten.value, ly_do_yeu_cau: lyDo })
    lyDoYeuCauOpen.value = false
    await chayHanhDong({ method: 'de_xuat_gui_duyet', label: 'Gửi duyệt' })
  } catch (e) {
    showToast(e.message || 'Không lưu được lý do yêu cầu.', 'error')
  } finally {
    dangLuuLyDo.value = false
  }
}

// Ruling coordinator (2) — "Xin sửa số lượng" không khớp khuôn args (đầu
// vào là NHIỀU dòng số lượng, không phải một ô lý do), nên xử lý RIÊNG ở
// đây thay vì đi qua `argModalAction`. Chỉ đề nghị sửa những dòng ĐANG NẰM
// trên đơn (`so_luong_duyet > 0`) — dòng quản lý đã hạ về 0 không còn trên
// Sales Order, xin sửa nó chỉ nhận lỗi "không còn trên đơn" từ server.
const xinSuaOpen = ref(false)
// review Task 5 (việc 5) — CỐ Ý giữ CHUỖI THÔ (không `v-model.number` ở
// template), khoá theo `item_code`. `Number('')` = 0: nếu để Vue tự ép kiểu
// lúc gõ, một ô bị XOÁ TRẮNG (rất hay gặp trên điện thoại) sẽ lặng lẽ biến
// thành SỐ 0 — mà `0` mang nghĩa THẬT ở `de_xuat_xin_sua` ("xin bỏ mặt hàng
// này khỏi đơn", chốt I2 Task 9 backend). Giữ chuỗi thô tới tận lúc gửi cho
// phép phân biệt BA trạng thái: '' (chưa đổi gì — không gửi dòng này), '0'
// (yêu cầu THẬT — xin bỏ), số khác 0 (đổi số lượng).
const xinSuaSoLuong = ref({})
const xinSuaDangGui = ref(false)
const dongXinSua = computed(() => (doc.value?.items || []).filter((it) => Number(it.so_luong_duyet) > 0))
function moXinSua() {
  xinSuaSoLuong.value = Object.fromEntries(dongXinSua.value.map((it) => [it.item_code, String(it.so_luong_duyet)]))
  xinSuaOpen.value = true
}
// Dòng đang mang giá trị 0 TƯỜNG MINH (ô KHÔNG rỗng) — dùng để hiện cảnh
// báo cạnh ô nhập, và để `guiXinSua()` phân biệt "xin bỏ" khỏi "chưa đổi".
function laXinBoMatHang(it) {
  const raw = xinSuaSoLuong.value[it.item_code]
  return raw !== '' && raw !== undefined && raw !== null && Number(raw) === 0
}
async function guiXinSua() {
  if (xinSuaDangGui.value) return
  const doiItems = []
  for (const it of dongXinSua.value) {
    const raw = xinSuaSoLuong.value[it.item_code]
    // Ô để TRỐNG = "không đổi gì" — KHÔNG đưa vào `dong` gửi lên. Đây là
    // điểm sửa chính của việc 5: trước đây `Number('')` = 0 khiến một ô bị
    // xoá trắng do vô ý lặng lẽ thành yêu cầu xoá mặt hàng.
    if (raw === '' || raw === undefined || raw === null) continue
    const so = Number(raw)
    // Giá trị gõ không hợp lệ (chữ, số âm...) — bỏ qua, không gửi rác lên
    // server. `<input type="number">` đã chặn phần lớn, đây là lớp phòng
    // thủ thứ hai.
    if (!Number.isFinite(so) || so < 0) continue
    if (so !== Number(it.so_luong_duyet)) {
      doiItems.push({ item_code: it.item_code, qty: so })
    }
  }
  if (!doiItems.length) {
    showToast('Chưa sửa số lượng dòng nào.', 'error')
    return
  }
  xinSuaDangGui.value = true
  try {
    await api.callDeXuat('de_xuat_xin_sua', { ten: ten.value, dong: JSON.stringify({ items: doiItems }) })
    xinSuaOpen.value = false
    showToast('Đã gửi yêu cầu xin sửa số lượng — chờ quản lý duyệt.')
    await load()
  } catch (e) {
    showToast(e.message || 'Không gửi được yêu cầu xin sửa số lượng.', 'error')
  } finally {
    xinSuaDangGui.value = false
  }
}

function onClickAction(action) {
  if (action.method === 'de_xuat_gui_duyet') return nhanGuiDuyet(action)
  // C1 — "Duyệt" đi qua nhanDuyet() để gom `dieu_chinh` từ các ô đang nhập.
  if (action.method === 'de_xuat_duyet_phieu') return nhanDuyet(action)
  if (action.method === 'de_xuat_xin_sua') return moXinSua()
  // Việc 3 (Task 5) — "Xoá" là hành động KHÔNG ĐẢO NGƯỢC ĐƯỢC DUY NHẤT của
  // toolbar này: xoá thật khỏi CSDL (khác "Huỷ phiếu" — bản ghi còn nguyên).
  // CHỈ thêm xác nhận cho method này — mọi when() khác của registry giữ
  // nguyên, đã được đối chiếu với máy trạng thái thật.
  if (action.method === 'de_xuat_xoa_nhap') {
    if (!window.confirm('Xoá phiếu này? Dữ liệu sẽ bị xoá VĨNH VIỄN khỏi hệ thống — KHÔNG thể khôi phục.')) return
    return chayHanhDong(action)
  }
  if (action.args && action.args.length) {
    argModalAction.value = action
    return
  }
  chayHanhDong(action)
}

const VARIANT_CLASS = {
  primary: 'btn',
  success: 'btn-g',
  danger: 'btn-o btn-danger',
  secondary: 'btn-o',
}
function classHanhDong(action) {
  return VARIANT_CLASS[action.variant] || 'btn-o'
}

onMounted(async () => {
  loadKhoaPhongList()
  if (!store.me) {
    try {
      store.setMe(await api.call('portal_me'))
    } catch (e) {
      // Không có `me` thì panel hành động rơi về rỗng (hanhDongChoPhep bọc
      // when() trong try/catch) — an toàn hơn là chặn cả màn.
    }
  }
  load()
})
</script>

<template>
  <div>
    <div class="topbar">
      <div>
        <router-link :to="quayLaiTo">
          <button class="btn-o" style="margin-bottom: 8px">{{ quayLaiNhan }}</button>
        </router-link>
      </div>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>

    <template v-else-if="doc">
      <!-- Đầu phiếu: mã + badge trạng thái, khoa phòng, khối truy vết —
           QĐ-KP-9: ba thứ này hiện ngay đầu, không đi tìm trong lịch sử. -->
      <div class="card mb10" style="margin-bottom: 14px">
        <div class="sb">
          <b style="font-size: 18px">{{ doc.ma_de_xuat || '(chưa gửi duyệt)' }}</b>
          <span class="badge" :class="deXuatBadge(doc.trang_thai)">{{ doc.trang_thai }}</span>
        </div>
        <p class="tag" style="margin-top: 4px">{{ tenKhoa }}</p>

        <div style="margin-top: 12px; border-top: 1px solid var(--line); padding-top: 10px">
          <p class="tag" style="font-size: 12px; text-transform: uppercase; letter-spacing: 0.03em; margin-bottom: 6px">
            Truy vết yêu cầu
          </p>
          <p style="font-size: 13px; margin-bottom: 2px">
            <b>Người yêu cầu:</b> {{ doc.nguoi_yeu_cau || doc.owner }}
          </p>
          <p style="font-size: 13px; margin-bottom: 2px">
            <b>Thời điểm gửi:</b> {{ doc.thoi_diem_gui ? fmtDateTime(doc.thoi_diem_gui) : 'Chưa gửi' }}
          </p>
          <p style="font-size: 13px">
            <b>Lý do yêu cầu:</b>
            <span v-if="doc.ly_do_yeu_cau"> {{ doc.ly_do_yeu_cau }}</span>
            <span v-else class="tag"> Chưa có</span>
          </p>
        </div>

        <p v-if="doc.ly_do_tu_choi" class="tag" style="color: var(--red); margin-top: 8px">
          Lý do từ chối: {{ doc.ly_do_tu_choi }}
        </p>

        <!-- Đơn hàng sinh ra từ phiếu — mã tra cứu của khách (`ma_de_xuat`,
             chép sang `custom_ma_tra_cuu` của Sales Order lúc duyệt) hiện
             TRƯỚC, mã hệ thống sau (QĐ-A4). -->
        <p v-if="doc.sales_order" style="font-size: 13px; margin-top: 8px">
          <b>Đơn hàng:</b>
          <router-link :to="`/orders/${doc.sales_order}`" style="text-decoration: underline; margin-left: 4px">
            {{ doc.ma_de_xuat || doc.sales_order }}
            <span v-if="doc.ma_de_xuat" class="tag">({{ doc.sales_order }})</span>
          </router-link>
        </p>
      </div>

      <!-- Panel hành động — render từ hanhDongChoPhep(doc, me). Hide, don't
           disable: khi rỗng thì không hiện khối này luôn. -->
      <div v-if="actions.length" class="card mb10" style="margin-bottom: 14px">
        <!-- C1 — nói rõ quyền "sửa rồi duyệt" NGAY CẠNH nút Duyệt. Không có
             câu này thì cột SL duyệt nhập được vẫn trông như một ô chỉ đọc. -->
        <p v-if="quanLyDangDuyet" class="tag" style="margin-bottom: 10px">
          Bạn có thể <b>sửa số lượng duyệt</b> ở bảng bên dưới trước khi bấm Duyệt. Để trống một ô
          nghĩa là <b>giữ nguyên</b> dòng đó; gõ <b>0</b> nghĩa là <b>bỏ mặt hàng</b> khỏi đơn.
          Cột SL đề xuất khoá vĩnh viễn, không sửa được.
        </p>
        <div class="flex" style="flex-wrap: wrap">
          <button
            v-for="a in actions"
            :key="a.method"
            :class="classHanhDong(a)"
            :disabled="!!dangChay"
            @click="onClickAction(a)"
          >
            {{ dangChay === a.method ? 'Đang gửi…' : a.label }}
          </button>
        </div>
      </div>

      <!-- Bảng dòng hàng — ba cột số, điểm cốt lõi của màn. -->
      <div class="card" style="padding: 0; overflow-x: auto">
        <table>
          <thead>
            <tr>
              <th>Mặt hàng</th>
              <th class="right">SL đề xuất</th>
              <th class="right">SL duyệt</th>
              <th v-if="hienCotXinSua" class="right">SL xin sửa</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="it in doc.items" :key="it.item_code" :style="khongDuyet(it) ? 'text-decoration: line-through; color: var(--gray)' : ''">
              <td>
                <b>{{ it.item_code }}</b>
                <template v-if="it.item_name"> — {{ it.item_name }}</template>
                <span v-if="it.dvt" class="tag"> ({{ it.dvt }})</span>
                <br />
                <span v-if="khongDuyet(it)" class="badge b-red" style="margin-top: 4px">Không duyệt</span>
                <span v-if="it.nguon_dong === 'Quản lý thêm'" class="badge b-purple" style="margin-top: 4px">Quản lý thêm</span>
                <template v-if="it.ghi_chu_quan_ly && !quanLyDangDuyet">
                  <br /><span class="tag">Ghi chú quản lý: {{ it.ghi_chu_quan_ly }}</span>
                </template>
                <!-- C1 — ô ghi chú của quản lý cho TỪNG dòng. Khi đang duyệt,
                     ô này thay cho dòng hiển thị ở trên (nó đã mang sẵn giá
                     trị cũ) để không hiện hai lần cùng một nội dung. -->
                <template v-if="quanLyDangDuyet">
                  <br />
                  <input
                    type="text"
                    v-model="ghiChuSua[it.item_code]"
                    placeholder="Ghi chú của quản lý (tuỳ chọn)"
                    :aria-label="`Ghi chú quản lý cho ${it.item_code}`"
                    style="width: 100%; max-width: 340px; margin-top: 6px"
                  />
                </template>
              </td>
              <td class="right" title="Khoá vĩnh viễn từ lúc gửi duyệt">{{ it.so_luong_de_xuat }}</td>
              <!-- C1 — nửa NHẬP LIỆU của thao tác mà nửa HIỂN THỊ (gạch ngang,
                   badge "Không duyệt", "Ghi chú quản lý") đã render sẵn từ
                   Task 4. KHÔNG `.number` trên v-model: xem `slDuyetSua`. -->
              <td class="right">
                <template v-if="quanLyDangDuyet">
                  <input
                    type="number" min="0" step="any"
                    v-model="slDuyetSua[it.item_code]"
                    :placeholder="String(it.so_luong_duyet)"
                    :aria-label="`SL duyệt cho ${it.item_code}`"
                    style="width: 90px; text-align: right"
                  />
                  <br v-if="soDuyetMoi(it) !== null" />
                  <span v-if="laBoMatHang(it)" class="tag" style="color: var(--red)">
                    Sẽ bỏ mặt hàng này khỏi đơn
                  </span>
                  <span v-else-if="soDuyetMoi(it) !== null" class="tag">
                    Sẽ duyệt {{ soDuyetMoi(it) }} / xin {{ it.so_luong_de_xuat }}
                  </span>
                </template>
                <template v-else>{{ it.so_luong_duyet }}</template>
              </td>
              <td v-if="hienCotXinSua" class="right">
                <span v-if="it.so_luong_xin_sua !== null && it.so_luong_xin_sua !== undefined">{{ it.so_luong_xin_sua }}</span>
                <span v-else class="tag">—</span>
              </td>
            </tr>
            <tr v-if="!doc.items || !doc.items.length">
              <td :colspan="hienCotXinSua ? 4 : 3" class="tag">Chưa có dòng hàng nào.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="doc.ghi_chu" class="card mb10" style="margin-top: 14px">
        <div class="h3">Ghi chú</div>
        <p style="font-size: 13px; margin-top: 6px">{{ doc.ghi_chu }}</p>
      </div>
    </template>

    <!-- Ruling coordinator (1) — hỏi lý do yêu cầu khi bấm Gửi duyệt mà
         phiếu chưa có lý do. Server bắt buộc non-empty, không có ngưỡng ký
         tự tối thiểu nào khác — `min-len="1"`. -->
    <ReasonModal
      :open="lyDoYeuCauOpen"
      title="Nhập lý do yêu cầu"
      desc="Lý do yêu cầu là bắt buộc khi gửi duyệt — quản lý sẽ đọc lý do này khi xét phiếu."
      placeholder="VD: Khoa cần bổ sung vật tư tiêu hao cho quý này..."
      :min-len="1"
      :submitting="dangLuuLyDo"
      submit-label="Lưu và gửi duyệt"
      @close="lyDoYeuCauOpen = false"
      @submit="xacNhanLyDoRoiGui"
    />

    <!-- Hành động có `args` dạng một textarea bắt buộc (Từ chối, Không đồng
         ý sửa) — dùng chung một modal, khoá theo `argModalAction`. -->
    <ReasonModal
      :open="!!argModalAction"
      :title="argModalAction ? argModalAction.label : ''"
      :desc="argModalAction ? `${argModalAction.args[0].label} — bắt buộc, được ghi vào phiếu.` : ''"
      :min-len="1"
      :submitting="!!dangChay"
      submit-label="Gửi"
      @close="argModalAction = null"
      @submit="onSubmitArgModal"
    />

    <!-- Ruling coordinator (2) — "Xin sửa số lượng": khoa nhập số mong muốn
         cho từng dòng đang có trên đơn, chỉ những dòng ĐỔI thật mới được
         gửi (khớp `_loc_thay_doi_that` phía server). -->
    <div v-if="xinSuaOpen" :class="isMobile ? 'sheet' : 'modal'" @click.self="xinSuaOpen = false">
      <div class="card" style="width: 520px; max-width: 92vw">
        <h3>Xin sửa số lượng</h3>
        <p class="tag" style="margin: 8px 0 12px">
          Nhập số lượng mong muốn cho từng dòng — chỉ dòng có đổi số mới được gửi. Quản lý sẽ duyệt lại yêu cầu này.
        </p>
        <div v-for="it in dongXinSua" :key="it.item_code" class="rowline">
          <span>
            <b>{{ it.item_code }}</b>
            <template v-if="it.item_name"> — {{ it.item_name }}</template>
            <br /><span class="tag">Đang duyệt: {{ it.so_luong_duyet }} {{ it.dvt }}</span>
            <!-- việc 5 — chỉ hiện khi ô mang số 0 TƯỜNG MINH (không phải ô
                 trống): người dùng phải NHÌN THẤY mình đang xin gì, không
                 đoán qua một con số. -->
            <br v-if="laXinBoMatHang(it)" />
            <span v-if="laXinBoMatHang(it)" class="tag" style="color: var(--red)">
              Sẽ đề nghị bỏ mặt hàng này khỏi đơn
            </span>
          </span>
          <!-- KHÔNG `.number`: ô xoá trắng phải giữ nguyên chuỗi rỗng ''
               (nghĩa "chưa đổi gì") thay vì bị Vue tự ép thành số 0 — xem
               giải thích ở khai báo `xinSuaSoLuong`. -->
          <input
            type="number" min="0" step="any"
            v-model="xinSuaSoLuong[it.item_code]"
            style="width: 90px; text-align: right"
          />
        </div>
        <p v-if="!dongXinSua.length" class="tag">Không có dòng nào đang trên đơn để xin sửa.</p>
        <div class="flex" style="justify-content: flex-end; margin-top: 14px; gap: 8px">
          <button class="btn-o" :disabled="xinSuaDangGui" @click="xinSuaOpen = false">Quay lại</button>
          <button class="btn" :disabled="xinSuaDangGui" @click="guiXinSua">
            {{ xinSuaDangGui ? 'Đang gửi…' : 'Gửi yêu cầu' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
