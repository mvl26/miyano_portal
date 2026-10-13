// Luật giỏ hàng của màn Đặt hàng theo Price List của khách (spec
// `docs/superpowers/specs/2026-10-09-gia-theo-price-list-design.md` §3.2, §4.1,
// §7). JS thuần, không import Vue: `gio-hang.test.mjs` chạy thẳng bằng
// `node --test`.
//
// Một dòng giỏ mang HAI thứ khác nhau:
//   * `tang` — `'bang_gia'` / `'cho_bao_gia'`: dòng đi đường nào (đặt ngay hay
//     vòng báo giá). Việc tách giỏ và các nhãn đọc `tang`.
//   * `don_gia` — con số để hiện và để cộng tạm tính. Có thể VẮNG trên một
//     dòng tầng bảng giá: phiếu Nháp mở lại chỉ lưu nguồn giá, giá được đóng
//     dấu lúc gửi duyệt (§4.3). `<= 0` là "chưa có giá", không phải "0 đồng".

export const TANG_BANG_GIA = 'bang_gia'
export const TANG_CHO_BAO_GIA = 'cho_bao_gia'

export function laTangBangGia(row) {
  return row?.tang === TANG_BANG_GIA
}

// Dòng có CON SỐ để hiện: thuộc tầng bảng giá và đơn giá dương.
export function coGia(row) {
  return laTangBangGia(row) && Number(row.don_gia) > 0
}

// Thành tiền một dòng giỏ; `null` khi không có con số nào để nhân.
export function thanhTienDong(row) {
  if (!coGia(row)) return null
  return Number(row.don_gia) * (Number(row.so_luong_de_xuat) || 0)
}

// Tầng của một dòng phiếu đã lưu, suy từ `nguon_gia` của dòng đó. Chỉ là
// phỏng đoán ban đầu cho tới khi màn hỏi lại danh mục: phiếu cũ còn dòng
// `"Hợp đồng"` (không phiếu mới nào nhận giá trị này) chỉ được coi là có giá
// khi mang sẵn đơn giá đã đóng dấu.
export function tangTuNguonGia(nguonGia, donGia) {
  if (nguonGia === 'Bảng giá') return TANG_BANG_GIA
  if (nguonGia === 'Hợp đồng' && Number(donGia) > 0) return TANG_BANG_GIA
  return TANG_CHO_BAO_GIA
}

// Tóm tắt giỏ cho thông báo trước khi gửi và dòng tạm tính.
//   `items`        — dòng có mã trong giỏ;
//   `soDongGoTay`  — số dòng "hàng chưa có mã" khách ĐÃ gõ gì đó (dòng trống
//                    không được gửi đi nên không được đếm);
//   `daTungGui`    — phiếu đã có mã đề xuất (thu hồi về Nháp): server chỉ tách
//                    ở lần gửi đầu tiên (§4.1), lần gửi lại vẫn là một phiếu.
// Dòng gõ tay luôn thuộc nhóm chờ báo giá (§4.1).
export function tomTatGio(items, soDongGoTay = 0, daTungGui = false) {
  const ds = items || []
  const soDatNgay = ds.filter(laTangBangGia).length
  const soChoBaoGia = ds.length - soDatNgay + (Number(soDongGoTay) || 0)
  return {
    soDatNgay,
    soChoBaoGia,
    seTach: !daTungGui && soDatNgay > 0 && soChoBaoGia > 0,
    tongTamTinh: ds.reduce((t, r) => t + (thanhTienDong(r) || 0), 0),
    soCoGia: ds.filter(coGia).length,
    // Dòng tầng bảng giá chưa biết con số — tạm tính KHÔNG gồm chúng, và màn
    // phải nói ra điều đó thay vì để tổng lặng lẽ thiếu.
    soChuaRoGia: ds.filter((r) => laTangBangGia(r) && !coGia(r)).length,
  }
}

// Lấy đúng dòng của `itemCode` trong một trang kết quả `portal_catalog_gop`.
// Endpoint tìm theo `LIKE` trên mã và tên, nên một từ khoá là mã hàng có thể
// trả cả những mã chứa nó — chỉ dòng trùng mã CHÍNH XÁC mới được dùng.
export function dongKhopMa(rows, itemCode) {
  return (rows || []).find((r) => r.item_code === itemCode) || null
}
