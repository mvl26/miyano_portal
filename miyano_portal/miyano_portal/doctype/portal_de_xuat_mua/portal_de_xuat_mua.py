"""Chứng từ đề xuất mua của khoa phòng (spec §5).

KHÔNG dùng module Workflow của Frappe — `trang_thai` là Select thường, đúng
khuôn `Portal Item Request`. Lý do: máy trạng thái ở §5.4 có cạnh quay lui
(`Từ chối --sửa--> Chờ duyệt`) và vài chốt theo nội dung (bắt buộc lý do khi
từ chối) mà Workflow không biểu diễn gọn hơn một bảng viết tay.

Zero DocPerm cho role `Customer` — khách chỉ vào qua `api/de_xuat.py`, suy
khách và khoa từ phiên đăng nhập. Nhân sự Miyano CÓ quyền desk (như mọi
doctype cổng khác) để hỗ trợ được khi bệnh viện gọi. Bảo đảm "Miyano không
thấy đơn chưa duyệt" của §5.1 do việc đây là một doctype RIÊNG mang lại —
không có `SAL-ORD` nào sinh ra trước khi bệnh viện chốt, nên không có đơn ma
nào lọt vào danh sách, báo cáo, dashboard của Miyano — chứ không do DocPerm.

(Sửa spec §5.1 — vòng sửa 19/08/2026: bản đầu của §5.1 viết "Miyano không
được cấp quyền nào trên doctype này", mạnh hơn thứ mà chính §5.1 cần và trái
với tiền lệ ba doctype cổng khác (`Portal Item Request`/`Portal Delivery
Inspection`/`Portal Member`, cả ba đều cấp desk cho System Manager/Sales
Manager/Sales User, zero cho `Customer`). Bất biến thật của app là "zero
DocPerm cho Customer", không phải "zero DocPerm tuyệt đối" — bắt được bởi
`test_kho_isolation.py::TestKhoDocPermConfig.test_staff_roles_keep_desk_
permissions`.)
"""

import frappe
from frappe.model.document import Document

TRANG_THAI_NHAP = "Nháp"
TRANG_THAI_CHO_DUYET = "Chờ duyệt"
TRANG_THAI_DA_DUYET = "Đã duyệt"
TRANG_THAI_TU_CHOI = "Từ chối"
TRANG_THAI_DA_HUY = "Đã huỷ"
# Task 9 dùng — vòng sửa sau khi bị từ chối. Khai sẵn hằng ở đây để Task 9
# không phải sửa lại chỗ này, dù chưa có cạnh nào của máy trạng thái đi tới
# nó trong task này (chưa thêm vào options của field `trang_thai`).
TRANG_THAI_CHO_DUYET_SUA = "Chờ duyệt sửa"


class PortalDeXuatMua(Document):
	def validate(self):
		self._chan_khoa_phong_khac_benh_vien()

	def _chan_khoa_phong_khac_benh_vien(self):
		"""Khoa phòng phải thuộc chính bệnh viện đứng tên phiếu.

		`khoa_phong` rỗng là HỢP LỆ — đó là phiếu cấp bệnh viện của quản lý
		("Toàn viện", §5.5), mang mã khoa dành riêng CHUNG.
		"""
		if not self.khoa_phong:
			return
		cua = frappe.db.get_value("Customer Department", self.khoa_phong, "customer")
		if cua != self.customer:
			frappe.throw(
				f'Khoa phòng "{self.khoa_phong}" không thuộc đơn vị '
				f'"{self.customer}".',
				frappe.ValidationError,
			)
