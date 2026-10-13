// Quy tắc hiển thị tên mặt hàng trên cổng (chủ đầu tư 13/10/2026) — MỘT chỗ
// cho mọi bảng mặt hàng: Chọn hàng, Giỏ hàng, Chi tiết đơn/phiếu, Kiểm hàng,
// Báo giá. Server: `miyano_portal/ten_hang.py`.
//
//   * Thứ tự cố định: Mã → Tên mặt hàng → Tên thường gọi.
//   * Tên mặt hàng là tên XUẤT HOÁ ĐƠN (`item_name`), không bao giờ bị cắt —
//     ô tự xuống dòng.
//   * Tên thường gọi là của CHÍNH đơn vị đang xem; nhiều tên cách nhau bằng
//     dấu phẩy; chưa có thì "—".
//
// Thuần hàm, không import Vue, để `node --test` canh được
// (`ten-hang.test.mjs`), cùng khuôn `gio-hang.js`.

export const TIEU_DE_COT = Object.freeze({
  ma: 'Mã',
  ten: 'Tên mặt hàng',
  tenGoi: 'Tên thường gọi',
})

export const KHONG_CO = '—'

// Chuỗi hiện ở cột "Tên thường gọi". Bỏ tên rỗng và tên lặp (Miyano có thể
// nhập hai dòng giống nhau trên Item).
export function ghepTenThuongGoi(ds) {
  const ten = [...new Set((ds || []).map((t) => String(t || '').trim()).filter(Boolean))]
  return ten.length ? ten.join(', ') : KHONG_CO
}

// Các mã trên màn mà kho tên chưa có — chỉ những mã này mới phải hỏi server.
export function maCanNap(codes, kho) {
  return [...new Set((codes || []).filter(Boolean))].filter((m) => !(m in kho))
}

// Tên mặt hàng của một dòng: tên ghi TRÊN CHỨNG TỪ thắng (chứng từ đã lập giữ
// tên lúc lập, khớp hoá đơn); dòng không mang tên thì lấy tên hiện tại của
// Item; cả hai đều trống thì "—", không lặp lại mã ở cột tên.
export function tenMatHang(tenTrenDong, tenTrongKho) {
  return String(tenTrenDong || '').trim() || String(tenTrongKho || '').trim() || KHONG_CO
}
