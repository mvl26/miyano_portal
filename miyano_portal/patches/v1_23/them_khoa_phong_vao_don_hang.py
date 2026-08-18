"""Thêm `Sales Order.custom_khoa_phong`.

Chỉ đọc, ghi lúc tạo đơn. Thứ dẫn xuất (phiếu giao, hoá đơn, biên bản kiểm)
CỐ Ý không có field riêng — chúng lọc qua đơn cha, để không bao giờ có
chuyện phiếu giao nói khoa A còn đơn nói khoa B.

Đơn CŨ để trống: chúng thuộc thời kỳ một-bệnh-viện-một-tài-khoản, không quy
về khoa nào được, và `pham_vi_don()` cho quản lý thấy hết nên không đơn nào
biến mất khỏi màn hình ai cả.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def execute():
	create_custom_field("Sales Order", {
		"fieldname": "custom_khoa_phong",
		"label": "Khoa phòng",
		"fieldtype": "Link",
		"options": "Customer Department",
		"read_only": 1,
		"search_index": 1,
		"insert_after": "custom_so_po_khach",
	})
