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
  // E6/F-07 — "Chờ bạn đồng ý" là một trạng thái của CHÍNH Sales Order
  // (`workflow_state`), lộ ra qua `portal_order_track().chap_nhan`. Server
  // tự tính `can_dong_y` (đã trừ báo giá hết hạn) — client KHÔNG suy lại.
  { method: 'portal_order_accept', label: '✔ Đồng ý đặt hàng', variant: 'success',
    nhom: 'don', args: [{ key: 'action', const: 'dong_y' }],
    when: (d) => !!d.chap_nhan?.can_dong_y },

  { method: 'portal_order_accept', label: '✕ Không đồng ý…', variant: 'secondary',
    nhom: 'don',
    args: [
      { key: 'action', const: 'khong_dong_y' },
      { key: 'ly_do', label: 'Lý do không đồng ý báo giá', type: 'textarea', required: true },
    ],
    when: (d) => !!d.chap_nhan?.can_dong_y },

  // Việc 2/brief 2026-08-15 — huỷ THẬT (đơn đóng ngay), khác
  // `portal_request_cancel` bên dưới. Server đòi lý do >= 10 ký tự
  // (`LY_DO_TOI_THIEU_KHACH`) — nói ra ở đây để hộp thoại đòi đúng bằng đó.
  //
  // `desc`/`placeholder` (review toàn nhánh 03/09/2026) — chép NGUYÊN VĂN
  // từ hộp thoại riêng của `OrderDetail.vue` (màn cũ, đã nghỉ). Khi màn gộp
  // đẩy hành động này qua `ReasonModal` chung, `desc` sinh máy móc từ `label`
  // chỉ còn nói về ĐỊNH DẠNG Ô NHẬP ("Lý do huỷ đơn (≥ 10 ký tự) — bắt
  // buộc."), không nói chuyện gì sắp xảy ra. Trên cùng màn đó, "Xoá" và
  // "Thu hồi để sửa" vẫn có `window.confirm` nói rõ hệ quả — huỷ đơn khi ấy
  // là hành động KHÔNG ĐẢO NGƯỢC DUY NHẤT chỉ hỏi lý do mà không cảnh báo.
  //
  // Hai khoá này là TUỲ CHỌN cho mọi mục args: không mục nào khác khai
  // chúng và không mục nào khác đổi (`ChiTietYeuCau.vue` giữ nguyên câu
  // sinh máy móc làm đường lui) — chỉ hành động không quay lại được mới cần
  // một câu viết tay.
  { method: 'portal_order_huy', label: '🗑 Huỷ đơn…', variant: 'danger',
    nhom: 'don',
    args: [{ key: 'ly_do', label: 'Lý do huỷ đơn (≥ 10 ký tự)', type: 'textarea', required: true, minLen: 10,
      desc: 'Đơn sẽ ĐÓNG NGAY, không thể hoàn tác từ phía khách. Vui lòng nêu lý do (≥ 10 ký tự) — được gửi kèm email cho Miyano.',
      placeholder: 'VD: Đặt nhầm số lượng, không còn nhu cầu...' }],
    when: (d) => !!d.chap_nhan?.can_dong_y },

  // Task 6 (QĐ-G2b) + Task 7 (Ruling P49) — CHỐT, không phải nhãn. Soi
  // gương hai điều kiện của `portal.portal_order_sua_so_luong`: loại đơn đi
  // vòng báo giá, và guard vai trò `dam_bao_duoc_sua_don_da_duyet` mà server
  // TỰ TRẢ LỜI qua `duoc_sua_da_duyet` — KHÔNG suy lại từ dữ kiện client.
  //
  // `!== false` chứ không `=== true`, CÓ CHỦ Ý: khoá vắng mặt chỉ có thể do
  // backend cũ hơn bundle, và `=== true` khi đó giấu chức năng khỏi CẢ quản
  // lý. Server không bao giờ mất quyền nói không.
  { method: 'portal_order_sua_so_luong', label: '✎ Gửi lại để báo giá', variant: 'secondary',
    nhom: 'don', dacBiet: 'sua_so_luong',
    when: (d) => !!d.chap_nhan?.can_dong_y
      && d.loai_don === 'Mua lẻ'
      && d.duoc_sua_da_duyet !== false },

  // Đơn ĐÃ XÁC NHẬN — chỉ GHI một yêu cầu chờ nhân viên Miyano xử lý, không
  // đóng đơn. Ẩn khi đang "Chờ bạn đồng ý": ở đó đã có đường "Không đồng ý"
  // riêng, hai bộ hành động cùng hiện sẽ tranh nhau.
  { method: 'portal_request_cancel', label: 'Huỷ / Sửa đơn', variant: 'secondary',
    nhom: 'don',
    args: [{ key: 'reason', label: 'Lý do yêu cầu huỷ / sửa đơn', type: 'textarea', required: true }],
    when: (d) => d.status_vi === 'Chờ xác nhận' && !d.chap_nhan?.can_dong_y },
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
