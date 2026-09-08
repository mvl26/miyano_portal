<script setup>
// Bảng mặt hàng của màn chi tiết GỘP. MỘT bảng cho cả hai nửa của một yêu
// cầu — trước 03/09/2026 đây là hai bảng ở hai màn, và "khoa xin 100 /
// duyệt 40 / giao 25" là ba con số người dùng phải tự ghép bằng mắt qua
// hai lần điều hướng.
//
// NGUỒN DÒNG là PHIẾU khi có phiếu, không phải đơn. Phiếu là tập cha: nó
// giữ cả dòng quản lý đã hạ về 0 (bằng chứng "khoa đã xin gì" — §5.3 cấm
// xoá dòng, chỉ cho hạ về 0) lẫn dòng "Quản lý thêm". Lấy dòng từ đơn sẽ
// làm mất đúng những dòng đó, tức mất câu trả lời cho câu hỏi hệ thống này
// tồn tại để trả lời.
//
// Giá và số đã giao đi CÙNG dòng phiếu, do server nối
// (`de_xuat_chi_tiet`) — không nối ở đây: `frontend/` không có test nào,
// còn phía Python thì `tests/test_chi_tiet_gop.py` canh được.
import { ref, computed } from 'vue'
import api from '../../api'
import { fmtVND, fmtDate, todayISO, addDaysISO } from '../../format'
import { THE_KHO_COLUMNS } from '../../kho-bao-cao-columns'
import TheHangMoi from './TheHangMoi.vue'

const props = defineProps({
  phieu: { type: Object, default: null },
  don: { type: Object, default: null },
  quanLyDangDuyet: { type: Boolean, default: false },
  slDuyetSua: { type: Object, default: () => ({}) },
  ghiChuSua: { type: Object, default: () => ({}) },
  // CR-04 (05/09/2026) — căn cứ tồn kho theo item_code, `{item_code: {ton,
  // dang_ve, adu, con_dung_duoc, muc, vat_tu}}`. Item KHÔNG có mặt trong
  // dict = không tra được (khách chưa mở kho / vật tư chưa nối item_code /
  // hàng không có trong danh mục kho) — xem `canCu()` bên dưới, đây là NƠI
  // DUY NHẤT phân biệt "không tra được" với "tồn 0".
  canCuKho: { type: Object, default: () => ({}) },
  // Tên PHIẾU — chỉ để dựng đường ảnh riêng tư của khối "Xem chi tiết"
  // (`portal_dat_ngoai_xem_anh` kiểm sở hữu theo đề xuất). Rỗng với ~102 đơn
  // cũ không có phiếu; những đơn đó cũng không có ảnh CR-03 nào.
  deXuat: { type: String, default: '' },
})

// Đơn cũ không có phiếu (~102 đơn trước luồng duyệt) — dòng lấy từ đơn, và
// hai cột của phiếu tự vắng mặt theo `coPhieu` bên dưới.
// Dòng gõ tay ĐÃ KHỚP MÃ, gom theo mã Miyano gán — nhiều yêu cầu về CÙNG
// một mã là ca thường, không phải ngoại lệ: `_gop_hoac_them_dong_hang` cộng
// thẳng số lượng vào MỘT dòng `Sales Order Item`. Dựng bản đồ 1-nhiều ở đây
// để chỗ nào cũng đọc cùng một phép gom, thay vì `find()` rải rác (bản
// trước `find()` một dòng và mất phần còn lại).
const yeuCauKhopTheoMa = computed(() => {
  const nhom = {}
  for (const d of props.don?.dat_ngoai || []) {
    if (!d.da_xu_ly || !d.item_khop) continue
    if (!nhom[d.item_khop]) nhom[d.item_khop] = []
    nhom[d.item_khop].push(d)
  }
  return nhom
})

const dong = computed(() => {
  const co_ban = props.phieu
    ? (props.phieu.items || []).map((r) => ({ ...r }))
    : (props.don?.items || []).map((it) => ({
        item_code: it.item_code,
        item_name: it.item_name,
        dvt: it.uom,
        so_luong_tren_don: it.qty,   // Ruling preflight #2 — nuôi cột "SL đặt"
        don_gia_tren_don: it.rate,
        thanh_tien_tren_don: it.amount,
        da_giao_tren_don: it.delivered_qty,
      }))

  // MỘT BẢNG, KHÔNG BA (chủ đầu tư 08/09/2026: "sau khi đã khớp mã hàng từ
  // Miyano thì chỉ hiển thị đúng 1 bảng"). Trước bản này dòng đã khớp KHÔNG
  // BAO GIỜ vào được bảng chính, và lý do là cấu trúc chứ không phải sót:
  // khớp mã dựng dòng hàng trên ĐƠN, còn bảng chính lấy dòng từ PHIẾU. Nên
  // phải nối lại ở đây — đó chính là việc hai bảng phụ cũ đang làm thay.
  const nhom = yeuCauKhopTheoMa.value
  const da_gan = new Set()
  for (const r of co_ban) {
    if (!nhom[r.item_code]) continue
    r.yeu_cau_khop = nhom[r.item_code]
    da_gan.add(r.item_code)
  }
  // Mã CHƯA từng có trên phiếu (ca thường: khoa gõ tay "dây truyền dịch",
  // Miyano khớp ra một mã khoa không hề xin) — dựng dòng tổng hợp. Bỏ qua
  // nhánh này là để đúng nhóm hàng CR-03 rơi khỏi bảng, tức tái lập nguyên
  // con lỗi "quản lý duyệt thứ mình không nhìn thấy".
  for (const ma of Object.keys(nhom)) {
    if (da_gan.has(ma)) continue
    const hang = (props.don?.items || []).find((h) => h.item_code === ma)
    const ycs = nhom[ma]
    co_ban.push({
      item_code: ma,
      item_name: hang?.item_name || '',
      dvt: hang?.uom || ycs[0].dvt || '',
      // Tổng SL của MỌI yêu cầu gộp vào mã này — không phải của yêu cầu đầu.
      so_luong_de_xuat: ycs.reduce((t, y) => t + (Number(y.so_luong) || 0), 0),
      // `null`, KHÔNG chép `so_luong_de_xuat`: dòng gõ tay không đi qua
      // `_dong_dau_so_luong_duyet` (hàm đó đóng dấu dòng của PHIẾU), nên ở
      // đây KHÔNG CÓ con số duyệt nào cả. Chép cột đề xuất sang là in ra một
      // con số duyệt chưa ai duyệt — cùng luật "—" của CR-04.
      so_luong_duyet: null,
      so_luong_xin_sua: null,
      so_luong_tren_don: hang ? Number(hang.qty) : null,
      don_gia_tren_don: hang ? Number(hang.rate) : null,
      thanh_tien_tren_don: hang ? Number(hang.amount) : null,
      da_giao_tren_don: hang ? Number(hang.delivered_qty) : null,
      ghi_chu_quan_ly: '',
      yeu_cau_khop: ycs,
      // Dòng KHÔNG có mặt trên phiếu — quản lý không được sửa SL duyệt của
      // nó (không có gì để sửa), xem ô nhập ở template.
      chi_tu_yeu_cau: true,
    })
  }
  return co_ban
})

const coPhieu = computed(() => !!props.phieu)
const coDon = computed(() => !!props.don)
// "Đã đóng dấu duyệt" — `so_luong_duyet` chỉ mang nghĩa SAU khi phiếu rời
// Nháp (`_dong_dau_so_luong_duyet` chạy trong `gui_duyet`). Hiện cột đó
// trên một phiếu Nháp là in ra một bản sao vô nghĩa của cột đề xuất.
const coCotDuyet = computed(() => coPhieu.value && props.phieu.trang_thai !== 'Nháp')
const coCotXinSua = computed(() => props.phieu?.trang_thai === 'Chờ duyệt sửa')
// Cột "Đã giao" chỉ hiện khi CÓ đợt giao — một cột toàn số 0 trên đơn vừa
// duyệt là một cột chiếm chỗ mà không nói gì.
const coCotDaGiao = computed(
  () => coDon.value && (props.don.deliveries || []).length > 0
)

// M1 (Task 4) — "hạ về 0" chỉ có nghĩa SAU khi quản lý đã thật sự cầm phiếu
// lên xử lý. Ở "Nháp"/"Chờ duyệt", `so_luong_duyet` mới là bản sao mặc định
// của `so_luong_de_xuat`, coi nó là "Không duyệt" sẽ gắn badge sai cho MỌI
// dòng của MỌI phiếu chưa ai đụng tới.
const daDieuChinh = computed(
  () => ['Đã duyệt', 'Chờ duyệt sửa'].includes(props.phieu?.trang_thai)
)
function khongDuyet(row) {
  // `Number(null) === 0` — bẫy thật, không phải phòng xa: dòng đã khớp mã có
  // `so_luong_duyet === null` ("không có số duyệt"), và thiếu chốt này thì
  // MỌI dòng như vậy bị gạch ngang kèm badge "Không duyệt" trên đơn đã duyệt.
  if (row.so_luong_duyet === null || row.so_luong_duyet === undefined) return false
  return daDieuChinh.value && Number(row.so_luong_duyet) === 0
}

// Chép lại đúng logic `soDuyetMoi`/`laBoMatHang` của DeXuatDetail.vue — hai
// hàm đó KHÔNG nằm trong hợp đồng props (chỉ có `slDuyetSua` là dữ liệu
// thô), nên ô nhập SL duyệt ở đây phải tự tính lại thay vì nhận hàm qua
// prop. Sai một ký tự ở đây là sai đúng cái bẫy `Number('')`/`Number(' ')`
// = 0 mà bản gốc đã né (ô trống = "không đổi", CHỈ số 0 gõ tường minh mới
// là bỏ mặt hàng — §5.3).
function soDuyetMoi(row) {
  const raw = props.slDuyetSua[row.item_code]
  if (raw === undefined || raw === null) return null
  const chuoi = String(raw).trim()
  if (!chuoi) return null
  const n = Number(chuoi)
  if (!Number.isFinite(n) || n < 0) return null
  return n === (Number(row.so_luong_duyet) || 0) ? null : n
}
function laBoMatHang(row) {
  return soDuyetMoi(row) === 0
}

// Số cột thật đang hiện — nuôi `colspan` của dòng "Chưa có dòng hàng nào."
// Đếm động vì bộ cột co giãn theo giai đoạn (coPhieu/coCotDuyet/coCotXinSua/
// coDon/coCotDaGiao), không phải một hằng số như bảng cũ (luôn 3 hoặc 4).
const soCotTong = computed(() => {
  let n = 2 // Mặt hàng, ĐVT — hai cột luôn có mặt
  if (coPhieu.value) n += 1 // SL đề xuất
  if (coCotDuyet.value) n += 1
  if (coCotXinSua.value) n += 1
  if (coDon.value) n += 3 // SL đặt, Đơn giá, Thành tiền
  if (coCotDaGiao.value) n += 1
  if (coPhieu.value) n += 1 // Ghi chú quản lý
  if (coCanCuKho.value) n += 4 // Tồn hiện có, Đang về, Dùng TB/ngày, Còn dùng được
  return n
})

// --- CR-04 — căn cứ tồn kho ngay cạnh dòng hàng khi duyệt -------------
//
// Gate theo ĐIỀU KIỆN MÀN DUYỆT (`quanLyDangDuyet`), KHÔNG theo việc
// `canCuKho` có dữ liệu hay không: khách CHƯA MỞ KHO (1/6 khách hiện tại,
// spec §2/§4) chính là nhóm PHẢI thấy gạch ngang + dòng giải thích — ẩn cả
// cột đi vì `canCuKho` rỗng sẽ xoá mất đúng thông tin CR-04 sinh ra để hiện.
const coCanCuKho = computed(() => props.quanLyDangDuyet)

// `undefined` khi item KHÔNG có mặt trong dict — "không tra được", khác hẳn
// một object mang `ton: 0` ("hết hàng"). Mọi nơi đọc căn cứ tồn kho của MỘT
// dòng phải đi qua đúng hàm này, không tự với thẳng `canCuKho[...]` rải rác.
function canCu(row) {
  return props.canCuKho[row.item_code]
}

// Định dạng SL/ngày cho bốn cột mới — kiểm `null`/`undefined` TƯỜNG MINH.
// KHÔNG `Number(v || 0)` (bẫy `fmtVND` đã né ở "Ruling preflight #1" của
// chính file này): `0` là một giá trị THẬT ("hết hàng"/"còn dùng được 0
// ngày"), chỉ null/undefined ("không tra được") mới ra gạch ngang.
function fmtSl(v) {
  if (v === null || v === undefined) return '—'
  return Number(v).toLocaleString('vi-VN', { maximumFractionDigits: 1 })
}
function fmtNgay(v) {
  if (v === null || v === undefined) return '—'
  return Math.round(Number(v)).toLocaleString('vi-VN') + ' ngày'
}

// Ít nhất một dòng đang hiện KHÔNG tra được → hiện dòng giải thích BA lý do
// (§4) thay vì để quản lý tự đoán vì sao cột trống.
const coDongKhongTraDuoc = computed(
  () => coCanCuKho.value && dong.value.some((r) => !canCu(r))
)

// Ngưỡng ⚠ CHÉP TỪ `kho/can_cu_duyet.py::NGUONG_DAT_KHI_CHUA_CAN` (spec §5).
// KHÔNG tính được ở server: `co_canh_bao()` cần `nv_dat`, một trường sống
// trên PHIẾU (`so_luong_de_xuat`) mà module `kho/` không biết tới. Đặt ở
// MỘT hằng số có tên (Ruling #19) — `test_cr04_giao_dien.py` đối chiếu số
// này với hằng Python để một lần đổi ngưỡng ở backend không lặng lẽ để JS
// lệch theo.
const NGUONG_DAT_KHI_CHUA_CAN_JS = 30
function coCanhBaoDatKhiChuaCan(row) {
  const cc = canCu(row)
  if (!cc || cc.con_dung_duoc === null || cc.con_dung_duoc === undefined) return false
  return cc.con_dung_duoc >= NGUONG_DAT_KHI_CHUA_CAN_JS && Number(row.so_luong_de_xuat) > 0
}

// --- Sổ kho xổ NGAY TẠI DÒNG (§6) — không rời màn duyệt ---------------
//
// `dongMoRong`/`soKhoTheo` khoá theo `item_code`, cùng khuôn `slDuyetSua`/
// `ghiChuSua` (gán trực tiếp qua bracket vào object của `ref()`, Vue 3 theo
// dõi được thuộc tính MỚI thêm vào một object phản ứng).
const dongMoRong = ref({})
const soKhoTheo = ref({})

// Dòng KHÔNG tra được (canCu(row) rỗng) thì KHÔNG có `vat_tu` để gọi sổ kho
// — "đừng hiện nút chết" (§6): mọi nơi quyết định HIỆN/ẨN nút xổ sổ kho
// phải đi qua đúng hàm này.
function coTheXoSo(row) {
  return coCanCuKho.value && !!canCu(row)?.vat_tu
}

async function toggleSoKho(row) {
  if (!coTheXoSo(row)) return
  const ma = row.item_code
  dongMoRong.value[ma] = !dongMoRong.value[ma]
  if (!dongMoRong.value[ma] || soKhoTheo.value[ma]) return // đóng lại, hoặc đã tải rồi
  soKhoTheo.value[ma] = { loading: true, error: '', rows: [] }
  try {
    // Dùng lại `kho_the_kho` đã có (đọc riêng, tự kiểm vật tư thuộc kho
    // người gọi) — KHÔNG dựng đường đọc thứ hai, xem docstring module kho.
    const res = await api.callKho('kho_the_kho', {
      vat_tu: canCu(row).vat_tu, tu_ngay: addDaysISO(-90), den_ngay: todayISO(),
    })
    soKhoTheo.value[ma] = { loading: false, error: '', rows: Array.isArray(res) ? res : (res?.rows || []) }
  } catch (e) {
    soKhoTheo.value[ma] = { loading: false, error: e.message || 'Không tải được thẻ kho.', rows: [] }
  }
}

// --- "Xem chi tiết" — dòng này khớp với yêu cầu NÀO (08/09/2026) -------
//
// Thay hai bảng phụ cũ ("Đã khớp mã" + "Đang chờ Miyano xác nhận nguồn"). Hai
// bảng đó tồn tại vì dòng đã khớp không vào được bảng chính; nay `dong` đã
// nối chúng vào, giữ lại là in cùng một dòng hàng hai lần ở hai chỗ.
//
// Khoá theo `item_code`, cùng khuôn `dongMoRong` của sổ kho — nhưng là ref
// RIÊNG: hai thứ xổ ra ở cùng một dòng vì hai lý do khác nhau (sổ kho để
// quyết định số lượng, chi tiết yêu cầu để đối chiếu hàng), dùng chung một
// cờ thì mở cái này tắt cái kia.
const chiTietMoRong = ref({})
function toggleChiTietKhop(row) {
  chiTietMoRong.value[row.item_code] = !chiTietMoRong.value[row.item_code]
}
</script>

<template>
  <div class="card" style="padding: 0; overflow-x: auto">
    <!-- CR-04 §4 — dòng giải thích BA lý do, chỉ hiện khi có ít nhất một
         dòng không tra được. Đừng để quản lý tự đoán vì sao cột trống. -->
    <p v-if="coDongKhongTraDuoc" class="tag" style="margin: 10px 12px 0">
      Một số dòng hiện "—" (không tra được) vì: bệnh viện chưa mở kho trên cổng,
      vật tư kho chưa nối mã hàng, hoặc hàng này không có trong danh mục kho.
      "—" khác hẳn "0" — "0" nghĩa là hết hàng.
    </p>
    <table>
      <thead>
        <tr>
          <th>Mặt hàng</th>
          <th>ĐVT</th>
          <!-- CR-04 §3 — bốn cột căn cứ tồn kho, BÊN TRÁI "SL đề xuất". Gate
               theo `coCanCuKho` (điều kiện MÀN DUYỆT), không theo dữ liệu:
               xem lý do ở khai báo `coCanCuKho` trong <script setup>. -->
          <th v-if="coCanCuKho" class="right">Tồn hiện có</th>
          <th v-if="coCanCuKho" class="right">Đang về</th>
          <th v-if="coCanCuKho" class="right">Dùng TB/ngày</th>
          <th v-if="coCanCuKho" class="right">Còn dùng được</th>
          <!-- "NV đặt" (spec §3) CHÍNH LÀ cột "SL đề xuất" đã có — GIỮ
               NGUYÊN nhãn, không đổi tên: banner "Việc đang chờ bạn" phía
               trên (ChiTietYeuCau.vue) nói thẳng "Cột SL đề xuất khoá vĩnh
               viễn", và `title` ngay dưới nhắc lại đúng câu đó — đổi nhãn ở
               đây mà không đổi hai chỗ kia sẽ làm ba chỗ nói về CÙNG một
               cột bằng BA tên khác nhau. Dựng thêm một cột thứ SÁU song
               song thì in `so_luong_de_xuat` hai lần — không cột nào trong
               hai lựa chọn đó tốt hơn giữ nguyên. -->
          <th v-if="coPhieu" class="right">SL đề xuất</th>
          <th v-if="coCotDuyet" class="right">SL duyệt</th>
          <th v-if="coCotXinSua" class="right">SL xin sửa</th>
          <!-- Ruling preflight #2 — SỐ THẬT TRÊN ĐƠN, không phải `so_luong_
               duyet`. Hai con số này lệch nhau khi Miyano khớp một dòng gõ
               tay vào đơn (Ruling P51: `_gop_hoac_them_dong_hang` cộng
               thẳng vào `Sales Order Item.qty` mà không đụng cột duyệt).
               Với đơn cũ KHÔNG có phiếu, đây là cột số lượng DUY NHẤT —
               thiếu nó thì bảng in giá của một thứ không ai biết đặt bao
               nhiêu. -->
          <th v-if="coDon" class="right">SL đặt</th>
          <th v-if="coDon" class="right">Đơn giá</th>
          <th v-if="coDon" class="right">Thành tiền</th>
          <th v-if="coCotDaGiao" class="right">Đã giao</th>
          <!-- `min-width` bằng `rem` (không phải `px`) — co giãn theo cỡ
               chữ người dùng đặt trong trình duyệt, và là cột NÊN rộng khi
               còn chỗ. Bảng đã nằm trong khung `overflow-x: auto` nên đòi
               chỗ ở đây không đẩy cả trang cuộn ngang. -->
          <th v-if="coPhieu" style="min-width: 16rem">Ghi chú quản lý</th>
        </tr>
      </thead>
      <tbody>
        <!-- `dong` (không phải `phieu.items`/`don.items` trực tiếp) — nguồn
             dòng đã được quyết định ở computed `dong` phía trên: PHIẾU khi
             có phiếu, đơn khi không, để mỗi `<tr>` dưới đây không phải tự
             hỏi lại câu đó.

             CR-04 §6 — bọc trong `<template v-for>` (thay vì `<tr v-for>`
             thẳng) để chèn được một `<tr>` XỔ SỔ KHO ngay dưới, KHÔNG rời
             màn duyệt: quản lý đang cân nhắc cả đơn, rời màn là mất mạch. -->
        <template v-for="row in dong" :key="row.item_code">
        <tr
          :style="khongDuyet(row) ? 'text-decoration: line-through; color: var(--gray)' : ''"
        >
          <td>
            <b>{{ row.item_code }}</b>
            <template v-if="row.item_name"> — {{ row.item_name }}</template>
            <br />
            <span v-if="khongDuyet(row)" class="badge b-red" style="margin-top: 4px">Không duyệt</span>
            <span v-if="row.nguon_dong === 'Quản lý thêm'" class="badge b-purple" style="margin-top: 4px">Quản lý thêm</span>
            <!-- Nhãn + lối vào chi tiết cho dòng Miyano khớp từ hàng gõ tay
                 (chủ đầu tư 08/09/2026). Nhãn một mình chưa đủ: khoa gõ tên
                 hàng theo cách của họ, Miyano trả về một MÃ — không nói rõ
                 mã này khớp với yêu cầu nào thì khoa không nối lại được, mà
                 nối lại chính là việc bảng này sinh ra để làm. -->
            <template v-if="row.yeu_cau_khop">
              <span class="badge b-green" style="margin-top: 4px">Đã khớp với yêu cầu</span>
              <button
                type="button"
                class="nut-chi-tiet"
                :aria-expanded="chiTietMoRong[row.item_code] ? 'true' : 'false'"
                :aria-label="`Xem chi tiết yêu cầu đã khớp với ${row.item_code}`"
                @click="toggleChiTietKhop(row)"
              >{{ chiTietMoRong[row.item_code] ? '▾' : '▸' }} Xem chi tiết</button>
            </template>
          </td>
          <td>{{ row.dvt }}</td>
          <!-- CR-04 §3/§4 — bốn ô này đọc QUA `canCu(row)` (KHÔNG với thẳng
               `canCuKho[row.item_code]` rải rác), và dùng `fmtSl`/`fmtNgay`
               (KHÔNG `|| 0`) để phân biệt "không tra được" (—) với "0" (hết
               hàng). Chấm màu (§5) mang class ĐỘNG theo `canCu(row).muc` do
               SERVER trả, KHÔNG suy lại màu ở đây. -->
          <td v-if="coCanCuKho" class="right">
            <!-- Review (advisor) — KHÔNG `class="tag"` ở đây: `.tag` (style.
                 css) là 11px/xám, tức RA CHỮ NHỎ HƠN đúng con số CR-04 dựng
                 cột này để làm nổi bật, trong khi dòng KHÔNG tra được (nhánh
                 v-else, không có nút) lại in "—" ở cỡ chữ thường — nghịch
                 đảo đúng thứ tự quan trọng. Chỉ giữ style cục bộ báo hiệu
                 "bấm được" (con trỏ + gạch dưới), không đổi cỡ/màu chữ. -->
            <button
              v-if="coTheXoSo(row)"
              type="button"
              style="cursor: pointer; background: none; border: none; padding: 0; text-decoration: underline; font: inherit; color: inherit"
              :aria-label="`Xem sổ kho cho ${row.item_code}`"
              @click="toggleSoKho(row)"
            >{{ dongMoRong[row.item_code] ? '▾' : '▸' }} {{ fmtSl(canCu(row)?.ton) }}</button>
            <template v-else>{{ fmtSl(canCu(row)?.ton) }}</template>
          </td>
          <td v-if="coCanCuKho" class="right">{{ fmtSl(canCu(row)?.dang_ve) }}</td>
          <td v-if="coCanCuKho" class="right">{{ fmtSl(canCu(row)?.adu) }}</td>
          <td v-if="coCanCuKho" class="right">
            <span
              v-if="canCu(row)?.muc"
              class="muc-cham"
              :class="canCu(row).muc"
              :title="`Mức tồn trữ: ${canCu(row).muc}`"
            ></span>
            {{ fmtNgay(canCu(row)?.con_dung_duoc) }}
          </td>
          <td v-if="coPhieu" class="right" title="Khoá vĩnh viễn từ lúc gửi duyệt">
            {{ row.so_luong_de_xuat }}
            <span
              v-if="coCanCuKho && coCanhBaoDatKhiChuaCan(row)"
              title="Còn dùng được lâu mà vẫn đặt — xem kỹ"
              style="color: var(--orange)"
            > ⚠</span>
          </td>
          <!-- C1 (chép từ DeXuatDetail.vue) — nửa NHẬP LIỆU của thao tác mà
               nửa HIỂN THỊ (gạch ngang, badge "Không duyệt") đã render sẵn
               ở cột "Mặt hàng". KHÔNG `.number` trên v-model: xem
               `soDuyetMoi` ở trên (ô trống = "không đổi"). -->
          <td v-if="coCotDuyet" class="right">
            <!-- `!row.chi_tu_yeu_cau` — dòng Miyano khớp từ hàng gõ tay KHÔNG
                 có dòng tương ứng trên phiếu, nên không có `so_luong_duyet`
                 để sửa; `de_xuat_duyet` khớp payload theo `item_code` của
                 dòng PHIẾU và sẽ bỏ qua nó trong im lặng. Đưa ra một ô nhập
                 gõ vào không ăn thua là hứa suông với quản lý. -->
            <template v-if="quanLyDangDuyet && !row.chi_tu_yeu_cau">
              <input
                type="number" min="0" step="any"
                v-model="slDuyetSua[row.item_code]"
                :placeholder="String(row.so_luong_duyet)"
                :aria-label="`SL duyệt cho ${row.item_code}`"
                style="width: 90px; text-align: right"
              />
              <br v-if="soDuyetMoi(row) !== null" />
              <span v-if="laBoMatHang(row)" class="tag" style="color: var(--red)">
                Sẽ bỏ mặt hàng này khỏi đơn
              </span>
              <span v-else-if="soDuyetMoi(row) !== null" class="tag">
                Sẽ duyệt {{ soDuyetMoi(row) }} / xin {{ row.so_luong_de_xuat }}
              </span>
            </template>
            <template v-else-if="row.so_luong_duyet !== null && row.so_luong_duyet !== undefined">{{ row.so_luong_duyet }}</template>
            <span v-else class="tag" title="Dòng này Miyano khớp từ yêu cầu gõ tay của khoa — không đi qua bước đóng dấu SL duyệt">—</span>
          </td>
          <td v-if="coCotXinSua" class="right">
            <span v-if="row.so_luong_xin_sua !== null && row.so_luong_xin_sua !== undefined">{{ row.so_luong_xin_sua }}</span>
            <span v-else class="tag">—</span>
          </td>
          <!-- Ruling preflight #2 — SL đặt: chỉ "—" khi dòng KHÔNG có mặt
               trên đơn (quản lý đã hạ về 0 lúc duyệt); `null` và "chưa có
               đơn" là hai khoá khác nhau ở tầng server, ở đây gộp lại vì cả
               hai đều nghĩa "không có số thật để in". -->
          <td v-if="coDon" class="right">
            <template v-if="row.so_luong_tren_don !== null && row.so_luong_tren_don !== undefined">{{ row.so_luong_tren_don }}</template>
            <template v-else>—</template>
          </td>
          <!-- Ruling preflight #1 — "—" chứ KHÔNG "0 ₫" cho dòng chưa có
               trên đơn. Backend cố ý trả `null` (không phải `0`) ở
               `de_xuat_chi_tiet`; `fmtVND(null)` tự quy về "0 ₫" (xem
               `format.js`: `Number(v || 0)`) nên PHẢI chặn ở đây, gọi thẳng
               `fmtVND` sẽ nói với khoa rằng hàng của họ giá 0. -->
          <td v-if="coDon" class="right">
            <!-- Giá 0 trên một dòng ĐÃ KHỚP MÃ nghĩa là MIYANO CHƯA BÁO GIÁ,
                 không phải "miễn phí": `_gop_hoac_them_dong_hang` chỉ tự lấy
                 đơn giá khi mặt hàng thuộc một hợp đồng khung còn hiệu lực,
                 ngoài ra để 0 và chờ Miyano điền. Câu này chuyển nguyên từ
                 bảng "Đã khớp mã" cũ — bỏ nó lúc gộp bảng là nói với khoa
                 rằng hàng của họ giá 0. Chỉ áp cho dòng khớp: một dòng hàng
                 thường giá 0 là chuyện khác (hàng tặng kèm), không đoán hộ. -->
            <template v-if="row.yeu_cau_khop && !row.don_gia_tren_don">
              <span class="tag">Chờ Miyano báo giá</span>
            </template>
            <template v-else-if="row.don_gia_tren_don !== null && row.don_gia_tren_don !== undefined">{{ fmtVND(row.don_gia_tren_don) }}</template>
            <template v-else>—</template>
          </td>
          <td v-if="coDon" class="right">
            <template v-if="row.thanh_tien_tren_don !== null && row.thanh_tien_tren_don !== undefined">{{ fmtVND(row.thanh_tien_tren_don) }}</template>
            <template v-else>—</template>
          </td>
          <td v-if="coCotDaGiao" class="right">
            <template v-if="row.da_giao_tren_don !== null && row.da_giao_tren_don !== undefined">{{ row.da_giao_tren_don }}</template>
            <template v-else>—</template>
          </td>
          <!-- C1 (chép từ DeXuatDetail.vue) — cột riêng ở bảng gộp thay vì
               nằm lồng trong cột "Mặt hàng" như bản gốc, vì header ở đây
               đã có `<th>Ghi chú quản lý</th>` của riêng nó. -->
          <td v-if="coPhieu">
            <!-- Cùng chốt `!row.chi_tu_yeu_cau` của ô SL duyệt: `de_xuat_duyet`
                 khớp payload theo `item_code` của dòng PHIẾU, nên ghi chú gõ
                 vào một dòng chỉ có trên đơn sẽ rơi im lặng. Hôm nay hai thứ
                 loại trừ nhau (`quanLyDangDuyet` chỉ bật ở "Chờ duyệt", lúc đó
                 chưa có đơn nên chưa có dòng khớp nào) — chốt đứng đây để một
                 lần mở màn duyệt cho trạng thái khác không lặng lẽ dựng ra ô
                 nhập gõ vào không ăn thua. -->
            <template v-if="quanLyDangDuyet && !row.chi_tu_yeu_cau">
              <!-- `textarea` hai dòng thay cho `input` một dòng, và BỎ
                   `max-width: 340px` (chủ đầu tư 05/09/2026: "cho to ra").
                   Ghi chú duyệt là chỗ quản lý giải thích VÌ SAO cắt số —
                   một ô một dòng cắt cụt câu ở ký tự thứ 40 khiến người ta
                   viết cụt theo, và lý do cắt số là thứ khoa sẽ đọc lại.
                   `width: 100%` + `min-width` trên `<th>` cho cột tự co giãn
                   theo bề ngang thật thay vì bị ghim ở một con số px. -->
              <textarea
                rows="2"
                v-model="ghiChuSua[row.item_code]"
                placeholder="Ghi chú của quản lý (tuỳ chọn)"
                :aria-label="`Ghi chú quản lý cho ${row.item_code}`"
                style="width: 100%; margin-top: 6px; resize: vertical"
              ></textarea>
            </template>
            <template v-else-if="row.ghi_chu_quan_ly">
              <span class="tag">Ghi chú quản lý: {{ row.ghi_chu_quan_ly }}</span>
            </template>
          </td>
        </tr>
        <!-- Chi tiết "khớp với yêu cầu nào" — xổ NGAY DƯỚI dòng hàng, cùng
             kiểu sổ kho của CR-04: câu hỏi sinh ra khi mắt đang ở dòng đó,
             trả lời ở một bảng khác dưới trang là bắt người ta cuộn đi rồi
             cuộn về. Vẽ bằng `TheHangMoi` — ĐÚNG component khối "hàng chưa
             có trong hệ thống" đang dùng, nên chín trường và ảnh hiện y hệt
             ở cả trước lẫn sau khi khớp mã. -->
        <tr v-if="row.yeu_cau_khop && chiTietMoRong[row.item_code]">
          <td :colspan="soCotTong" style="background: #f8fafc">
            <p class="tag" style="margin: 0 0 0.5rem">
              Dòng hàng này Miyano khớp từ {{ row.yeu_cau_khop.length }} yêu cầu
              hàng chưa có mã của khoa:
            </p>
            <TheHangMoi
              v-for="(y, k) in row.yeu_cau_khop"
              :key="y.name || k"
              :d="y"
              :de-xuat="deXuat"
            />
          </td>
        </tr>
        <!-- CR-04 §6 — thẻ kho (nhập/xuất/tồn luỹ kế) xổ NGAY DƯỚI dòng
             hàng, không rời màn duyệt. Chỉ tải khi mở LẦN ĐẦU
             (`toggleSoKho` giữ cache theo item_code); dùng lại
             `THE_KHO_COLUMNS`/cách render của BaoCaoNXT.vue tab "Thẻ kho" —
             không tự khai một bảng cột thứ hai. Khung `overflow-x: auto`
             RIÊNG cho bảng con này — bảng cha đã cuộn ngang trong khung của
             chính nó, một bảng con rộng hơn không được kéo cả trang cuộn
             theo trên điện thoại. -->
        <tr v-if="coCanCuKho && dongMoRong[row.item_code]">
          <td :colspan="soCotTong" style="background: #f8fafc">
            <div v-if="soKhoTheo[row.item_code]?.loading" class="loading">Đang tải sổ kho…</div>
            <div v-else-if="soKhoTheo[row.item_code]?.error" class="empty">{{ soKhoTheo[row.item_code].error }}</div>
            <div v-else-if="!soKhoTheo[row.item_code]?.rows?.length" class="empty">
              Không có phát sinh trong 90 ngày gần đây.
            </div>
            <div v-else style="overflow-x: auto">
              <table>
                <thead>
                  <tr>
                    <th
                      v-for="c in THE_KHO_COLUMNS" :key="c.field"
                      :class="{ right: ['sl_nhap', 'sl_xuat', 'ton_luy_ke'].includes(c.field) }"
                    >{{ c.label }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(r, idx) in soKhoTheo[row.item_code].rows" :key="idx">
                    <td
                      v-for="c in THE_KHO_COLUMNS" :key="c.field"
                      :class="{ right: ['sl_nhap', 'sl_xuat', 'ton_luy_ke'].includes(c.field) }"
                    >
                      <template v-if="c.field === 'ngay'">{{ fmtDate(r.ngay) }}</template>
                      <template v-else-if="c.field === 'chung_tu'"><b>{{ r.chung_tu }}</b></template>
                      <template v-else-if="['sl_nhap', 'sl_xuat', 'ton_luy_ke'].includes(c.field)">{{ fmtSl(r[c.field]) }}</template>
                      <template v-else>{{ r[c.field] || '—' }}</template>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </td>
        </tr>
        </template>
        <tr v-if="!dong.length">
          <td :colspan="soCotTong" class="tag">Chưa có dòng hàng nào.</td>
        </tr>
      </tbody>
    </table>

  </div>
</template>

<style scoped>
/* Nút chữ, không phải nút khối: nó nằm trong ô "Mặt hàng" cạnh tên hàng và
   nhãn — một nút có nền/viền ở đó sẽ nặng hơn chính tên hàng. Kích thước
   theo `rem` để co giãn theo cỡ chữ trình duyệt (chủ đầu tư 05/09/2026). */
.nut-chi-tiet {
  display: inline-block;
  margin-top: 0.25rem;
  margin-left: 0.375rem;
  padding: 0;
  background: none;
  border: none;
  font: inherit;
  font-size: 0.8rem;
  color: var(--blue, #2563eb);
  text-decoration: underline;
  cursor: pointer;
}
</style>
