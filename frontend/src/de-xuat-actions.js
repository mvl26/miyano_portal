// Registry hành động cho phiếu Đề xuất mua.
//
// Hành động là DỮ LIỆU: một bảng ánh xạ trạng thái + vai trò -> nút được
// phép. Rải v-if khắp component sẽ sinh ra đúng lỗi "nút luôn hiện rồi lỗi
// lúc bấm" — người dùng học cách sợ thanh công cụ.
//
// ĐÂY KHÔNG PHẢI CHỐT AN NINH. Server đã enforce đủ (suite Python canh). Registry
// chỉ quyết định HIỆN GÌ. Không bao giờ để một when() ở đây là thứ duy nhất
// ngăn một chuyển trạng thái sai.
//
// `variant: 'danger'` CHỈ dùng cho việc KHÔNG ĐẢO NGƯỢC ĐƯỢC — "Xoá" (xoá
// thật khỏi CSDL) và "Huỷ phiếu". "Từ chối" KHÔNG đỏ: phiếu bị từ chối vẫn
// sửa và gửi lại được. Gắn đỏ bừa thì người dùng thôi đọc màu.
//
// Hide, don't disable: when() trả false thì nút BIẾN MẤT khỏi
// hanhDongChoPhep(), không hiện xám. Một nút xám đặt ra câu hỏi nó không trả
// lời được.
//
// Mọi chuỗi `method` phải là endpoint whitelist có thật ở api/de_xuat.py —
// `tests/test_de_xuat_action_registry.py` canh điều đó bằng lưới Python đọc
// file này bằng regex (KHÔNG có test JS nào canh — package.json chỉ có vite).
//
// File này CỐ Ý là JS thuần, không import Vue — để test được (kể cả từ Python
// qua regex) mà không cần hạ tầng component.

export const ACTIONS_DE_XUAT = [
  // Task 3 — `me.user` = `frappe.session.user`, bơm vào `portal_me()`
  // (api/portal.py) đúng bản vá này. Trước đó `portal_me()` không có khoá
  // này và vế `d.owner === me.user` luôn false — hai nút "Gửi duyệt"/"Xoá"
  // không bao giờ hiện, kể cả cho chủ phiếu.
  { method: 'de_xuat_gui_duyet', label: 'Gửi duyệt', variant: 'primary',
    when: (d, me) => d.trang_thai === 'Nháp' && d.owner === me.user },

  // `!d.ma_de_xuat` (review toàn nhánh 03/09/2026) — SOI GƯƠNG chốt server
  // sau khi nó đổi từ TRẠNG THÁI sang MÃ. `thu_hoi()` đưa một phiếu ĐÃ gửi
  // duyệt về lại Nháp mà vẫn giữ mã, nên "đang ở Nháp" thôi không còn nghĩa
  // là "xoá được": `on_trash`/`de_xuat_xoa_nhap` chắc chắn từ chối. Giữ
  // điều kiện cũ là hiện một nút chỉ biết ném lỗi — đúng thứ đầu file này
  // cấm. Phiếu đó đi ra bằng "Huỷ phiếu" (giữ dấu vết, §5.4b).
  { method: 'de_xuat_xoa_nhap', label: 'Xoá', variant: 'danger',
    when: (d, me) => d.trang_thai === 'Nháp' && !d.ma_de_xuat
      && (d.owner === me.user || me.la_quan_ly) },

  // Chủ đầu tư chốt 03/09/2026 — "NV sửa được đơn ở trạng thái Chờ duyệt".
  // Cột "Số lượng đề xuất" khoá vĩnh viễn từ lúc Gửi duyệt (§5.3), nên
  // "sửa" ở đây là THU HỒI về Nháp rồi sửa ở màn Đặt hàng và gửi lại — xem
  // `PortalDeXuatMua.thu_hoi()` để biết vì sao không nới cái khoá đó.
  //
  // CHỈ chủ phiếu (`d.owner === me.user`), ĐÚNG chốt owner-only của
  // `de_xuat_thu_hoi` phía server — registry chỉ quyết định HIỆN GÌ, nhưng
  // hiện một nút chắc chắn 403 lúc bấm là dạy người dùng sợ thanh công cụ.
  // Quản lý KHÔNG có nút này trên phiếu người khác: họ sửa thẳng ở cột "SL
  // duyệt" ngay trên màn, và muốn trả phiếu về cho khoa thì dùng Từ chối
  // (có ghi lý do).
  //
  // KHÔNG `variant: 'danger'`: thu hồi đảo ngược được bằng đúng một cú bấm
  // Gửi duyệt, và mã phiếu giữ nguyên. Đỏ để dành cho việc không quay lại
  // được (Xoá, Huỷ phiếu).
  { method: 'de_xuat_thu_hoi', label: 'Thu hồi để sửa', variant: 'secondary',
    when: (d, me) => d.trang_thai === 'Chờ duyệt' && d.owner === me.user },

  { method: 'de_xuat_duyet_phieu', label: 'Duyệt', variant: 'success',
    when: (d, me) => d.trang_thai === 'Chờ duyệt' && me.la_quan_ly },

  { method: 'de_xuat_tu_choi', label: 'Từ chối', variant: 'secondary',
    when: (d, me) => d.trang_thai === 'Chờ duyệt' && me.la_quan_ly,
    args: [{ key: 'ly_do', label: 'Lý do từ chối', type: 'textarea', required: true }] },

  // Nhánh `Nháp` + CÓ MÃ (review toàn nhánh 03/09/2026) = phiếu VỪA BỊ THU
  // HỒI. Cạnh `Nháp → Đã huỷ` mở ở doctype cùng lúc `on_trash` khoá đường
  // xoá cho phiếu đã từng gửi; không có nhánh này thì phiếu đó nằm lại vĩnh
  // viễn — xoá bị server cấm, huỷ không có nút. Phiếu Nháp CHƯA có mã cố ý
  // KHÔNG hiện nút này: với nó "Xoá" mới là việc đúng, và hai nút đỏ cạnh
  // nhau cho hai việc khác nhau là chỗ để bấm nhầm.
  //
  // Vẫn CHỈ quản lý — `de_xuat_huy` là quản lý-only từ §5.4b và bản vá này
  // không đụng tới quyền đó. Nhân viên vừa thu hồi phiếu của mình thì sửa
  // rồi gửi lại (đường chính), hoặc nhờ quản lý huỷ.
  { method: 'de_xuat_huy', label: 'Huỷ phiếu', variant: 'danger',
    when: (d, me) => (
      ['Chờ duyệt', 'Từ chối'].includes(d.trang_thai)
      || (d.trang_thai === 'Nháp' && !!d.ma_de_xuat)
    ) && me.la_quan_ly },

  { method: 'de_xuat_duyet_sua', label: 'Đồng ý sửa', variant: 'success',
    when: (d, me) => d.trang_thai === 'Chờ duyệt sửa' && me.la_quan_ly },

  { method: 'de_xuat_tu_choi_sua', label: 'Không đồng ý sửa', variant: 'secondary',
    when: (d, me) => d.trang_thai === 'Chờ duyệt sửa' && me.la_quan_ly,
    args: [{ key: 'ly_do', label: 'Lý do', type: 'textarea', required: true }] },

  // Task 4, ruling coordinator (2) — trước bản này registry KHÔNG có mục
  // nào cho "Đã duyệt" phía nhân viên khoa: toolbar rỗng, và luồng "xin sửa
  // số lượng" backend đã xây đủ (Task 9 — ba endpoint, trạng thái "Chờ duyệt
  // sửa", năm chốt ở `PortalDeXuatMua.xin_sua`) không có đường vào từ giao
  // diện. `!d.sales_order` bị loại vì `de_xuat_xin_sua`/`_kiem_don_dung_
  // duoc_xin_sua` throw ngay nếu chưa có đơn đứng sau. `!me.la_quan_ly` vì
  // quản lý sửa THẲNG trên đơn (không qua vòng xin-rồi-chờ-duyệt-lại này).
  { method: 'de_xuat_xin_sua', label: 'Xin sửa số lượng', variant: 'secondary',
    when: (d, me) => d.trang_thai === 'Đã duyệt' && !!d.sales_order && !me.la_quan_ly },
]

// Lọc ACTIONS_DE_XUAT theo doc + người dùng hiện tại. Bọc when() trong
// try/catch: một field thiếu (doc chưa nạp đủ) phải làm nút đó biến mất,
// không được làm sập cả thanh công cụ.
export function hanhDongChoPhep(doc, me) {
  if (!doc || !me) return []
  return ACTIONS_DE_XUAT.filter((a) => {
    try {
      return a.when(doc, me)
    } catch (e) {
      // Việc (a) — `return false` trần nuốt lỗi KHÔNG TIẾNG ĐỘNG: một when()
      // ném lỗi (doc thiếu field, me sai hình dạng) làm nút BIẾN MẤT y hệt
      // như khi nó hợp lệ trả false. Người dùng báo "không thấy nút Duyệt",
      // và không có gì ở đâu để đối chiếu. Vẫn nuốt (một nút hỏng không được
      // làm sập cả thanh công cụ) nhưng để lại dấu vết ở console.
      console.warn(`[de-xuat-actions] when() của "${a.method}" ném lỗi — ẩn nút này:`, e)
      return false
    }
  })
}
