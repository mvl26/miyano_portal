<script setup>
// Bộ hiện CHI TIẾT MỘT dòng "hàng chưa có trong hệ thống" — ảnh + chín
// trường CR-03.
//
// ĐỔI VAI (05/09/2026, gộp bảng — chủ đầu tư báo *"anh chưa ưng hiển thị 2
// bảng xem hàng sau khi tạo phiếu"*): trước bản này khối tự vẽ CẢ danh sách
// N dòng, đứng RIÊNG một khối ngoài bảng mặt hàng (bản `b4d3325`, đúng theo
// yêu cầu TRƯỚC ĐÓ của chính chủ đầu tư — "hàng này có nhiều trường và là
// hàng mới cần xem xét kĩ"). Hai yêu cầu không mâu thuẫn: `BangMatHang.vue`
// nay gộp dòng "hàng mới" vào CÙNG một bảng (mang nhãn "hàng mới" NỔI, xổ
// sẵn khi phiếu "Chờ duyệt"), và gọi ĐÚNG component này làm NỘI DUNG XỔ của
// MỘT dòng — giống hệt cách sổ kho CR-04 xổ tại dòng cho hàng đã có mã. Xem
// chú thích `dongHangMoi`/`moRongHangMoi` trong BangMatHang.vue.
//
// Phần render CHÍN TRƯỜNG + ảnh GIỮ NGUYÊN — nó đã đúng (đo được bằng test,
// không suy đoán lại), CHỈ đổi HÌNH DẠNG props: một OBJECT (một dòng), không
// còn một MẢNG N dòng. Bỏ vòng lặp `v-for`, bỏ khung `.card` ngoài, bỏ tiêu
// đề khối ("Hàng chưa có trong hệ thống…") — ba thứ đó nay do bảng/dòng bảng
// đảm nhiệm (nhãn "hàng mới" + khung nền của `<tr>` xổ ra).
import { fmtVND } from '../../format'

const props = defineProps({
  dong: { type: Object, default: null }, // MỘT dòng dat_ngoai — KHÔNG còn là mảng
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

function danhSachAnh() {
  if (!props.dong?.anh) return []
  try {
    const ds = JSON.parse(props.dong.anh)
    return Array.isArray(ds) ? ds.filter((x) => typeof x === 'string' && x) : []
  } catch {
    // Field hỏng (bản ghi cũ, ai đó gõ tay trên Desk) KHÔNG được làm chết cả
    // khối — quản lý vẫn phải đọc được các trường còn lại để mà duyệt.
    return []
  }
}
</script>

<template>
  <div v-if="dong">
    <!-- Ảnh ĐẶT TRÊN các ô mô tả: một tấm ảnh nhãn hộp nói được nhiều hơn
         cả bốn trường chữ, và nó là thứ CR-03 bắt buộc phải có. -->
    <div
      v-if="danhSachAnh().length"
      style="display: flex; flex-wrap: wrap; gap: 8px"
    >
      <a
        v-for="(u, k) in danhSachAnh()"
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
    <p v-else-if="dong.khong_co_anh" class="tag" style="margin-top: 4px">
      ⚠ Không có ảnh — nhân viên mô tả bằng lời:
    </p>
    <p v-if="dong.khong_co_anh && dong.mo_ta_nhan_dang" style="margin: 4px 0 0">
      {{ dong.mo_ta_nhan_dang }}
    </p>

    <!-- Bốn ô "thông tin trên hộp". Chỉ hiện ô CÓ giá trị: một hàng nhãn
         với ô trống bên cạnh làm quản lý phải đọc qua chỗ trống để tìm
         chỗ có chữ. -->
    <div class="sb" style="flex-wrap: wrap; gap: 4px 18px; margin-top: 8px">
      <span v-if="dong.model_ma" class="tag">Model / mã: <b>{{ dong.model_ma }}</b></span>
      <span v-if="dong.hang_san_xuat" class="tag">Hãng: <b>{{ dong.hang_san_xuat }}</b></span>
      <span v-if="dong.nuoc_san_xuat" class="tag">Nước SX: <b>{{ dong.nuoc_san_xuat }}</b></span>
      <span v-if="dong.quy_cach" class="tag">Quy cách: <b>{{ dong.quy_cach }}</b></span>
    </div>

    <!-- Hai ô thương mại tách riêng, có nhãn nói rõ nguồn: đây là thông
         tin bệnh viện tự khai về nhà cung cấp hiện tại, không phải giá
         Miyano báo. Trộn chung là để quản lý đọc nhầm thành báo giá. -->
    <div
      v-if="dong.ncc_hien_tai || dong.gia_hien_tai"
      class="sb"
      style="flex-wrap: wrap; gap: 4px 18px; margin-top: 6px"
    >
      <span v-if="dong.ncc_hien_tai" class="tag">
        Khoa đang mua của: <b>{{ dong.ncc_hien_tai }}</b>
      </span>
      <span v-if="dong.gia_hien_tai" class="tag">
        Giá đang mua: <b>{{ fmtVND(dong.gia_hien_tai) }}</b>
      </span>
    </div>

    <p v-if="dong.ghi_chu" class="tag" style="margin: 6px 0 0">{{ dong.ghi_chu }}</p>
  </div>
</template>
