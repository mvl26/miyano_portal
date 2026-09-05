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

      <div
        v-for="(d, i) in dong"
        :key="d.name || i"
        class="card"
        style="margin-bottom: 10px"
      >
        <div class="sb">
          <b>{{ d.ten_hang }}</b>
          <span class="tag">{{ d.so_luong }} {{ d.dvt }}</span>
        </div>

        <!-- Ảnh ĐẶT TRÊN các ô mô tả: một tấm ảnh nhãn hộp nói được nhiều hơn
             cả bốn trường chữ, và nó là thứ CR-03 bắt buộc phải có. -->
        <div
          v-if="danhSachAnh(d).length"
          style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px"
        >
          <a
            v-for="(u, k) in danhSachAnh(d)"
            :key="k"
            :href="anhUrl(u)"
            target="_blank"
            rel="noopener"
          >
            <img
              :src="anhUrl(u)"
              alt="Ảnh mặt hàng"
              style="width: 96px; height: 96px; object-fit: cover; border: 1px solid var(--line); border-radius: 6px"
            />
          </a>
        </div>
        <p v-else-if="d.khong_co_anh" class="tag" style="margin-top: 8px">
          ⚠ Không có ảnh — nhân viên mô tả bằng lời:
        </p>
        <p v-if="d.khong_co_anh && d.mo_ta_nhan_dang" style="margin: 4px 0 0">
          {{ d.mo_ta_nhan_dang }}
        </p>

        <!-- Bốn ô "thông tin trên hộp". Chỉ hiện ô CÓ giá trị: một hàng nhãn
             với ô trống bên cạnh làm quản lý phải đọc qua chỗ trống để tìm
             chỗ có chữ. -->
        <div class="sb" style="flex-wrap: wrap; gap: 4px 18px; margin-top: 10px">
          <span v-if="d.model_ma" class="tag">Model / mã: <b>{{ d.model_ma }}</b></span>
          <span v-if="d.hang_san_xuat" class="tag">Hãng: <b>{{ d.hang_san_xuat }}</b></span>
          <span v-if="d.nuoc_san_xuat" class="tag">Nước SX: <b>{{ d.nuoc_san_xuat }}</b></span>
          <span v-if="d.quy_cach" class="tag">Quy cách: <b>{{ d.quy_cach }}</b></span>
        </div>

        <!-- Hai ô thương mại tách riêng, có nhãn nói rõ nguồn: đây là thông
             tin bệnh viện tự khai về nhà cung cấp hiện tại, không phải giá
             Miyano báo. Trộn chung là để quản lý đọc nhầm thành báo giá. -->
        <div
          v-if="d.ncc_hien_tai || d.gia_hien_tai"
          class="sb"
          style="flex-wrap: wrap; gap: 4px 18px; margin-top: 6px"
        >
          <span v-if="d.ncc_hien_tai" class="tag">
            Khoa đang mua của: <b>{{ d.ncc_hien_tai }}</b>
          </span>
          <span v-if="d.gia_hien_tai" class="tag">
            Giá đang mua: <b>{{ fmtVND(d.gia_hien_tai) }}</b>
          </span>
        </div>

        <p v-if="d.ghi_chu" class="tag" style="margin: 6px 0 0">{{ d.ghi_chu }}</p>
      </div>
    </div>
  </template>
</template>
