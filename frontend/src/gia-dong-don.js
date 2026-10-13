// Giá của một dòng TRÊN ĐƠN ở bảng mặt hàng của màn chi tiết
// (`components/chi-tiet/BangMatHang.vue`). Tách khỏi component để `node --test`
// canh được (`gia-dong-don.test.mjs`), cùng khuôn `gio-hang.js`.
//
// Luật (spec 2026-10-09): giá `<= 0` là "chưa có giá", không bao giờ là "bán 0
// đồng". Một dòng của đơn báo giá mà Miyano chưa điền giá phải nói "Chờ báo
// giá" — in "0 ₫" ở Đơn giá và Thành tiền là nói với khoa rằng hàng miễn phí.

// MỘT cách gọi cho cả dòng báo giá lẫn dòng gõ tay đã khớp mã (trước đây dòng
// khớp mã ghi "Chờ Miyano báo giá").
export const NHAN_CHO_BAO_GIA = 'Chờ báo giá'

// Dấu của dòng đơn (`Sales Order Item.custom_nguon_gia`) cho dòng Miyano phải
// báo giá. Dòng "Bảng giá" luôn mang giá dương; dòng cũ không có dấu.
const NGUON_BAO_GIA = 'Báo giá'

// Dòng đang CHỜ Miyano báo giá — quyết từ DẤU và giá, không đoán từ con số:
//   * đã có giá dương → không;
//   * dòng gõ tay đã khớp mã (`yeu_cau_khop`) chưa có giá → có, kể cả khi dòng
//     hàng chưa kịp có trên đơn (giá `null`);
//   * dòng có trên đơn, dấu "Báo giá", giá `<= 0` → có;
//   * dòng KHÔNG có trên đơn (giá `null`) → không: ô in "—";
//   * dòng cũ không dấu mà giá 0 (đơn lập trước spec này) → không: giữ cách
//     hiện cũ, không gán nhầm "chờ báo giá" cho một đơn đã xong từ lâu.
export function choBaoGiaTrenDon(row) {
  if (!row) return false
  const gia = row.don_gia_tren_don
  if (Number(gia) > 0) return false
  if (row.yeu_cau_khop) return true
  if (gia === null || gia === undefined) return false
  return row.nguon_gia_tren_don === NGUON_BAO_GIA
}
