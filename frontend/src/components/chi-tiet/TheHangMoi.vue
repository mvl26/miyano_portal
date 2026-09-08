<script setup>
// MỘT thẻ "hàng chưa có trong hệ thống" — chín trường CR-03 + ảnh.
//
// TÁCH RA TỪ `KhoiHangMoi.vue` (chủ đầu tư 08/09/2026: "sau khi đã khớp mã
// hàng từ Miyano thì chỉ hiển thị đúng 1 bảng"). Từ bản đó, chín trường này
// phải vẽ được ở HAI chỗ:
//
//   * `KhoiHangMoi.vue` — khối riêng, cho dòng Miyano CHƯA khớp mã (quản lý
//     còn phải xem kỹ trước khi duyệt);
//   * `BangMatHang.vue` — xổ ra ngay dưới dòng hàng khi bấm "Xem chi tiết",
//     cho dòng ĐÃ khớp (trả lời "dòng này khớp với yêu cầu nào").
//
// Chép đôi phần vẽ này là chép đôi cả `danhSachAnh` (bắt lỗi JSON hỏng) lẫn
// `anhUrl` (đường ảnh riêng tư) — hai chỗ dễ trôi lệch nhất, và lệch thì
// một trong hai màn lặng lẽ mất ảnh.
import { fmtVND } from '../../format'

const props = defineProps({
  d: { type: Object, required: true },
  deXuat: { type: String, default: '' },
  // Nhãn trạng thái ở đầu thẻ, rỗng = không vẽ. Cần vì cùng một thẻ này nói
  // hai chuyện khác nhau tuỳ chỗ đứng: ở khối riêng SAU khi đơn đã duyệt nó
  // là "Miyano đang tìm nguồn"; ở khối xổ "Xem chi tiết" của bảng chính thì
  // dòng đã khớp rồi, thêm nhãn vào là nói ngược.
  nhan: { type: String, default: '' },
})

// Ảnh riêng tư đi qua endpoint kiểm sở hữu TỪNG LẦN XEM. KHÔNG trỏ thẳng
// `/private/files/…`: role `Customer` có ZERO DocPerm trên `Portal De Xuat
// Mua`, nên đường mặc định của Frappe 403 với CHÍNH người vừa tải ảnh lên.
function anhUrl(fileUrl) {
  return (
    '/api/method/miyano_portal.api.portal.portal_dat_ngoai_xem_anh?de_xuat=' +
    encodeURIComponent(props.deXuat) +
    '&file_url=' +
    encodeURIComponent(fileUrl)
  )
}

// Có ít nhất một trong bốn trường "thông tin trên hộp"? Không có thì KHÔNG
// dựng lưới rỗng — một khối chỉ có khoảng trắng làm người đọc tưởng dữ liệu
// bị mất, trong khi thật ra nhân viên không khai (cả bốn đều tuỳ chọn).
const coThongTinHop = () =>
  !!(props.d?.model_ma || props.d?.hang_san_xuat || props.d?.nuoc_san_xuat || props.d?.quy_cach)

function danhSachAnh() {
  if (!props.d?.anh) return []
  try {
    const ds = JSON.parse(props.d.anh)
    return Array.isArray(ds) ? ds.filter((x) => typeof x === 'string' && x) : []
  } catch {
    // Field hỏng (bản ghi cũ, ai đó gõ tay trên Desk) KHÔNG được làm chết cả
    // khối — quản lý vẫn phải đọc được các trường còn lại để mà duyệt.
    return []
  }
}
</script>

<template>
  <div class="hm-the">
    <!-- Đầu thẻ: tên hàng + số lượng. `gap` + `flex-wrap` để trên màn
         hẹp số lượng xuống dòng thay vì bóp tên hàng. -->
    <div class="hm-dau">
      <b>{{ d.ten_hang }}</b>
      <span class="hm-phai">
        <span v-if="nhan" class="badge b-gray">{{ nhan }}</span>
        <span class="tag hm-sl">{{ d.so_luong }} {{ d.dvt }}</span>
      </span>
    </div>

    <!-- ẢNH TRƯỚC MỌI THỨ: một tấm ảnh nhãn hộp nói được nhiều hơn cả
         bốn trường chữ, và nó là thứ CR-03 bắt buộc phải có.
         Lưới `auto-fill` + `minmax(min(100%, 7rem), 1fr)`: một ảnh trên
         màn rất hẹp chiếm trọn bề ngang, nhiều ảnh thì tự xếp thành
         hàng — KHÔNG ghim 96px như bản trước, vốn tràn trên điện thoại
         nhỏ và phí chỗ trên màn rộng. -->
    <div v-if="danhSachAnh().length" class="hm-anh">
      <a
        v-for="(u, k) in danhSachAnh()"
        :key="k"
        :href="anhUrl(u)"
        target="_blank"
        rel="noopener"
      >
        <img :src="anhUrl(u)" alt="Ảnh mặt hàng" />
      </a>
    </div>
    <p v-else-if="d.khong_co_anh" class="tag hm-khong-anh">
      ⚠ Nhân viên không chụp được ảnh — mô tả bằng lời:
    </p>
    <p v-if="d.khong_co_anh && d.mo_ta_nhan_dang" class="hm-mo-ta">
      {{ d.mo_ta_nhan_dang }}
    </p>

    <!-- LƯỚI NHÃN / GIÁ TRỊ thay cho dãy chip dính nhau (chủ đầu tư
         05/09/2026: "sắp xếp lại cách hiển thị các trường").
         Bản trước xếp bốn trường thành `<span class="tag">Model: X</span>`
         cạnh nhau — mọi trường cùng một sức nặng thị giác, nhãn và giá
         trị cùng cỡ cùng màu, nên mắt phải đọc từng chữ mới tách được
         đâu là nhãn đâu là dữ liệu.
         Ở đây nhãn nhỏ/nhạt/viết hoa nằm TRÊN, giá trị đậm nằm DƯỚI —
         quét dọc một cột là đọc được hết giá trị.
         `auto-fit` + `minmax`: 1 cột trên điện thoại, 2-3 cột trên màn
         rộng, tự quyết theo bề ngang thật chứ không theo breakpoint
         đoán trước. -->
    <dl v-if="coThongTinHop()" class="hm-luoi">
      <div v-if="d.model_ma">
        <dt>Model / mã catalogue</dt>
        <dd>{{ d.model_ma }}</dd>
      </div>
      <div v-if="d.hang_san_xuat">
        <dt>Hãng sản xuất</dt>
        <dd>{{ d.hang_san_xuat }}</dd>
      </div>
      <div v-if="d.nuoc_san_xuat">
        <dt>Nước sản xuất</dt>
        <dd>{{ d.nuoc_san_xuat }}</dd>
      </div>
      <div v-if="d.quy_cach">
        <dt>Quy cách đóng gói</dt>
        <dd>{{ d.quy_cach }}</dd>
      </div>
    </dl>

    <!-- Hai ô thương mại TÁCH KHỐI RIÊNG, có nhãn nói rõ nguồn: đây là
         giá bệnh viện ĐANG MUA của nhà cung cấp khác, KHÔNG phải giá
         Miyano báo. Trộn chung lưới trên là để quản lý đọc nhầm thành
         báo giá — và một con số tiền đọc nhầm nguồn thì hỏng nặng. -->
    <dl v-if="d.ncc_hien_tai || d.gia_hien_tai" class="hm-luoi hm-thuong-mai">
      <div v-if="d.ncc_hien_tai">
        <dt>Khoa đang mua của</dt>
        <dd>{{ d.ncc_hien_tai }}</dd>
      </div>
      <div v-if="d.gia_hien_tai">
        <dt>Giá đang mua</dt>
        <dd>{{ fmtVND(d.gia_hien_tai) }}</dd>
      </div>
    </dl>

    <p v-if="d.ghi_chu" class="tag hm-ghi-chu">{{ d.ghi_chu }}</p>
  </div>
</template>

<style scoped>
/* MỌI kích thước dưới đây dùng `rem`/`%`/`clamp()`, KHÔNG dùng `px` cứng —
   chủ đầu tư 05/09/2026: "tất cả những gì hiển thị đều phải scale theo màn
   hình". `rem` còn co giãn theo cỡ chữ người dùng đặt trong trình duyệt,
   thứ `px` bỏ qua hoàn toàn. */
.hm-the {
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  padding: clamp(0.6rem, 2vw, 1rem);
  margin-bottom: 0.75rem;
}
.hm-the:last-child { margin-bottom: 0; }

.hm-dau {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.25rem 0.75rem;
}
.hm-dau b { font-size: clamp(0.95rem, 2.4vw, 1.05rem); }
.hm-sl { white-space: nowrap; }
.hm-phai {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.25rem 0.5rem;
}

.hm-anh {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 7rem), 1fr));
  gap: 0.5rem;
  margin-top: 0.6rem;
}
.hm-anh img {
  width: 100%;
  aspect-ratio: 1;
  object-fit: cover;
  border: 1px solid var(--line);
  border-radius: 0.375rem;
  display: block;
}

.hm-khong-anh { margin: 0.6rem 0 0; }
.hm-mo-ta { margin: 0.25rem 0 0; }

.hm-luoi {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 12rem), 1fr));
  gap: 0.5rem 1.25rem;
  margin: 0.75rem 0 0;
}
.hm-luoi dt {
  font-size: 0.7rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--muted, #6b7280);
  margin: 0;
}
.hm-luoi dd {
  margin: 0.1rem 0 0;
  font-weight: 500;
  overflow-wrap: anywhere; /* mã catalogue dài không đẩy vỡ lưới */
}

/* Khối thương mại tách bằng một đường kẻ mảnh — đủ để mắt biết đây là nhóm
   khác, không cần thêm một khung viền thứ hai lồng trong thẻ. */
.hm-thuong-mai {
  border-top: 1px dashed var(--line);
  padding-top: 0.6rem;
}

.hm-ghi-chu { margin: 0.6rem 0 0; }
</style>
