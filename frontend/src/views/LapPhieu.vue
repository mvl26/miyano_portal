<script setup>
// Task 10 (kế hoạch gộp luồng đặt hàng, 21/08/2026) — màn **ĐẶT HÀNG**, cửa
// DUY NHẤT để đi mua đồ trên cổng. Màn này NUỐT ba cửa cũ:
//   * `/catalog` (Catalog.vue) — tìm hàng, có bộ chuyển "Theo HĐNT | Mua lẻ";
//   * `/cart`    (Cart.vue)    — giỏ hai ngăn, mỗi ngăn một nút xác nhận;
//   * `/de-xuat/lap` (chính file này, bản Task 8) — lập phiếu đề xuất.
// Chủ đầu tư nguyên văn 21/08: *"anh đang có 2 luồng là đặt hàng và lập
// phiếu, anh thấy chúng đang trùng nhau… nên bỏ lập phiếu và sửa đặt hàng
// thành flow của lập phiếu nhưng vẫn giữ là mục đặt hàng"*. Hai cửa cùng
// nghĩa "đi mua đồ" là để lộ lịch sử thi công ra mặt người dùng (QĐ-G5).
//
// HAI BƯỚC trên MỘT màn (`buoc`): (1) danh sách hàng hoá + tìm + thêm vào
// giỏ, (2) giỏ hàng + thông tin giao hàng + nút gửi. Bước giỏ GIỮ LẠI vì
// địa chỉ giao, ngày cần, lý do yêu cầu thuộc về bước đó, không thuộc bước
// tìm hàng — nhưng nó là một BƯỚC, không phải một cửa riêng trên nav.
//
// QĐ-G6 — MỘT màn, ĐỘNG TỪ đổi theo vai trò. Nhân viên khoa thấy "Gửi
// duyệt" (sinh phiếu Nháp → Chờ duyệt, quản lý duyệt). Quản lý thấy "Đặt
// hàng": MỘT lần bấm ra đơn, và `portal_order_place` vẫn sinh một phiếu đề
// xuất TỰ DUYỆT đứng sau (`_dam_bao_phieu_tu_duyet`, §5.5) nên vết truy
// không mất. Ép quản lý đi đường "gửi duyệt rồi tự duyệt" là bắt họ bấm hai
// lần cho việc vốn bấm một lần. Backend ĐÃ CÓ SẴN — không dựng lại.
//
// Nhánh quản lý CỐ Ý KHÔNG đi qua `damBaoCoTen()`/`ghiPhieu()`: nếu đi, một
// lần bấm sẽ đẻ ra HAI chứng từ (một phiếu Nháp mồ côi nổi lên đầu
// `/de-xuat`, CỘNG phiếu tự duyệt do `portal_order_place` sinh). Vì vậy nút
// "Đặt hàng" chỉ hiện khi CHƯA có phiếu nào gắn vào màn (`!tenPhieu`). Quản
// lý MỞ LẠI một phiếu Nháp có sẵn (`/dat-hang/:ten`, thường là bấm "Sửa
// nháp" từ màn chi tiết) thì màn giữ nguyên luồng phiếu — phiếu đó đã bắt
// đầu một vết duyệt, không được bỏ lửng để tạo một chứng từ thứ hai.
//
// QĐ-G8 — vượt hạn mức: CẢNH BÁO tại dòng, KHÔNG chặn, KHÔNG tự tách dòng.
// Khoa xin 100 khi còn 40 vẫn gửi được; quản lý gõ số duyệt (cơ chế đã
// chạy). Tách dòng theo hạn mức là hệ thống thay quản lý ra một quyết định
// thương mại mà nó không đủ thông tin để ra.
//
// QĐ-G9 — giỏ hiện ĐƠN GIÁ TỪNG DÒNG, KHÔNG có dòng tổng nào. Dòng hợp đồng
// hiện đơn giá; dòng chờ báo giá hiện `—`. Không có "tạm tính"/"tổng cộng"
// ở bất cứ đâu trên màn này (kể cả hộp xác nhận): tránh việc khoa nhớ một
// con số rồi đem so với hoá đơn cuối, trong khi Miyano báo giá đầy đủ ở
// bước sau.
//
// QĐ-G10 — trang đầu là HÀNG TRONG HỢP ĐỒNG CỦA CHÍNH KHÁCH, hết rồi mới
// tới danh mục chung; 10 dòng/trang, cắt trang trong SQL. Thứ tự đó do
// `portal_catalog_gop` quyết (Task 10), màn chỉ hiện đúng thứ tự nhận được
// — KHÔNG sắp xếp lại phía client.
//
// TẦNG GIÁ đọc `tang`, KHÔNG suy từ `don_gia` (Ruling P23). `tang` đến từ
// Blanket Order, `don_gia` đến từ Item Price — HAI NGUỒN KHÁC NHAU, chúng
// bất đồng được trên dữ liệu thật: một mặt hàng ĐANG trong hợp đồng nhưng
// chưa có dòng Item Price sẽ có `tang = "hop_dong"` và `don_gia = null`.
// Suy tầng từ giá sẽ dán nhãn cam "Chờ báo giá" cho nó và bắn cả câu "cả
// đơn sẽ chờ Miyano báo giá" cho một đơn không có lý do gì phải chờ. Dòng
// hợp đồng thiếu giá hiện nhãn hợp đồng KHÔNG KÈM SỐ — không bao giờ rơi
// xuống nhãn chờ báo giá.
//
// `boi_so` được TIÊU THỤ ở đây, không chỉ nhận về: ô số lượng CHẶN số sai
// bội số và nêu đúng bội số (cùng câu chữ `portal_dat_hang.kiem_boi_so()`
// dùng ở server). Không chặn ở đây thì lỗi "7 hộp của lốc 10" nổ vào mặt
// QUẢN LÝ lúc duyệt, cho một con số quản lý không hề chọn.
//
// RESUME-SỬA một phiếu Nháp đã lưu — route `/dat-hang/:ten?` (`ten` tuỳ
// chọn). Tầng của dòng đã lưu đọc từ `Portal De Xuat Mua Item.nguon_gia`
// (Select, hệ thống tự suy ở `validate()` qua `_suy_nguon_gia`) — KHÔNG
// đoán từ `don_gia`, cùng lý do Ruling P23 ở trên.
//
// TẠO LƯỜI (lazy): `de_xuat_tao_nhap()` chỉ gọi ở lần LƯU/GỬI ĐẦU TIÊN,
// không gọi lúc vào màn — gọi lúc mount sẽ chèn một phiếu Nháp rác mỗi lần
// một trong sáu tài khoản thật bấm vào mục nav rồi đổi ý.
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import { store } from '../store'
import { fmtVND, addWorkDaysISO, todayISO } from '../format'
import { useIsMobile } from '../useMobile'
import { showToast } from '../toast'
import PhanTrang from '../components/PhanTrang.vue'

const route = useRoute()
const router = useRouter()
const isMobile = useIsMobile()

// --- Vai trò -------------------------------------------------------------
// ĐỌC `la_quan_ly` (khoá riêng của `portal_me`), KHÔNG tự suy từ chuỗi
// `vai_tro === 'Quản lý'` — cùng chốt App.vue đã ghi: kế hoạch sau thêm uỷ
// quyền tạm thời, khi đó một Nhân viên khoa đang được uỷ quyền vẫn phải
// đi đúng nhánh quản lý, còn so chuỗi vai trò sẽ bỏ sót và gãy lặng lẽ.
const laQuanLy = computed(() => !!store.me?.la_quan_ly)

// --- Hồ sơ khách (best-effort) -----------------------------------------
const khoaPhongList = ref([])
async function loadKhoaPhongList() {
  try {
    khoaPhongList.value = await api.callKho('kho_khoa_phong_list', { ca_inactive: 1 })
  } catch (e) {
    // Best-effort — cùng khuôn YeuCauList.vue: chỉ mất phần dịch tên khoa.
  }
}
const tenKhoa = computed(() => {
  const ma = store.me?.khoa_phong
  if (!ma) return 'Toàn viện'
  const k = khoaPhongList.value.find((x) => x.name === ma)
  return k ? k.ten_khoa_phong : ma
})

// --- Bước hiện tại -------------------------------------------------------
// `'chon'` = danh sách hàng hoá; `'gio'` = giỏ hàng + thông tin giao hàng.
// Trạng thái CỤC BỘ, không phải route: giỏ là một BƯỚC của việc đặt hàng,
// không phải một đích đến ai đó mở cổng lên để vào xem (xem bản đồ chức
// năng, mục 2.2). Một route riêng cho nó là dựng lại đúng cái cửa vừa gộp.
const buoc = ref('chon')

// --- Phiếu đang lập -------------------------------------------------------
// `tenPhieu` rỗng cho tới lần Lưu/Gửi đầu tiên — xem ghi chú "TẠO LƯỜI".
const tenPhieu = ref('')
const phieuLoading = ref(false)
const phieuError = ref('')
// Chủ phiếu THẬT (`doc.owner` sau khi resume), để ẩn nút "Gửi duyệt"
// (owner-only ở `de_xuat_gui_duyet`) khi quản lý vào SỬA phiếu của người
// khác. Rỗng nghĩa "chưa biết/phiếu còn mới" — coi là CỦA MÌNH (đúng: một
// phiếu chưa từng lưu luôn thuộc về người đang tạo).
const phieuOwner = ref('')

// Kết quả đơn hàng của nhánh QUẢN LÝ (một lần bấm ra đơn) — giữ lại để hiện
// màn xác nhận sau khi giỏ đã bị dọn.
const donDaDat = ref(null)

// KHÔNG cần cờ "đang tạo" riêng: hai nơi gọi (`luuNhap`, `guiDuyet`) đã tự
// khoá bằng `dangLuu`/`dangGui` NGAY ĐẦU HÀM. Lỗi thật (mạng, quyền…) ném
// thẳng ra ngoài, rơi vào đúng `catch` đã có ở nơi gọi.
async function damBaoCoTen() {
  if (tenPhieu.value) return tenPhieu.value
  const res = await api.callDeXuat('de_xuat_tao_nhap')
  tenPhieu.value = res.name
  // Đồng bộ URL NGAY khi phiếu vừa được tạo: trước bản này `tenPhieu` chỉ
  // sống trong bộ nhớ — dựng phiếu 12 dòng, bấm Lưu nháp, bấm F5 → về form
  // trắng. `router.replace` (không `push`) — đây không phải một bước điều
  // hướng của người dùng, chỉ là URL bắt kịp trạng thái đã có. Kích hoạt
  // `watch(route.params.ten, …)` bên dưới; xem chốt "tenParam === tenPhieu"
  // ở đó để KHÔNG nạp đè lên dữ liệu vừa tạo.
  router.replace({ name: 'dat-hang', params: { ten: tenPhieu.value } })
  return tenPhieu.value
}

// --- Bội số quy cách (BR-O11 / Ruling P16) -------------------------------
// `boi_so` `null`/`0` = KHÔNG ràng buộc (quy ước của cả `portal_catalog_gop`
// lẫn `kiem_boi_so()`). `1` cũng không ràng buộc trên thực tế (mọi số nguyên
// đều là bội của 1) nhưng vẫn đi qua cùng phép chia, không cần nhánh riêng.
function boiSo(row) {
  const n = Number(row?.boi_so)
  return Number.isFinite(n) && n > 0 ? n : 0
}
// Câu chữ NGUYÊN VĂN của server (`portal_dat_hang.kiem_boi_so`, ma trận
// FormSpec §5 dòng NL-1.6) — khách phải đọc CÙNG MỘT CÂU dù lỗi bị bắt ở
// client hay ở server, không phải hai cách nói cho cùng một luật.
function loiBoiSo(row, so) {
  const b = boiSo(row)
  if (!b) return ''
  const n = Number(so)
  if (!Number.isFinite(n) || n % b === 0) return ''
  return `Số lượng phải là bội số của ${b}. Gần nhất: ${Math.ceil(n / b) * b}.`
}

// --- Hạn mức (QĐ-G8 — CẢNH BÁO, không chặn) ------------------------------
// `khong_gioi_han` là khoá PHÂN ĐỊNH riêng, không suy từ `remaining`: dòng
// khai `qty = 0` (không giới hạn) và dòng tầng 2 (không thuộc hợp đồng nào)
// đều có `remaining === null`, nhưng chỉ cái đầu mới là "không giới hạn".
function nhanHanMuc(row) {
  if (row.tang !== 'hop_dong') return ''
  if (row.khong_gioi_han) return 'Không giới hạn'
  if (row.remaining === null || row.remaining === undefined) return ''
  if (row.remaining <= 0) return 'Hết hạn mức'
  return `còn ${row.remaining}/${row.total}`
}
function canhBaoHanMuc(row, so) {
  if (row.tang !== 'hop_dong' || row.khong_gioi_han) return ''
  if (row.remaining === null || row.remaining === undefined) return ''
  const n = Number(so)
  if (!Number.isFinite(n) || n <= row.remaining) return ''
  return `Vượt hạn mức HĐ — còn ${row.remaining}`
}

// --- Dòng hàng đã chọn (tầng 1 + tầng 2, có mã) ---------------------------
const items = ref([])
const qtys = reactive({}) // item_code → số lượng đang chọn ở danh sách

// `so_luong_de_xuat` là Float trên doctype con và ô sửa số lượng dùng
// `step="any"` — vật tư y tế đặt lẻ (2.5 mét băng gạc) là chuyện bình
// thường. `parseInt` sẽ CẮT phần thập phân MÀ KHÔNG BÁO GÌ (2.5 → 2), đúng
// lớp lỗi "im lặng làm sai số lượng". Chỉ rơi về mặc định khi giá trị THẬT
// SỰ không hợp lệ (rỗng, chữ, ≤ 0).
function soHienTai(row) {
  const n = Number(qtys[row.item_code])
  if (Number.isFinite(n) && n > 0) return n
  return boiSo(row) || 1
}
// Bước nhảy của stepper = bội số quy cách, không phải 1: mặt hàng bán theo
// lốc 10 thì +1 luôn sai bội số ngay từ lần bấm đầu tiên.
function buoc1(row) {
  return boiSo(row) || 1
}

function themDong(row) {
  const so = soHienTai(row)
  const loi = loiBoiSo(row, so)
  if (loi) return showToast(`${row.item_code}: ${loi}`, 'error')
  const daCo = items.value.find((r) => r.item_code === row.item_code)
  if (daCo) {
    daCo.so_luong_de_xuat = (Number(daCo.so_luong_de_xuat) || 0) + so
    // Làm MỚI các trường chỉ-để-hiển-thị của dòng đã có (tầng, giá, hợp
    // đồng, hạn mức, bội số) theo kết quả tìm vừa nhận — chúng đến từ cùng
    // một endpoint và bản mới luôn đúng hơn bản cũ. Số lượng thì CỘNG, không
    // ghi đè: khách vừa nói "thêm nữa".
    Object.assign(daCo, dongTuKetQua(row), {
      so_luong_de_xuat: daCo.so_luong_de_xuat,
    })
  } else {
    items.value.push({ ...dongTuKetQua(row), so_luong_de_xuat: so })
  }
  showToast(`Đã thêm ${so} ${row.dvt || ''} · ${row.item_name} vào giỏ`)
  qtys[row.item_code] = buoc1(row)
}
function dongTuKetQua(row) {
  return {
    item_code: row.item_code,
    item_name: row.item_name,
    dvt: row.dvt,
    tang: row.tang,
    don_gia: row.don_gia,
    blanket_order: row.blanket_order,
    boi_so: row.boi_so,
    total: row.total,
    used: row.used,
    remaining: row.remaining,
    khong_gioi_han: row.khong_gioi_han,
  }
}
function xoaDong(itemCode) {
  items.value = items.value.filter((r) => r.item_code !== itemCode)
}

// Ruling P23 — nhãn tầng đọc `tang`, KHÔNG suy từ `don_gia`. Dòng hợp đồng
// CHƯA CÓ GIÁ hiện nhãn hợp đồng KHÔNG KÈM SỐ: `fmtVND(null)` trả "0 ₫"
// (`format.js` ép `Number(v || 0)`), in ra thành "Giá HĐ · 0 ₫" đọc như giá
// THẬT là 0 đồng — đúng ngược quy ước "`null` không phải `0`" của chính hợp
// đồng `portal_catalog_gop`. Không có giá thì không đoán số.
function nhanTang(row) {
  if (row.tang !== 'hop_dong') return 'Chờ báo giá'
  const co = row.don_gia !== null && row.don_gia !== undefined
  const ma = row.blanket_order ? ` · ${row.blanket_order}` : ''
  return co ? `Giá HĐ ${fmtVND(row.don_gia)}${ma}` : `Giá HĐ${ma}`
}
function classTang(row) {
  return row.tang === 'hop_dong' ? 'b-blue' : 'b-orange'
}
// Đơn giá trong giỏ (QĐ-G9) — dòng chờ báo giá hiện `—`, KHÔNG hiện 0 ₫.
function giaTrongGio(row) {
  if (row.tang !== 'hop_dong') return '—'
  if (row.don_gia === null || row.don_gia === undefined) return '—'
  return fmtVND(row.don_gia)
}

// --- Dòng đặt ngoài (tầng 3, khách gõ tay, KHÔNG có mã) -------------------
// Cùng hình dạng `Sales Order Dat Ngoai Item`: { ten_hang, dvt, so_luong,
// ghi_chu }.
const datNgoai = ref([])
const dnMoRong = ref(false)
// Nút "+ Thêm dòng" LUÔN HIỆN (brief Task 10), không chỉ khi tìm không ra:
// khách biết trước mặt hàng mình cần chưa có mã thì không việc gì phải gõ
// một từ khoá vô vọng để mở được lối gõ tay. Đẩy dòng mới khi: chưa có dòng
// nào, HOẶC dòng cuối đã có nội dung, HOẶC có sẵn một gợi ý tên hàng từ ô
// tìm (luôn muốn một dòng MANG ĐÚNG từ khoá đó).
function moDatNgoai(tenGoiY) {
  dnMoRong.value = true
  const cuoi = datNgoai.value[datNgoai.value.length - 1]
  const cuoiCoNoiDung =
    !!cuoi &&
    !!((cuoi.ten_hang || '').trim() || (cuoi.dvt || '').trim() || String(cuoi.so_luong || '').trim() || (cuoi.ghi_chu || '').trim())
  if (!datNgoai.value.length || cuoiCoNoiDung || tenGoiY) {
    datNgoai.value.push({ ten_hang: tenGoiY || '', dvt: '', so_luong: '', ghi_chu: '' })
  }
}
function themDongDatNgoai() {
  datNgoai.value.push({ ten_hang: '', dvt: '', so_luong: '', ghi_chu: '' })
}
function xoaDongDatNgoai(i) {
  datNgoai.value.splice(i, 1)
}
// Chỉ những dòng ĐÃ ĐIỀN ĐỦ mới gửi lên server. AN TOÀN dùng làm BỘ LỌC
// payload (không phải bộ soi lỗi): `kiemTraSoLuong()` chạy TRƯỚC mọi lần
// lưu/gửi và CHẶN nếu có dòng "gõ dở nhưng thiếu field".
const datNgoaiHopLe = computed(() =>
  datNgoai.value.filter(
    (d) => (d.ten_hang || '').trim() && (d.dvt || '').trim() && Number(d.so_luong) > 0
  )
)

// Cảnh báo phải hiện TRƯỚC khi bấm, không phải sau. Cố ý dùng
// `datNgoai.length` (MỌI dòng, kể cả đang gõ dở): một dòng vừa mở ra đã LÀ
// tín hiệu "đơn này sắp có hàng chờ báo giá".
const coHangChoBaoGia = computed(
  () => items.value.some((r) => r.tang === 'cho_bao_gia') || datNgoai.value.length > 0
)
const tongDongGio = computed(() => items.value.length + datNgoai.value.length)

// --- Danh sách hàng hoá (một ô tìm, ba tầng) -----------------------------
const search = ref('')
const searchResults = ref([])
const searchLoading = ref(false)
const searchError = ref('')
const searchTong = ref(0)
const searchTrang = ref(1)
// 10 dòng/trang (chủ đầu tư chốt 21/08). `PhanTrang.vue` có thể ghi đè bằng
// lựa chọn đã lưu của chính khách ở màn khác — đó là hợp đồng dùng chung của
// component phân trang toàn cổng, không phải chỗ để phá lệ.
const searchSoDong = ref(10)
let searchTimer = null

async function timKiem() {
  searchLoading.value = true
  searchError.value = ''
  try {
    // `portal_catalog_gop` sống ở api/portal.py — gọi qua `api.call`, KHÔNG
    // qua `callDeXuat`. Lưới `test_de_xuat_action_registry.py` canh CẢ HAI
    // đường gọi này (Ruling P13).
    const res = await api.call('portal_catalog_gop', {
      tu_khoa: search.value.trim() || undefined,
      start: (searchTrang.value - 1) * searchSoDong.value,
      limit: searchSoDong.value,
    })
    searchResults.value = res.rows || []
    searchTong.value = res.tong || 0
    // Gieo sẵn số lượng mặc định = ĐÚNG MỘT LÔ (bội số), không phải 1 —
    // thiếu dòng này, "mặc định" trở thành một quy ước VÔ HÌNH chỉ đúng
    // trong code (`soHienTai()`), không đúng trên màn hình.
    searchResults.value.forEach((r) => {
      if (!(r.item_code in qtys)) qtys[r.item_code] = buoc1(r)
    })
  } catch (e) {
    searchResults.value = []
    searchTong.value = 0
    searchError.value = e.message || 'Không tìm được vật tư lúc này.'
  } finally {
    searchLoading.value = false
  }
}

// Coi LỖI TÌM KIẾM cùng nhóm với "không có kết quả": cả hai đều phải mở
// đường cho khách gõ tay, không được để một lỗi mạng khoá luôn lối thoát.
const timKhongRa = computed(
  () => !searchLoading.value && (!!searchError.value || searchResults.value.length === 0)
)

watch(search, () => {
  clearTimeout(searchTimer)
  searchTrang.value = 1
  searchTimer = setTimeout(timKiem, 300)
})
watch([searchTrang, searchSoDong], timKiem)
onBeforeUnmount(() => clearTimeout(searchTimer))

// --- Thông tin đơn hàng + giao hàng --------------------------------------
const lyDoYeuCau = ref('')
const ghiChu = ref('')
const ngayCan = ref(addWorkDaysISO(2)) // gợi ý hợp lý, không bắt buộc
const ngayToiThieu = todayISO()
const diaChiGiao = ref('')
const diaChiOptions = computed(() => store.me?.addresses || [])

// --- Nạp một phiếu Nháp có sẵn (route `/dat-hang/:ten`) -------------------
function resetState() {
  tenPhieu.value = ''
  phieuOwner.value = ''
  // `phieuError` PHẢI được dọn ở đây: mở `/dat-hang/DXM-xxx` gặp lỗi → bấm
  // "Đặt hàng" ở nav (route về `/dat-hang`, không `:ten`) → nếu để nguyên,
  // template ưu tiên nhánh lỗi và form KHÔNG BAO GIỜ hiện. Đó là trạng thái
  // LỖI CỦA MỘT PHIẾU CŨ, không mang nghĩa gì cho một phiếu MỚI.
  phieuError.value = ''
  items.value = []
  datNgoai.value = []
  dnMoRong.value = false
  lyDoYeuCau.value = ''
  ghiChu.value = ''
  ngayCan.value = addWorkDaysISO(2)
  diaChiGiao.value = (store.me?.addresses || [])[0]?.name || ''
  donDaDat.value = null
  buoc.value = 'chon'
}

// Đổ dữ liệu một phiếu Nháp đã lưu (`de_xuat_chi_tiet`) vào form.
//
// `nguon_gia` (Select trên `Portal De Xuat Mua Item`, hệ thống tự suy ở
// `validate()`, ĐỌC-CHỈ) là nguồn của TẦNG — `"Hợp đồng"` → tầng 1, mọi giá
// trị khác (kể cả rỗng) → tầng 2. KHÔNG đoán tầng từ `don_gia` (Ruling P23).
// `boi_so` đi kèm từng dòng (Task 10, `de_xuat_chi_tiet`) để ô số lượng ở
// giỏ vẫn chặn được bội số cho một phiếu mở lại — dòng này không đi qua ô
// tìm kiếm nên không có cách nào khác biết bội số.
function napTuPhieu(d) {
  tenPhieu.value = d.name
  phieuOwner.value = d.owner || ''
  items.value = (d.items || []).map((it) => ({
    item_code: it.item_code,
    item_name: it.item_name,
    dvt: it.dvt,
    so_luong_de_xuat: it.so_luong_de_xuat,
    tang: it.nguon_gia === 'Hợp đồng' ? 'hop_dong' : 'cho_bao_gia',
    don_gia: it.don_gia,
    blanket_order: it.blanket_order || null,
    boi_so: it.boi_so ?? null,
    // Hạn mức KHÔNG được đóng băng trên dòng phiếu (nó đổi mỗi khi một khoa
    // khác đặt hàng) — phiếu mở lại không mang theo con số nào để hiện, và
    // BỊA một con số cũ còn tệ hơn không hiện gì. Dòng vào giỏ lại từ ô tìm
    // kiếm sẽ có ngay hạn mức mới nhất (xem `themDong`).
    total: null, used: null, remaining: null, khong_gioi_han: false,
  }))
  datNgoai.value = (d.dat_ngoai || []).map((dn) => ({
    ten_hang: dn.ten_hang,
    dvt: dn.dvt,
    so_luong: dn.so_luong,
    ghi_chu: dn.ghi_chu || '',
  }))
  dnMoRong.value = datNgoai.value.length > 0
  lyDoYeuCau.value = d.ly_do_yeu_cau || ''
  ghiChu.value = d.ghi_chu || ''
  ngayCan.value = d.ngay_can || ''
  diaChiGiao.value = d.dia_chi_giao || (store.me?.addresses || [])[0]?.name || ''
  // Mở thẳng ở bước GIỎ: người dùng quay lại một phiếu dở dang là để xem/sửa
  // những gì đã có trong đó, không phải để bắt đầu tìm hàng lại từ đầu.
  buoc.value = 'gio'
}

// `de_xuat_gui_duyet` là OWNER-ONLY tường minh phía server (khác
// `de_xuat_luu_nhap`/`de_xuat_xoa_nhap`, owner HOẶC quản lý). Một quản lý
// vào SỬA phiếu của nhân viên lưu được nhưng KHÔNG gửi duyệt được — bày nút
// ra cho họ là show một nút cho thao tác họ không có quyền làm. Hide, don't
// disable. `!phieuOwner` (phiếu mới) coi là CỦA MÌNH: `de_xuat_tao_nhap()`
// luôn đặt owner = phiên đang gọi.
const laChuPhieu = computed(() => !phieuOwner.value || phieuOwner.value === store.me?.user)

// QĐ-G6 — MỘT nút chính, ĐỘNG TỪ đổi theo vai trò. Quản lý đi đường đặt
// thẳng CHỈ khi màn chưa gắn phiếu nào (xem ghi chú đầu file).
const dangDatThang = computed(() => laQuanLy.value && !tenPhieu.value)
const nhanNutChinh = computed(() => (dangDatThang.value ? 'Đặt hàng' : 'Gửi duyệt'))

// Điều phối theo `route.params.ten`. PHẢI là `watch`, không phải đọc một
// lần ở `onMounted`: Vue Router TÁI DÙNG cùng một instance khi chỉ tham số
// đổi, nên thiếu `watch` thì bấm "Sửa" từ phiếu này sang phiếu khác sẽ giữ
// nguyên dữ liệu của phiếu TRƯỚC trên màn.
async function taiHoacKhoiTao() {
  const tenParam = route.params.ten
  if (!tenParam) {
    resetState()
    return
  }
  // `damBaoCoTen()` tự `router.replace` sang `/dat-hang/<ten>` NGAY khi tạo
  // phiếu. Đổi route đó kích hoạt `watch` này y hệt một điều hướng thật —
  // thiếu dòng chặn dưới đây, hàm sẽ NẠP LẠI phiếu vừa tạo (còn rỗng, vì
  // `de_xuat_luu_nhap` CHƯA kịp chạy) ĐÈ LÊN đúng những dòng khách vừa gõ.
  if (tenParam === tenPhieu.value) return
  phieuLoading.value = true
  phieuError.value = ''
  try {
    const d = await api.callDeXuat('de_xuat_chi_tiet', { ten: tenParam })
    if (d.trang_thai !== 'Nháp') {
      // TỪ CHỐI mở một phiếu không phải Nháp ở màn sửa này. Server cũng ném
      // lỗi cho ca này, nhưng người dùng không nên phải CHẠM lỗi đó mới
      // biết — đưa thẳng về màn chi tiết chỉ đọc kèm một câu giải thích.
      showToast(
        `Phiếu ${d.ma_de_xuat || tenParam} không còn ở trạng thái Nháp — không sửa được ở đây nữa.`,
        'error'
      )
      router.replace({ name: 'de-xuat-detail', params: { ten: tenParam }, query: { tu: 'yeu-cau' } })
      return
    }
    napTuPhieu(d)
  } catch (e) {
    phieuError.value = e.message || 'Không tải được phiếu nháp.'
  } finally {
    phieuLoading.value = false
  }
}
watch(() => route.params.ten, taiHoacKhoiTao, { immediate: true })

// --- Kiểm số lượng trước khi lưu/gửi/đặt ---------------------------------
// Phiếu đang lập không có khái niệm "ô trống = giữ nguyên" — mỗi dòng gửi
// lên PHẢI mang một số lượng dương tường minh, nên ô trống/không hợp lệ ở
// màn này bị CHẶN (không phải lặng lẽ hạ về 0), đặt tên đúng dòng.
//
// Bội số kiểm ở ĐÂY nữa, không chỉ ở ô số lượng của danh sách: khách gõ
// thẳng 7 vào ô số lượng TRONG GIỎ thì chốt ở bước thêm dòng không nhìn
// thấy, và con số sai lại đi tới tận màn duyệt của quản lý.
function kiemTraSoLuong() {
  for (const r of items.value) {
    const n = Number(r.so_luong_de_xuat)
    if (!Number.isFinite(n) || n <= 0) {
      return `Mặt hàng "${r.item_code}" chưa có số lượng hợp lệ (phải lớn hơn 0).`
    }
    const loi = loiBoiSo(r, n)
    if (loi) return `Mặt hàng "${r.item_code}": ${loi}`
  }
  // Một dòng đặt ngoài ĐÃ ĐỘNG TỚI (bất kỳ ô nào khác rỗng) mà CHƯA ĐỦ CẢ
  // BA field bắt buộc phải CHẶN, nêu đúng field còn thiếu — nếu không nó sẽ
  // bị `datNgoaiHopLe` LẶNG LẼ lọc khỏi payload và mặt hàng biến mất khỏi
  // đơn mà không một chỗ nào nói cho khách biết. Dòng HOÀN TOÀN TRỐNG (mới
  // bấm "+ Thêm dòng") vẫn được bỏ qua — đó không phải một mặt hàng khách
  // định gửi, ép gõ nó mới cho lưu được là sai chiều.
  for (const d of datNgoai.value) {
    const tenHang = (d.ten_hang || '').trim()
    const dvt = (d.dvt || '').trim()
    const soLuongChuoi = (d.so_luong === null || d.so_luong === undefined) ? '' : String(d.so_luong).trim()
    const ghiChuDong = (d.ghi_chu || '').trim()
    const daDongTay = tenHang || dvt || soLuongChuoi || ghiChuDong
    if (!daDongTay) continue
    const con = Number(soLuongChuoi)
    const thieu = []
    if (!tenHang) thieu.push('tên hàng')
    if (!dvt) thieu.push('ĐVT')
    if (!soLuongChuoi || !Number.isFinite(con) || con <= 0) thieu.push('số lượng hợp lệ')
    if (thieu.length) {
      return `Dòng đặt ngoài "${tenHang || '(chưa đặt tên)'}" còn thiếu ${thieu.join(', ')} — hoàn tất hoặc xoá dòng này trước khi gửi.`
    }
  }
  return ''
}

const itemsPayload = computed(() =>
  items.value.map((r) => ({
    item_code: r.item_code,
    item_name: r.item_name,
    dvt: r.dvt,
    so_luong_de_xuat: Number(r.so_luong_de_xuat) || 0,
  }))
)
// Ép kiểu số TRƯỚC khi gửi — `d.so_luong` sống trong ô nhập không `.number`
// (giữ chuỗi thô, để một ô đang gõ dở không lặng lẽ hoá thành 0).
const datNgoaiPayload = computed(() =>
  datNgoaiHopLe.value.map((d) => ({
    ten_hang: d.ten_hang,
    dvt: d.dvt,
    so_luong: Number(d.so_luong) || 0,
    ghi_chu: d.ghi_chu || '',
  }))
)

async function ghiPhieu(ten) {
  await api.callDeXuat('de_xuat_luu_nhap', {
    ten,
    items: JSON.stringify(itemsPayload.value),
    dat_ngoai: JSON.stringify(datNgoaiPayload.value),
    // `?? ''` — KHÔNG `|| null`: `de_xuat_luu_nhap` coi `None`/`null` là
    // "đừng đụng vào field này", nên gửi `null` cho một ô VỪA BỊ XOÁ TRẮNG
    // sẽ làm giá trị cũ SỐNG LẠI sau khi lưu.
    ngay_can: ngayCan.value ?? '',
    dia_chi_giao: diaChiGiao.value ?? '',
    ghi_chu: ghiChu.value ?? '',
    ly_do_yeu_cau: lyDoYeuCau.value ?? '',
  })
}

// --- Hành động ------------------------------------------------------------
const dangLuu = ref(false)
const dangGui = ref(false)
const dangXoa = ref(false)

function gioTrong() {
  return !items.value.length && !datNgoaiHopLe.value.length
}

async function luuNhap() {
  if (dangLuu.value || dangGui.value) return
  // Lưu nháp KHÔNG chấp nhận 0 dòng: một phiếu Nháp HOÀN TOÀN RỖNG nổi lên
  // đầu `/de-xuat` (sắp `modified desc`) là đúng lớp rác mà "tạo lười" đã
  // cố tránh, chỉ đi vòng qua cửa Lưu thay vì cửa mount.
  if (gioTrong()) {
    return showToast('Giỏ chưa có mặt hàng nào — thêm ít nhất một dòng trước khi lưu.', 'error')
  }
  const loi = kiemTraSoLuong()
  if (loi) return showToast(loi, 'error')
  dangLuu.value = true
  try {
    const ten = await damBaoCoTen()
    await ghiPhieu(ten)
    showToast('Đã lưu nháp.')
  } catch (e) {
    showToast(e.message || 'Không lưu được phiếu.', 'error')
  } finally {
    dangLuu.value = false
  }
}

async function guiDuyet() {
  if (dangLuu.value || dangGui.value) return
  if (gioTrong()) {
    return showToast('Giỏ chưa có mặt hàng nào — thêm ít nhất một dòng trước khi gửi duyệt.', 'error')
  }
  if (!lyDoYeuCau.value.trim()) {
    return showToast('Vui lòng nhập lý do yêu cầu trước khi gửi duyệt.', 'error')
  }
  const loi = kiemTraSoLuong()
  if (loi) return showToast(loi, 'error')
  dangGui.value = true
  try {
    const ten = await damBaoCoTen()
    await ghiPhieu(ten)
    const res = await api.callDeXuat('de_xuat_gui_duyet', { ten })
    showToast(`Đã gửi duyệt — mã phiếu ${res.ma_de_xuat}.`)
    router.push({ name: 'de-xuat-detail', params: { ten }, query: { tu: 'yeu-cau' } })
  } catch (e) {
    showToast(e.message || 'Không gửi được phiếu.', 'error')
  } finally {
    dangGui.value = false
  }
}

// QĐ-G6, nhánh QUẢN LÝ — MỘT lần bấm ra đơn. `portal_order_place` tự sinh
// phiếu đề xuất TỰ DUYỆT đứng sau (§5.5), nên KHÔNG tạo/lưu phiếu Nháp ở
// đây: làm cả hai sẽ đẻ ra hai chứng từ cho một lần bấm.
//
// KHÔNG truyền `contract`: từ Task 4 hàm dựng đơn quyết định theo TỪNG DÒNG
// (mỗi dòng tự tìm hợp đồng của nó trong các hợp đồng CỦA CHÍNH khách), nên
// một giỏ trộn hợp đồng + chờ báo giá đi qua đúng một lời gọi. KHÔNG truyền
// `mode` vì tham số đó đã hết tác dụng từ Task 4.
async function datHang() {
  if (dangGui.value) return
  if (gioTrong()) {
    return showToast('Giỏ chưa có mặt hàng nào — thêm ít nhất một dòng trước khi đặt.', 'error')
  }
  const loi = kiemTraSoLuong()
  if (loi) return showToast(loi, 'error')
  dangGui.value = true
  try {
    // BR-O12 — sinh mã chống trùng MỘT LẦN và giữ nguyên cho tới khi đơn tạo
    // xong: bấm lại phải gửi CÙNG một mã thì server mới nhận ra và trả về
    // đơn cũ thay vì tạo đơn thứ hai.
    store.batDauDatHang()
    const res = await api.call('portal_order_place', {
      items: JSON.stringify(
        items.value.map((r) => ({
          item_code: r.item_code,
          qty: Number(r.so_luong_de_xuat) || 0,
        }))
      ),
      dat_ngoai: JSON.stringify(datNgoaiPayload.value),
      delivery_date: ngayCan.value || null,
      note: ghiChu.value || null,
      address: diaChiGiao.value || null,
      request_id: store.requestId,
    })
    if (res.da_ton_tai) showToast(`Đơn ${res.sales_order} đã được tạo trước đó.`)
    donDaDat.value = res
    store.ketThucDatHang()
    items.value = []
    datNgoai.value = []
    dnMoRong.value = false
  } catch (e) {
    // Lỗi CÓ CẤU TRÚC theo từng dòng (`e.loi`, vd. hết hạn mức/sai bội số)
    // — nêu ĐỦ từng dòng, không nuốt còn một câu chung chung.
    if (e.loi && e.loi.length) {
      showToast(
        'Chưa gửi được đơn: ' + e.loi.map((d) => d.thong_diep).join(' · '),
        'error'
      )
    } else {
      showToast(e.message || 'Không đặt được hàng.', 'error')
    }
  } finally {
    dangGui.value = false
  }
}

function nutChinh() {
  return dangDatThang.value ? datHang() : guiDuyet()
}

async function xoaPhieu() {
  if (!tenPhieu.value || dangXoa.value) return
  if (!window.confirm('Xoá phiếu này? Dữ liệu sẽ bị xoá VĨNH VIỄN khỏi hệ thống — KHÔNG thể khôi phục.')) return
  dangXoa.value = true
  try {
    await api.callDeXuat('de_xuat_xoa_nhap', { ten: tenPhieu.value })
    showToast('Đã xoá phiếu.')
    router.push({ name: 'yeu-cau' })
  } catch (e) {
    showToast(e.message || 'Không xoá được phiếu.', 'error')
  } finally {
    dangXoa.value = false
  }
}

onMounted(async () => {
  loadKhoaPhongList()
  try {
    if (!store.me) store.setMe(await api.call('portal_me'))
    if (!diaChiGiao.value) diaChiGiao.value = (store.me?.addresses || [])[0]?.name || ''
  } catch (e) {
    // Best-effort — thiếu `me` chỉ mất tên khoa/địa chỉ mặc định, không chặn
    // cả màn (khách vẫn tìm và chọn hàng được).
  }
  timKiem()
})
</script>

<template>
  <div>
    <div class="topbar">
      <div>
        <h2>Đặt hàng</h2>
        <div class="sub">{{ tenKhoa }}<span v-if="tenPhieu"> · Nháp {{ tenPhieu }}</span></div>
      </div>
    </div>

    <div v-if="phieuLoading" class="loading">Đang tải phiếu…</div>
    <div v-else-if="phieuError" class="empty">{{ phieuError }}</div>

    <template v-else>
    <!-- Hai BƯỚC của cùng một việc, không phải hai cửa (QĐ-G5). -->
    <div class="tabs">
      <button :class="{ on: buoc === 'chon' }" @click="buoc = 'chon'">1 · Chọn hàng</button>
      <button :class="{ on: buoc === 'gio' }" @click="buoc = 'gio'">
        2 · Giỏ hàng ({{ tongDongGio }})
      </button>
    </div>

    <!-- ==================== BƯỚC 1 — DANH SÁCH HÀNG HOÁ ==================== -->
    <template v-if="buoc === 'chon'">
      <div class="card mb10">
        <div class="field" style="margin-bottom: 8px">
          <label>Tìm vật tư</label>
          <input v-model="search" placeholder="Nhập mã hoặc tên mặt hàng..." />
        </div>
        <!-- LUÔN HIỆN (brief Task 10): khách biết trước hàng mình cần chưa
             có mã thì không phải gõ một từ khoá vô vọng để mở được lối này. -->
        <button class="btn-o btn-sm" @click="moDatNgoai(search.trim())">
          + Thêm dòng — hàng chưa có trong hệ thống
        </button>
      </div>

      <div v-if="searchError" class="note note-r" style="margin-bottom: 12px">
        {{ searchError }}
      </div>
      <div v-if="searchLoading" class="loading">Đang tải danh mục…</div>

      <template v-else-if="searchResults.length">
        <div v-if="!isMobile" class="card mb10" style="padding: 0; overflow-x: auto">
          <table>
            <thead>
              <tr>
                <th>Mã</th><th>Tên mặt hàng</th><th>ĐVT</th>
                <th>Tình trạng</th><th>Tầng giá</th><th style="min-width: 130px">Hạn mức</th>
                <th style="width: 130px">Số lượng</th><th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in searchResults" :key="r.item_code">
                <td><b>{{ r.item_code }}</b></td>
                <td>{{ r.item_name }}</td>
                <td>{{ r.dvt }}</td>
                <td>
                  <span class="badge" :class="r.trang_thai_hang === 'Còn hàng' ? 'b-green' : 'b-gray'">
                    {{ r.trang_thai_hang }}
                  </span>
                </td>
                <td><span class="badge" :class="classTang(r)">{{ nhanTang(r) }}</span></td>
                <!-- Kiểu hạn mức đọc từ DỮ LIỆU (`khong_gioi_han`/
                     `remaining`), KHÔNG so chuỗi với nhãn: một lần biên tập
                     lại câu chữ trong `nhanHanMuc()` mà so chuỗi thì badge
                     lặng lẽ rơi về kiểu chung, không ai thấy gì hỏng. -->
                <td>
                  <span v-if="!nhanHanMuc(r)" class="tag">—</span>
                  <span v-else-if="r.khong_gioi_han" class="tag tag-kgh">{{ nhanHanMuc(r) }}</span>
                  <span v-else-if="r.remaining <= 0" class="tag tag-het">{{ nhanHanMuc(r) }}</span>
                  <span v-else class="tag">{{ nhanHanMuc(r) }} {{ r.dvt }}</span>
                </td>
                <td>
                  <div class="step">
                    <button @click="qtys[r.item_code] = Math.max(buoc1(r), soHienTai(r) - buoc1(r))">−</button>
                    <input v-model="qtys[r.item_code]" inputmode="decimal" />
                    <button @click="qtys[r.item_code] = soHienTai(r) + buoc1(r)">+</button>
                  </div>
                  <!-- QĐ-G8: vượt hạn mức là CẢNH BÁO, không phải khoá nút. -->
                  <div v-if="canhBaoHanMuc(r, soHienTai(r))" class="warn">
                    {{ canhBaoHanMuc(r, soHienTai(r)) }}
                  </div>
                  <div v-if="loiBoiSo(r, soHienTai(r))" class="warn">{{ loiBoiSo(r, soHienTai(r)) }}</div>
                  <div v-else-if="boiSo(r) > 1" class="muted sm">bội số {{ boiSo(r) }}</div>
                </td>
                <td><button class="btn btn-sm" @click="themDong(r)">+ Giỏ</button></td>
              </tr>
            </tbody>
          </table>
        </div>
        <template v-else>
          <div v-for="r in searchResults" :key="r.item_code" class="card item mb10">
            <div class="nm">{{ r.item_code }} · {{ r.item_name }}</div>
            <div class="tag" style="margin: 2px 0 6px">{{ r.dvt }}</div>
            <div class="sb" style="flex-wrap: wrap; gap: 6px">
              <span class="badge" :class="r.trang_thai_hang === 'Còn hàng' ? 'b-green' : 'b-gray'">
                {{ r.trang_thai_hang }}
              </span>
              <span class="badge" :class="classTang(r)">{{ nhanTang(r) }}</span>
            </div>
            <div v-if="nhanHanMuc(r)" class="tag" style="margin-top: 6px">
              Hạn mức: {{ nhanHanMuc(r) }}
            </div>
            <div class="sb" style="margin-top: 10px">
              <div class="step">
                <button @click="qtys[r.item_code] = Math.max(buoc1(r), soHienTai(r) - buoc1(r))">−</button>
                <input v-model="qtys[r.item_code]" inputmode="decimal" />
                <button @click="qtys[r.item_code] = soHienTai(r) + buoc1(r)">+</button>
              </div>
              <button class="btn btn-sm" @click="themDong(r)">+ Giỏ</button>
            </div>
            <div v-if="canhBaoHanMuc(r, soHienTai(r))" class="warn">
              {{ canhBaoHanMuc(r, soHienTai(r)) }}
            </div>
            <div v-if="loiBoiSo(r, soHienTai(r))" class="warn">{{ loiBoiSo(r, soHienTai(r)) }}</div>
            <div v-else-if="boiSo(r) > 1" class="muted sm">Đặt theo bội số {{ boiSo(r) }} {{ r.dvt }}</div>
          </div>
        </template>
        <PhanTrang v-model:trang="searchTrang" v-model:so-dong="searchSoDong" :tong="searchTong" />
      </template>

      <div v-if="timKhongRa && !searchError" class="card mb10 tag">
        Không có mặt hàng khớp tìm kiếm trong hệ thống — dùng nút
        <b>“+ Thêm dòng”</b> ở trên để Miyano tìm nguồn và báo giá.
      </div>

      <!-- Hàng chưa có mã (tầng 3) — khách gõ tay, không bao giờ lẫn vào
           `items`. Ô nhập nằm ở BƯỚC CHỌN vì đây là chỗ khách "thêm hàng";
           giỏ chỉ liệt kê lại. -->
      <template v-if="dnMoRong || datNgoai.length">
        <div class="card mb10">
          <div class="sb" style="cursor: pointer" @click="dnMoRong = !dnMoRong">
            <b>Hàng chưa có trong hệ thống — Miyano sẽ tìm nguồn và báo giá</b>
            <span>{{ dnMoRong ? '▾' : '▸' }}</span>
          </div>
          <template v-if="dnMoRong">
            <div v-for="(d, i) in datNgoai" :key="i" class="card mb10" style="margin-top: 10px">
              <div class="field">
                <label>Tên hàng <span class="req">*</span></label>
                <input v-model="d.ten_hang" placeholder="VD: Găng tay nitrile không bột size M" />
              </div>
              <div class="sb" style="gap: 8px">
                <div class="field" style="flex: 1">
                  <label>ĐVT <span class="req">*</span></label>
                  <input v-model="d.dvt" placeholder="Hộp" />
                </div>
                <div class="field" style="flex: 1">
                  <label>Số lượng <span class="req">*</span></label>
                  <!-- `decimal`, không `numeric`: bàn phím ảo `numeric` KHÔNG
                       có dấu thập phân, khách trên điện thoại không gõ nổi
                       2.5 mét băng gạc. -->
                  <input v-model="d.so_luong" inputmode="decimal" />
                </div>
              </div>
              <div class="field">
                <label>Ghi chú</label>
                <input v-model="d.ghi_chu" placeholder="Quy cách, hãng mong muốn..." />
              </div>
              <button class="btn-o btn-sm" @click="xoaDongDatNgoai(i)">Xoá dòng</button>
            </div>
            <button class="btn-o" style="width: 100%" @click="themDongDatNgoai">+ Thêm dòng</button>
          </template>
        </div>
      </template>

      <div class="card mb10">
        <button class="btn" style="width: 100%" @click="buoc = 'gio'">
          Xem giỏ hàng ({{ tongDongGio }}) →
        </button>
      </div>
    </template>

    <!-- ==================== BƯỚC 2 — GIỎ HÀNG ==================== -->
    <template v-else>
      <!-- Nhánh quản lý: xác nhận đơn vừa đặt. KHÔNG có con số tổng nào ở
           đây (QĐ-G9) — Miyano báo giá đầy đủ ở bước sau. -->
      <div v-if="donDaDat" class="card success">
        <div style="font-size: 52px">✅</div>
        <h2 style="margin: 10px 0 6px">Đã đặt hàng!</h2>
        <p style="margin: 14px 0; font-size: 17px">
          Mã đơn: <b style="color: var(--blue)">{{ donDaDat.sales_order }}</b>
          <span class="badge b-gray">Chờ xác nhận</span>
        </p>
        <p class="tag">
          Phiếu đề xuất tự duyệt đứng sau đơn:
          <b>{{ donDaDat.de_xuat || '—' }}</b>
        </p>
        <div class="flex" style="justify-content: center; margin-top: 20px; flex-wrap: wrap">
          <button class="btn-o" @click="router.push({ name: 'yeu-cau' })">Xem đơn hàng</button>
          <button class="btn" @click="donDaDat = null; buoc = 'chon'">Tiếp tục đặt hàng</button>
        </div>
      </div>

      <template v-else>
        <div class="card mb10" style="padding: 0; overflow-x: auto">
          <div class="h3" style="padding: 12px 14px 0">Thông tin đơn hàng</div>
          <table>
            <thead>
              <tr>
                <th>MÃ</th><th>TÊN VẬT TƯ</th><th>ĐVT</th>
                <th style="width: 150px">SL</th><th>MÃ HĐ KHUNG</th>
                <th class="right">ĐƠN GIÁ</th><th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="r in items" :key="r.item_code">
                <td><b>{{ r.item_code }}</b></td>
                <td>
                  {{ r.item_name }}
                  <div><span class="badge" :class="classTang(r)">{{ nhanTang(r) }}</span></div>
                </td>
                <td>{{ r.dvt }}</td>
                <td>
                  <!-- KHÔNG `min="1"`: mâu thuẫn với chính quyết định "số
                       lượng có thể lẻ" (0.5, 2.5 mét băng gạc) — `min` gắn cờ
                       `:invalid` cho MỌI số dưới 1, kể cả số lẻ hợp lệ. Chốt
                       thật ở `kiemTraSoLuong()`, chạy trước mọi lần gửi. -->
                  <input
                    type="number" step="any"
                    v-model="r.so_luong_de_xuat"
                    :aria-label="`Số lượng cho ${r.item_code}`"
                    style="width: 90px; text-align: right"
                  />
                  <div v-if="canhBaoHanMuc(r, r.so_luong_de_xuat)" class="warn">
                    {{ canhBaoHanMuc(r, r.so_luong_de_xuat) }}
                  </div>
                  <div v-if="loiBoiSo(r, r.so_luong_de_xuat)" class="warn">
                    {{ loiBoiSo(r, r.so_luong_de_xuat) }}
                  </div>
                  <div v-else-if="boiSo(r) > 1" class="muted sm">bội số {{ boiSo(r) }}</div>
                </td>
                <td>{{ r.blanket_order || '—' }}</td>
                <!-- QĐ-G9 — ĐƠN GIÁ TỪNG DÒNG, không có cột thành tiền và
                     KHÔNG có dòng tổng ở cuối bảng. -->
                <td class="right">{{ giaTrongGio(r) }}</td>
                <td><button class="btn-o btn-sm btn-danger" @click="xoaDong(r.item_code)">Xoá</button></td>
              </tr>
              <tr v-for="(d, i) in datNgoai" :key="'dn' + i">
                <td class="tag">—</td>
                <td>
                  {{ d.ten_hang || '(chưa đặt tên)' }}
                  <div><span class="badge b-orange">Chờ báo giá</span></div>
                </td>
                <td>{{ d.dvt || '—' }}</td>
                <td>{{ d.so_luong || '—' }}</td>
                <td>—</td>
                <td class="right">—</td>
                <td><button class="btn-o btn-sm btn-danger" @click="xoaDongDatNgoai(i)">Xoá</button></td>
              </tr>
              <tr v-if="!tongDongGio">
                <td colspan="7" class="tag">
                  Giỏ chưa có mặt hàng nào — quay lại bước <b>Chọn hàng</b> để thêm.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="datNgoai.length" class="tag" style="margin: -4px 0 12px 4px">
          Sửa dòng hàng chưa có mã ở bước <a href="#" @click.prevent="buoc = 'chon'">Chọn hàng</a>.
        </div>

        <div class="card mb10">
          <div class="h3">Thông tin giao hàng</div>
          <!-- Lý do yêu cầu là dữ liệu của LUỒNG DUYỆT (quản lý đọc trước khi
               duyệt). Đường đặt thẳng của quản lý không có ai duyệt nên
               `portal_order_place` tự ghi lý do "đặt trực tiếp, tự động
               duyệt" — hỏi lại khách một ô mà server sẽ bỏ qua là hỏi một
               câu không dùng vào việc gì. -->
          <div v-if="!dangDatThang" class="field">
            <label>Lý do yêu cầu <span class="req">*</span></label>
            <textarea rows="2" v-model="lyDoYeuCau" placeholder="VD: Khoa cần bổ sung vật tư tiêu hao cho quý này..."></textarea>
          </div>
          <div class="sb" style="gap: 8px">
            <div class="field" style="flex: 1">
              <label>Ngày giao mong muốn</label>
              <input type="date" v-model="ngayCan" :min="ngayToiThieu" />
            </div>
            <div class="field" style="flex: 1">
              <label>Địa chỉ giao hàng</label>
              <select v-model="diaChiGiao">
                <option value="">—</option>
                <option v-for="a in diaChiOptions" :key="a.name" :value="a.name">{{ a.display }}</option>
              </select>
            </div>
          </div>
          <div class="field" style="margin-bottom: 0">
            <label>Ghi chú</label>
            <textarea rows="2" v-model="ghiChu" placeholder="Yêu cầu giao giờ hành chính..."></textarea>
          </div>
        </div>

        <div class="card mb10">
          <div v-if="coHangChoBaoGia" class="note note-b" style="margin-bottom: 12px">
            Đơn có hàng chờ báo giá — cả đơn sẽ chờ Miyano báo giá trước khi giao.
          </div>
          <div class="flex" style="flex-wrap: wrap; gap: 8px">
            <button class="btn-o" @click="buoc = 'chon'">‹ Chọn thêm hàng</button>
            <!-- Hide, don't disable — nút "Lưu nháp"/"Gửi duyệt" thuộc luồng
                 phiếu; quản lý đặt thẳng không có phiếu Nháp nào để lưu. -->
            <button v-if="!dangDatThang" class="btn-o" :disabled="dangLuu || dangGui" @click="luuNhap">
              {{ dangLuu ? 'Đang lưu…' : 'Lưu nháp' }}
            </button>
            <!-- QĐ-G6 — MỘT nút, ĐỘNG TỪ đổi theo vai trò. `de_xuat_gui_duyet`
                 là OWNER-ONLY phía server nên nhánh phiếu chỉ hiện nút cho chủ
                 phiếu; nhánh đặt thẳng của quản lý không có ràng buộc đó. -->
            <button
              v-if="dangDatThang || laChuPhieu"
              class="btn"
              :disabled="dangLuu || dangGui"
              @click="nutChinh"
            >
              {{ dangGui ? 'Đang gửi…' : nhanNutChinh }}
            </button>
            <button
              v-if="tenPhieu"
              class="btn-o btn-danger"
              style="margin-left: auto"
              :disabled="dangLuu || dangGui || dangXoa"
              @click="xoaPhieu"
            >
              {{ dangXoa ? 'Đang xoá…' : 'Xoá phiếu' }}
            </button>
          </div>
        </div>
      </template>
    </template>
    </template>
  </div>
</template>
