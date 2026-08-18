"""Thành viên cổng khách — nguồn sự thật DUY NHẤT cho danh tính cổng.

Trước 18/08/2026 danh tính suy từ `Contact` (field `user`) + `Dynamic Link`.
Cách đó trả lời được "user này thuộc bệnh viện nào" nhưng không mang nổi hai
chiều mới: VAI TRÒ (quản lý / nhân viên khoa) và KHOA PHÒNG. Giữ cả hai
đường song song sẽ tạo hai câu trả lời cho cùng một câu hỏi — nên `Contact`
thôi làm căn cứ phân quyền, chỉ còn giữ email/liên hệ.
"""

import frappe
from frappe.model.document import Document

QUAN_LY = "Quản lý"
NHAN_VIEN_KHOA = "Nhân viên khoa"


class PortalMember(Document):
	def validate(self):
		self._chan_vai_tro_va_khoa_phong()
		self._chan_khoa_cua_benh_vien_khac()
		self._chan_hai_quan_ly()
		self._chan_thieu_ma_ngan()

	def _chan_vai_tro_va_khoa_phong(self):
		if self.vai_tro == NHAN_VIEN_KHOA and not self.khoa_phong:
			frappe.throw(
				"Nhân viên khoa phải được gán một khoa phòng.", frappe.ValidationError
			)
		if self.vai_tro == QUAN_LY and self.khoa_phong:
			frappe.throw(
				"Quản lý nhìn xuyên mọi khoa nên không gắn vào khoa phòng nào. "
				"Bỏ trống ô Khoa phòng.",
				frappe.ValidationError,
			)

	def _chan_khoa_cua_benh_vien_khac(self):
		"""Không chặn thì gán được khoa của bệnh viện khác — một lỗ phân quyền
		mở bằng đúng một thao tác nhập liệu."""
		if not self.khoa_phong:
			return
		cua = frappe.db.get_value("Customer Department", self.khoa_phong, "customer")
		if cua != self.customer:
			frappe.throw(
				"Khoa phòng được chọn không thuộc khách hàng này.", frappe.ValidationError
			)

	def _chan_hai_quan_ly(self):
		"""Mỗi bệnh viện đúng MỘT quản lý đang hoạt động. Nhiều quản lý cùng
		lúc làm khái niệm uỷ quyền tạm thời trở nên vô nghĩa (spec QĐ-KP-4).

		GIỚI HẠN ĐÃ BIẾT (vòng sửa 2, review độc lập, chưa vá trong task này):
		guard này chỉ chạy trong `validate()`, tức chỉ chặn được đường
		`doc.save()`/`doc.insert()`. Hai đường sau ĐI VÒNG được hoàn toàn,
		không qua validate(), không có ràng buộc DB nào đứng chặn:
		  - `frappe.db.set_value("Portal Member", <name>, "active", 1)`
		  - `doc.db_set("active", 1)` (hoặc field khác) trên một instance đã
		    tải sẵn.
		Hai insert `Quản lý` active=1 đồng thời (race condition) cũng lọt vì
		đây là một lần đọc-rồi-throw ở tầng Python, không phải constraint
		nguyên tử của DB. KHÔNG thêm unique index để vá trong task này — đó
		là thay đổi schema nằm ngoài phạm vi, cân nhắc riêng ở lần sau.

		VÌ VẬY: mọi code phía server tạo/sửa `Portal Member` (kể cả script
		backfill Task 5) PHẢI đi qua `doc.save()`/`doc.insert()` — KHÔNG được
		dùng `frappe.db.set_value()`/`doc.db_set()` cho các field ảnh hưởng
		tới luật này (`vai_tro`, `khoa_phong`, `active`, `customer`)."""
		if self.vai_tro != QUAN_LY or not self.active:
			return
		da_co = frappe.db.get_value(
			"Portal Member",
			{"customer": self.customer, "vai_tro": QUAN_LY, "active": 1,
			 "name": ["!=", self.name or ""]},
			["name", "user"], as_dict=True,
		)
		if da_co:
			frappe.throw(
				f"Bệnh viện này đã có quản lý là {da_co.user}. Tắt thành viên đó "
				"trước, hoặc đặt tài khoản này là Nhân viên khoa.",
				frappe.ValidationError,
			)

	def _chan_thieu_ma_ngan(self):
		"""Mã ngắn của bệnh viện đi vào tên phiếu Đề nghị mua. Kiểm ĐÚNG LÚC
		bật tính năng khoa phòng cho một bệnh viện — để tới lúc nhân viên bấm
		gửi mới báo thiếu là bắt họ soạn xong rồi mới nhận một lỗi khó hiểu."""
		if self.vai_tro != NHAN_VIEN_KHOA:
			return
		if not frappe.db.get_value("Customer", self.customer, "custom_ma_ngan"):
			frappe.throw(
				f'Khách hàng "{self.customer}" chưa có Mã ngắn. Đặt mã ngắn trước '
				"khi cấp tài khoản theo khoa phòng.",
				frappe.ValidationError,
			)
