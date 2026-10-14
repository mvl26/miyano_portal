// Registry hành động cho ĐƠN HÀNG (Sales Order) trên màn chi tiết gộp.
//
// Anh em sinh đôi của `de-xuat-actions.js`, cùng hình dạng và cùng luật:
// hành động là DỮ LIỆU, hide-don't-disable, và ĐÂY KHÔNG PHẢI CHỐT AN NINH
// (server đã enforce; registry chỉ quyết định HIỆN GÌ).
//
// Vì sao FILE RIÊNG chứ không thêm vào `de-xuat-actions.js`: hai bộ gọi hai
// module endpoint khác nhau (`api.call` → `api/portal.py` ở đây, `api.
// callDeXuat` → `api/de_xuat.py` ở kia), và `tests/test_de_xuat_action_
// registry.py` đối chiếu tên endpoint với ĐÚNG một module cho mỗi file. Trộn
// hai họ tên vào một mảng làm lưới đó mất khả năng nói "tên này không tồn
// tại" — nó không biết phải hỏi module nào.
//
// `nhom: 'don'` để người gọi biết dùng `api.call`. Mục của
// `de-xuat-actions.js` không mang khoá này (mặc định là phiếu) — cố ý không
// đi sửa tám mục đã có và tám dòng test đang canh chúng.
//
// File CỐ Ý là JS thuần, không import Vue.

export const ACTIONS_DON = [
  // Đơn không còn vòng báo giá với khách (patch v1_44): báo giá, đồng ý và
  // sửa số lượng đi trên Quotation (màn Báo giá). Đơn chỉ còn yêu cầu huỷ /
  // sửa khi Miyano chưa xác nhận.
  //
  // Chỉ GHI một yêu cầu chờ nhân viên Miyano xử lý, không đóng đơn.
  { method: 'portal_request_cancel', label: 'Huỷ / Sửa đơn', variant: 'secondary',
    nhom: 'don',
    args: [{ key: 'reason', label: 'Lý do yêu cầu huỷ / sửa đơn', type: 'textarea', required: true }],
    when: (d) => d.status_vi === 'Chờ xác nhận' },
]

// Lọc theo doc + người dùng. Bọc `when()` trong try/catch vì đúng lý do
// `de-xuat-actions.js` đã ghi: một field thiếu phải làm nút BIẾN MẤT, không
// làm sập cả thanh công cụ — nhưng phải để lại dấu vết ở console, không nuốt
// im lặng.
export function hanhDongDonChoPhep(don, me) {
  if (!don || !me) return []
  return ACTIONS_DON.filter((a) => {
    try {
      return a.when(don, me)
    } catch (e) {
      console.warn(`[don-actions] when() của "${a.label}" ném lỗi — ẩn nút này:`, e)
      return false
    }
  })
}
