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
import { computed } from 'vue'
import { fmtVND } from '../../format'

const props = defineProps({
  phieu: { type: Object, default: null },
  don: { type: Object, default: null },
  quanLyDangDuyet: { type: Boolean, default: false },
  slDuyetSua: { type: Object, default: () => ({}) },
  ghiChuSua: { type: Object, default: () => ({}) },
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
  return n
})

// Dòng đặt ngoài sống trên ĐƠN (`don.dat_ngoai`), không trên phiếu — tách
// theo `da_xu_ly` đúng cách OrderDetail.vue đang làm (review I-4): dòng đã
// khớp mã KHÔNG được đọc như đang chờ, nhét chung một tiêu đề "đang chờ"
// là lỗi đã phải sửa một lần rồi.
const datNgoaiDaKhop = computed(() => (props.don?.dat_ngoai || []).filter((d) => d.da_xu_ly))
const datNgoaiChoXuLy = computed(() => (props.don?.dat_ngoai || []).filter((d) => !d.da_xu_ly))
</script>

<template>
  <div class="card" style="padding: 0; overflow-x: auto">
    <table>
      <thead>
        <tr>
          <th>Mặt hàng</th>
          <th>ĐVT</th>
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
        <!-- CHÉP các ô từ bảng cũ của DeXuatDetail.vue (gạch ngang + nhãn
             "Không duyệt" theo `khongDuyet(row)`, ô nhập SL duyệt và ô ghi
             chú khi `quanLyDangDuyet`) và thêm ba ô mới: đơn giá, thành
             tiền, đã giao — dùng `fmtVND` cho hai ô tiền.
             Ô tiền của dòng KHÔNG có trên đơn in "—", KHÔNG in "0 ₫". -->
        <tr
          v-for="row in dong"
          :key="row.item_code"
          :style="khongDuyet(row) ? 'text-decoration: line-through; color: var(--gray)' : ''"
        >
          <td>
            <b>{{ row.item_code }}</b>
            <template v-if="row.item_name"> — {{ row.item_name }}</template>
            <br v-if="khongDuyet(row) || row.nguon_dong === 'Quản lý thêm'" />
            <span v-if="khongDuyet(row)" class="badge b-red" style="margin-top: 4px">Không duyệt</span>
            <span v-if="row.nguon_dong === 'Quản lý thêm'" class="badge b-purple" style="margin-top: 4px">Quản lý thêm</span>
          </td>
          <td>{{ row.dvt }}</td>
          <td v-if="coPhieu" class="right" title="Khoá vĩnh viễn từ lúc gửi duyệt">{{ row.so_luong_de_xuat }}</td>
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
                style="width: 100%; max-width: 340px"
              />
            </template>
            <template v-else-if="row.ghi_chu_quan_ly">
              <span class="tag">Ghi chú quản lý: {{ row.ghi_chu_quan_ly }}</span>
            </template>
          </td>
        </tr>
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
