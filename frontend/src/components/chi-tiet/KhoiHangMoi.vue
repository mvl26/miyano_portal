<script setup>
// Khối "Hàng chưa có trong hệ thống" — HIỆN RIÊNG cho quản lý xem trước khi
// duyệt.
//
// VÌ SAO CÓ KHỐI NÀY (chủ đầu tư báo 05/09/2026): quản lý duyệt KHÔNG NHÌN
// THẤY các dòng hàng gõ tay. Nguyên nhân: `BangMatHang.vue` đọc
// `don.dat_ngoai` — tức từ ĐƠN HÀNG, mà đơn chỉ tồn tại SAU khi duyệt. Ở
// "Chờ duyệt" chỉ có PHIẾU, nên đúng khoảnh khắc quản lý bấm duyệt thì các
// dòng đó vô hình. Họ duyệt một thứ họ không nhìn thấy.
//
// Dữ liệu LUÔN CÓ SẴN — `de_xuat_chi_tiet` trả đủ chín trường CR-03 (đã đo,
// không suy đoán). Lỗi thuần ở chỗ đọc nhầm nguồn.
//
// VÌ SAO RIÊNG, KHÔNG NHÉT VÀO BẢNG: chủ đầu tư chốt, và lý do của chính họ
// đứng vững — "hàng này có nhiều trường và là hàng mới cần xem xét kĩ".
// Chín trường nhồi vào một hàng của bảng thì hoặc bảng tràn ngang, hoặc phải
// giấu bớt trường — mà giấu bớt đúng là thứ vừa gây ra lỗi này.
import { fmtVND } from '../../format'

const props = defineProps({
  dong: { type: Array, default: () => [] },
  deXuat: { type: String, default: '' },
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
function coThongTinHop(d) {
  return !!(d?.model_ma || d?.hang_san_xuat || d?.nuoc_san_xuat || d?.quy_cach)
}

function danhSachAnh(d) {
  if (!d?.anh) return []
  try {
    const ds = JSON.parse(d.anh)
    return Array.isArray(ds) ? ds.filter((x) => typeof x === 'string' && x) : []
  } catch {
    // Field hỏng (bản ghi cũ, ai đó gõ tay trên Desk) KHÔNG được làm chết cả
    // khối — quản lý vẫn phải đọc được các trường còn lại để mà duyệt.
    return []
  }
}
</script>

<template>
  <template v-if="dong && dong.length">
    <div class="card mb10">
      <div class="h3">Hàng chưa có trong hệ thống — cần xem kỹ trước khi duyệt</div>
      <p class="tag" style="margin: 4px 0 10px">
        {{ dong.length }} mặt hàng nhân viên tự khai vì không tìm thấy trong danh
        mục. Miyano sẽ tìm nguồn và báo giá sau khi được duyệt.
      </p>

      <div v-for="(d, i) in dong" :key="d.name || i" class="hm-the">
        <!-- Đầu thẻ: tên hàng + số lượng. `gap` + `flex-wrap` để trên màn
             hẹp số lượng xuống dòng thay vì bóp tên hàng. -->
        <div class="hm-dau">
          <b>{{ d.ten_hang }}</b>
          <span class="tag hm-sl">{{ d.so_luong }} {{ d.dvt }}</span>
        </div>

        <!-- ẢNH TRƯỚC MỌI THỨ: một tấm ảnh nhãn hộp nói được nhiều hơn cả
             bốn trường chữ, và nó là thứ CR-03 bắt buộc phải có.
             Lưới `auto-fill` + `minmax(min(100%, 7rem), 1fr)`: một ảnh trên
             màn rất hẹp chiếm trọn bề ngang, nhiều ảnh thì tự xếp thành
             hàng — KHÔNG ghim 96px như bản trước, vốn tràn trên điện thoại
             nhỏ và phí chỗ trên màn rộng. -->
        <div v-if="danhSachAnh(d).length" class="hm-anh">
          <a
            v-for="(u, k) in danhSachAnh(d)"
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
        <dl v-if="coThongTinHop(d)" class="hm-luoi">
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
    </div>
  </template>
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
