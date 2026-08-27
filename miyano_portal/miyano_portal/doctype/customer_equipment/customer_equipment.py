import frappe
from frappe.model.document import Document


class CustomerEquipment(Document):
	"""Master thiết bị của khách hàng (máy xét nghiệm, máy thở...).

	Treo vào `Customer` chứ KHÔNG vào `Customer Warehouse`: khoa phòng đã
	chuyển chủ sở hữu sang bệnh viện từ 18/08, và máy đặt ở khoa chứ không
	đặt ở kho. Bệnh viện chưa mở kho trên cổng vẫn khai được máy.
	"""

	def validate(self):
		self._chuan_hoa()
		self._chan_trung_ma()
		self._chan_trung_ten()
		self._chan_khoa_khac_benh_vien()

	def _chuan_hoa(self):
		self.ma_thiet_bi = (self.ma_thiet_bi or "").strip().upper()
		self.ten_thiet_bi = (self.ten_thiet_bi or "").strip()
		if not self.ma_thiet_bi:
			frappe.throw("Thiếu Mã máy.", frappe.ValidationError)
		if not self.ten_thiet_bi:
			frappe.throw("Thiếu Tên máy.", frappe.ValidationError)
		self.khoa_phong = self.khoa_phong or None

	def _chan_trung_ma(self):
		if frappe.db.exists("Customer Equipment", {
			"customer": self.customer, "ma_thiet_bi": self.ma_thiet_bi,
			"name": ["!=", self.name or ""],
		}):
			frappe.throw(
				f'Đơn vị này đã có máy mang mã "{self.ma_thiet_bi}".',
				frappe.ValidationError,
			)

	def _chan_trung_ten(self):
		"""So sánh dựa THẲNG vào collation utf8mb4_unicode_ci của CSDL — đã
		sẵn không dấu và không phân biệt hoa thường (spec 18/08 đã đo bằng
		truy vấn thật). Không thêm cột chuẩn hoá cho một phép so duy nhất."""
		trung = frappe.db.sql(
			"""select name from `tabCustomer Equipment`
			   where customer=%s and ten_thiet_bi=%s and name!=%s limit 1""",
			(self.customer, self.ten_thiet_bi, self.name or ""),
		)
		if trung:
			frappe.throw(
				f'Đơn vị này đã có máy tên "{self.ten_thiet_bi}" '
				f"(mã {frappe.db.get_value('Customer Equipment', trung[0][0], 'ma_thiet_bi')}).",
				frappe.ValidationError,
			)

	def _chan_khoa_khac_benh_vien(self):
		if not self.khoa_phong:
			return
		if frappe.db.get_value("Customer Department", self.khoa_phong, "customer") != self.customer:
			frappe.throw(
				"Khoa phòng được chọn không thuộc đơn vị này.", frappe.ValidationError
			)

	def on_trash(self):
		"""BR-TB-9 — máy đã xuất hiện trên phiếu xuất thì không xoá được.

		Xoá sẽ làm mọi dòng phiếu cũ trỏ vào một Link chết, và báo cáo theo
		máy của các kỳ trước im lặng đổi số. Hướng người dùng sang bỏ tích
		`active` — máy biến khỏi dropdown mà số liệu cũ còn nguyên.
		"""
		if frappe.db.exists("Customer Stock Issue Item", {"thiet_bi": self.name}):
			frappe.throw(
				f'Máy "{self.ten_thiet_bi}" đã được dùng trên phiếu xuất nên '
				"không xoá được. Hãy bỏ tích \"Đang hoạt động\" để ngừng dùng — "
				"số liệu các kỳ trước sẽ được giữ nguyên.",
				frappe.ValidationError,
			)
