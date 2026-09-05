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
})

// Đơn cũ không có phiếu (~102 đơn trước luồng duyệt) — dòng lấy từ đơn, và
// hai cột của phiếu tự vắng mặt theo `coPhieu` bên dưới.
const dong = computed(() => {
  if (props.phieu) return props.phieu.items || []
  return (props.don?.items || []).map((it) => ({
    item_code: it.item_code,
    item_name: it.item_name,
    dvt: it.uom,
    so_luong_tren_don: it.qty,   // Ruling preflight #2 — nuôi cột "SL đặt"
    don_gia_tren_don: it.rate,
    thanh_tien_tren_don: it.amount,
    da_giao_tren_don: it.delivered_qty,
  }))
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

// Dòng đặt ngoài sống trên ĐƠN (`don.dat_ngoai`), không trên phiếu — tách
// theo `da_xu_ly` đúng cách OrderDetail.vue đang làm (review I-4): dòng đã
// khớp mã KHÔNG được đọc như đang chờ, nhét chung một tiêu đề "đang chờ"
// là lỗi đã phải sửa một lần rồi.
const datNgoaiDaKhop = computed(() => (props.don?.dat_ngoai || []).filter((d) => d.da_xu_ly))
const datNgoaiChoXuLy = computed(() => (props.don?.dat_ngoai || []).filter((d) => !d.da_xu_ly))
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
          <th v-if="coPhieu">Ghi chú quản lý</th>
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
            <template v-if="quanLyDangDuyet">
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
            <template v-else>{{ row.so_luong_duyet }}</template>
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
            <template v-if="row.don_gia_tren_don !== null && row.don_gia_tren_don !== undefined">{{ fmtVND(row.don_gia_tren_don) }}</template>
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
            <template v-if="quanLyDangDuyet">
              <input
                type="text"
                v-model="ghiChuSua[row.item_code]"
                placeholder="Ghi chú của quản lý (tuỳ chọn)"
                :aria-label="`Ghi chú quản lý cho ${row.item_code}`"
                style="width: 100%; max-width: 340px; margin-top: 6px"
              />
            </template>
            <template v-else-if="row.ghi_chu_quan_ly">
              <span class="tag">Ghi chú quản lý: {{ row.ghi_chu_quan_ly }}</span>
            </template>
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

    <!-- Dòng đặt ngoài: hàng khách gõ tay chưa có mã, sống trên ĐƠN chứ
         không trên phiếu. Bảng con RIÊNG, không gộp vào bảng trên — chúng
         là một loại dòng khác ("Miyano đang tìm nguồn"), nhét chung sẽ nói
         sai về chúng. Tách tiếp theo `da_xu_ly` như OrderDetail.vue đã
         làm (review I-4): dòng đã khớp mã KHÔNG được đọc như đang chờ. -->
    <template v-if="datNgoaiDaKhop.length">
      <h4 style="margin: 14px 12px 6px">Đã khớp mã (từ yêu cầu đặt ngoài)</h4>
      <table>
        <thead>
          <tr><th>Mã đã khớp</th><th>Yêu cầu của bạn</th><th>ĐVT</th><th class="right">SL</th></tr>
        </thead>
        <tbody>
          <tr v-for="(d, i) in datNgoaiDaKhop" :key="'khop-' + i">
            <td><b>{{ d.item_khop }}</b> <span class="badge b-green">Đã tìm được nguồn</span></td>
            <td>
              <span class="tag">(từ yêu cầu: {{ d.ten_hang }})</span>
              <template v-if="d.ghi_chu"><br /><span class="tag">{{ d.ghi_chu }}</span></template>
            </td>
            <td>{{ d.dvt }}</td>
            <td class="right">{{ d.so_luong }}</td>
          </tr>
        </tbody>
      </table>
    </template>

    <template v-if="datNgoaiChoXuLy.length">
      <h4 style="margin: 14px 12px 6px">Đang chờ Miyano xác nhận nguồn</h4>
      <table>
        <thead>
          <tr><th>Tên hàng</th><th>ĐVT</th><th class="right">SL</th><th>Tình trạng</th></tr>
        </thead>
        <tbody>
          <tr v-for="(d, i) in datNgoaiChoXuLy" :key="i">
            <td>{{ d.ten_hang }}<br /><span v-if="d.ghi_chu" class="tag">{{ d.ghi_chu }}</span></td>
            <td>{{ d.dvt }}</td>
            <td class="right">{{ d.so_luong }}</td>
            <td><span class="badge b-gray">Miyano đang tìm nguồn</span></td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>
