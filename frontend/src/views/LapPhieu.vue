<script setup>
// Task 8 (kế hoạch gộp luồng đặt hàng, 2026-08-19) — màn LẬP PHIẾU đề xuất
// mua. Trước bản này KHÔNG có đường nào trên giao diện để tạo một phiếu đề
// xuất — DeXuatList.vue chỉ XEM, DeXuatDetail.vue chỉ DUYỆT/XOÁ/GỬI một
// phiếu đã tồn tại. Đây là màn khởi tạo.
//
// MỘT Ô TÌM, MỘT DANH SÁCH KẾT QUẢ, BA TẦNG (hard requirement 1) — chủ đầu
// tư đã từ chối tách "theo hợp đồng" / "mua lẻ" thành hai luồng, nguyên văn.
// KHÔNG có bộ chuyển chế độ, KHÔNG có tab ở màn này. `portal_catalog_gop`
// (T3, api/portal.py — cùng module với `portal_catalog`/`portal_catalog_
// ban_le`, KHÔNG phải api/de_xuat.py) trả về `tang` cho từng dòng:
//   - "hop_dong"    → tầng 1, có `don_gia` — "Giá hợp đồng · <số tiền>"
//   - "cho_bao_gia" → tầng 2, `don_gia = null` — "Chờ báo giá"
// Tầng 3 (hàng chưa có mã) KHÔNG đến từ endpoint này — khách gõ tay, vào
// bảng "đặt ngoài" riêng (`dat_ngoai`), không bao giờ lẫn vào `items`.
//
// RESUME-SỬA một phiếu Nháp đã lưu (Vòng sửa 1, review) — route
// `/de-xuat/lap/:ten?` với `ten` tuỳ chọn. Bản đầu của màn này KHÔNG có
// `:ten` với lý do "`portal_catalog_gop` chỉ gắn `tang` cho kết quả tìm
// kiếm, phiếu đã lưu không mang field này, suy ngược từ `don_gia` sẽ phạm
// đúng luật '0 là giá hợp lệ' của hợp đồng đóng băng" — ĐÚNG về mặt kỹ
// thuật nhưng SAI về hệ quả: không có `:ten` nghĩa là một phiếu Nháp đã Lưu
// rồi RỜI MÀN thì không còn đường nào sửa lại (`DeXuatDetail.vue` chỉ đọc),
// đúng ngược yêu cầu tường minh của chủ đầu tư ("phiếu trạng thái nháp có
// thể sửa số lượng ... và họ có thể xóa phiếu nháp").
//
// Lý do đó hết hiệu lực vì Task 2 (chạy song song) đã thêm ĐÚNG field còn
// thiếu: `Portal De Xuat Mua Item.nguon_gia` (Select, hệ thống tự suy ở
// `validate()`) — `"Hợp đồng"` → tầng 1 (đọc `don_gia` CHÍNH DÒNG ĐÓ, không
// đoán từ 0), mọi giá trị khác → tầng 2. Xem `napTuPhieu()`. KHÔNG có tầng
// thứ tư, không cần đoán gì nữa — chỉ đọc field.
//
// TẠO LƯỜI (lazy): `de_xuat_tao_nhap()` chỉ được gọi ở lần LƯU/GỬI ĐẦU
// TIÊN, không gọi ngay khi vào màn. Gọi ngay lúc mount sẽ chèn một bản ghi
// Nháp mỗi lần một trong sáu tài khoản thật bấm vào mục nav rồi đổi ý —
// DeXuatList.vue sắp theo `modified desc` nên những phiếu rác đó sẽ nằm
// TRÊN CÙNG. Cùng khuôn `PhieuNhapDetail.vue` (isNew → không gọi API tạo
// cho tới khi `save()`), chỉ khác: kho có MỘT endpoint save gộp cả tạo lẫn
// sửa (`kho_phieu_nhap_save`), còn de_xuat TÁCH `de_xuat_tao_nhap` (không
// tham số — `loai_don` đang bị xoá khỏi doctype, xem hợp đồng đóng băng)
// và `de_xuat_luu_nhap` (lưu items/dat_ngoai/...), nên `damBaoCoTen()` gọi
// cái trước CHỈ MỘT LẦN rồi tái dùng `tenPhieu` cho mọi lần lưu sau.
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

// --- Hồ sơ khách (best-effort) -----------------------------------------
const khoaPhongList = ref([])
async function loadKhoaPhongList() {
  try {
    khoaPhongList.value = await api.callKho('kho_khoa_phong_list', { ca_inactive: 1 })
  } catch (e) {
    // Best-effort — cùng khuôn DeXuatList.vue: chỉ mất phần dịch tên khoa.
  }
}
const tenKhoa = computed(() => {
  const ma = store.me?.khoa_phong
  if (!ma) return 'Toàn viện'
  const k = khoaPhongList.value.find((x) => x.name === ma)
  return k ? k.ten_khoa_phong : ma
})

// --- Phiếu đang lập -------------------------------------------------------
// `tenPhieu` rỗng cho tới lần Lưu/Gửi đầu tiên — xem ghi chú "TẠO LƯỜI" ở
// đầu file.
const tenPhieu = ref('')
// Trạng thái nạp phiếu Nháp có sẵn (route có `:ten`) — riêng biệt với
// `dangLuu`/`dangGui`/`dangXoa` bên dưới (những cờ đó canh HÀNH ĐỘNG của
// khách, cờ này canh việc TẢI phiếu lúc vào màn/đổi phiếu).
const phieuLoading = ref(false)
const phieuError = ref('')

// KHÔNG cần tự chốt "đang tạo" ở đây: hai nơi gọi duy nhất (`luuNhap`,
// `guiDuyet`) đã tự khoá bằng `dangLuu`/`dangGui` NGAY ĐẦU HÀM, trước khi gọi
// tới đây — bấm kép Lưu nháp hay Gửi duyệt trong lúc phiếu đang được tạo đều
// bị chặn từ vòng ngoài. Từng có một bản giữ thêm một cờ `dangTao` riêng và
// `return null` khi trùng — nhưng đường đó KHÔNG BAO GIỜ chạy tới (hai cờ
// ngoài đã chặn hết), và nếu một ngày nó chạy tới, `null` lọt xuống dưới
// dạng "không có gì xảy ra" — không toast, không lỗi, người dùng chỉ thấy
// nút nháy rồi thôi. Bỏ hẳn nhánh chết đó: lỗi thật (mạng, quyền...) giờ ném
// thẳng ra ngoài, rơi vào đúng `catch` đã có sẵn ở `luuNhap`/`guiDuyet`.
async function damBaoCoTen() {
  if (tenPhieu.value) return tenPhieu.value
  // Brief T8 — GỌI KHÔNG THAM SỐ. `loai_don` từng là tham số của hàm này
  // nhưng đang bị xoá khỏi doctype cùng đợt kế hoạch này (khái niệm "loại
  // đơn" bỏ hẳn khỏi phiếu đề xuất) — truyền nó hôm nay bị lặng lẽ bỏ qua,
  // và mai kia sẽ là một tham số không còn tồn tại.
  const res = await api.callDeXuat('de_xuat_tao_nhap')
  tenPhieu.value = res.name
  return tenPhieu.value
}

// --- Dòng hàng đã chọn (tầng 1 + tầng 2, có mã) ---------------------------
const items = ref([]) // { item_code, item_name, dvt, so_luong_de_xuat, tang, don_gia }
const qtys = reactive({}) // item_code → số lượng đang chọn ở ô tìm kiếm

// `so_luong_de_xuat` là Float trên doctype con, và chính ô sửa số lượng ở
// bảng "Danh sách đề xuất" bên dưới dùng `step="any"` — vật tư y tế đặt lẻ
// (vd. 2.5 mét băng gạc) là chuyện bình thường. `parseInt` sẽ CẮT phần thập
// phân MÀ KHÔNG BÁO GÌ (2.5 → 2) — đúng lớp lỗi "im lặng làm sai số lượng"
// mà `kiemTraSoLuong()` bên dưới đã tránh cho đường lưu; hàm này tránh nó
// cho đường CỘNG DÒNG. Chỉ rơi về 1 khi giá trị THẬT SỰ không hợp lệ
// (rỗng, chữ, ≤ 0) — không phải mọi số có phần thập phân.
function soHienTai(itemCode) {
  const n = Number(qtys[itemCode])
  return Number.isFinite(n) && n > 0 ? n : 1
}

function themDong(row) {
  const so = soHienTai(row.item_code)
  const daCo = items.value.find((r) => r.item_code === row.item_code)
  if (daCo) {
    daCo.so_luong_de_xuat = (Number(daCo.so_luong_de_xuat) || 0) + so
    // Cố ý GIỮ `tang`/`don_gia` của dòng đã có trên phiếu, không ghi đè
    // bằng kết quả tìm kiếm mới — hai điều này chỉ để HIỂN THỊ badge, giá
    // thật do server tự suy lại ở `validate()` (`_suy_nguon_gia`, Task 2)
    // mỗi lần lưu, không đọc từ đây. Badge có thể trễ một nhịp so với một
    // tìm kiếm khác vừa chạy sau đó; chấp nhận được vì đây chỉ là gợi ý
    // hiển thị, không phải giá trị được gửi lên server.
  } else {
    items.value.push({
      item_code: row.item_code,
      item_name: row.item_name,
      dvt: row.dvt,
      so_luong_de_xuat: so,
      tang: row.tang,
      don_gia: row.don_gia,
    })
  }
  showToast(`Đã thêm ${so} ${row.dvt || ''} · ${row.item_name} vào phiếu`)
  qtys[row.item_code] = 1
}
function xoaDong(itemCode) {
  items.value = items.value.filter((r) => r.item_code !== itemCode)
}
function nhanTang(row) {
  return row.tang === 'hop_dong' ? `Giá hợp đồng · ${fmtVND(row.don_gia)}` : 'Chờ báo giá'
}
function classTang(row) {
  return row.tang === 'hop_dong' ? 'b-blue' : 'b-orange'
}

// --- Dòng đặt ngoài (tầng 3, khách gõ tay, KHÔNG có mã) -------------------
// Cùng hình dạng `Sales Order Dat Ngoai Item` / `store.cartDatNgoai`:
// { ten_hang, dvt, so_luong, ghi_chu }.
const datNgoai = ref([])
const dnMoRong = ref(false)
function moDatNgoai(tenGoiY) {
  dnMoRong.value = true
  if (!datNgoai.value.length) {
    datNgoai.value.push({ ten_hang: tenGoiY || '', dvt: '', so_luong: '', ghi_chu: '' })
  }
}
function themDongDatNgoai() {
  datNgoai.value.push({ ten_hang: '', dvt: '', so_luong: '', ghi_chu: '' })
}
function xoaDongDatNgoai(i) {
  datNgoai.value.splice(i, 1)
}
// Chỉ những dòng ĐÃ ĐIỀN ĐỦ mới gửi lên server — dòng đang gõ dở (mới bấm
// "+ Thêm dòng", chưa gõ gì) không được coi là một mặt hàng thật.
const datNgoaiHopLe = computed(() =>
  datNgoai.value.filter(
    (d) => (d.ten_hang || '').trim() && (d.dvt || '').trim() && Number(d.so_luong) > 0
  )
)

// Hard requirement 4 — cảnh báo phải hiện TRƯỚC khi bấm, không phải sau.
// Cố ý dùng `datNgoai.length` (MỌI dòng, kể cả đang gõ dở), KHÔNG phải
// `datNgoaiHopLe` — cổng HIỂN THỊ phải hỏi câu khác cổng NÚT (cùng khuôn
// `leTrong` vs `leTrongHienThi` của Cart.vue): một dòng vừa mở ra do bấm
// "Hàng chưa có trong hệ thống" đã LÀ tín hiệu "đơn này sắp có hàng chờ báo
// giá", khách phải thấy câu cảnh báo ngay lúc đó, không phải đợi tới khi
// gõ xong đủ ba ô.
const coHangChoBaoGia = computed(
  () => items.value.some((r) => r.tang === 'cho_bao_gia') || datNgoai.value.length > 0
)

// --- Tìm kiếm (một ô tìm duy nhất) -----------------------------------------
const search = ref('')
const searchResults = ref([])
const searchLoading = ref(false)
const searchError = ref('')
const searchTong = ref(0)
const searchTrang = ref(1)
const searchSoDong = ref(20)
let searchTimer = null

async function timKiem() {
  searchLoading.value = true
  searchError.value = ''
  try {
    // `portal_catalog_gop` sống ở api/portal.py (T3) — gọi qua `api.call`,
    // KHÔNG qua `callDeXuat`. Lưới `test_de_xuat_action_registry.py` chỉ
    // quét `callDeXuat('...')` và `method:` của `de-xuat-actions.js`, nên
    // lời gọi này KHÔNG được lưới đó canh — xem báo cáo Task 8.
    const res = await api.call('portal_catalog_gop', {
      tu_khoa: search.value.trim() || undefined,
      start: (searchTrang.value - 1) * searchSoDong.value,
      limit: searchSoDong.value,
    })
    searchResults.value = res.rows || []
    searchTong.value = res.tong || 0
  } catch (e) {
    // Backend T3 chạy song song với màn này (Ruling P11) — cho tới khi T3
    // xong, lời gọi này CHẮC CHẮN lỗi. Hiện thông báo tại chỗ, KHÔNG chặn
    // khối "Hàng chưa có trong hệ thống" bên dưới — đó vẫn là đường lập
    // phiếu duy nhất còn sống trong lúc chờ.
    searchResults.value = []
    searchTong.value = 0
    searchError.value = e.message || 'Không tìm được vật tư lúc này.'
  } finally {
    searchLoading.value = false
  }
}

// Không tìm ra (hard requirement 3) — coi LỖI TÌM KIẾM cùng nhóm với
// "không có kết quả": cả hai đều phải mở đường cho khách gõ tay, không
// được để một lỗi mạng khoá luôn lối thoát duy nhất của màn.
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

// --- Thông tin yêu cầu (khối truy vết + giao hàng) ------------------------
const lyDoYeuCau = ref('')
const ghiChu = ref('')
const ngayCan = ref(addWorkDaysISO(2)) // gợi ý hợp lý, không bắt buộc
const ngayToiThieu = todayISO()
const diaChiGiao = ref('')
const diaChiOptions = computed(() => store.me?.addresses || [])

// --- Nạp một phiếu Nháp có sẵn (route `/de-xuat/lap/:ten`) ----------------
// Về trạng thái LẬP MỚI trắng — dùng khi route KHÔNG có `:ten` (vào thẳng
// `/de-xuat/lap`, hoặc rời một phiếu đang sửa để bắt đầu một phiếu khác).
function resetState() {
  tenPhieu.value = ''
  items.value = []
  datNgoai.value = []
  dnMoRong.value = false
  lyDoYeuCau.value = ''
  ghiChu.value = ''
  ngayCan.value = addWorkDaysISO(2)
  diaChiGiao.value = (store.me?.addresses || [])[0]?.name || ''
}

// Đổ dữ liệu một phiếu Nháp đã lưu (`de_xuat_chi_tiet`) vào form.
//
// `nguon_gia` (Task 2, chạy song song — Select trên `Portal De Xuat Mua
// Item`, hệ thống tự suy ở `validate()`, ĐỌC-CHỈ) thay cho việc đoán tầng
// từ `don_gia`: `"Hợp đồng"` → tầng 1 (đọc `don_gia` CHÍNH DÒNG đó — dòng
// nào cũng đã đóng dấu số thật, không phải kết quả tìm kiếm nữa), mọi giá
// trị khác (kể cả rỗng/null — dòng chưa từng qua `validate()`) → tầng 2.
// Không có tầng thứ tư ở đây.
function napTuPhieu(d) {
  tenPhieu.value = d.name
  items.value = (d.items || []).map((it) => ({
    item_code: it.item_code,
    item_name: it.item_name,
    dvt: it.dvt,
    so_luong_de_xuat: it.so_luong_de_xuat,
    tang: it.nguon_gia === 'Hợp đồng' ? 'hop_dong' : 'cho_bao_gia',
    don_gia: it.don_gia,
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
}

// Vòng sửa 1 (review) — điều phối theo `route.params.ten`. QUAN TRỌNG: đây
// PHẢI là một `watch`, không phải chỉ đọc một lần ở `onMounted`. Vue Router
// TÁI DÙNG cùng một instance component khi chỉ tham số đổi (từ
// `/de-xuat/lap/PHIEU-1` sang `/de-xuat/lap/PHIEU-2`, `onMounted` không
// chạy lại) — thiếu `watch` thì bấm "Sửa" từ phiếu này sang phiếu khác sẽ
// giữ nguyên dữ liệu của phiếu TRƯỚC trên màn (đúng lỗi đang treo trong sổ
// nợ của `DeXuatDetail.vue`, không lặp lại ở đây).
async function taiHoacKhoiTao() {
  const tenParam = route.params.ten
  if (!tenParam) {
    resetState()
    return
  }
  phieuLoading.value = true
  phieuError.value = ''
  try {
    const d = await api.callDeXuat('de_xuat_chi_tiet', { ten: tenParam })
    if (d.trang_thai !== 'Nháp') {
      // Việc cần làm 2 — TỪ CHỐI mở một phiếu không phải Nháp ở màn sửa này.
      // `de_xuat_luu_nhap` phía server cũng ném lỗi cho ca này, nhưng người
      // dùng không nên phải CHẠM lỗi đó mới biết — đưa thẳng về màn chi
      // tiết chỉ đọc, kèm một câu giải thích tại sao.
      showToast(
        `Phiếu ${d.ma_de_xuat || tenParam} không còn ở trạng thái Nháp — không sửa được ở đây nữa.`,
        'error'
      )
      router.replace({ name: 'de-xuat-detail', params: { ten: tenParam }, query: { tu: 'de-xuat' } })
      return
    }
    napTuPhieu(d)
  } catch (e) {
    phieuError.value = e.message || 'Không tải được phiếu nháp.'
  } finally {
    phieuLoading.value = false
  }
}
// `immediate: true` — chạy ngay ở lần vào màn đầu tiên (thay cho việc gọi
// tay trong `onMounted`), RỒI chạy lại mỗi khi tham số đổi vì lý do ở trên.
watch(() => route.params.ten, taiHoacKhoiTao, { immediate: true })

// --- Kiểm số lượng trước khi lưu/gửi ---------------------------------------
// Cùng bẫy đã ghi trong DeXuatDetail.vue (`Number('') === 0`), nhưng NGƯỢC
// nghĩa ở đây: phiếu đang LẬP không có khái niệm "ô trống = giữ nguyên" —
// mỗi dòng gửi lên PHẢI mang một số lượng dương tường minh. Vì vậy ô trống/
// không hợp lệ ở màn này phải bị CHẶN LƯU (không phải lặng lẽ hạ về 0), đặt
// tên đúng dòng để khách biết sửa ở đâu — cùng chốt `_dong_dau_so_luong_
// duyet` phía server rồi sẽ ném "Không còn dòng nào có số lượng duyệt lớn
// hơn 0" nếu một dòng 0 lọt qua tới đây.
function kiemTraSoLuong() {
  for (const r of items.value) {
    const n = Number(r.so_luong_de_xuat)
    if (!Number.isFinite(n) || n <= 0) {
      return `Mặt hàng "${r.item_code}" chưa có số lượng hợp lệ (phải lớn hơn 0).`
    }
  }
  for (const d of datNgoai.value) {
    if ((d.ten_hang || '').trim() && (d.dvt || '').trim()) {
      const n = Number(d.so_luong)
      if (!Number.isFinite(n) || n <= 0) {
        return `Dòng đặt ngoài "${d.ten_hang}" chưa có số lượng hợp lệ (phải lớn hơn 0).`
      }
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
// Ép kiểu số TRƯỚC khi gửi — `d.so_luong` sống trong ô nhập v-model không
// `.number` (giữ chuỗi thô, cùng lý do `datNgoaiHopLe` không dùng `.number`
// ở template: một ô đang gõ dở không được lặng lẽ hoá thành 0). Payload gửi
// server thì phải là số thật, không phải chuỗi "5".
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
    // "đừng đụng vào field này" (`if v is not None: doc.set(...)`). Gửi
    // `null` cho một ô VỪA BỊ XOÁ TRẮNG sẽ làm giá trị cũ SỐNG LẠI sau khi
    // lưu — đúng ngược điều khách vừa làm.
    ngay_can: ngayCan.value ?? '',
    dia_chi_giao: diaChiGiao.value ?? '',
    ghi_chu: ghiChu.value ?? '',
    ly_do_yeu_cau: lyDoYeuCau.value ?? '',
  })
}

// --- Hành động: Lưu nháp / Gửi duyệt / Xoá phiếu --------------------------
const dangLuu = ref(false)
const dangGui = ref(false)
const dangXoa = ref(false)

async function luuNhap() {
  if (dangLuu.value || dangGui.value) return
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
  if (!items.value.length && !datNgoaiHopLe.value.length) {
    return showToast('Phiếu chưa có mặt hàng nào — thêm ít nhất một dòng trước khi gửi duyệt.', 'error')
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
    router.push({ name: 'de-xuat-detail', params: { ten }, query: { tu: 'de-xuat' } })
  } catch (e) {
    showToast(e.message || 'Không gửi được phiếu.', 'error')
  } finally {
    dangGui.value = false
  }
}

async function xoaPhieu() {
  if (!tenPhieu.value || dangXoa.value) return
  if (!window.confirm('Xoá phiếu này? Dữ liệu sẽ bị xoá VĨNH VIỄN khỏi hệ thống — KHÔNG thể khôi phục.')) return
  dangXoa.value = true
  try {
    await api.callDeXuat('de_xuat_xoa_nhap', { ten: tenPhieu.value })
    showToast('Đã xoá phiếu.')
    router.push({ name: 'de-xuat' })
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
    // Best-effort — thiếu `me` chỉ mất tên khoa/địa chỉ mặc định, không
    // chặn cả màn (khách vẫn tìm và lập phiếu được).
  }
  timKiem()
})
</script>

<template>
  <div>
    <div class="topbar">
      <div>
        <h2>Lập phiếu đề xuất mua</h2>
        <div class="sub">{{ tenKhoa }}<span v-if="tenPhieu"> · Nháp {{ tenPhieu }}</span></div>
      </div>
      <router-link to="/de-xuat"><button class="btn-o">← Đề xuất mua</button></router-link>
    </div>

    <!-- Vòng sửa 1 — trạng thái nạp một phiếu Nháp có sẵn (route có
         `:ten`). LẬP MỚI (không `:ten`) không đi qua nhánh này —
         `taiHoacKhoiTao()` trả về ngay sau `resetState()`. -->
    <div v-if="phieuLoading" class="loading">Đang tải phiếu…</div>
    <div v-else-if="phieuError" class="empty">{{ phieuError }}</div>

    <template v-else>
    <!-- ============ Ô TÌM (một ô duy nhất, ba tầng) ============ -->
    <div class="card mb10">
      <div class="field" style="margin-bottom: 0">
        <label>Tìm vật tư</label>
        <input v-model="search" placeholder="Nhập mã hoặc tên mặt hàng..." />
      </div>
    </div>

    <div v-if="searchError" class="note note-r" style="margin-bottom: 12px">
      {{ searchError }}
    </div>
    <div v-if="searchLoading" class="loading">Đang tìm…</div>

    <template v-else-if="searchResults.length">
      <div v-if="!isMobile" class="card mb10" style="padding: 0; overflow-x: auto">
        <table>
          <thead>
            <tr>
              <th>Mã</th><th>Tên mặt hàng</th><th>ĐVT</th><th>Tầng giá</th>
              <th style="width: 120px">Số lượng</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in searchResults" :key="r.item_code">
              <td><b>{{ r.item_code }}</b></td>
              <td>{{ r.item_name }}</td>
              <td>{{ r.dvt }}</td>
              <td><span class="badge" :class="classTang(r)">{{ nhanTang(r) }}</span></td>
              <td>
                <div class="step">
                  <button @click="qtys[r.item_code] = Math.max(1, soHienTai(r.item_code) - 1)">−</button>
                  <input v-model="qtys[r.item_code]" inputmode="decimal" />
                  <button @click="qtys[r.item_code] = soHienTai(r.item_code) + 1">+</button>
                </div>
              </td>
              <td><button class="btn btn-sm" @click="themDong(r)">+ Thêm</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <template v-else>
        <div v-for="r in searchResults" :key="r.item_code" class="card item mb10">
          <div class="nm">{{ r.item_code }} · {{ r.item_name }}</div>
          <div class="tag" style="margin: 2px 0 6px">{{ r.dvt }}</div>
          <span class="badge" :class="classTang(r)">{{ nhanTang(r) }}</span>
          <div class="sb" style="margin-top: 10px">
            <div class="step">
              <button @click="qtys[r.item_code] = Math.max(1, soHienTai(r.item_code) - 1)">−</button>
              <input v-model="qtys[r.item_code]" inputmode="decimal" />
              <button @click="qtys[r.item_code] = soHienTai(r.item_code) + 1">+</button>
            </div>
            <button class="btn btn-sm" @click="themDong(r)">+ Thêm</button>
          </div>
        </div>
      </template>
      <PhanTrang v-model:trang="searchTrang" v-model:so-dong="searchSoDong" :tong="searchTong" />
    </template>

    <!-- ============ Không tìm ra → mở lối gõ tay (tầng 3) ============ -->
    <div v-if="timKhongRa" class="card mb10">
      <div v-if="!searchError" class="tag" style="margin-bottom: 8px">
        Không có mặt hàng khớp tìm kiếm trong hệ thống.
      </div>
      <button class="btn-o" @click="moDatNgoai(search.trim())">Hàng chưa có trong hệ thống</button>
    </div>

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
                <input v-model="d.so_luong" inputmode="numeric" />
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

    <!-- ============ Danh sách đề xuất (đã chọn) ============ -->
    <div class="card mb10" style="padding: 0; overflow-x: auto">
      <div class="h3" style="padding: 12px 14px 0">Danh sách đề xuất</div>
      <table>
        <thead>
          <tr>
            <th>Mặt hàng</th><th>Tầng giá</th><th class="right" style="width: 140px">Số lượng</th><th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in items" :key="r.item_code">
            <td>
              <b>{{ r.item_code }}</b> — {{ r.item_name }}
              <span v-if="r.dvt" class="tag">({{ r.dvt }})</span>
            </td>
            <td><span class="badge" :class="classTang(r)">{{ nhanTang(r) }}</span></td>
            <td class="right">
              <input
                type="number" min="1" step="any"
                v-model="r.so_luong_de_xuat"
                :aria-label="`Số lượng cho ${r.item_code}`"
                style="width: 90px; text-align: right"
              />
            </td>
            <td><button class="btn-o btn-sm" style="color: var(--red); border-color: var(--red)" @click="xoaDong(r.item_code)">Xoá</button></td>
          </tr>
          <tr v-if="!items.length">
            <td colspan="4" class="tag">Chưa có mặt hàng nào — tìm ở ô trên để thêm.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ============ Thông tin yêu cầu (truy vết + giao hàng) ============ -->
    <div class="card mb10">
      <div class="h3">Thông tin yêu cầu</div>
      <div class="field">
        <label>Lý do yêu cầu <span class="req">*</span></label>
        <textarea rows="2" v-model="lyDoYeuCau" placeholder="VD: Khoa cần bổ sung vật tư tiêu hao cho quý này..."></textarea>
      </div>
      <div class="sb" style="gap: 8px">
        <div class="field" style="flex: 1">
          <label>Ngày cần hàng</label>
          <input type="date" v-model="ngayCan" :min="ngayToiThieu" />
        </div>
        <div class="field" style="flex: 1">
          <label>Địa chỉ giao</label>
          <select v-model="diaChiGiao">
            <option value="">—</option>
            <option v-for="a in diaChiOptions" :key="a.name" :value="a.name">{{ a.display }}</option>
          </select>
        </div>
      </div>
      <div class="field" style="margin-bottom: 0">
        <label>Ghi chú</label>
        <textarea rows="2" v-model="ghiChu" placeholder="Ghi chú thêm cho quản lý..."></textarea>
      </div>
    </div>

    <!-- ============ Hành động ============ -->
    <div class="card mb10">
      <!-- Hard requirement 4 — cảnh báo PHẢI hiện ở đây, trước hàng nút, để
           khách đọc được TRƯỚC khi bấm, không phải phát hiện sau. -->
      <div v-if="coHangChoBaoGia" class="note note-b" style="margin-bottom: 12px">
        Đơn có hàng chờ báo giá — cả đơn sẽ chờ Miyano báo giá trước khi giao.
      </div>
      <div class="flex" style="flex-wrap: wrap; gap: 8px">
        <button class="btn-o" :disabled="dangLuu || dangGui" @click="luuNhap">
          {{ dangLuu ? 'Đang lưu…' : 'Lưu nháp' }}
        </button>
        <button class="btn" :disabled="dangLuu || dangGui" @click="guiDuyet">
          {{ dangGui ? 'Đang gửi…' : 'Gửi duyệt' }}
        </button>
        <!-- Hide, don't disable (de-xuat-actions.js) — nút Xoá chỉ hiện SAU
             khi phiếu đã thật sự tồn tại (`tenPhieu` khác rỗng); trước đó
             không có gì để xoá. -->
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
  </div>
</template>
