from frappe.model.document import Document


class DongMay(Document):
	"""Danh mục DÒNG MÁY dùng chung của Miyano (28/09/2026) — nguồn của bảng
	"Máy sử dụng" trên `Item` (`custom_may_su_dung`) và ô lọc máy ở màn Đặt
	hàng của cổng.

	KHÁC `Customer Equipment`: bản ghi đó là MỘT CHIẾC máy cụ thể của MỘT bệnh
	viện (có `customer`, serial, khoa). Danh mục hàng của Miyano dùng chung cho
	mọi khách nên phải trỏ tới DÒNG máy — cùng một model ở sáu bệnh viện là
	một dòng ở đây, không phải sáu.
	"""
