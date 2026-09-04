<script setup>
// Chi tiết MỘT yêu cầu mua — cả hai nửa của nó, trên một màn.
//
// Thay `DeXuatDetail.vue` + `OrderDetail.vue` (03/09/2026, chủ đầu tư
// chốt). Trước bản này, bấm một dòng ở danh sách cho ra màn PHIẾU, rồi phải
// bấm tiếp một link để sang màn ĐƠN — "khoa xin 100 / duyệt 40 / giao 25"
// là ba con số của MỘT việc nằm ở HAI trang. Đó đúng là nghịch lý QĐ-G11 đã
// dỡ ở tầng danh sách và bỏ quên ở tầng chi tiết.
//
// HAI ĐƯỜNG, MỘT MÀN — cố ý không tạo route mới, không chuyển hướng:
// `Portal De Xuat Mua.name` và `Sales Order.name` là hai naming khác nhau,
// nên "một route nhận cả hai id" phải ĐOÁN loại chứng từ từ chuỗi id. Giữ
// hai đường thì mọi bookmark và mọi link trong thông báo ĐÃ GỬI ĐI
// (`/yeu-cau/don/<name>`, xem `api/portal.py::_link_chung_tu`) không phải
// đụng một dòng nào.
//
// TASK 7b — cả hai đường `/yeu-cau/phieu/:ten` và `/yeu-cau/don/:name` nay
// trỏ vào màn này (xem router.js); `OrderDetail.vue`/`DeXuatDetail.vue` đã
// nghỉ, xoá khỏi cây view.
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { fmtDate, giaiDoanBadge, nhanGiaiDoan } from '../format'
import { useIsMobile } from '../useMobile'
import { store } from '../store'
import { showToast } from '../toast'
import { hanhDongChoPhep } from '../de-xuat-actions'
import { hanhDongDonChoPhep } from '../don-actions'
import { capNhatChoDuyetCount } from '../cho-duyet'
import ReasonModal from '../components/ReasonModal.vue'
import KhoiTruyVet from '../components/chi-tiet/KhoiTruyVet.vue'
import KhoiTienTrinh from '../components/chi-tiet/KhoiTienTrinh.vue'
import KhoiDongThoiGian from '../components/chi-tiet/KhoiDongThoiGian.vue'
import KhoiBaoGia from '../components/chi-tiet/KhoiBaoGia.vue'
import KhoiGiaoHang from '../components/chi-tiet/KhoiGiaoHang.vue'
import KhoiHoaDonTaiLieu from '../components/chi-tiet/KhoiHoaDonTaiLieu.vue'
import BangMatHang from '../components/chi-tiet/BangMatHang.vue'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

const loading = ref(true)
const error = ref('')
const phieu = ref(null)
const don = ref(null)
// Task 8 — dòng thời gian nhật ký (spec §9). Best-effort NGOÀI `load()`
// (helper riêng, `try/catch` của CHÍNH nó): một lần đọc sổ hỏng chỉ được
// làm rỗng khối này, không được kéo theo lỗi `error.value` làm trắng CẢ
// màn — cùng luật `napDon`/`napPhieu` bên dưới.
const nhatKy = ref([])
const dangTaiNhatKy = ref(false)

// Đầu mối = đường đã vào. `:ten` → phiếu, `:name` → đơn. Không đoán theo
// hình dạng chuỗi id.
const tenPhieuVao = computed(() => route.params.ten || '')
const tenDonVao = computed(() => route.params.name || '')

// Nạp cả hai nửa. Nửa THỨ HAI là best-effort: một yêu cầu vẫn phải đọc
// được khi nửa kia lỗi (hoặc không tồn tại) — thà thiếu một khối còn hơn
// trắng cả màn. Nhưng KHÔNG rơi im lặng: ghi console, cùng luật `App.vue`.
async function load() {
  loading.value = true
  error.value = ''
  phieu.value = null
  don.value = null
  nhatKy.value = []
  try {
    if (tenPhieuVao.value) {
      phieu.value = await api.callDeXuat('de_xuat_chi_tiet', { ten: tenPhieuVao.value })
      dungLaiDieuChinh()
      if (phieu.value.sales_order) await napDon(phieu.value.sales_order)
      // Task 8, note (d) — nhánh VÀO BẰNG PHIẾU: `de_xuat`, không `order`
      // (dù đơn đã có ở dòng trên — endpoint tự gộp nhật ký của CẢ hai
      // chứng từ khi biết `de_xuat`, xem docstring `portal_nhat_ky_yeu_
      // cau`). `napNhatKy()` chỉ gói phần DÙNG CHUNG (cờ đang tải + bắt
      // lỗi) — lời gọi API THẬT vẫn viết LITERAL ở từng nhánh (không dựng
      // đối tượng `{de_xuat}`/`{order}` từ một biến tên khoá động), để
      // lưới regex (`test_nhat_ky_giao_dien.py`) canh ĐÚNG cú pháp gọi của
      // TỪNG nhánh (bài học Task 7b: canh chỗ DÙNG, không canh gián tiếp).
      // KHÔNG `await` — đọc sổ là việc PHỤ, không được chặn màn chính.
      napNhatKy(() => api.call('portal_nhat_ky_yeu_cau', { de_xuat: tenPhieuVao.value }))
    } else {
      don.value = await api.call('portal_order_track', { order: tenDonVao.value })
      if (don.value.de_xuat) await napPhieu(don.value.de_xuat)
      // Task 8, note (d) — nhánh VÀO BẰNG ĐƠN: `order`. Thiếu nhánh này là
      // đúng nửa-sống mà note (d) cảnh — nửa người dùng vào bằng link
      // `/yeu-cau/don/...` (thông báo giao hàng/hoá đơn gửi từ Miyano)
      // thấy khối dòng thời gian trống, không ai biết vì sao.
      napNhatKy(() => api.call('portal_nhat_ky_yeu_cau', { order: tenDonVao.value }))
    }
  } catch (e) {
    error.value = e.message || 'Không tải được chi tiết yêu cầu.'
  } finally {
    loading.value = false
  }
}
// Best-effort — KHÔNG `await` trong `load()` (đọc sổ nhật ký không được
// làm CHẬM màn chính) và tự bọc lỗi của CHÍNH nó — cùng luật `napDon`/
// `napPhieu` ngay dưới: một khối phụ hỏng không được kéo trắng cả màn.
async function napNhatKy(goi) {
  dangTaiNhatKy.value = true
  try {
    nhatKy.value = await goi()
  } catch (e) {
    console.warn('Không nạp được dòng thời gian nhật ký:', e)
  } finally {
    dangTaiNhatKy.value = false
  }
}
async function napDon(ten) {
  try {
    don.value = await api.call('portal_order_track', { order: ten })
  } catch (e) {
    console.warn('Không nạp được nửa ĐƠN của yêu cầu này:', e)
  }
}
async function napPhieu(ten) {
  try {
    phieu.value = await api.callDeXuat('de_xuat_chi_tiet', { ten })
    // Mandatory #1 — gieo lại `ghiChuSua` sau MỖI lần nạp phiếu, kể cả khi
    // vào màn bằng đường đơn. Quên bước này ở đúng nhánh này là y hệt lỗi
    // đã bắt ở Task trước: quản lý bấm Duyệt sẽ gửi ghi chú rỗng đè lên ghi
    // chú cũ trong im lặng.
    dungLaiDieuChinh()
  } catch (e) {
    // Ca tới được: nhân viên khoa A mở link đơn của khoa B qua một thông
    // báo định tuyến sai — `_phieu_cua_toi()` chặn đúng. Mất khối truy vết,
    // không mất cả màn.
    console.warn('Không nạp được nửa PHIẾU của yêu cầu này:', e)
  }
}

// Review Task 7a (Critical 1) — giai đoạn ĐỌC THẲNG từ server, KHÔNG suy
// lại ở client. Bản suy trước đây (đối chiếu tay với `_sql_giai_doan()`,
// api/portal.py) là một TẬP CON THU HẸP của luật thật — thiếu ba nhánh:
//   * `d.status_vi === 'Từ chối'` không bao giờ khớp: `_so_status_vi_full()`
//     trả "Miyano đã từ chối", một chuỗi khác hẳn hằng trạng thái PHIẾU
//     'Từ chối' — đơn Miyano đã từ chối rơi hết nhánh, ra badge "Đã duyệt";
//   * thiếu `so.status == 'Closed'` (đơn đóng sớm giữa chừng);
//   * thiếu `workflow_state == 'Báo giá hết hạn'` (`chap_nhan` chỉ được set
//     khi đang "Chờ khách đồng ý", rỗng khi đã hết hạn).
// Ba lỗi đó đúng loại "bản sao thứ hai trôi khỏi bản gốc" mà kế hoạch gộp
// đã cảnh báo trước — sửa bằng cách xoá bản sao, không vá từng nhánh.
// `de_xuat_chi_tiet`/`portal_order_track` nay trả sẵn `giai_doan`, tính
// bằng CHÍNH `_sql_giai_doan()` mà danh sách dùng.
const giaiDoan = computed(() => phieu.value?.giai_doan || don.value?.giai_doan || 'da_duyet')

const ma = computed(() => phieu.value?.ma_de_xuat || don.value?.order || phieu.value?.name || '')

// Khoa phòng — chép từ DeXuatDetail.vue. Chỉ đọc được từ nửa PHIẾU
// (`portal_order_track` không trả `khoa_phong`, xem review 7a) — một đơn cũ
// không có phiếu (ca 6) thì ô này để trống, không phải một khiếm khuyết.
const khoaPhongList = ref([])
async function loadKhoaPhongList() {
  try {
    khoaPhongList.value = await api.callKho('kho_khoa_phong_list', { ca_inactive: 1 })
  } catch (e) {
    // Best-effort — một khách chưa mở kho vẫn phải xem được chi tiết, chỉ
    // mất phần dịch tên khoa.
  }
}
const tenKhoa = computed(() => {
  if (!phieu.value) return ''
  if (!phieu.value.khoa_phong) return 'Toàn viện'
  const k = khoaPhongList.value.find((x) => x.name === phieu.value.khoa_phong)
  return k ? k.ten_khoa_phong : phieu.value.khoa_phong
})

// "Tổng tiền" — CỐ Ý KHÔNG hiện ở đầu trang. `portal_order_track` tự dựng
// dict trả về (không đẩy thẳng `so.as_dict()`) và không có khoá
// `grand_total`; tự cộng `amount` từng dòng sẽ ra tổng TRƯỚC thuế/chiết
// khấu — sai với số trên PDF/hoá đơn của CHÍNH đơn đó, hiện trên CÙNG một
// màn. 7a không đụng file Python nên không thêm được field này ở nguồn.

const lyDoTuChoi = computed(() => phieu.value?.ly_do_tu_choi || don.value?.ly_do_tu_choi || '')

// Toolbar hành động — DỮ LIỆU, không rải v-if khắp template. Nối CẢ HAI
// registry: đây là điểm được nhiều nhất của việc gộp (nhân viên khoa và
// quản lý có hai đường sửa số lượng khác nhau, trước đây nằm ở hai màn).
//
// `dacBiet: 'sua_so_luong'` (đơn) BỊ LỌC khỏi thanh này — mục đó không phải
// một nút bấm-là-gọi-API: `KhoiBaoGia.vue` tự dựng khối sửa số lượng của
// riêng nó (đọc `suaDuocSoLuong` NGAY TRONG component, không qua registry)
// và phát sự kiện `sua-so-luong` mang sẵn phần chênh lệch đã tính. Render nó
// thêm một lần nữa ở đây qua `onClickAction` mặc định sẽ gọi thẳng API mà
// không có payload `dong` — một nút thứ hai, cùng nhãn, luôn lỗi.
const hanhDong = computed(() => [
  ...hanhDongChoPhep(phieu.value, store.me),
  ...hanhDongDonChoPhep(don.value, store.me).filter((a) => !a.dacBiet),
])

const quanLyDangDuyet = computed(
  () => phieu.value?.trang_thai === 'Chờ duyệt' && !!store.me?.la_quan_ly
)

// Vòng sửa 1 (review, Task 8) — lối vào SỬA cho phiếu Nháp, ngay tại màn
// chỉ đọc này (KHÔNG qua registry — đây là ĐIỀU HƯỚNG sang màn khác, không
// phải một hành động server).
const coTheSuaNhap = computed(
  () => phieu.value?.trang_thai === 'Nháp' && (phieu.value?.owner === store.me?.user || store.me?.la_quan_ly)
)

// Nút "Quay lại" mang theo bộ lọc đang mở của danh sách (C3). Giữ nguyên cơ
// chế `?chip=` / `?khoa=` — người dùng vào thẳng bằng URL (link thông báo,
// tab ghim) không có bước lịch sử nào để `router.back()` lùi.
const quayLaiTo = computed(() => ({
  name: 'yeu-cau',
  query: {
    ...(route.query.chip ? { chip: String(route.query.chip) } : {}),
    ...(route.query.khoa ? { khoa: String(route.query.khoa) } : {}),
  },
}))

// --- C1: quản lý SỬA rồi mới duyệt (chép nguyên từ DeXuatDetail.vue, đổi
// `doc.` → `phieu.`) --------------------------------------------------
//
// CỐ Ý giữ CHUỖI THÔ, không `v-model.number`: `Number('')` = 0, nên để Vue
// tự ép kiểu sẽ biến một ô KHÔNG ĐỘNG TỚI (hoặc bị xoá trắng) thành SỐ 0 —
// mà 0 ở đây mang nghĩa THẬT và KHÔNG ĐẢO NGƯỢC ĐƯỢC: "bỏ mặt hàng này khỏi
// đơn" (§5.3). Ô trống = "giữ nguyên dòng này"; CHỈ số 0 gõ tường minh mới
// là bỏ mặt hàng.
const slDuyetSua = ref({})
const ghiChuSua = ref({})
function dungLaiDieuChinh() {
  // Mandatory #1 — SL duyệt để TRỐNG (placeholder hiện số đang có): một ô
  // điền sẵn số cũ mời người dùng sửa đè lên một con số trông như đã được
  // xác nhận.
  slDuyetSua.value = {}
  // Mandatory #1 — GHI CHÚ thì PHẢI gieo lại từ dữ liệu vừa nạp: đây là ô
  // VĂN BẢN, quản lý phải thấy ghi chú cũ để sửa tiếp; `BangMatHang.vue`
  // chỉ GHI vào prop này, nó không tự gieo — bỏ bước này là Duyệt gửi chuỗi
  // rỗng đè lên ghi chú vòng trước, mất dữ liệu trong im lặng.
  ghiChuSua.value = Object.fromEntries(
    (phieu.value?.items || []).map((it) => [it.item_code, it.ghi_chu_quan_ly || ''])
  )
}

function soDuyetMoi(it) {
  const raw = slDuyetSua.value[it.item_code]
  if (raw === undefined || raw === null) return null
  const chuoi = String(raw).trim()
  if (!chuoi) return null
  const n = Number(chuoi)
  if (!Number.isFinite(n) || n < 0) return null
  return n === (Number(it.so_luong_duyet) || 0) ? null : n
}
function ghiChuDoi(it) {
  return (ghiChuSua.value[it.item_code] || '').trim() !== (it.ghi_chu_quan_ly || '').trim()
}

const dieuChinhItems = computed(() => {
  if (!quanLyDangDuyet.value) return []
  const ra = []
  for (const it of phieu.value?.items || []) {
    const so = soDuyetMoi(it)
    const doiGhiChu = ghiChuDoi(it)
    if (so === null && !doiGhiChu) continue // dòng không đổi → KHÔNG gửi
    const dong = { item_code: it.item_code, so_luong_duyet: so === null ? Number(it.so_luong_duyet) || 0 : so }
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
  const theoMa = Object.fromEntries((phieu.value.items || []).map((it) => [it.item_code, it]))
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

// --- Dispatch hành động chung -----------------------------------------
const dangChay = ref('')
const TOAST_THANH_CONG = {
  // Phiếu — chép nguyên từ DeXuatDetail.vue.
  de_xuat_xoa_nhap: 'Đã xoá phiếu.',
  de_xuat_duyet_phieu: 'Đã duyệt phiếu — đơn hàng đã được tạo.',
  de_xuat_tu_choi: 'Đã từ chối phiếu.',
  de_xuat_huy: 'Đã huỷ phiếu.',
  de_xuat_duyet_sua: 'Đã đồng ý sửa số lượng — đơn hàng đã cập nhật.',
  de_xuat_tu_choi_sua: 'Đã từ chối yêu cầu xin sửa.',
  de_xuat_thu_hoi: 'Đã thu hồi đơn về Nháp — sửa xong nhớ Gửi duyệt lại.',
  // Đơn — hai mục CHUNG method 'portal_order_accept' (Đồng ý / Không đồng
  // ý), nên khoá theo `method + '|' + label` — cùng khoá dùng cho `:key`
  // của v-for thanh hành động (mandatory #3).
  'portal_order_accept|✔ Đồng ý đặt hàng': 'Đã đồng ý — đơn chuyển sang chờ Miyano xác nhận.',
  'portal_order_accept|✕ Không đồng ý…': 'Đã gửi phản hồi không đồng ý — Miyano sẽ liên hệ lại.',
  'portal_order_huy|🗑 Huỷ đơn…': 'Đã huỷ đơn hàng theo yêu cầu của bạn.',
  'portal_request_cancel|Huỷ / Sửa đơn': 'Đã gửi yêu cầu huỷ/sửa đơn đến Miyano.',
}

async function chayHanhDong(action, extraArgs) {
  if (dangChay.value) return
  // Khoá theo `method + '|' + label` — cùng lý do mandatory #3 đã buộc
  // `:key` của v-for phải làm vậy: hai mục "Đồng ý"/"Không đồng ý" dùng
  // CHUNG method 'portal_order_accept', method suông không phân biệt được.
  dangChay.value = action.method + '|' + action.label
  try {
    // Chọn module theo `action.nhom` — đơn đi `api.call` kèm `order`, phiếu
    // đi `api.callDeXuat` kèm `ten` (brief Task 7, Step 3).
    if (action.nhom === 'don') {
      await api.call(action.method, { order: don.value.order, ...(extraArgs || {}) })
    } else {
      await api.callDeXuat(action.method, { ten: phieu.value.name, ...(extraArgs || {}) })
    }
    showToast(
      TOAST_THANH_CONG[action.method + '|' + action.label] ||
        TOAST_THANH_CONG[action.method] ||
        `Đã ${action.label}.`
    )
    if (action.method === 'de_xuat_xoa_nhap') {
      // Xoá nháp thì phiếu không còn tồn tại nữa — quay lại danh sách thay
      // vì tải lại một chi tiết đã bị xoá.
      router.push(quayLaiTo.value)
    } else if (action.method === 'de_xuat_thu_hoi') {
      // Thu hồi KHÔNG phải một đích đến — nó là bước đầu của việc SỬA. Thả
      // người dùng lại màn chỉ-đọc là bắt họ tự tìm đường sang màn Đặt hàng.
      router.push({ name: 'dat-hang', params: { ten: phieu.value.name } })
    } else {
      argModalAction.value = null
      await load()
    }
    // C3 — badge "Duyệt" trên nav phải nói đúng NGAY SAU thao tác. Chỉ áp
    // cho hành động PHIẾU — đơn không đổi hàng chờ duyệt của quản lý.
    if (action.nhom !== 'don') {
      try {
        await capNhatChoDuyetCount(store)
      } catch (e) {
        console.warn('Không cập nhật lại được số phiếu chờ duyệt:', e)
      }
    }
  } catch (e) {
    showToast(e.message || 'Không thực hiện được thao tác này.', 'error')
  } finally {
    dangChay.value = ''
  }
}

// Hành động có `args` → mở modal chung trước khi gọi, kiểm required qua
// chính ReasonModal.
//
// Mandatory #2 — KHÔNG đọc cứng `args[0]`. Registry phiếu chỉ có một
// textarea đơn (Từ chối/Không đồng ý sửa — khớp khuôn cũ). Registry đơn có
// hình dạng khác: "Đồng ý đặt hàng" mang MỘT hằng số (`{key:'action',
// const:'dong_y'}` — không phải ô nhập, không mở hộp thoại nào), "Không
// đồng ý" mang HAI phần tử (một hằng số + một textarea bắt buộc). Gom mọi
// phần tử có `const` vào đối số gửi thẳng; hết ô cần nhập thì gọi luôn; còn
// đúng MỘT ô thì mở modal cho ô đó (dùng `minLen` của nó nếu có).
const argModalAction = ref(null)
const argModalArg = ref(null)
const argModalConsts = ref({})
// Việc 5 (review toàn nhánh 03/09/2026) — mục args được phép mang `desc`/
// `placeholder` VIẾT TAY, và hai computed này là chỗ chúng tới được modal.
// Câu sinh máy móc bên dưới GIỮ LẠI làm đường lui: nó vẫn đúng cho ba mục
// args còn lại (đều đảo ngược được, hoặc chỉ ghi một yêu cầu chờ Miyano xử
// lý), nên bắt cả bốn mục tự viết một câu là bốn chỗ để trôi lệch. Chỉ hành
// động KHÔNG QUAY LẠI ĐƯỢC mới đáng một câu riêng — xem "🗑 Huỷ đơn…" trong
// `don-actions.js`.
const argModalDesc = computed(() => {
  if (!argModalArg.value) return ''
  return argModalArg.value.desc || `${argModalArg.value.label} — bắt buộc.`
})
const argModalPlaceholder = computed(() => argModalArg.value?.placeholder || '')
function onSubmitArgModal(gia_tri) {
  chayHanhDong(argModalAction.value, { ...argModalConsts.value, [argModalArg.value.key]: gia_tri })
}

function onClickAction(action) {
  if (action.method === 'de_xuat_gui_duyet') return nhanGuiDuyet(action)
  // C1 — "Duyệt" đi qua nhanDuyet() để gom `dieu_chinh` từ các ô đang nhập.
  if (action.method === 'de_xuat_duyet_phieu') return nhanDuyet(action)
  if (action.method === 'de_xuat_xin_sua') return moXinSua()
  // Thu hồi ĐỔI TRẠNG THÁI phiếu và rút nó khỏi hàng chờ của quản lý — nói
  // trước hệ quả, vì "Sửa" trên các màn khác của cổng không làm điều đó.
  if (action.method === 'de_xuat_thu_hoi') {
    if (!window.confirm(
      'Thu hồi đơn này về Nháp để sửa?\n\n'
      + 'Đơn sẽ rời hàng chờ duyệt của quản lý. Mã đơn giữ nguyên; sửa xong '
      + 'bạn phải bấm Gửi duyệt lại.'
    )) return
    return chayHanhDong(action)
  }
  // "Xoá" là hành động KHÔNG ĐẢO NGƯỢC ĐƯỢC DUY NHẤT của toolbar này: xoá
  // thật khỏi CSDL (khác "Huỷ phiếu" — bản ghi còn nguyên).
  if (action.method === 'de_xuat_xoa_nhap') {
    if (!window.confirm('Xoá phiếu này? Dữ liệu sẽ bị xoá VĨNH VIỄN khỏi hệ thống — KHÔNG thể khôi phục.')) return
    return chayHanhDong(action)
  }

  const consts = Object.fromEntries(
    (action.args || []).filter((a) => 'const' in a).map((a) => [a.key, a.const])
  )
  const canNhap = (action.args || []).filter((a) => !('const' in a))
  if (!canNhap.length) return chayHanhDong(action, consts)
  if (canNhap.length === 1) {
    argModalAction.value = action
    argModalConsts.value = consts
    argModalArg.value = canNhap[0]
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

// Ruling coordinator (1) — nút "Gửi duyệt" KHÔNG ẩn dù `ly_do_yeu_cau` trống.
// Bấm mà thiếu lý do → mở modal hỏi lý do (bắt buộc), lưu qua
// `de_xuat_luu_nhap` rồi mới gửi — KHÔNG hỏi lại nếu phiếu đã có lý do.
const lyDoYeuCauOpen = ref(false)
const dangLuuLyDo = ref(false)
function nhanGuiDuyet(action) {
  if ((phieu.value?.ly_do_yeu_cau || '').trim()) {
    chayHanhDong(action)
    return
  }
  lyDoYeuCauOpen.value = true
}
async function xacNhanLyDoRoiGui(lyDo) {
  dangLuuLyDo.value = true
  try {
    await api.callDeXuat('de_xuat_luu_nhap', { ten: phieu.value.name, ly_do_yeu_cau: lyDo })
    lyDoYeuCauOpen.value = false
    await chayHanhDong({ method: 'de_xuat_gui_duyet', label: 'Gửi duyệt' })
  } catch (e) {
    showToast(e.message || 'Không lưu được lý do yêu cầu.', 'error')
  } finally {
    dangLuuLyDo.value = false
  }
}

// Ruling coordinator (2) — "Xin sửa số lượng" không khớp khuôn args (đầu
// vào là NHIỀU dòng số lượng), nên xử lý RIÊNG. Chỉ đề nghị sửa những dòng
// ĐANG NẰM trên đơn — dòng quản lý đã hạ về 0 không còn trên Sales Order.
const xinSuaOpen = ref(false)
const xinSuaSoLuong = ref({})
const xinSuaDangGui = ref(false)
// Ruling P51 — "đang nằm trên đơn" phải đọc `so_luong_tren_don`, không
// `so_luong_duyet`.
const dongXinSua = computed(() =>
  (phieu.value?.items || []).filter((it) => Number(soDangCo(it)) > 0)
)
function soDangCo(it) {
  return it.so_luong_tren_don ?? it.so_luong_duyet
}
function lechVoiDon(it) {
  return it.so_luong_tren_don != null && Number(it.so_luong_tren_don) !== Number(it.so_luong_duyet)
}
function moXinSua() {
  xinSuaSoLuong.value = Object.fromEntries(dongXinSua.value.map((it) => [it.item_code, String(soDangCo(it))]))
  xinSuaOpen.value = true
}
function laXinBoMatHang(it) {
  const raw = xinSuaSoLuong.value[it.item_code]
  return raw !== '' && raw !== undefined && raw !== null && Number(raw) === 0
}
async function guiXinSua() {
  if (xinSuaDangGui.value) return
  const doiItems = []
  for (const it of dongXinSua.value) {
    const raw = xinSuaSoLuong.value[it.item_code]
    if (raw === '' || raw === undefined || raw === null) continue
    const so = Number(raw)
    if (!Number.isFinite(so) || so < 0) continue
    if (so !== Number(soDangCo(it))) {
      doiItems.push({ item_code: it.item_code, qty: so })
    }
  }
  if (!doiItems.length) {
    showToast('Chưa sửa số lượng dòng nào.', 'error')
    return
  }
  xinSuaDangGui.value = true
  try {
    await api.callDeXuat('de_xuat_xin_sua', { ten: phieu.value.name, dong: JSON.stringify({ items: doiItems }) })
    xinSuaOpen.value = false
    showToast('Đã gửi yêu cầu xin sửa số lượng — chờ quản lý duyệt.')
    await load()
  } catch (e) {
    showToast(e.message || 'Không gửi được yêu cầu xin sửa số lượng.', 'error')
  } finally {
    xinSuaDangGui.value = false
  }
}

// --- Nửa ĐƠN (chép từ OrderDetail.vue, đổi `data.` → `don.`) -----------

// Mã lý do do server trả về (`30_API_Spec` §5) → thông điệp cho người đọc.
const LY_DO = {
  het_han_muc: 'hết hạn mức',
  ngoai_hdnt: 'ngoài hợp đồng',
  thieu_gia: 'chưa có giá',
}

// UC-14 — đặt lại theo đơn cũ, theo giá hiện hành. Tạo thẳng một phiếu Nháp
// mang đúng các dòng đặt lại được, rồi mở `/dat-hang/<ten>` — KHÔNG còn
// giỏ toàn cục `/cart` (Task 10).
const dangDatLai = ref(false)
async function datLai() {
  if (dangDatLai.value) return
  dangDatLai.value = true
  try {
    const res = await api.call('portal_reorder', { order: don.value.order })
    if (!res.gio_hang.length) {
      showToast('Không mặt hàng nào của đơn này còn đặt lại được.', 'error')
      return
    }
    const tenMoi = (await api.callDeXuat('de_xuat_tao_nhap')).name
    await api.callDeXuat('de_xuat_luu_nhap', {
      ten: tenMoi,
      items: JSON.stringify(
        res.gio_hang.map((d) => ({
          item_code: d.item_code,
          item_name: d.item_name || d.item_code,
          dvt: d.uom || '',
          so_luong_de_xuat: Number(d.qty) || 0,
        }))
      ),
    })
    if (res.bi_loai.length) {
      showToast(
        'Không đưa vào giỏ được: ' +
          res.bi_loai
            .map((d) => `${d.item_code} (${LY_DO[d.ly_do] || d.ly_do})`)
            .join(', '),
        'error'
      )
    }
    router.push({ name: 'dat-hang', params: { ten: tenMoi } })
  } catch (e) {
    showToast(e.message || 'Không đặt lại được đơn này.', 'error')
  } finally {
    dangDatLai.value = false
  }
}

// Việc 1/brief 2026-08-15 + controller ruling 2026-08-16 — sửa số lượng
// trước khi gửi lại báo giá. `KhoiBaoGia.vue` tự validate + tính chênh lệch
// rồi phát `sua-so-luong` mang sẵn payload; CHA vẫn phải giữ modal xác nhận
// (`guiLaiOpen`, chép nguyên từ `OrderDetail.vue`) — review Task 7a Critical
// 2 đã sửa lại đúng chỗ bản đầu bỏ mất: hành động này đặt `rate` các dòng
// đã đổi về 0 và đẩy đơn về "Chờ xác nhận", khách MẤT báo giá đang có nếu
// bấm nhầm. `KhoiBaoGia` bày sẵn các dòng để SỬA số, không phải để XÁC
// NHẬN gửi đi — hai việc khác nhau, và ruling gốc đòi modal riêng cho việc
// sau. Modal chỉ đóng ở nhánh THÀNH CÔNG (đúng hợp đồng `KhoiBaoGia.vue` đã
// ghi: "modal xác nhận... KHÔNG đóng khi API lỗi, để khách bấm lại").
const dangSuaSoLuong = ref(false)
const guiLaiOpen = ref(false)
const dongGuiLai = ref({ items: [], dat_ngoai: [] })
function nhanSuaSoLuong(dong) {
  dongGuiLai.value = dong
  guiLaiOpen.value = true
}
async function guiLaiBaoGia() {
  if (dangSuaSoLuong.value) return
  const { items: doiItems, dat_ngoai: doiDatNgoai } = dongGuiLai.value
  if (!doiItems.length && !doiDatNgoai.length) {
    guiLaiOpen.value = false
    showToast('Chưa sửa số lượng dòng nào.', 'error')
    return
  }
  dangSuaSoLuong.value = true
  try {
    await api.call('portal_order_sua_so_luong', {
      order: don.value.order,
      dong: JSON.stringify({ items: doiItems, dat_ngoai: doiDatNgoai }),
    })
    guiLaiOpen.value = false
    showToast('Đã gửi số lượng mới — đơn chuyển sang chờ Miyano báo giá lại.')
    await load()
  } catch (e) {
    showToast(e.message || 'Không gửi được thay đổi số lượng. Vui lòng thử lại.', 'error')
  } finally {
    dangSuaSoLuong.value = false
  }
}

onMounted(async () => {
  loadKhoaPhongList()
  if (!store.me) {
    try {
      store.setMe(await api.call('portal_me'))
    } catch (e) {
      console.warn('Không nạp được hồ sơ phiên — thanh hành động sẽ rỗng:', e)
    }
  }
  await load()
})
</script>

<template>
  <div>
    <div class="topbar">
      <router-link :to="quayLaiTo"><button class="btn-o" style="margin-bottom: 8px">← Quay lại</button></router-link>
    </div>

    <div v-if="loading" class="loading">Đang tải…</div>
    <div v-else-if="error" class="empty">{{ error }}</div>

    <template v-else>
      <!-- 1. Đầu trang — MỘT mã, MỘT badge giai đoạn. Hai badge chồng nhau
           (loại đơn + trạng thái) là thứ màn cũ làm và là thứ khiến người
           đọc phải tự ghép hai từ điển trạng thái. -->
      <div class="card mb10" style="margin-bottom: 14px">
        <div class="sb">
          <b style="font-size: 16px">{{ ma }}</b>
          <span class="badge" :class="giaiDoanBadge(giaiDoan)">{{ nhanGiaiDoan(giaiDoan) }}</span>
        </div>
        <p class="tag" style="margin-top: 4px">
          <template v-if="tenKhoa">{{ tenKhoa }}</template>
          <template v-if="don?.order_date"> · Đặt ngày {{ fmtDate(don.order_date) }}</template>
          <template v-if="don?.po_khach"> · Số dự trù: {{ don.po_khach }}</template>
          <template v-if="don?.hdnt"> · {{ don.hdnt }}</template>
        </p>
        <p v-if="lyDoTuChoi" class="tag" style="color: var(--red); margin-top: 8px">
          Lý do từ chối: {{ lyDoTuChoi }}
        </p>
      </div>

      <!-- Review Task 7a (Important 3) — banner báo giá GATE RIÊNG theo
           `don?.chap_nhan?.can_dong_y`, KHÔNG lồng trong khối "Việc đang
           chờ bạn". Khối đó (và cả `hanhDong`) rỗng khi `store.me` chưa
           nạp được (`hanhDongChoPhep`/`hanhDongDonChoPhep` tự chặn `!me`) —
           lồng chung nghĩa là một lỗi `portal_me` cuốn theo cả hạn báo giá,
           link PDF và khối sửa số lượng, không chỉ mất thanh nút như
           `onMounted` tự nhận. -->
      <KhoiBaoGia v-if="don?.chap_nhan?.can_dong_y" :don="don" :dang-gui="dangSuaSoLuong" @sua-so-luong="nhanSuaSoLuong" />

      <!-- 2. Việc đang chờ bạn — banner + TOÀN BỘ nút, một chỗ duy nhất. -->
      <div v-if="hanhDong.length || coTheSuaNhap" class="card mb10" style="margin-bottom: 14px">
        <div class="h3">Việc đang chờ bạn</div>
        <p v-if="quanLyDangDuyet" class="tag" style="margin-bottom: 10px">
          Bạn có thể <b>sửa số lượng duyệt</b> ở bảng bên dưới trước khi bấm Duyệt. Để trống một ô
          nghĩa là <b>giữ nguyên</b> dòng đó; gõ <b>0</b> nghĩa là <b>bỏ mặt hàng</b> khỏi đơn.
          Cột SL đề xuất khoá vĩnh viễn, không sửa được.
        </p>
        <p v-if="coTheSuaNhap" class="tag" style="margin-bottom: 10px">
          Phiếu đang ở trạng thái Nháp — bảng dưới đây chỉ để xem. Sửa số lượng, thêm/xoá dòng ở màn Đặt hàng.
        </p>
        <div class="flex" style="flex-wrap: wrap">
          <router-link v-if="coTheSuaNhap" :to="{ name: 'dat-hang', params: { ten: phieu.name } }">
            <button class="btn">Sửa nháp</button>
          </router-link>
          <button
            v-for="a in hanhDong"
            :key="a.method + '|' + a.label"
            :class="classHanhDong(a)"
            :disabled="!!dangChay"
            @click="onClickAction(a)"
          >
            {{ dangChay === a.method + '|' + a.label ? 'Đang gửi…' : a.label }}
          </button>
        </div>
      </div>

      <KhoiTienTrinh v-if="don" :milestones="don.milestones" />

      <!-- §9.1 — "phần nở ra của Tiến trình": ngay dưới `KhoiTienTrinh`,
           trước `KhoiTruyVet`. Gate `v-if="phieu || don"`, KHÔNG chỉ
           `"don"` như `KhoiTienTrinh` phía trên — ca mắt số 1 của Task 8
           ("Phiếu vừa gửi duyệt") CHƯA có đơn; copy nguyên gate của khối
           kia sẽ để đúng ca đó ra một khối RỖNG TRƠN. -->
      <KhoiDongThoiGian v-if="phieu || don" :dong="nhatKy" :dang-tai="dangTaiNhatKy" />

      <KhoiTruyVet v-if="phieu" :phieu="phieu" :mo-san="giaiDoan !== 'da_giao'" />

      <div class="grid2">
        <BangMatHang
          :phieu="phieu" :don="don"
          :quan-ly-dang-duyet="quanLyDangDuyet"
          :sl-duyet-sua="slDuyetSua" :ghi-chu-sua="ghiChuSua"
        />
        <!-- `KhoiGiaoHang`/`KhoiHoaDonTaiLieu` là template NHIỀU GỐC (không
             bọc div riêng, xem chú thích trong hai file đó) — MỘT `.card`
             chung đúng như `OrderDetail.vue` đã giữ, không phải một wrapper
             trơn: mất class này là mất nền/viền/padding của cả khối. `v-if`
             trên chính wrapper (không chỉ trên hai con) — một phiếu chưa có
             đơn (Nháp/Chờ duyệt) không được để lại một khung `.card` RỖNG
             cạnh bảng mặt hàng. -->
        <div v-if="don" class="card">
          <KhoiGiaoHang :don="don" />
          <KhoiHoaDonTaiLieu :don="don" :dang-dat-lai="dangDatLai" @dat-lai="datLai" />
        </div>
      </div>

      <div v-if="phieu?.ghi_chu" class="card mb10" style="margin-top: 14px">
        <div class="h3">Ghi chú</div>
        <p style="font-size: 13px; white-space: pre-wrap">{{ phieu.ghi_chu }}</p>
      </div>
    </template>

    <!-- Ruling coordinator (1) — hỏi lý do yêu cầu khi bấm Gửi duyệt mà
         phiếu chưa có lý do. -->
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

    <!-- Hành động có ĐÚNG MỘT ô cần nhập (sau khi đã tách phần `const`) —
         dùng chung một modal cho CẢ HAI registry, khoá theo `argModalAction`
         (mandatory #2). -->
    <ReasonModal
      :open="!!argModalAction"
      :title="argModalAction ? argModalAction.label : ''"
      :desc="argModalDesc"
      :placeholder="argModalPlaceholder"
      :min-len="argModalArg ? (argModalArg.minLen || 1) : 1"
      :submitting="!!dangChay"
      submit-label="Gửi"
      @close="argModalAction = null"
      @submit="onSubmitArgModal"
    />

    <!-- controller ruling 2026-08-16 (chép nguyên từ OrderDetail.vue, xem
         Critical 2 review Task 7a) — "Gửi lại để báo giá" đặt rate về 0 và
         đẩy đơn về "Chờ xác nhận"; cần một bước xác nhận vì khách MẤT báo
         giá đang có nếu bấm nhầm. `min-len="0"` — không bắt nhập lý do, chỉ
         cần xác nhận trong đúng khuôn modal của app. -->
    <ReasonModal
      :open="guiLaiOpen"
      title="Gửi lại để báo giá"
      desc="Số lượng dòng đã đổi sẽ về giá 0 và đơn chuyển về 'Chờ xác nhận' để Miyano báo giá lại — báo giá hiện tại của các dòng đó KHÔNG còn hiệu lực. Bấm Xác nhận để tiếp tục."
      :min-len="0"
      :submitting="dangSuaSoLuong"
      submit-label="Xác nhận gửi lại"
      @close="guiLaiOpen = false"
      @submit="guiLaiBaoGia"
    />

    <!-- Ruling coordinator (2) — "Xin sửa số lượng": khoa nhập số mong muốn
         cho từng dòng đang có trên đơn, chỉ những dòng ĐỔI thật mới gửi. -->
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
            <br /><span class="tag">Quản lý duyệt: {{ it.so_luong_duyet }} {{ it.dvt }}</span>
            <span v-if="lechVoiDon(it)" class="tag">
              · Đang có trên đơn: <b>{{ it.so_luong_tren_don }}</b> {{ it.dvt }}
            </span>
            <br v-if="laXinBoMatHang(it)" />
            <span v-if="laXinBoMatHang(it)" class="tag" style="color: var(--red)">
              Sẽ đề nghị bỏ mặt hàng này khỏi đơn
            </span>
          </span>
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
