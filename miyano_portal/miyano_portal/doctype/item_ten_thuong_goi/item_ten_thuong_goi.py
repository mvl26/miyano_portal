from frappe.model.document import Document


class ItemTenThuongGoi(Document):
	"""Dòng "tên thường gọi" của `Item.custom_ten_thuong_goi`: tên mà MỘT khách
	hàng (bệnh viện) quen gọi mặt hàng này, khác tên xuất hoá đơn (`item_name`).

	Màn Đặt hàng của cổng tìm theo cột này, nhưng CHỈ trong các dòng có
	`customer` = khách đang đăng nhập — tên bệnh viện A tự đặt không lộ sang
	bệnh viện B (`portal_catalog_gop`)."""
